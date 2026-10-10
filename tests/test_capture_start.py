"""Capture publication and graphical workflow errors across real persistence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from test_regions import config, SCRATCH
import edge_capture as core
import rectoflow
from calibration.diagnostics import Diagnostic, scope
from calibration.geometry import CalibrationError


class StartTests(unittest.TestCase):
    def invoke(self, root, cfg=None, confirmation=None, capture=None):
        cfg = cfg or config()
        cfg.update(output_dir="captures", confirm_pdf_export=False)
        path = root / "config.json"
        path.write_text(json.dumps(cfg))
        gui = Mock(size=(320,240), template_bytes={})
        gui.title.return_value = "PRIVATE DOCUMENT TITLE"
        image = Image.new("RGB", (320,240), "white")
        def confirm(*args):
            self.assertEqual(list((root / "captures").glob("run_*")), [])
            if isinstance(confirmation, BaseException):
                raise confirmation
            return image
        diagnostic = Diagnostic(root, core.VERSION, "test")
        with patch.object(sys, "argv", ["rectoflow", "--config", str(path)]), \
             patch.object(core, "WindowsGUI", return_value=gui), \
             patch("calibration.calibration.confirm_capture", side_effect=confirm) as confirm_mock, \
             patch.object(core, "wait_ready", return_value=(image,"disabled",image)), \
             patch("calibration.exports.execute_plan", return_value="test.pdf"):
            if capture:
                with patch.object(core, "run_capture", side_effect=capture):
                    result = core.main(diagnostic)
            else:
                result = core.main(diagnostic)
        return result, diagnostic, confirm_mock

    def test_success_publishes_manifest_then_capture(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            root = Path(td)
            code, diagnostic, confirm = self.invoke(root)
            self.assertEqual(code, 0)
            confirm.assert_called_once()
            folders = list((root/"captures").glob("run_*"))
            self.assertEqual(len(folders), 1)
            manifest = json.loads((folders[0]/"manifest.json").read_bytes())
            self.assertEqual(manifest["status"], "COMPLETE")
            self.assertEqual(len(manifest["pairs"]), 1)
            self.assertEqual(diagnostic.data["capture_count"], 1)

    def test_cancel_and_confirmation_exception_create_no_run(self):
        for error in (CalibrationError("CALIBRATION_CANCELLED", "cancel"), RuntimeError("confirmation failed")):
            with self.subTest(error=error), tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                root = Path(td)
                with self.assertRaises(type(error)):
                    self.invoke(root, confirmation=error)
                self.assertFalse((root/"captures").exists())

    def test_legacy_without_confirmation_keeps_existing_ux(self):
        cfg=config(2)
        regions=cfg.pop("regions")
        cfg.update(left_rect=regions[0], right_rect=regions[1])
        cfg.pop("calibration", None)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            code, _, confirm = self.invoke(Path(td), cfg)
            self.assertEqual(code, 0)
            confirm.assert_not_called()

    def test_legacy_explicit_confirmation_remains_required(self):
        cfg=config(2); regions=cfg.pop("regions")
        cfg.update(left_rect=regions[0],right_rect=regions[1],calibration={"requires_visual_confirmation":True})
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            code, _, confirm=self.invoke(Path(td),cfg)
            self.assertEqual(code,0);confirm.assert_called_once()

    def test_mkdir_manifest_and_publish_failure_never_leave_normal_empty_run(self):
        for operation in ("mkdir", "manifest", "rename"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                root=Path(td); old=root/"run_existing";old.mkdir();(old/"keep").write_text("keep")
                diagnostic=Diagnostic(root,core.VERSION,"test")
                target = "pathlib.Path.mkdir" if operation=="mkdir" else "edge_capture.write_json" if operation=="manifest" else "edge_capture.os.rename"
                with scope(diagnostic), patch(target,side_effect=OSError(operation)):
                    with self.assertRaises(OSError):core.publish_run(root,{"status":"RUNNING"})
                self.assertEqual(list(root.glob("run_*")),[old])
                self.assertEqual((old/"keep").read_text(),"keep")

    def test_first_capture_failure_preserves_stopped_manifest(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            root=Path(td)
            code, diagnostic, _=self.invoke(root,capture=OSError("first capture"))
            self.assertEqual(code,2)
            folder=next((root/"captures").glob("run_*"))
            manifest=json.loads((folder/"manifest.json").read_bytes())
            self.assertEqual(manifest["status"],"STOPPED")
            self.assertEqual(manifest["pairs"],[])
            self.assertEqual(diagnostic.data["failure_phase"],"FIRST_CAPTURE")

    def test_failure_after_committed_capture_preserves_images(self):
        def fail(gui,cfg,folder,manifest,**kwargs):
            core.phase("FIRST_CAPTURE")
            manifest["pairs"].append(core.save_pair(folder,1,Image.new("RGB",(320,240),"white"),cfg))
            core.write_json(folder/"manifest.json",manifest)
            core.phase("CAPTURE_LOOP",capture_count=1)
            raise OSError("later capture")
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            root=Path(td);code, diagnostic, _=self.invoke(root,capture=fail)
            self.assertEqual(code,2)
            folder=next((root/"captures").glob("run_*"))
            manifest=json.loads((folder/"manifest.json").read_bytes())
            self.assertEqual(manifest["status"],"STOPPED")
            self.assertEqual(len(manifest["pairs"]),1)
            self.assertTrue(list(folder.glob("*.png")))
            self.assertEqual(diagnostic.data["failure_phase"],"CAPTURE_LOOP")


class GraphicalTests(unittest.TestCase):
    def test_zero_nonzero_details_exception_and_one_dialog(self):
        for outcome, detail in ((0,None),(2,"original failure"),(2,None),(ValueError("exception"),None)):
            with self.subTest(outcome=outcome,detail=detail),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                diagnostic=Diagnostic(td,core.VERSION,"gui")
                if detail:diagnostic.failure(ValueError(detail))
                def main():
                    # Launcher has already destroyed its original root.
                    return rectoflow.graphical_core()
                kwargs={"side_effect":outcome} if isinstance(outcome,Exception) else {"return_value":outcome}
                with patch.object(sys,"argv",["rectoflow","--gui"]), \
                     patch.object(rectoflow,"Diagnostic",return_value=diagnostic), \
                     patch.object(rectoflow,"main",side_effect=main), \
                     patch.object(core,"main",**kwargs), \
                     patch.object(rectoflow.tk,"Tk",return_value=Mock()), \
                     patch.object(rectoflow.messagebox,"showerror") as dialog:
                    code=rectoflow.entrypoint()
                self.assertEqual(code,0 if outcome==0 else 2)
                self.assertEqual(dialog.call_count,0 if code==0 else 1)
                if code:
                    text=dialog.call_args.args[1]
                    for key in ("Returncode: 2","Phase:","Diagnose-ID:","Logpfad:"):self.assertIn(key,text)
                    self.assertIn(detail or ("exception" if isinstance(outcome,Exception) else "Keine naeheren Fehlerdetails"),text)

    def test_log_fallback_and_total_failure_do_not_hide_error(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            root=Path(td);blocked=root/"blocked";blocked.write_text("file")
            diagnostic=Diagnostic(blocked,core.VERSION,"gui")
            with patch("calibration.diagnostics.tempfile.gettempdir",return_value=str(root/"temp")):
                diagnostic.failure(ValueError("original"))
            self.assertIn("temp",str(diagnostic.log_path))
            diagnostic=Diagnostic(root,core.VERSION,"gui")
            with patch.object(Path,"open",side_effect=OSError("denied")):
                diagnostic.failure(ValueError("original"));diagnostic.finish(2)
            self.assertIsNone(diagnostic.log_path)
            self.assertIn("original",diagnostic.dialog_text(2))

    def test_private_strings_and_source_lines_are_not_logged(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            diagnostic=Diagnostic(td,core.VERSION,"gui")
            diagnostic.private_values.add("PRIVATE TITLE")
            try:raise ValueError("PRIVATE TITLE https://private.example/book password=secret")
            except ValueError as error:diagnostic.failure(error)
            text=diagnostic.log_path.read_text()
            for private in ("PRIVATE TITLE","private.example","secret","raise ValueError"):
                self.assertNotIn(private,text)
            self.assertTrue(diagnostic.data["traceback"])

    def test_cli_nonzero_and_exception_never_open_dialog(self):
        with patch.object(sys,"argv",["rectoflow","--rebuild","missing"]), \
             patch.object(rectoflow.messagebox,"showerror") as dialog:
            for outcome in (2,ValueError("CLI")):
                kwargs={"side_effect":outcome} if isinstance(outcome,Exception) else {"return_value":outcome}
                with patch.object(core,"main",**kwargs):self.assertEqual(rectoflow.entrypoint(),2)
            dialog.assert_not_called()
