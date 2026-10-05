"""Contracts across native process locks, config recovery and free geometry."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
SCRATCH=ROOT/".build-tests-v02"
SCRATCH.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT))
from calibration.storage import exclusive, LockBusy,lock_identity,config_lock,config_exclusive
from calibration.config_io import atomic_update, backups, restore
from calibration.geometry import CalibrationError
from calibration.screenshot_picker import RectanglePicker
from calibration.dom_picker import DOMSession
from calibration.profiles import ProfileStore
from calibration.geometry import align_rect
from calibration.exports import (create_plan,execute_plan,source_snapshot,view_images,
    analyze_view,region_statistics,running_state,digest)
from PIL import Image
from pypdf import PdfReader
from test_calibration import payload
import edge_capture as core


class CalibrationV02Tests(unittest.TestCase):
    def test_oversized_numbers_rejected_at_config_and_dom_boundaries(self):
        from calibration.dom_picker import parse_payload
        from calibration.geometry import measured_mapping,css_to_screen
        cfg=json.loads((ROOT/"config.json").read_bytes())
        for key in ("start_delay","poll_seconds","stable_seconds","disabled_seconds","min_after_click","timeout_seconds","pdf_dpi","change_threshold","template_tolerance","template_margin","stable_tolerance"):
            bad=copy.deepcopy(cfg);bad[key]=10**400
            with self.subTest(key=key),self.assertRaises(ValueError):core.validate(bad,(32768,32768))
        for key in ("scroll","viewport"):
            data=payload();data[key][0]=10**400
            with self.subTest(dom=key),self.assertRaises(CalibrationError):parse_payload(json.dumps(data),data["token"])
        data=payload();data["rects"]["LEFT"]["width"]=10**400
        with self.assertRaises(CalibrationError):parse_payload(json.dumps(data),data["token"])
        with self.assertRaises(CalibrationError):measured_mapping([[0,0],[1,0],[0,1]],[[0,0],[1,0],[0,1]],10**400)
        with self.assertRaises(CalibrationError):css_to_screen({"left":0,"top":0,"width":10**400,"height":10},(1,1,0,0),(500,500))

    def test_project_version_matches_runtime(self):
        import tomllib
        self.assertEqual(tomllib.loads((ROOT/"pyproject.toml").read_text())["project"]["version"],core.VERSION)

    def test_frozen_cli_failure_never_opens_modal_dialog(self):
        import rectoflow
        with patch.object(sys,"argv",["RectoFlow.exe","--rebuild","interrupted"]),patch.object(sys,"frozen",True,create=True),patch.object(rectoflow,"main",side_effect=ValueError("RUNNING")),patch.object(rectoflow.messagebox,"showerror") as dialog:
            self.assertEqual(rectoflow.entrypoint(),2)
            dialog.assert_not_called()

    def test_junction_alias_resolves_to_same_config_lock(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);target=folder/"target";target.mkdir();config=target/"Config.json";config.write_text("{}")
            junction=folder/"junction"
            made=subprocess.run(["cmd.exe","/c","mklink","/J",str(junction),str(target)],capture_output=True,text=True)
            self.assertEqual(made.returncode,0,made.stderr)
            try:
                self.assertEqual(lock_identity(config),lock_identity(junction/"Config.json"))
                self.assertEqual(config_lock(config),config_lock(junction/"Config.json"))
            finally:junction.rmdir()  # removes this owned junction, never its target contents

    def test_native_file_lock_identity_case_dot_and_hardlink_aliases(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);path=folder/"Config.json";path.write_text("{}")
            sub=folder/"sub";sub.mkdir()
            alias=folder/"alias.json";os.link(path,alias)
            variants=[path,Path(str(path).swapcase()),sub/".."/"Config.json",alias]
            self.assertEqual(len({lock_identity(p) for p in variants}),1)
            self.assertEqual(config_lock(path),config_lock(sub/".."/"Config.json"))
            with config_exclusive(path):
                script="from calibration.storage import config_exclusive;import sys\nwith config_exclusive(sys.argv[1]): print('UNEXPECTED')"
                child=subprocess.run([sys.executable,"-c",script,str(alias)],cwd=ROOT,capture_output=True,text=True,timeout=10)
                self.assertNotEqual(child.returncode,0)
            missing=folder/"new.json"
            self.assertEqual(lock_identity(missing),lock_identity(sub/".."/"new.json"))

    def test_unpublished_backup_is_not_enumerated_on_failed_write(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            path=Path(td)/"config.json";original=b'{"old":true}';path.write_bytes(original)
            real_replace=os.replace
            def deny_backup(source,destination):
                if ".backup." in str(destination):
                    self.assertEqual(backups(path),[])
                    self.assertEqual(Path(source).read_bytes(),original)
                    raise OSError("backup publication failed")
                return real_replace(source,destination)
            with patch("calibration.config_io.os.replace",side_effect=deny_backup),self.assertRaises(CalibrationError):
                atomic_update(path,{"new":True},digest(original),lambda c:None)
            self.assertEqual(path.read_bytes(),original);self.assertEqual(backups(path),[])

    def test_console_accepts_unicode_browser_titles_on_cp1252(self):
        from io import BytesIO,TextIOWrapper
        data=BytesIO();stream=TextIOWrapper(data,encoding="cp1252")
        with patch.object(sys,"stdout",stream):
            core.configure_console();print("Browser\u200bTitle");stream.flush()
        self.assertIn(b"\\u200b",data.getvalue())

    def test_activation_checks_environment_before_focus_and_focus_after(self):
        g=core.WindowsGUI.__new__(core.WindowsGUI);g.hwnd=11;g.bound_identity=[1,2]
        g.user=Mock();g.user.IsWindow.return_value=True;g.process_identity=lambda:[1,2]
        calls=[];g.identity_environment_check=lambda:calls.append("identity-environment")
        g.user.SetForegroundWindow.side_effect=lambda hwnd:calls.append("activate")
        g.pause=lambda *a,**k:None
        g.guard=lambda **kw:calls.append("foreground-guard")
        g.activate_target();self.assertEqual(calls,["identity-environment","activate","foreground-guard"])

    def test_environment_failure_prevents_activation(self):
        g=core.WindowsGUI.__new__(core.WindowsGUI);g.hwnd=11;g.bound_identity=[1,2]
        g.user=Mock();g.user.IsWindow.return_value=True;g.process_identity=lambda:[1,2]
        g.identity_environment_check=Mock(side_effect=core.StopRun("changed"))
        with self.assertRaises(core.StopRun):g.activate_target()
        g.user.SetForegroundWindow.assert_not_called()

    def test_foreground_failure_after_activation_is_not_retried(self):
        g=core.WindowsGUI.__new__(core.WindowsGUI);g.hwnd=11;g.bound_identity=[1,2]
        g.user=Mock();g.user.IsWindow.return_value=True;g.process_identity=lambda:[1,2]
        g.identity_environment_check=Mock();g.pause=Mock();g.guard=Mock(side_effect=core.StopRun("focus"))
        with self.assertRaises(core.StopRun):g.activate_target()
        g.user.SetForegroundWindow.assert_called_once_with(11)

    def test_geometry_unchanged_when_paper_changes_and_free_resize(self):
        p=RectanglePicker.__new__(RectanglePicker)
        p.rects={"REGION_001":[10,20,90,33],"NEXT":None,"PROGRESS":None}
        p.selected="REGION_001";p.bounds=[0,0,500,500];p.render=Mock()
        p.paper=Mock(get=lambda:"A4");p.orientation=Mock(get=lambda:"portrait")
        before=copy.deepcopy(p.rects);p.paper_changed();self.assertEqual(p.rects,before)
        p.transform=(1,0,0);p.drag=([100,20],[10,20,90,33],"e",None)
        p.motion(Mock(x=140,y=20));self.assertEqual(p.rects["REGION_001"],[10,20,130,33])

    def test_backup_retention_and_exact_restore(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            path=Path(td)/"config.json";original=b'{ "original" : true }\n';path.write_bytes(original)
            for i in range(12):
                atomic_update(path,{"i":i},hashlib.sha256(path.read_bytes()).hexdigest(),lambda c:None)
            self.assertEqual(len(backups(path)),12)
            saved=next(p for p in backups(path) if p.read_bytes()==original)
            restore(path,saved,lambda c:None)
            self.assertEqual(path.read_bytes(),original);self.assertEqual(len(backups(path)),13)

    def test_two_process_lock_and_crash_release(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            path=Path(td)/"process.lock"
            script="from calibration.storage import exclusive; import time,sys\nwith exclusive(sys.argv[1]):\n print('READY',flush=True)\n time.sleep(30)"
            child=subprocess.Popen([sys.executable,"-c",script,str(path)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(),"READY")
                with self.assertRaises(LockBusy):
                    with exclusive(path,timeout=.1):pass
            finally:
                child.terminate();child.communicate(timeout=10)
            with exclusive(path,timeout=.1):pass
            self.assertTrue(path.exists())

    def test_duplicate_expired_and_cancelled_dom_session(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            session=DOMSession();p=payload();p.update(token=session.token,created_ms=session.created_ms)
            path=Path(td)/"result.json";path.write_text(json.dumps(p))
            self.assertEqual(session.import_file(path)["token"],session.token)
            with self.assertRaises(CalibrationError):session.import_file(path)
            session=DOMSession();session.started-=181
            with self.assertRaises(CalibrationError):session.import_file(path)
            session=DOMSession();session.cancel()
            with self.assertRaises(CalibrationError):session.import_file(path)

    def test_no_clipboard_transport_in_app_or_browser_helper(self):
        for name in ("calibration/calibration.py","calibration/dom_picker.js"):
            source=(ROOT/name).read_text(encoding="utf-8")
            for token in ("clipboard_get(","clipboard_clear(","clipboard_append(","navigator.clipboard","execCommand('copy')"):
                self.assertNotIn(token,source)


class ProfileTests(unittest.TestCase):
    def cfg(self):return json.loads((ROOT/"config.json").read_bytes())

    def test_malformed_profile_isolation_for_json_roots_and_large_numbers(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            store=ProfileStore(td);healthy=store.create("Healthy",self.cfg())
            cases=[("profile.json",[]),("profile.json",None),("config.json",[]),("config.json",None)]
            for key in ("pdf_dpi","start_delay","stable_tolerance"):
                cfg=self.cfg();cfg[key]=10**400;cases.append(("config.json",cfg))
            for filename,data in cases:
                identifier=store.create("Malformed",self.cfg())
                (store.path(identifier)/filename).write_text(json.dumps(data))
            rows=store.enumerate()
            self.assertEqual(len(rows),1+len(cases))
            self.assertEqual([row["uuid"] for row in rows if row["ready"]],[healthy])


    def test_template_recording_is_locked_atomic_and_rejects_stale_config(self):
        from io import BytesIO
        from calibration.config_io import record_template
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            store=ProfileStore(td);identifier=store.create("Book",self.cfg())
            path=store.path(identifier)/"config.json"
            cfg=self.cfg();cfg["button_mode"]="template"
            atomic_update(path,cfg,digest(path.read_bytes()),lambda c:None)
            snap=store.snapshot(identifier,include_templates=False)
            image=BytesIO();Image.new("RGB",tuple(cfg["button_rect"][2:]),"green").save(image,format="PNG")
            raw=image.getvalue()
            with self.assertRaises(FileNotFoundError):store.snapshot(identifier)
            with self.assertRaises(CalibrationError):record_template(path,"enabled",raw,"stale")
            self.assertFalse((path.parent/"button_enabled.png").exists())
            script="from calibration.config_io import record_template;import sys\nrecord_template(sys.argv[1],'enabled',bytes.fromhex(sys.argv[2]),sys.argv[3])"
            with store.transaction([identifier]):
                child=subprocess.run([sys.executable,"-c",script,str(path),raw.hex(),digest(snap["config_bytes"])],cwd=ROOT,capture_output=True,text=True,timeout=10)
                self.assertNotEqual(child.returncode,0)
                self.assertFalse((path.parent/"button_enabled.png").exists())
            saved=record_template(path,"enabled",raw,digest(snap["config_bytes"]))
            self.assertEqual(saved.read_bytes(),raw)
            with self.assertRaises(ValueError):record_template(path,"enabled",raw,digest(snap["config_bytes"]))
            record_template(path,"disabled",raw,digest(snap["config_bytes"]))
            self.assertEqual(store.snapshot(identifier)["templates"]["enabled"],raw)

    def test_indexless_enumeration_duplicate_rename_and_output_root(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            store=ProfileStore(td);identifier=store.create("Book",self.cfg())
            copied=store.duplicate(identifier,"Copy");store.rename(copied,"Renamed")
            bad=store.folder/"not-a-uuid";bad.mkdir();(bad/"profile.json").write_text("broken")
            items=store.enumerate();self.assertEqual(sum(x["ready"] for x in items),2)
            self.assertEqual(len(items),3);self.assertFalse((store.data/"profiles.json").exists())
            snap=store.snapshot(copied);self.assertEqual(snap["metadata"]["name"],"Renamed")
            self.assertEqual(snap["output_root"],store.data/"captures"/copied)
            self.assertEqual(snap["profile"]["config_sha256"],hashlib.sha256(snap["config_bytes"]).hexdigest())

    def test_template_snapshot_and_duplicate_are_isolated(self):
        from io import BytesIO
        from PIL import Image
        def png(color):
            data=BytesIO();Image.new("RGB",(80,60),color).save(data,format="PNG");return data.getvalue()
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            store=ProfileStore(td);cfg=self.cfg();cfg["button_mode"]="template"
            templates={"enabled":png("green"),"disabled":png("gray")}
            identifier=store.create("Templates",cfg,templates);copyid=store.duplicate(identifier,"Copy")
            snap=store.snapshot(identifier)
            (store.path(identifier)/"button_enabled.png").write_bytes(png("red"))
            self.assertEqual(snap["templates"],templates)
            self.assertEqual(store.snapshot(copyid)["templates"],templates)
            self.assertEqual(snap["profile"]["template_sha256"]["enabled"],hashlib.sha256(templates["enabled"]).hexdigest())
            gui=core.WindowsGUI.__new__(core.WindowsGUI);gui.cfg=cfg;gui.config_dir=store.path(identifier)
            gui.template_bytes={"button_"+key+".png":data for key,data in snap["templates"].items()}
            gui.prepare_button();self.assertEqual(gui.enabled.getpixel((0,0)),(0,128,0))

    def test_source_import_is_byte_preserving(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            source=Path(td)/"external.json";source.write_bytes(json.dumps(self.cfg(),indent=4).encode())
            before=source.read_bytes();store=ProfileStore(Path(td)/"data")
            identifier=store.import_config(source,"Imported")
            self.assertEqual(source.read_bytes(),before);self.assertEqual(store.snapshot(identifier)["config_bytes"],before)

    def test_store_lock_prevents_mutation_from_another_process(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            store=ProfileStore(td);identifier=store.create("Original",self.cfg())
            script="from calibration.profiles import ProfileStore;import sys\nProfileStore(sys.argv[1]).rename(sys.argv[2],'Unexpected')"
            with exclusive(store.locks/"profiles.lock"):
                child=subprocess.run([sys.executable,"-c",script,str(store.data),identifier],cwd=ROOT,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(child.returncode,0)
            self.assertEqual(store.snapshot(identifier)["metadata"]["name"],"Original")

    def test_alignment_is_exact_and_invalid_action_preserves_original(self):
        old=[100,50,30,60];ref=[10,20,40,70];bounds=[0,0,300,300]
        self.assertEqual(align_rect(old,ref,"right",bounds),[50,20,30,60])
        self.assertEqual(align_rect(old,ref,"size",bounds),[100,50,40,70])
        with self.assertRaises(CalibrationError):align_rect(old,[280,20,40,70],"right",bounds)
        self.assertEqual(old,[100,50,30,60])


class ExportTests(unittest.TestCase):
    def test_original_extreme_dpi_never_completes_zero_or_infinite_page(self):
        from calibration.exports import pdf_options
        with self.assertRaises(ValueError):pdf_options({"pdf_dpi":10**400})
        for dpi in (1e308,1e-320):
            with self.subTest(dpi=dpi),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                folder=Path(td);manifest=self.fixture(folder);before=(folder/"manifest.json").read_bytes()
                plan=create_plan(folder,[1],{"paper_format":"Original","pdf_dpi":dpi})
                with self.assertRaises(ValueError):execute_plan(folder,plan)
                result=json.loads((plan.parent/"result.json").read_bytes())
                self.assertEqual(result["status"],"FAILED");self.assertNotIn("pdf_sha256",result)
                self.assertFalse((plan.parent/"document.pdf").exists())
                self.assertEqual((folder/"manifest.json").read_bytes(),before)
                for schema in (1,2):
                    legacy=copy.deepcopy(manifest);legacy["schema"]=schema
                    legacy["config"].update(paper_format="Original",pdf_dpi=dpi)
                    with self.assertRaises(ValueError):core.build_pdf(folder,legacy,folder/f"legacy-{schema}.pdf")
                    self.assertFalse((folder/f"legacy-{schema}.pdf").exists())
                fixed=execute_plan(folder,create_plan(folder,[1],{"paper_format":"A4","pdf_dpi":dpi}))
                self.assertGreater(float(PdfReader(fixed).pages[0].mediabox.width),0)

    def fixture(self,folder,status="COMPLETE"):
        cfg=json.loads((ROOT/"config.json").read_bytes())
        cfg.update(regions=[[10,20,40,50],[70,20,45,30]],navigation_mode="none",paper_format="A4")
        pairs=[]
        for index,color in enumerate(("red","blue","green"),1):
            pairs.append(core.save_pair(folder,index,Image.new("RGB",(150,100),color),cfg))
        m={"schema":3,"version":"0.2.0","status":status,"finished":"2026-10-05T00:00:00+00:00","config":cfg,"pairs":pairs,"profile":None}
        core.write_json(folder/"manifest.json",m)
        return m

    def test_export_order_dimensions_provenance_and_immutable_originals(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);m=self.fixture(folder);before=(folder/"manifest.json").read_bytes()
            plan=create_plan(folder,[3,1],{"paper_format":"A5","paper_orientation":"landscape"})
            planbytes=plan.read_bytes();output=execute_plan(folder,plan)
            result=json.loads((output.parent/"result.json").read_bytes())
            self.assertEqual(result["status"],"COMPLETE");self.assertEqual(result["source_manifest_sha256"],digest(before))
            self.assertEqual(result["export_plan_sha256"],digest(planbytes));self.assertEqual(result["pdf_sha256"],digest(output.read_bytes()))
            pdf=PdfReader(output);self.assertEqual(len(pdf.pages),4)
            self.assertAlmostEqual(float(pdf.pages[0].mediabox.width)*25.4/72,210,places=3)
            self.assertEqual(pdf.pages[0].images[0].image.convert("RGB").getpixel((0,0)),(0,128,0))
            self.assertEqual(pdf.pages[2].images[0].image.convert("RGB").getpixel((0,0)),(255,0,0))
            self.assertEqual((folder/"manifest.json").read_bytes(),before)
            for pair in m["pairs"]:
                for entry in pair["images"]:self.assertEqual(core.sha256(folder/entry["file"]),entry["sha256"])

    def test_duplicate_empty_and_unknown_indices_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);self.fixture(folder)
            for indices in ([1,1],[],[4],[True]):
                with self.subTest(indices=indices),self.assertRaises(ValueError):create_plan(folder,indices)

    def test_schema3_public_legacy_api_cannot_bypass_plan(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);m=self.fixture(folder)
            with self.assertRaises(ValueError):core.build_pdf(folder,m,folder/"bypass.pdf")
            self.assertFalse((folder/"bypass.pdf").exists())

    def test_running_is_never_exported_or_modified(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);self.fixture(folder,"RUNNING");before=(folder/"manifest.json").read_bytes()
            self.assertIn("INTERRUPTED",running_state(folder))
            with exclusive(folder/".writer.lock"):
                self.assertIn("aktiv",running_state(folder))
            with self.assertRaises(ValueError):create_plan(folder)
            with patch.object(sys,"argv",["edge_capture.py","--rebuild",str(folder)]),self.assertRaises(ValueError):core.main()
            self.assertEqual((folder/"manifest.json").read_bytes(),before)

    def test_decode_uses_verified_bytes_after_path_replacement(self):
        from io import BytesIO
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);m=self.fixture(folder);path=folder/m["pairs"][0]["images"][0]["file"]
            original_open=Image.open;changed=False
            def decode(source,*args,**kwargs):
                nonlocal changed
                self.assertIsInstance(source,BytesIO)
                if not changed:
                    changed=True;Image.new("RGB",(40,50),"black").save(path)
                return original_open(source,*args,**kwargs)
            with patch("calibration.exports.Image.open",side_effect=decode):images=view_images(folder,m,1)
            self.assertEqual(images[0].getpixel((0,0)),(255,0,0))

    def test_invalid_dimensions_after_decoding_block_export(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);m=self.fixture(folder)
            entry=m["pairs"][0]["images"][0];path=folder/entry["file"]
            Image.new("RGB",(5,5),"red").save(path);entry["sha256"]=core.sha256(path)
            core.write_json(folder/"manifest.json",m)
            plan=create_plan(folder,[1])
            with self.assertRaises(ValueError):execute_plan(folder,plan)
            self.assertEqual(json.loads((plan.parent/"result.json").read_bytes())["status"],"FAILED")

    def test_invalid_excluded_view_does_not_block_valid_export(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);m=self.fixture(folder);(folder/m["pairs"][1]["images"][0]["file"]).write_bytes(b"broken")
            output=execute_plan(folder,create_plan(folder,[1,3]));self.assertEqual(len(PdfReader(output).pages),4)

    def test_plan_changed_during_render_fails_without_mutating_manifest(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);self.fixture(folder);before=(folder/"manifest.json").read_bytes();plan=create_plan(folder)
            renderer=core._render_pdf
            def change(*args,**kwargs):
                result=renderer(*args,**kwargs);plan.write_bytes(plan.read_bytes()+b" ");return result
            with patch.object(core,"_render_pdf",side_effect=change),self.assertRaises(ValueError):execute_plan(folder,plan)
            self.assertEqual(json.loads((plan.parent/"result.json").read_bytes())["status"],"FAILED")
            self.assertEqual((folder/"manifest.json").read_bytes(),before)

    def test_persisted_plan_bytes_determine_order_and_result_hash(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);self.fixture(folder);plan=create_plan(folder,[1])
            stored=json.loads(plan.read_bytes());stored["selected_view_indices"]=[2]
            plan.write_bytes(json.dumps(stored,separators=(",",":")).encode())
            actual=plan.read_bytes();output=execute_plan(folder,plan)
            self.assertEqual(json.loads((output.parent/"result.json").read_bytes())["export_plan_sha256"],digest(actual))
            self.assertEqual(PdfReader(output).pages[0].images[0].image.convert("RGB").getpixel((0,0)),(0,0,255))

    def test_rebuild_schema3_with_and_without_plan_has_provenance(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);self.fixture(folder)
            with patch.object(sys,"argv",["edge_capture.py","--rebuild",str(folder),"--paper","A5"]):self.assertEqual(core.main(),0)
            first=next((folder/"exports").glob("*/result.json"));self.assertEqual(json.loads(first.read_bytes())["status"],"COMPLETE")
            plan=create_plan(folder,[2])
            with patch.object(sys,"argv",["edge_capture.py","--rebuild",str(folder),"--export-plan",str(plan)]):self.assertEqual(core.main(),0)
            with patch.object(sys,"argv",["edge_capture.py","--rebuild",str(folder),"--export-plan",str(plan),"--paper","A4"]),self.assertRaises(SystemExit):core.main()

    def test_similarity_and_contrast_are_deterministic(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);m=self.fixture(folder)
            for index in (1,2):
                m["pairs"][index-1]=core.save_pair(folder,index,Image.new("RGB",(150,100),"white"),m["config"])
            analysis=analyze_view(folder,m,2);self.assertEqual(analysis["similarity"],1)
            self.assertEqual(analysis["low_contrast_stddev"],[0,0]);self.assertEqual(len(analysis["warnings"]),3)
            a=Image.new("RGB",(64,64),(100,100,100));a.paste((104,104,104),(32,0,64,64))
            self.assertAlmostEqual(region_statistics(a)[1],2,places=8)

    def test_export_cancel_records_separate_result_and_preserves_capture(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);self.fixture(folder);before=(folder/"manifest.json").read_bytes();plan=create_plan(folder)
            with patch.object(core,"_render_pdf",side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):execute_plan(folder,plan)
            self.assertEqual(json.loads((plan.parent/"result.json").read_bytes())["status"],"CANCELLED")
            self.assertEqual((folder/"manifest.json").read_bytes(),before)


if __name__=="__main__":unittest.main()
