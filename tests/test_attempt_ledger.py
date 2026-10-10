"""Boundary failures and durable attempt evidence, using synthetic pixels only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image

from test_regions import config, SCRATCH
from test_edge_capture import FakeGUI, config as legacy_config, picture
import edge_capture as core
from calibration.diagnostics import Diagnostic, scope, checkpoint
from calibration.failures import StopRun, UserCancelled, boundary
from calibration.geometry import assert_same_selection
from scripts.build_windows import public_bundle_members


class LedgerTests(unittest.TestCase):
    def attempt(self, root):
        d=Diagnostic(root,core.VERSION,"test")
        self.assertTrue((d.attempt_dir/"attempt.json").is_file())
        self.assertTrue((d.attempt_dir/"events.jsonl").is_file())
        self.assertTrue((d.attempt_dir/"SUMMARY.txt").is_file())
        self.assertFalse(d.data["first_frame_acquired"])
        self.assertFalse(d.data["run_created"])
        return d

    def events(self,d):
        return [json.loads(line) for line in (d.attempt_dir/"events.jsonl").read_text(encoding="utf-8").splitlines()]

    def failed(self,d,code,step):
        d.finish(2)
        self.assertEqual(d.data["primary_failure"]["code"],code)
        self.assertEqual(d.data["failed_checkpoint"],step)
        self.assertEqual(d.data["terminal_outcome"],"TECHNICAL_FAILURE")
        self.assertEqual(d.data["exit_code"],2)
        self.assertNotIn("WORKFLOW_COMPLETE",[e["event"] for e in self.events(d)])
        saved=json.loads((d.attempt_dir/"attempt.json").read_bytes())
        self.assertEqual(saved["primary_failure"]["code"],code)
        self.assertIn(code,(d.attempt_dir/"SUMMARY.txt").read_text())
        event=next(e for e in reversed(self.events(d)) if e["event"]=="FAIL")
        self.assertEqual(event["code"],code)
        for key in ("checkpoint","failure_class","exception_type","message","timestamp"):
            self.assertIn(key,event)
        return event

    def test_attempt_exists_before_config_and_fallback_no_run(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            root=Path(td);blocked=root/"not-dir";blocked.write_text("file")
            with patch("calibration.diagnostics.tempfile.gettempdir",return_value=str(root/"temp")):
                d=self.attempt(blocked)
            self.assertIn("temp",str(d.attempt_dir))
            self.assertEqual(self.events(d)[0]["event"],"LAUNCHER_ENTER")
            self.assertEqual(d.data["last_successful_checkpoint"],"LAUNCHER_ENTER")
            self.assertFalse(list(root.glob("run_*")))

    def test_non_object_config_is_invalid_before_target_creation(self):
        for content in ("null","[]","true"):
            with self.subTest(content=content),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                root=Path(td);(root/"config.json").write_text(content);d=self.attempt(root)
                with patch.object(sys,"argv",["rectoflow","--config",str(root/"config.json")]),patch.object(core,"WindowsGUI") as gui:
                    with self.assertRaises(StopRun):core.main(d)
                gui.assert_not_called();self.failed(d,"CFG_INVALID","CONFIG_LOAD")
                self.assertFalse(d.data["screenshot_requested"])

    def test_actual_main_config_load_validation_binding_confirmation_boundaries(self):
        cases=[("load","CFG_LOAD_FAILED","CONFIG_LOAD","LAUNCHER_ENTER"),
               ("validation","CFG_INVALID","CONFIG_VALIDATE","TARGET_ADAPTER_OK"),
               ("selection","TARGET_SELECTION_FAILED","TARGET_PICK","CONFIG_VALIDATE_OK"),
               ("bind","TARGET_BIND_FAILED","TARGET_BIND","TARGET_PICK_OK"),
               ("guard","TARGET_FOCUS_LOST","TARGET_GUARD","TARGET_PICK_OK"),
               ("confirmation","CONFIRMATION_FAILED","FINAL_CONFIRMATION","TARGET_BIND_OK"),
               ("changed","TARGET_CHANGED","FINAL_CONFIRMATION","TARGET_BIND_OK")]
        for case,code,step,last in cases:
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                root=Path(td);path=root/"config.json";cfg=config();cfg["output_dir"]="captures"
                path.write_text(json.dumps(cfg))
                if case=="load":path.unlink()
                if case=="validation":cfg["regions"]=[[9999,0,20,20]];path.write_text(json.dumps(cfg))
                gui=Mock(size=(320,240),template_bytes={});gui.title.return_value="private book"
                def bind():
                    with boundary("TARGET_PICK","TARGET_SELECTION_FAILED"):
                        if case=="selection":raise OSError("selection API failed")
                    if case=="bind":raise RuntimeError("binding API failed")
                    if case=="guard":
                        with boundary("TARGET_GUARD","TARGET_BIND_FAILED"):
                            raise StopRun("foreground","TARGET_FOCUS_LOST")
                gui.bind.side_effect=bind
                error=StopRun("target changed","TARGET_CHANGED") if case=="changed" else RuntimeError("confirmation failed")
                d=self.attempt(root)
                with patch.object(sys,"argv",["rectoflow","--config",str(path)]),patch.object(core,"WindowsGUI",return_value=gui), \
                     patch("calibration.calibration.confirm_capture",side_effect=error):
                    with self.assertRaises(Exception):core.main(d)
                self.failed(d,code,step)
                self.assertEqual(d.data["primary_failure"]["last_successful_checkpoint"],last)
                self.assertFalse(d.data["first_frame_acquired"])
                self.assertFalse(list((root/"captures").glob("run_*")))
                self.assertFalse(d.data["manifest_created"])

    def test_snapshot_pre_guard_acquire_dimension_persist_post_guard(self):
        cases=[("pre","TARGET_FOCUS_LOST","TARGET_GUARD",False,False),
               ("acquire","SCREENSHOT_ACQUIRE_FAILED","SCREENSHOT_ACQUIRE",False,False),
               ("dimension","SCREENSHOT_DIMENSION_MISMATCH","FIRST_FRAME_GUARD",True,True),
               ("persist","SCREENSHOT_PERSIST_FAILED","FIRST_FRAME_PERSIST",True,False),
               ("post","TARGET_CHANGED","FIRST_FRAME_GUARD",True,True)]
        for case,code,step,acquired,persisted in cases:
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                root=Path(td);d=self.attempt(root);gui=core.WindowsGUI.__new__(core.WindowsGUI);gui.size=(20,20)
                gui.guard=Mock(side_effect=StopRun("focus","TARGET_FOCUS_LOST") if case=="pre" else [None,StopRun("changed","TARGET_CHANGED")] if case=="post" else None)
                image=Image.new("RGB",(21,20) if case=="dimension" else (20,20),"red")
                original=OSError("ImageGrab unavailable")
                with scope(d),patch("PIL.ImageGrab.grab",side_effect=original if case=="acquire" else None,return_value=image) as grab:
                    if case=="persist":
                        with patch.object(Image.Image,"save",side_effect=OSError("storage failed")):
                            with self.assertRaises(Exception):gui.snapshot()
                    else:
                        with self.assertRaises(Exception):gui.snapshot()
                event=self.failed(d,code,step)
                self.assertEqual(grab.call_count,0 if case=="pre" else 1)
                self.assertEqual(d.data["first_frame_acquired"],acquired)
                frame=d.attempt_dir/"first-frame.png"
                self.assertEqual(frame.exists(),persisted)
                self.assertFalse(list(root.glob("run_*")))
                if persisted:
                    self.assertEqual(d.data["first_frame_sha256"],hashlib.sha256(frame.read_bytes()).hexdigest())
                    self.assertEqual((d.data["first_frame_width"],d.data["first_frame_height"]),image.size)
                    self.assertIn("FIRST_FRAME_PERSIST_OK",[e["event"] for e in self.events(d)])
                if case=="acquire":self.assertEqual(event["causes"][0]["exception_type"],"OSError")

    def test_initial_manifest_and_publish_failures_preserve_hidden_stage(self):
        for case,code,step,last in (("mkdir","RUN_CREATE_FAILED","RUN_STAGE_CREATE","LAUNCHER_ENTER"),
                                   ("manifest","MANIFEST_WRITE_FAILED","INITIAL_MANIFEST_WRITE","RUN_STAGE_CREATE_OK"),
                                   ("publish","RUN_PUBLISH_FAILED","RUN_PUBLISH","INITIAL_MANIFEST_WRITE_OK")):
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                root=Path(td);d=self.attempt(root);runs=root/"runs"
                target="pathlib.Path.mkdir" if case=="mkdir" else "edge_capture.write_json" if case=="manifest" else "edge_capture.os.rename"
                with scope(d),patch(target,side_effect=OSError(case)):
                    with self.assertRaises(OSError):core.publish_run(runs,{"status":"RUNNING","pairs":[]})
                self.failed(d,code,step)
                self.assertEqual(d.data["primary_failure"]["last_successful_checkpoint"],last)
                self.assertFalse(list(runs.glob("run_*")))
                pending=list(runs.glob(".pending-run_*"))
                self.assertEqual(bool(pending),case!="mkdir")
                self.assertEqual(bool(list(runs.glob(".pending-run_*/manifest.json"))),case=="publish")
                self.assertEqual(d.data["initial_manifest_created"],case=="publish")

    def test_real_nested_post_screenshot_guard_is_distinct_from_pre_guard(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            d=self.attempt(td);gui=core.WindowsGUI.__new__(core.WindowsGUI);gui.size=(20,20);gui.cfg=config()
            gui.abort_check=lambda:None;gui.identity_environment_check=Mock(side_effect=[None,StopRun("process changed","TARGET_CHANGED")])
            gui.user=Mock();gui.hwnd=123;gui.user.GetForegroundWindow.return_value=123
            gui.user.GetSystemMetrics.side_effect=lambda i:gui.size[i];gui.initial_geometry=(0,0,20,20);gui.geometry=lambda:gui.initial_geometry
            gui.title=lambda:"synthetic"
            with scope(d),patch("PIL.ImageGrab.grab",return_value=Image.new("RGB",(20,20))):
                with self.assertRaises(StopRun):gui.snapshot(areas=False)
            event=self.failed(d,"TARGET_CHANGED","FIRST_FRAME_GUARD")
            self.assertTrue(d.data["first_frame_path"])
            self.assertEqual(event["metadata"]["guard_checkpoint"],"TARGET_GUARD")

    def test_crop_first_second_and_append_are_separate_and_preserve_run(self):
        for case in ("first","second","append"):
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                root=Path(td);d=self.attempt(root);cfg=config(2);im=Image.new("RGB",(320,240),"green")
                with scope(d):
                    folder=core.publish_run(root/"runs",{"status":"RUNNING","pairs":[]})
                    d.first_frame(im)
                    real_save=Image.Image.save
                    def save(image,path,*args,**kwargs):
                        if (case=="first" or case=="second" and "region_002" in str(path)):
                            raise OSError("crop storage")
                        return real_save(image,path,*args,**kwargs)
                    with patch.object(core,"wait_ready",return_value=(im,"disabled",im)),patch.object(Image.Image,"save",save):
                        if case=="append":
                            with patch.object(core,"write_json",side_effect=OSError("append")):
                                with self.assertRaises(OSError):core.run_capture(Mock(),cfg,folder,{"pairs":[]})
                        else:
                            with self.assertRaises(OSError):core.run_capture(Mock(),cfg,folder,{"pairs":[]})
                code="CAPTURE_MANIFEST_APPEND_FAILED" if case=="append" else "CAPTURE_CROP_FAILED"
                step="FIRST_MANIFEST_APPEND" if case=="append" else "FIRST_CROP"
                event=self.failed(d,code,step)
                self.assertTrue((folder/"manifest.json").is_file());self.assertTrue(d.data["manifest_created"])
                self.assertTrue(d.data["run_created"]);self.assertTrue(d.data["first_frame_path"])
                self.assertEqual(len(list(folder.glob("*.png"))),{"first":0,"second":1,"append":2}[case])
                if case!="append":self.assertEqual(event["metadata"]["slot"],1 if case=="first" else 2)

    def test_pure_cancel_preserves_code2_without_crash_dialog(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            d=self.attempt(td)
            with scope(d):
                with self.assertRaises(UserCancelled):
                    with boundary("FINAL_CONFIRMATION","CONFIRMATION_FAILED"):
                        raise UserCancelled("cancel")
            d.finish(2)
            self.assertIsNone(d.data["primary_failure"]);self.assertFalse(d.needs_error_dialog(2))
            self.assertEqual(d.data["terminal_outcome"],"USER_CANCELLED")
            self.assertEqual(d.data["history"][-1]["code"],"USER_CANCELLED")

    def test_capture_main_failure_artifacts_and_causality_after_accepted_confirmation(self):
        cases=[("prepare","BUTTON_PREPARE_FAILED","BUTTON_PREPARE",False,0),
               ("target-after-confirm","TARGET_CHANGED","TARGET_GUARD",False,0),
               ("uia-unknown","BUTTON_STATE_UNKNOWN","WAIT_NEW_VIEW",True,0),
               ("template-unknown","BUTTON_STATE_UNKNOWN","WAIT_NEW_VIEW",True,0),
               ("partial-click","NAVIGATION_CLICK_FAILED","NEXT_CLICK",True,2),
               ("sent-no-change","VIEW_CHANGE_NOT_DETECTED","WAIT_NEW_VIEW",True,2),
               ("disabled",None,None,True,2)]
        for case,code,step,frame,crops in cases:
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                root=Path(td);d=self.attempt(root);cfg=config(2,"next_button")
                cfg.update(output_dir="runs",confirm_pdf_export=False,poll_seconds=.25,stable_seconds=.5,disabled_seconds=.5,timeout_seconds=3,min_after_click=.5)
                cfg["button_mode"]="template" if case=="template-unknown" else "uia"
                (root/"config.json").write_text(json.dumps(cfg))
                if cfg["button_mode"]=="template":
                    for name in ("button_enabled.png","button_disabled.png"):Image.new("RGB",(25,20),"white").save(root/name)
                im=Image.new("RGB",(320,240),"red")
                gui=core.WindowsGUI.__new__(core.WindowsGUI);gui.cfg=cfg;gui.size=(320,240);gui.user=Mock();gui.now=0
                gui.title=lambda:"synthetic";gui.bind=lambda:checkpoint("TARGET_BIND_OK");gui.park=lambda:None
                gui.pause=lambda seconds:setattr(gui,"now",gui.now+seconds)
                gui.guard=Mock(side_effect=StopRun("window changed","TARGET_CHANGED") if case=="target-after-confirm" else None)
                gui.prepare_button=Mock(side_effect=ImportError("UIA missing") if case=="prepare" else None)
                gui.button_state=lambda image:"unknown" if "unknown" in case else "disabled" if case=="disabled" else "enabled"
                gui.user.SendInput.return_value=1 if case=="partial-click" else 2
                wait=core.wait_ready
                with patch.object(sys,"argv",["rectoflow","--config",str(root/"config.json")]),patch.object(core,"WindowsGUI",return_value=gui), \
                     patch("calibration.calibration.confirm_capture",return_value=im),patch("PIL.ImageGrab.grab",return_value=im), \
                     patch.object(core,"wait_ready",side_effect=lambda g,c,previous=None:wait(g,c,previous,clock=lambda:g.now)):
                    result=core.main(d)
                self.assertEqual(result,0 if code is None else 2)
                self.assertTrue(d.data["confirmation_accepted"])
                self.assertTrue(d.data["run_created"]);self.assertTrue(d.data["manifest_created"])
                folder=Path(d.data["run_path"]);manifest=json.loads((folder/"manifest.json").read_bytes())
                self.assertEqual(len(list(folder.glob("*.png"))),crops)
                self.assertEqual(bool(d.data["first_frame_path"]),frame)
                self.assertEqual(d.data["first_frame_acquired"],frame)
                self.assertEqual(manifest["status"],"COMPLETE" if code is None else "STOPPED")
                if code:self.failed(d,code,step)
                else:self.assertEqual(d.data["terminal_outcome"],"SUCCESS")
                if case=="sent-no-change":self.assertEqual(gui.user.SendInput.call_count,1)
                if case=="partial-click":self.assertEqual(gui.user.SendInput.call_count,2)

    def test_transition_unknown_no_change_unstable_timeout_and_terminal_disabled(self):
        cases=[("uia-unknown","BUTTON_STATE_UNKNOWN"),("template-unknown","BUTTON_STATE_UNKNOWN"),
               ("unchanged","VIEW_CHANGE_NOT_DETECTED"),("unstable","VIEW_NOT_STABLE"),("timeout","VIEW_TRANSITION_TIMEOUT"),("disabled",None)]
        for case,code in cases:
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                d=self.attempt(td);cfg=legacy_config();previous=core.progress_image(picture(),cfg)
                gui=FakeGUI([(picture("green","yellow"),"unknown" if "unknown" in case else "disabled")]);gui.cfg=cfg
                if case=="unchanged":gui.snapshot=lambda:picture()
                if case=="unstable":gui.snapshot=lambda:picture("green" if int(gui.now*4)%2 else "yellow","yellow")
                if "unknown" in case:gui.cfg["button_mode"]="uia" if case.startswith("uia") else "template"
                if case=="timeout":cfg["min_after_click"]=cfg["timeout_seconds"]+10
                with scope(d):
                    if code:
                        with self.assertRaises(StopRun):core.wait_ready(gui,cfg,previous,clock=gui.clock)
                    else:core.wait_ready(gui,cfg,previous,clock=gui.clock);d.finish(0)
                if code:
                    event=self.failed(d,code,"WAIT_NEW_VIEW")
                    metrics=event["metadata"]
                else:
                    self.assertEqual(d.data["terminal_outcome"],"SUCCESS")
                    metrics=next(e for e in self.events(d) if e["event"]=="WAIT_NEW_VIEW_OK")
                for key in ("poll_count","elapsed","change_detected","stable_detected","last_button_state","progress_difference","content_difference"):
                    self.assertIn(key,metrics)
                self.assertEqual(metrics["last_button_state"],"unknown" if "unknown" in case else "disabled")
                self.assertEqual(metrics["change_detected"],case!="unchanged")
                self.assertLess(len(self.events(d)),20)

    def test_partial_sendinput_and_preclick_guard_no_click_retry(self):
        for case in ("guard","partial"):
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                d=self.attempt(td);gui=core.WindowsGUI.__new__(core.WindowsGUI);gui.cfg=legacy_config()
                gui.guard=Mock(side_effect=RuntimeError("guard") if case=="guard" else None)
                gui.snapshot=lambda:picture();gui.button_state=lambda image:"enabled";gui.park=Mock();gui.user=Mock()
                gui.user.SendInput.side_effect=[1,1]
                with scope(d):
                    with self.assertRaises(StopRun):gui.click_next()
                self.failed(d,"NAVIGATION_PRECLICK_GUARD_FAILED" if case=="guard" else "NAVIGATION_CLICK_FAILED", "NEXT_PRECLICK_GUARD" if case=="guard" else "NEXT_CLICK")
                self.assertEqual(gui.user.SendInput.call_count,0 if case=="guard" else 2)
                if case=="partial":
                    self.assertEqual([call.args[0] for call in gui.user.SendInput.call_args_list],[2,1])
                    self.assertEqual(next(e for e in self.events(d) if e["event"]=="NEXT_CLICK_SENT")["inserted_events"],1)

    def test_changed_content_with_static_progress_is_visible_in_aggregate(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            d=self.attempt(td);cfg=legacy_config();cfg["progress_rect"]=[100,80,20,10]
            gui=FakeGUI([(picture("green","yellow"),"enabled")]);gui.cfg=cfg
            gui.transition_content_baseline=core.content_image(picture(),cfg)
            previous=core.progress_image(picture(),cfg)
            with scope(d):
                with self.assertRaises(StopRun):core.wait_ready(gui,cfg,previous,clock=gui.clock)
            event=self.failed(d,"VIEW_CHANGE_NOT_DETECTED","WAIT_NEW_VIEW")
            self.assertTrue(event["metadata"]["content_change_detected"])
            self.assertGreater(event["metadata"]["content_difference"],cfg["change_threshold"])
            self.assertEqual(event["metadata"]["progress_difference"],0)
            self.assertFalse(event["metadata"]["change_detected"])

    def test_real_target_guards_keep_specific_codes_and_exact_environment(self):
        cases=[("foreground","TARGET_FOCUS_LOST"),("window","TARGET_CHANGED"),("process","TARGET_CHANGED"),
               ("exe","TARGET_CHANGED"),("lifetime","TARGET_CHANGED"),("dpi","TARGET_ENVIRONMENT_CHANGED"),
               ("monitor","TARGET_ENVIRONMENT_CHANGED"),("bounds","TARGET_ENVIRONMENT_CHANGED"),
               ("title","TARGET_CHANGED"),("covered","TARGET_OCCLUDED")]
        for case,code in cases:
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                d=self.attempt(td);gui=core.WindowsGUI.__new__(core.WindowsGUI);gui.user=Mock()
                gui.cfg=config();gui.hwnd=123;gui.size=(320,240);gui.bound_identity=[1,2];gui.bound_exe="msedge.exe"
                gui.bound_environment=dict(dpi=96,monitor="main",window_bounds=[0,0,320,240]);gui.window_property="test-property"
                gui.initial_geometry=(0,0,320,240);gui.geometry=lambda:gui.initial_geometry
                gui.environment=lambda:dict(gui.bound_environment);gui.abort_check=lambda:None
                gui.process_identity=lambda:gui.bound_identity;gui.process_executable=lambda:gui.bound_exe;gui.title=lambda:"synthetic"
                gui.user.IsWindow.return_value=True;gui.user.IsWindowVisible.return_value=True;gui.user.IsIconic.return_value=False
                gui.user.GetPropW.return_value=1;gui.user.GetForegroundWindow.return_value=123
                gui.user.GetSystemMetrics.side_effect=lambda i:gui.size[i];gui.user.GetAncestor.return_value=123
                if case=="foreground":gui.user.GetForegroundWindow.return_value=124
                if case=="window":gui.user.IsWindow.return_value=False
                if case=="process":gui.process_identity=lambda:[1,3]
                if case=="exe":gui.process_executable=lambda:"replaced.exe"
                if case=="lifetime":gui.user.GetPropW.return_value=0
                if case in ("dpi","monitor","bounds"):
                    gui.environment=lambda:{**gui.bound_environment, {"dpi":"dpi","monitor":"monitor","bounds":"window_bounds"}[case]:None}
                if case=="title":gui.cfg["window_title_contains"]="private other book"
                if case=="covered":gui.user.GetAncestor.return_value=456
                with scope(d):
                    with self.assertRaises(StopRun):gui.guard()
                event=self.failed(d,code,"TARGET_GUARD");self.assertTrue(event["metadata"]["guard"])
                self.assertFalse(d.data["screenshot_requested"]);self.assertFalse(d.data["run_created"])

    def test_real_uia_and_template_unknown_preserve_sanitized_underlying_cause(self):
        for mode in ("uia","template"):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                d=self.attempt(td);gui=core.WindowsGUI.__new__(core.WindowsGUI);gui.cfg=legacy_config();gui.cfg["button_mode"]=mode
                gui.hwnd=123;gui.auto=Mock();gui.auto.ControlFromPoint.side_effect=OSError("UIA unavailable password=private https://private.invalid/book")
                gui.enabled=Image.new("RGB",(30,20),"black");gui.disabled=Image.new("RGB",(30,20),"white")
                with scope(d):self.assertEqual(core.read_button(gui,Image.new("RGB",(150,100),"gray")),"unknown")
                event=next(e for e in self.events(d) if e["event"]=="BUTTON_STATE_READ_OK")
                self.assertEqual(event["state"],"unknown");self.assertEqual(event["mode"],mode)
                if mode=="uia":
                    self.assertIn("UIA unavailable",event["cause"])
                    self.assertNotIn("private.invalid",event["cause"])
                    self.assertNotIn("password=private",event["cause"])

    def test_exact_selection_pixels_are_logged_without_image_content(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            d=self.attempt(td);im=Image.new("RGB",(20,20),"white");changed=im.copy();changed.putpixel((4,4),(254,255,255))
            with scope(d):
                with self.assertRaises(Exception):
                    with boundary("SELECTION_GUARD","PIXEL_GUARD_FAILED"):
                        assert_same_selection(im,changed,{"REGION_1":[0,0,10,10]})
            event=self.failed(d,"PIXEL_GUARD_FAILED","SELECTION_GUARD")
            self.assertEqual(event["metadata"],dict(region_number=1,difference_metric=1,threshold=0,compared_region_count=1))

    def test_button_prepare_and_export_failures_are_classified(self):
        for step,code in (("BUTTON_PREPARE","BUTTON_PREPARE_FAILED"),("EXPORT","EXPORT_FAILED")):
            with self.subTest(step=step),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                d=self.attempt(td)
                with scope(d):
                    with self.assertRaises(OSError):
                        with boundary(step,code):raise OSError("external dependency")
                event=self.failed(d,code,step)
                self.assertTrue(event["traceback"]);self.assertEqual(event["causes"][0]["exception_type"],"OSError")

    def test_public_zip_inputs_exclude_private_attempt_and_frame(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            root=Path(td);(root/"RectoFlow.exe").touch()
            d=self.attempt(root);d.first_frame(Image.new("RGB",(20,20),"blue"))
            self.assertEqual(list(public_bundle_members(root)),[root/"RectoFlow.exe"])
            internal=root/"_internal";internal.mkdir();(internal/"first-frame.png").touch()
            with self.assertRaises(RuntimeError):list(public_bundle_members(root))

    def test_hard_process_exit_keeps_actual_flushed_boundaries(self):
        program=r'''
import os,sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from PIL import Image
from unittest.mock import patch
import edge_capture as core
from calibration.diagnostics import Diagnostic,scope,checkpoint
root=Path(sys.argv[2]); stop=sys.argv[3]
d=Diagnostic(root,core.VERSION,"crash-test")
original=d.checkpoint
def emit(name,**values):
    original(name,**values)
    if name==stop:os._exit(17)
d.checkpoint=emit
with scope(d):
    if stop=="TARGET_BIND_OK":
        from unittest.mock import Mock
        gui=core.WindowsGUI.__new__(core.WindowsGUI);gui.cfg={};gui.user=Mock();gui.title=lambda:"synthetic"
        gui.activate_target=lambda:None;gui.guard=lambda **kw:None
        selected=dict(hwnd=123,ready=True,browser="Edge",identity=[1,2],exe="msedge.exe",environment=dict(dpi=96,monitor="main",window_bounds=[0,0,20,20]))
        with patch("calibration.window_picker.choose_window",return_value=selected),patch("calibration.window_picker.inspect_window",return_value=selected):gui.bind(check_config=False,check_calibration=False)
    if stop=="FIRST_SCREENSHOT_ACQUIRED":
        gui=core.WindowsGUI.__new__(core.WindowsGUI);gui.size=(20,20);gui.guard=lambda **kw:None
        with patch("PIL.ImageGrab.grab",return_value=Image.new("RGB",(20,20))):gui.snapshot()
    folder=core.publish_run(root/"runs",{"status":"RUNNING","pairs":[]})
    core.save_pair(folder,1,Image.new("RGB",(20,20)),{"regions":[[0,0,10,10]]})
raise AssertionError("hard exit did not occur")
'''
        for stop in ("TARGET_BIND_OK","FIRST_SCREENSHOT_ACQUIRED","INITIAL_MANIFEST_WRITE_OK","FIRST_CROP_OK"):
            with self.subTest(stop=stop),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                root=Path(td)
                result=subprocess.run([sys.executable,"-B","-c",program,str(Path(core.__file__).parent),str(root),stop],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,17,result.stderr)
                attempt=next((root/"data"/"diagnostics"/"attempts").iterdir())
                d=json.loads((attempt/"attempt.json").read_bytes());events=[json.loads(line) for line in (attempt/"events.jsonl").read_text().splitlines()]
                self.assertEqual(events[-1]["event"],stop);self.assertEqual(d["last_successful_checkpoint"],stop)
                self.assertIsNone(d["terminal_outcome"]);self.assertIsNone(d["exit_code"])
                self.assertNotIn("WORKFLOW_COMPLETE",[e["event"] for e in events])
                self.assertEqual(bool(list(root.glob("runs/run_*"))),stop=="FIRST_CROP_OK")
                self.assertEqual(bool(list(root.glob("runs/.pending-run_*/manifest.json"))),stop=="INITIAL_MANIFEST_WRITE_OK")


if __name__=="__main__":unittest.main()
