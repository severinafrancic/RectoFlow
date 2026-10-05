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
from calibration.storage import exclusive, LockBusy
from calibration.config_io import atomic_update, backups, restore
from calibration.geometry import CalibrationError
from calibration.screenshot_picker import RectanglePicker
from calibration.dom_picker import DOMSession
from calibration.profiles import ProfileStore
from calibration.geometry import align_rect
from test_calibration import payload
import edge_capture as core


class CalibrationV02Tests(unittest.TestCase):
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


if __name__=="__main__":unittest.main()
