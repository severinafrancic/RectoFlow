"""Real wizard → diagnostic scope → GUI/CLI outcome, without book content."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from test_regions import config, SCRATCH
from calibration import calibration as wizard
from calibration.diagnostics import Diagnostic, scope
from calibration.geometry import CalibrationError
from calibration.regions import selection
import edge_capture as core
import rectoflow


class CausalityTests(unittest.TestCase):
    def invoke(self,root,technical=True,action="cancel",fallback="manual",retry=False):
        cfg=config(2);path=root/"config.json";path.write_text(json.dumps(cfg));raw=path.read_bytes()
        image=Image.new("RGB",(320,240),"white")
        gui=Mock(size=(320,240));gui.target_metadata.return_value={"selection_bounds":[0,0,320,240],"screen_size":[320,240]}
        diagnostic=Diagnostic(root,core.VERSION,"gui")
        choice={"mode":"dom" if technical else "manual","copied":technical,"payload":{}}
        result={"action":action,"rects":selection(cfg),"point":None,"paper":"A4","orientation":"portrait","navigation":"none"}
        error=CalibrationError("COORDINATE_TRANSFORM_FAILED","Sitzungsmarker fehlen oder sind mehrdeutig.")
        outcomes=[error,({"LEFT":cfg["regions"][0],"RIGHT":cfg["regions"][1]}, {"mapping":[1,1,0,0]})] if retry else error
        with scope(diagnostic),patch.object(wizard.tk,"Tk",return_value=Mock()), \
             patch.object(wizard,"choose_dom",return_value=choice) as choose, \
             patch.object(wizard,"suggestions",side_effect=outcomes), \
             patch.object(wizard,"fresh_image",return_value=image),patch.object(wizard,"clean_dom",return_value=image), \
             patch.object(wizard,"fallback_choice",return_value="retry" if retry else fallback), \
             patch.object(wizard,"RectanglePicker",return_value=Mock(show=Mock(return_value=result))) as editor:
            code=wizard.calibrate(gui,cfg,path,hashlib.sha256(raw).hexdigest(),core.validate)
            diagnostic.finish(code)
        if action=="cancel" or fallback=="cancel":self.assertEqual(path.read_bytes(),raw)
        return code,diagnostic,choose,editor

    def test_four_failure_outcomes_keep_exit2_and_primary_cause(self):
        cases=[(True,"cancel","cancel","USER_CANCELLED",2,True),
               (True,"save","manual","SUCCESS",0,False),
               (True,"cancel","manual","USER_CANCELLED",2,True),
               (False,"cancel","manual","USER_CANCELLED",2,False)]
        for technical,action,fallback,outcome,expected,primary in cases:
            with self.subTest(technical=technical,action=action,fallback=fallback),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                code,diag,_,editor=self.invoke(Path(td),technical,action,fallback)
                self.assertEqual(code,expected);self.assertEqual(diag.data["exit_code"],expected)
                self.assertEqual(diag.data["terminal_outcome"],outcome)
                self.assertEqual(bool(diag.data["primary_failure"]),primary)
                if primary:self.assertEqual(diag.data["primary_failure"]["code"],"COORDINATE_TRANSFORM_FAILED")
                if technical:self.assertEqual(diag.data["history"][0]["code"],"COORDINATE_TRANSFORM_FAILED")
                self.assertEqual(diag.needs_error_dialog(code),bool(expected and technical))
                if fallback=="cancel":editor.assert_not_called()
                if technical and action=="save":self.assertEqual(editor.call_count,2)
                stored=json.loads(diag.log_path.read_text().splitlines()[-1]);self.assertEqual(stored["history"],diag.data["history"])

    def test_technical_failure_without_fallback_exit2(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            diag=Diagnostic(td,core.VERSION,"gui")
            diag.phase("CALIBRATION")
            diag.failure(CalibrationError("COORDINATE_TRANSFORM_FAILED","unsafe mapping"));diag.finish(2)
            self.assertEqual(diag.data["terminal_outcome"],"TECHNICAL_FAILURE")
            self.assertEqual(diag.data["primary_failure"]["code"],"COORDINATE_TRANSFORM_FAILED")
            self.assertTrue(diag.needs_error_dialog(2))

    def test_retry_new_session_token_then_editor_success_retains_warning(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            code,diag,choose,editor=self.invoke(Path(td),True,"save",retry=True)
            self.assertEqual(code,0);self.assertEqual(choose.call_count,2)
            self.assertNotEqual(choose.call_args_list[0].args[1],choose.call_args_list[1].args[1])
            self.assertEqual(editor.call_count,2)
            self.assertIsNone(diag.data["primary_failure"])
            self.assertEqual(diag.data["history"][0]["kind"],"warning")

    def test_gui_pure_cancel_no_crash_and_technical_cancel_exactly_one_dialog(self):
        for technical in (False,True):
            with self.subTest(technical=technical),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                diag=Diagnostic(td,core.VERSION,"gui")
                if technical:diag.failure(CalibrationError("COORDINATE_TRANSFORM_FAILED","unsafe mapping"),recoverable=True)
                diag.failure(CalibrationError("CALIBRATION_CANCELLED","manual cancel"))
                with patch.object(sys,"argv",["rectoflow","--gui"]),patch.object(rectoflow,"Diagnostic",return_value=diag), \
                     patch.object(rectoflow,"main",side_effect=rectoflow.graphical_core),patch.object(core,"main",return_value=2), \
                     patch.object(rectoflow.tk,"Tk",return_value=Mock()),patch.object(rectoflow.messagebox,"showerror") as dialog:
                    self.assertEqual(rectoflow.entrypoint(),2)
                self.assertEqual(dialog.call_count,1 if technical else 0)
                if technical:
                    text=dialog.call_args.args[1];self.assertIn("unsafe mapping",text);self.assertIn("USER_CANCELLED",text)

    def test_escape_cancel_survives_fresh_image_wrapper_and_cli(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            diag=Diagnostic(td,core.VERSION,"cli");gui=Mock()
            error=core.UserCancelled("ESC")
            gui.activate_target.side_effect=error
            with self.assertRaises(core.UserCancelled):wizard.fresh_image(gui)
            with patch.object(sys,"argv",["rectoflow","--config","cancelled"]),patch.object(rectoflow,"Diagnostic",return_value=diag), \
                 patch.object(rectoflow,"main",side_effect=error),patch.object(rectoflow.messagebox,"showerror") as dialog:
                self.assertEqual(rectoflow.entrypoint(),2)
            self.assertEqual(diag.data["terminal_outcome"],"USER_CANCELLED");self.assertIsNone(diag.data["primary_failure"])
            dialog.assert_not_called()

    def test_same_exception_not_duplicated_by_nested_entrypoints(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            diag=Diagnostic(td,core.VERSION,"gui");error=ValueError("once")
            diag.failure(error);diag.failure(error);diag.finish(2)
            self.assertEqual(len(diag.data["history"]),1)
