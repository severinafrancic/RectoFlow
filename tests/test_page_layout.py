"""Sparse views across policy, capture, immutable manifest, profiles and PDF."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from pypdf import PdfReader
from test_regions import config, SCRATCH
from calibration.page_layout import default_policy, policy_for, resolve_view, validate_policy
from calibration.exports import create_plan, execute_plan, view_images, readable_manifest, running_state
from calibration.config_io import atomic_update, backups, restore, updated_config
from calibration.profiles import ProfileStore
from calibration.regions import selection
from calibration.geometry import CalibrationError
import edge_capture as core


def sparse_config(known=True, mode="next_button"):
    cfg=config(2,mode)
    cfg.update(expected_spreads=4 if known else None,max_spreads=8,pdf_layout="separate")
    cfg["page_layout_policy"]=default_policy(2)
    cfg["page_layout_policy"].update(first=[2],last=[1])
    return cfg


def frames(cfg):
    result=[]
    for view in range(1,5):
        image=Image.new("RGB",(320,240),"white")
        for slot,rect in enumerate(cfg["regions"],1):image.paste((view*40,slot*60,17),core.box(rect))
        result.append(image)
    return result


class PageLayoutTests(unittest.TestCase):
    def test_main_runtime_composition_schema4_real_readiness_and_pdf(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);cfg=sparse_config(False);cfg.update(stable_seconds=.01,disabled_seconds=.01,min_after_click=.01,poll_seconds=.01,timeout_seconds=1,output_dir="captures",confirm_pdf_export=False)
            path=folder/"config.json";path.write_text(json.dumps(cfg));images=frames(cfg)
            gui=Mock(size=(320,240),template_bytes={});gui.title.return_value="Synthetic browser"
            state={"view":0,"clock":0.0}
            gui.snapshot.side_effect=lambda:images[state["view"]]
            gui.button_state.side_effect=lambda im:"disabled" if state["view"]==3 else "enabled"
            def click():state["view"]+=1
            gui.click_next.side_effect=click
            def clock():state["clock"]+=.02;return state["clock"]
            real_ready=core.wait_ready
            with patch.object(sys,"argv",["rectoflow","--config",str(path)]),patch.object(core,"WindowsGUI",return_value=gui), \
                 patch("calibration.calibration.confirm_capture",return_value=images[0]), \
                 patch.object(core,"wait_ready",side_effect=lambda g,c,previous=None:real_ready(g,c,previous=previous,clock=clock)):
                self.assertEqual(core.main(),0)
            run=next((folder/"captures").glob("run_*"));manifest=json.loads((run/"manifest.json").read_bytes())
            self.assertEqual(manifest["schema"],4);self.assertEqual(manifest["status"],"COMPLETE")
            self.assertEqual([p["slots"] for p in manifest["pairs"]],[[2],[1,2],[1,2],[1]])
            self.assertGreaterEqual(gui.guard.call_count,4);self.assertEqual(gui.click_next.call_count,3)
            self.assertEqual(len(PdfReader(next((run/"exports").glob("*/document.pdf"))).pages),6)

    def test_inactive_slot_still_bound_to_confirmed_pixels(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            cfg=sparse_config(False);confirmed=frames(cfg)[0];changed=confirmed.copy()
            changed.putpixel((10,30),(0,0,0));manifest={"schema":4,"pairs":[]}
            with patch.object(core,"wait_ready",return_value=(changed,"enabled",core.progress_image(changed,cfg))),self.assertRaises(CalibrationError):
                core.run_capture(Mock(),cfg,Path(td),manifest,confirmed_image=confirmed)
            self.assertEqual(manifest["pairs"],[]);self.assertFalse(list(Path(td).glob("*.png")))

    def capture(self,folder,cfg):
        images=frames(cfg)
        state="manual" if cfg["navigation_mode"]=="manual" else "enabled"
        ready=[(image,state if i<3 or state=="manual" else "disabled",core.progress_image(image,cfg)) for i,image in enumerate(images)]
        gui=Mock();gui.manual_transition.side_effect=[True,True,True,False]
        gui.snapshot.side_effect=images[:-1]
        manifest={"schema":4,"status":"RUNNING","config":cfg,"pairs":[]}
        with patch.object(core,"wait_ready",side_effect=ready):core.run_capture(gui,cfg,folder,manifest,confirmed_image=images[0])
        manifest.update(status="COMPLETE",finished="2026-10-10T00:00:00Z")
        core.write_json(folder/"manifest.json",manifest)
        return manifest,gui

    def test_known_and_unknown_length_1221_png_manifest_pdf_pixels(self):
        for known in (True,False):
            with self.subTest(known=known),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                folder=Path(td);cfg=sparse_config(known);manifest,gui=self.capture(folder,cfg)
                self.assertEqual([p["slots"] for p in manifest["pairs"]],[[2],[1,2],[1,2],[1]])
                self.assertEqual([p["layout"]["source"] for p in manifest["pairs"]],["first","middle","middle","last"])
                self.assertEqual(len(list(folder.glob("*.png"))),6)
                self.assertFalse((folder/"000001_region_001.png").exists())
                self.assertFalse((folder/"000004_region_002.png").exists())
                gui.manual_transition.assert_not_called();self.assertEqual(gui.click_next.call_count,3)
                original=(folder/"manifest.json").read_bytes()
                pdf=execute_plan(folder,create_plan(folder))
                pages=PdfReader(pdf).pages;self.assertEqual(len(pages),6)
                expected=[(40,120,17),(80,60,17),(80,120,17),(120,60,17),(120,120,17),(160,60,17)]
                self.assertEqual([p.images[0].image.convert("RGB").getpixel((0,0)) for p in pages],expected)
                self.assertEqual((folder/"manifest.json").read_bytes(),original)
                self.assertEqual([len(view_images(folder,manifest,i)) for i in range(1,5)],[1,2,2,1])

    def test_first_left_last_right_and_both_legacy_defaults(self):
        for first,last,expected in (([1],[2],[[1],[1,2],[1,2],[2]]),([1,2],[1,2],[[1,2]]*4)):
            with self.subTest(first=first,last=last),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                cfg=sparse_config();cfg["page_layout_policy"].update(first=first,last=last)
                manifest,_=self.capture(Path(td),cfg)
                self.assertEqual([p["slots"] for p in manifest["pairs"]],expected)

    def test_unknown_manual_final_view_not_published_before_terminal_decision(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);cfg=sparse_config(False,"manual");images=frames(cfg);calls=[]
            gui=Mock()
            def transition():
                index=len(calls)+1
                self.assertFalse(list(folder.glob(f"{index:06d}_*.png")))
                calls.append(index)
                return index<4
            gui.manual_transition.side_effect=transition
            manifest={"schema":4,"status":"RUNNING","config":cfg,"pairs":[]}
            with patch.object(core,"wait_ready",side_effect=[(im,"manual",im) for im in images]):core.run_capture(gui,cfg,folder,manifest)
            self.assertEqual([p["slots"] for p in manifest["pairs"]],[[2],[1,2],[1,2],[1]])
            gui.click_next.assert_not_called();self.assertEqual(calls,[1,2,3,4])

    def test_override_wins_without_changing_geometry_or_navigation(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            cfg=sparse_config(False);geometry=copy.deepcopy(cfg["regions"])
            cfg["page_layout_policy"]["overrides"]={"2":[2],"4":[2]}
            manifest,gui=self.capture(Path(td),cfg)
            self.assertEqual([p["slots"] for p in manifest["pairs"]],[[2],[2],[1,2],[2]])
            self.assertEqual(cfg["regions"],geometry);self.assertEqual(gui.click_next.call_count,3)
            self.assertEqual(manifest["pairs"][-1]["layout"],{"source":"override","is_last":True})

    def test_single_view_last_wins_and_generic_slots(self):
        policy=default_policy(5);policy.update(first=[1],middle=[2,3],last=[4,5])
        validate_policy(policy,5)
        self.assertEqual(resolve_view(policy,1,True)[0],[4,5])
        policy["overrides"]={"1":[2]}
        self.assertEqual(resolve_view(policy,1,True)[0],[2])

    def test_invalid_policy_empty_stale_duplicate_unordered_boolean(self):
        base=default_policy(2)
        for changes in ({"first":[]},{"middle":[1,1]},{"last":[2,1]},{"first":[True]},
                        {"slot_count":3},{"schema":True},{"overrides":{"0":[1]}},{"overrides":{"01":[1]}},
                        {"overrides":{"9":[1]}},{"overrides":{"2":[]}},{"overrides":{"1/../":[1]}}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):validate_policy({**base,**changes},2,8)
                cfg=sparse_config();cfg["page_layout_policy"]={**base,**changes}
                with self.assertRaises(ValueError):core.validate(cfg,(320,240))

    def test_profile_snapshot_backup_restore_and_legacy_configs(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);cfg=sparse_config(mode="manual");store=ProfileStore(folder/"data")
            identifier=store.create("Sparse",cfg);snapshot=store.snapshot(identifier)
            self.assertEqual(snapshot["config"]["page_layout_policy"],cfg["page_layout_policy"])
            path=snapshot["config_path"];raw=path.read_bytes()
            changed=copy.deepcopy(cfg);changed["page_layout_policy"]["overrides"]={"2":[1]}
            atomic_update(path,changed,core.hashlib.sha256(raw).hexdigest(),lambda c:core.validate(c,(320,240)))
            self.assertEqual(store.snapshot(identifier)["config"]["page_layout_policy"],changed["page_layout_policy"])
            restore(path,backups(path)[0],lambda c:core.validate(c,(320,240)))
            self.assertEqual(path.read_bytes(),raw)
        for count in (1,2,5):
            cfg=config(count);self.assertEqual(policy_for(cfg),default_policy(count));core.validate(cfg,(320,240))
        legacy=config(2);rects=legacy.pop("regions");legacy.update(left_rect=rects[0],right_rect=rects[1])
        self.assertEqual(policy_for(legacy),default_policy(2));core.validate(legacy,(320,240))

    def test_sparse_manifest_tampering_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);manifest,_=self.capture(folder,sparse_config())
            for change in ("slot","missing","policy","last","name","bool"):
                bad=copy.deepcopy(manifest)
                if change=="slot":bad["pairs"][0]["images"][0]["slot"]=1
                elif change=="missing":bad["pairs"][0]["images"]=[]
                elif change=="policy":bad["config"]["page_layout_policy"]["first"]=[1]
                elif change=="last":bad["pairs"][0]["layout"]["is_last"]=True
                elif change=="name":bad["pairs"][0]["images"][0]["file"]="../other.png"
                else:bad["pairs"][0]["slots"]=[True]
                with self.subTest(change=change),self.assertRaises(ValueError):
                    readable_manifest(bad);view_images(folder,bad,1)

    def test_unknown_failure_does_not_guess_terminal_page(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);cfg=sparse_config(False);image=frames(cfg)[0];gui=Mock(snapshot=Mock(return_value=image))
            manifest={"schema":4,"config":cfg,"pairs":[]}
            with patch.object(core,"wait_ready",side_effect=[(image,"enabled",core.progress_image(image,cfg)),core.StopRun("unknown terminal")]),self.assertRaises(core.StopRun):
                core.run_capture(gui,cfg,folder,manifest)
            self.assertEqual(manifest["pairs"][0]["slots"],[2])
            self.assertFalse(manifest["pairs"][0]["layout"]["is_last"])
            self.assertEqual(gui.click_next.call_count,1)

    def test_sparse_rebuild_cli_and_running_recovery(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);manifest,_=self.capture(folder,sparse_config())
            with patch.object(sys,"argv",["edge_capture","--rebuild",str(folder)]):self.assertEqual(core.main(),0)
            output=next((folder/"exports").glob("*/document.pdf"))
            self.assertEqual(len(PdfReader(output).pages),6)
            manifest["status"]="RUNNING";core.write_json(folder/"manifest.json",manifest)
            self.assertIn("RECOVERY_REQUIRED",running_state(folder))
            with self.assertRaises(ValueError):create_plan(folder)
