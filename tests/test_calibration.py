import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import os
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
SCRATCH=Path(os.environ.get("EDGE_CAPTURE_TEST_TMP",str(ROOT/"test-work")))
SCRATCH.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT))
from calibration.geometry import *
from calibration.config_io import updated_config,atomic_update
from calibration.dom_picker import parse_payload,suggestions
from calibration.screenshot_picker import RectanglePicker
from calibration import calibration as wizard

spec=importlib.util.spec_from_file_location("edge",ROOT/"edge_capture.py")
edge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(edge)


def cfg():
    c=json.loads((ROOT/"config.json").read_text())
    c.pop("regions",None)  # legacy fixtures stay independent of the new default
    c.update(left_rect=[20,30,100,150],button_rect=[260,80,30,20],next_point=[275,90],park_point=[15,15],progress_rect=None)
    return c


def selections():
    return {"LEFT":[20,30,100,150],"RIGHT":[140,30,110,160],"NEXT":[260,80,30,20],"PROGRESS":None}


def target():
    return {"selection_bounds":[10,10,310,230],"screen_size":[320,240],"window_bounds":[10,10,310,230],"dpi":120,"monitor":{"primary":True,"device":"test","bounds":[0,0,320,240]},"hwnd":123,"pid":42,"process_created":11}


def payload(dpr=1):
    return {"schema":1,"token":"session","created_ms":time.time()*1000,"dpr":dpr,"viewport":[500,400],"scroll":[0,0],"visual_scale":1,
            "markers":[{"css_center":[36,84],"color":[239,17,131]}, {"css_center":[464,84],"color":[17,239,131]}, {"css_center":[36,364],"color":[131,17,239]}],
            "rects":{"LEFT":{"left":80,"top":120,"right":200,"bottom":300,"width":120,"height":180}}}


class GeometryTests(unittest.TestCase):
    def test_paper_fit_repeated_preview_is_idempotent(self):
        bounds=[0,0,2200,1800]
        for paper in PAPER_MM:
            for direction in ("portrait","landscape"):
                ratio=paper_ratio(paper,direction)
                for w in range(12,80):
                    for h in (17,33,77,99,801):
                        rect=fit_aspect([100,100,w,h],ratio,bounds)
                        self.assertEqual(rect,fit_aspect(rect,ratio,bounds))
        rect=fit_aspect([100,100,567,801],paper_ratio("A4","portrait"),bounds)
        self.assertEqual(rect,fit_aspect(rect,paper_ratio("A4","portrait"),bounds))

    def test_legacy_fallback_and_explicit_right(self):
        c=cfg()
        self.assertEqual(right_rect(c),[120,30,100,150])
        c["right_rect"]=[145,40,88,170]
        self.assertEqual(right_rect(c),[145,40,88,170])

    def test_center_and_next_invariant(self):
        self.assertEqual(center([20,30,9,11]),[24,35])
        with self.assertRaises(CalibrationError):
            validate_selection(selections(),[290,100],target()["selection_bounds"])

    def test_invalid_rectangles(self):
        for rect in ([1,2,0,10],[1,2,-1,10],[1,2,float("nan"),10],[True,2,10,10],[-1,2,10,10],[319,2,10,10],[1,2,10]):
            with self.subTest(rect=rect),self.assertRaises(CalibrationError):
                validate_rect(rect,[0,0,320,240])

    def test_identical_rejected_overlap_warned(self):
        r=selections()
        r["RIGHT"]=r["LEFT"][:]
        with self.assertRaises(CalibrationError):
            validate_selection(r,[275,90],target()["selection_bounds"])
        r["RIGHT"]=[30,40,100,150]
        self.assertTrue(validate_selection(r,[275,90],target()["selection_bounds"]))

    def test_small_next_rejected(self):
        r=selections()
        r["NEXT"]=[260,80,2,2]
        with self.assertRaises(CalibrationError):
            validate_selection(r,[260,80],target()["selection_bounds"])

    def test_move_clamped_to_bounds(self):
        self.assertEqual(move_rect([20,30,100,150],1000,-1000,[10,10,310,230]),[210,10,100,150])

    def test_resize_all_eight_handles(self):
        for h in ("n","s","e","w","nw","ne","sw","se"):
            r=resize_rect([20,30,100,150],h,7,9,[10,10,310,230])
            validate_rect(r,[10,10,310,230])
            self.assertNotEqual(r,[20,30,100,150])

    def test_new_rectangle_reverse_direction(self):
        self.assertEqual(new_rect([100,100],[30,20],[0,0,320,240]),[30,20,70,80])

    def test_canvas_offset_and_scaled_coordinates(self):
        tr=canvas_transform((1920,1080),(1000,1000))
        self.assertEqual(to_screen((tr[1]+100*tr[0],tr[2]+250*tr[0]),tr),[100,250])

    def test_a4_a3_letter_orientation(self):
        for p in PAPER_MM:
            for orientation in ("portrait","landscape"):
                ratio=paper_ratio(p,orientation)
                r=fit_aspect([20,30,200,190],ratio,[0,0,320,240])
                self.assertLess(abs(r[2]/r[3]-ratio),.015)
                validate_rect(r,[0,0,320,240])
        self.assertEqual(fit_aspect([20,30,200,190],None,[0,0,320,240]),[20,30,200,190])

    def test_a4_can_grow_from_each_side_and_corner(self):
        original=[250,250,140,198]
        for handle,dx,dy in (("e",20,0),("w",-20,0),("s",0,20),("n",0,-20),("ne",20,-20),("nw",-20,-20),("se",20,20),("sw",-20,20)):
            new=resize_aspect(original,handle,dx,dy,[0,0,1000,1000],210/297)
            self.assertGreater(new[2],original[2],handle)
            self.assertGreater(new[3],original[3],handle)
            self.assertLess(abs(new[2]/new[3]-210/297),.01)

    def test_a4_resize_clamped_at_screen_boundary(self):
        new=resize_aspect([250,250,140,198],"se",1000,1000,[0,0,600,600],210/297)
        validate_rect(new,[0,0,600,600])
        self.assertLess(abs(new[2]/new[3]-210/297),.01)

    def test_synthetic_css_dpi_zoom_nonmaximized(self):
        for dpr in (1,1.25,1.5,1.5625,2):
            css=[[36,84],[464,84],[36,364]]
            pixels=[[91+x*dpr,143+y*dpr] for x,y in css]
            mapping=measured_mapping(css,pixels,dpr)
            r=css_to_screen(payload()["rects"]["LEFT"],mapping,[500,400])
            self.assertEqual(r[0],math.floor(91+80*dpr))
            self.assertEqual(r[1],math.floor(143+120*dpr))

    def test_wrong_scale_rejected(self):
        with self.assertRaises(CalibrationError):
            measured_mapping([[0,0],[100,0],[0,100]],[[20,30],[220,30],[20,230]],1.25)

    def test_css_visible_clipping(self):
        r=css_to_screen({"left":-20,"top":-30,"width":100,"height":100},(1.5,1.5,80,120),[500,400])
        self.assertEqual(r,[80,120,120,105])


class ConfigTests(unittest.TestCase):
    def test_other_settings_preserved_and_right_written(self):
        original=cfg()
        original["custom"]={"future":7}
        changed=updated_config(original,selections(),[275,90],target(),None)
        self.assertEqual(changed["right_rect"],[140,30,110,160])
        self.assertEqual(changed["custom"],original["custom"])
        self.assertNotIn("right_rect",original)

    def test_atomic_write_and_temp_cleanup(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            path=Path(tmp)/"config.json"
            path.write_text('{"old":1}')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            atomic_update(path,{"new":2},digest,lambda c:None)
            self.assertEqual(json.loads(path.read_bytes()),{"new":2})
            self.assertEqual(list(Path(tmp).glob("*.tmp")),[])

    def test_replace_failure_keeps_old_config(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            path=Path(tmp)/"config.json"
            path.write_text('{"old":1}')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with patch("calibration.config_io.os.replace",side_effect=PermissionError("blocked")),self.assertRaises(CalibrationError):
                atomic_update(path,{"new":2},digest,lambda c:None)
            self.assertEqual(json.loads(path.read_bytes()),{"old":1})
            self.assertEqual(list(Path(tmp).glob("*.tmp")),[])

    def test_conflict_never_overwrites_external_edit(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            path=Path(tmp)/"config.json"
            path.write_text('{"external":1}')
            with self.assertRaises(CalibrationError):
                atomic_update(path,{"new":2},"old-digest",lambda c:None)
            self.assertEqual(json.loads(path.read_bytes()),{"external":1})

    def test_invalid_candidate_cannot_replace(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            path=Path(tmp)/"config.json"
            path.write_text('{"old":1}')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(CalibrationError):
                atomic_update(path,{"new":float("nan")},digest,lambda c:None)
            self.assertEqual(json.loads(path.read_bytes()),{"old":1})


class DOMTests(unittest.TestCase):
    def test_marker_mapping_100_125_150(self):
        for dpr in (1,1.25,1.5):
            p=payload(dpr)
            image=Image.new("RGB",(1200,1000),"white")
            draw=ImageDraw.Draw(image)
            for marker in p["markers"]:
                x,y=marker["css_center"]
                l,t=round(100+x*dpr-10*dpr),round(150+y*dpr-10*dpr)
                r,b=round(100+x*dpr+10*dpr),round(150+y*dpr+10*dpr)
                draw.rectangle([l,t,r-1,b-1],fill=tuple(marker["color"]))
            proposed,metadata=suggestions(p,image,[0,0,1200,1000])
            self.assertLessEqual(abs(proposed["LEFT"][0]-(100+80*dpr)),1)
            self.assertEqual(metadata["dpr"],dpr)

    def test_missing_markers_fail(self):
        with self.assertRaises(CalibrationError):
            suggestions(payload(),Image.new("RGB",(1200,1000),"white"),[0,0,1200,1000])

    def test_wrong_token_and_expired_payload(self):
        with self.assertRaises(CalibrationError):
            parse_payload(json.dumps(payload()),"other")
        p=payload()
        p["created_ms"]-=181000
        with self.assertRaises(CalibrationError):
            parse_payload(json.dumps(p),"session")

    def test_payload_does_not_keep_page_contents(self):
        p=payload()
        p["cookies"]="private"
        p["rects"]["LEFT"]["text"]="private"
        cleaned=parse_payload(json.dumps(p),"session")
        self.assertNotIn("private",json.dumps(cleaned))

    def test_broken_dom_coordinates_fail(self):
        p=payload()
        p["rects"]["LEFT"]["right"]=float("nan")
        with self.assertRaises(CalibrationError):
            parse_payload(json.dumps(p),"session")


class UITests(unittest.TestCase):
    def picker(self):
        p=RectanglePicker.__new__(RectanglePicker)
        p.rects=selections()
        p.point=[275,90]
        p.bounds=target()["selection_bounds"]
        p.paper=Mock(get=lambda:"A4")
        p.orientation=Mock(get=lambda:"portrait")
        p.window=Mock()
        p.render=Mock()
        p.selected="PROGRESS"
        return p

    def test_cancel_and_recalibrate_states(self):
        p=self.picker()
        p.cancel()
        self.assertEqual(p.result,{"action":"cancel"})
        p.recalibrate()
        self.assertEqual(p.result,{"action":"recalibrate"})

    def test_save_requires_confirmation(self):
        p=self.picker()
        with patch("calibration.screenshot_picker.messagebox.askyesno",return_value=False):
            p.accept()
            p.window.destroy.assert_not_called()
        with patch("calibration.screenshot_picker.messagebox.askyesno",return_value=True):
            p.accept()
            self.assertEqual(p.result["action"],"save")
            self.assertIsNone(p.result["rects"]["PROGRESS"])

    def test_progress_delete_is_optional(self):
        p=self.picker()
        p.rects["PROGRESS"]=[10,10,20,10]
        p.delete()
        self.assertIsNone(p.rects["PROGRESS"])

    def test_manual_point_only_inside_next(self):
        p=self.picker()
        p.mode,p.selected,p.transform="point","NEXT",(1,0,0)
        p.press(Mock(x=200,y=200))
        self.assertEqual(p.point,[275,90])
        p.press(Mock(x=270,y=85))
        self.assertEqual(p.point,[270,85])


class CaptureIntegrationTests(unittest.TestCase):
    def test_distinct_sizes_and_a4_pdf(self):
        c=cfg()
        c.update(right_rect=[150,40,80,170],paper_format="A4",paper_orientation="portrait")
        edge.validate(c,(320,240))
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            folder=Path(tmp)
            pair=edge.save_pair(folder,1,Image.new("RGB",(320,240),"white"),c)
            with Image.open(folder/"000001_right.png") as im:
                self.assertEqual(im.size,(80,170))
            manifest={"config":c,"pairs":[pair]}
            edge.build_pdf(folder,manifest,folder/"a4.pdf")
            pages=PdfReader(folder/"a4.pdf").pages
            self.assertEqual(len(pages),2)
            self.assertAlmostEqual(float(pages[0].mediabox.width),210*72/25.4,places=4)
            self.assertAlmostEqual(float(pages[0].mediabox.height),297*72/25.4,places=4)
            c["pdf_layout"]="spread"
            c["paper_orientation"]="landscape"
            edge.build_pdf(folder,manifest,folder/"spread.pdf")
            self.assertEqual(len(PdfReader(folder/"spread.pdf").pages),1)

    def test_gap_pixels_do_not_fake_progress(self):
        c=cfg()
        c["right_rect"]=[160,30,100,150]
        a=Image.new("RGB",(320,240),"white")
        b=a.copy()
        b.paste("red",(125,50,150,100))
        self.assertEqual(edge.difference(edge.content_image(a,c),edge.content_image(b,c)),0)

    def test_interactive_cli_routes_without_capture_loop(self):
        fake=Mock()
        with patch.object(edge,"WindowsGUI",return_value=fake),patch("calibration.calibration.calibrate",return_value=0) as calibrate,patch.object(edge,"run_capture",side_effect=AssertionError("No capture")),patch.object(sys,"argv",["edge_capture.py","--calibrate"]):
            self.assertEqual(edge.main(),0)
            calibrate.assert_called_once()

    def test_stored_geometry_or_dpi_change_requires_recalibration(self):
        # Production guard is exercised with synthetic native API outputs.
        gui=edge.WindowsGUI.__new__(edge.WindowsGUI)
        gui.hwnd=123
        gui.cfg=cfg()
        gui.size=(320,240)
        gui.initial_geometry=(10,10,310,230)
        gui.bound_identity=[42,11]
        gui.bound_environment={"dpi":120}
        gui.abort_check=lambda:None
        gui.process_identity=lambda:[42,11]
        gui.geometry=lambda:(10,10,310,230)
        gui.environment=lambda:{"dpi":144}
        gui.user=Mock()
        gui.user.GetForegroundWindow.return_value=123
        gui.user.GetSystemMetrics.side_effect=[320,240]
        with self.assertRaises(edge.StopRun):
            gui.guard()

    def test_handle_reuse_is_not_trusted(self):
        gui=edge.WindowsGUI.__new__(edge.WindowsGUI)
        gui.hwnd=123
        gui.bound_identity=[42,11]
        gui.process_identity=lambda:[42,12]
        gui.user=Mock()
        gui.user.IsWindow.return_value=True
        with self.assertRaises(edge.StopRun):
            gui.activate_target()
        gui.user.SetForegroundWindow.assert_not_called()


class WizardTests(unittest.TestCase):
    def confirmation(self,images,action="save"):
        c=cfg()
        c.update(right_rect=selections()["RIGHT"],paper_format="A4",paper_orientation="portrait")
        result={"action":action,"rects":selections(),"point":c["next_point"],"paper":"A4","orientation":"portrait"}
        gui=Mock()
        gui.target_metadata.return_value=target()
        with patch.object(wizard.tk,"Tk",return_value=Mock()),patch.object(wizard,"fresh_image",side_effect=images),patch.object(wizard,"RectanglePicker",return_value=Mock(show=Mock(return_value=result))):
            return wizard.confirm_capture(gui,c)

    def test_changed_pixels_after_start_confirmation_abort(self):
        before=Image.new("RGB",(320,240),"white")
        for name,rect in selections().items():
            if rect:
                after=before.copy()
                x,y,w,h=rect
                after.paste("black",(x,y,x+w,y+h))
                with self.subTest(region=name),self.assertRaises(CalibrationError) as error:
                    self.confirmation([before,after])
                self.assertEqual(error.exception.code,"SCREENSHOT_FAILED")

    def test_unchanged_start_returns_confirmed_pixels(self):
        image=Image.new("RGB",(320,240),"white")
        self.assertIs(self.confirmation([image,image]),image)

    def test_start_cancel_does_not_read_second_snapshot(self):
        with self.assertRaises(CalibrationError) as error:
            self.confirmation([Image.new("RGB",(320,240),"white")],"cancel")
        self.assertEqual(error.exception.code,"CALIBRATION_CANCELLED")

    def test_changed_first_capture_aborts_before_save_or_click(self):
        c=cfg()
        before=Image.new("RGB",(320,240),"white")
        after=before.copy()
        after.paste("black",(20,30,120,180))
        gui=Mock()
        manifest={"pairs":[]}
        with patch.object(edge,"wait_ready",return_value=(after,"enabled",after)),patch.object(edge,"save_pair") as save:
            with self.assertRaises(CalibrationError):
                edge.run_capture(gui,c,Path("unused"),manifest,confirmed_image=before)
            save.assert_not_called()
            gui.click_next.assert_not_called()
        self.assertEqual(manifest["pairs"],[])

    def test_first_capture_saves_confirmed_pair_in_order(self):
        c=cfg()
        image=Image.new("RGB",(320,240),"white")
        image.paste("red",(20,30,120,180))
        gui=Mock()
        manifest={"pairs":[]}
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp,patch.object(edge,"wait_ready",return_value=(image,"disabled",image)):
            edge.run_capture(gui,c,Path(tmp),manifest,confirmed_image=image.copy())
            self.assertEqual([r["file"] for r in manifest["pairs"][0]["images"]],["000001_left.png","000001_right.png"])
            with Image.open(Path(tmp)/"000001_left.png") as saved:
                self.assertEqual(saved.getpixel((0,0)),(255,0,0))
            gui.click_next.assert_not_called()

    def test_screenshot_failure_has_correct_code(self):
        gui=edge.WindowsGUI.__new__(edge.WindowsGUI)
        gui.size=(320,240)
        gui.guard=Mock()
        with patch("PIL.ImageGrab.grab",side_effect=OSError("capture unavailable")):
            with self.assertRaises(edge.StopRun) as error:gui.snapshot()
        self.assertIn("SCREENSHOT_FAILED",str(error.exception))
        with patch.object(gui,"activate_target"),patch.object(gui,"pause"):
            with patch("PIL.ImageGrab.grab",side_effect=OSError("capture unavailable")):
                with self.assertRaises(CalibrationError) as error:wizard.fresh_image(gui)
        self.assertEqual(error.exception.code,"SCREENSHOT_FAILED")

    def test_dom_cleanup_ignores_cancel_but_checks_pinned_target(self):
        gui=edge.WindowsGUI.__new__(edge.WindowsGUI)
        gui.hwnd=123
        gui.cfg=cfg()
        gui.size=(320,240)
        gui.initial_geometry=(10,10,310,230)
        gui.bound_identity=[42,11]
        gui.bound_environment={"dpi":120}
        gui.abort_check=Mock(side_effect=edge.StopRun("ESC"))
        gui.process_identity=lambda:[42,11]
        gui.geometry=lambda:(10,10,310,230)
        gui.environment=lambda:{"dpi":120}
        gui.user=Mock()
        gui.user.IsWindow.return_value=True
        gui.user.GetForegroundWindow.return_value=123
        gui.user.GetSystemMetrics.side_effect=lambda i:gui.size[i]
        with patch("PIL.ImageGrab.grab",return_value=Image.new("RGB",(320,240),"white")),patch.object(edge.time,"sleep"):
            wizard.clean_dom(gui)
        gui.abort_check.assert_not_called()
        self.assertEqual(gui.user.keybd_event.call_count,2)
        gui.user.keybd_event.reset_mock()
        gui.process_identity=lambda:[42,12]
        with self.assertRaises(edge.StopRun):wizard.clean_dom(gui)
        gui.user.keybd_event.assert_not_called()

    def run_wizard(self,actions,dom_failure=False):
        original=cfg()
        original["custom_future_setting"]={"preserve":True}
        r=selections()
        result={"action":"save","rects":r,"point":[275,90],"paper":"A4","orientation":"portrait"}
        picks=[Mock(show=Mock(return_value=result if a=="save" else {"action":a})) for a in actions]
        fake_gui=Mock()
        fake_gui.size=(320,240)
        fake_gui.target_metadata.return_value=target()
        fake_root=Mock()
        fake_root.clipboard_get.return_value="old clipboard"
        choice={"mode":"dom" if dom_failure else "manual","copied":dom_failure,"payload":payload()}
        image=Image.new("RGB",(320,240),"white")
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            path=Path(tmp)/"config.json"
            path.write_text(json.dumps(original))
            before=path.read_bytes()
            with patch.object(wizard.tk,"Tk",return_value=fake_root),patch.object(wizard,"choose_dom",return_value=choice),patch.object(wizard,"fresh_image",return_value=image),patch.object(wizard,"clean_dom",return_value=image),patch.object(wizard,"RectanglePicker",side_effect=picks) as picker,patch.object(wizard,"suggestions",side_effect=CalibrationError("COORDINATE_TRANSFORM_FAILED","failed")),patch.object(wizard.messagebox,"showwarning"):
                status=wizard.calibrate(fake_gui,original,path,hashlib.sha256(before).hexdigest(),edge.validate)
            return status,before,path.read_bytes(),picker.call_count

    def test_cancel_keeps_config_byte_identical(self):
        status,before,after,count=self.run_wizard(["cancel"])
        self.assertEqual(status,2)
        self.assertEqual(before,after)

    def test_final_cancel_keeps_config_byte_identical(self):
        status,before,after,count=self.run_wizard(["save","cancel"])
        self.assertEqual(status,2)
        self.assertEqual(before,after)

    def test_save_preserves_extra_fields_and_adds_right_and_a4(self):
        status,before,after,count=self.run_wizard(["save","save"])
        self.assertEqual(status,0)
        c=json.loads(after)
        self.assertEqual(c["custom_future_setting"],{"preserve":True})
        self.assertEqual(c["right_rect"],selections()["RIGHT"])
        self.assertEqual(c["paper_format"],"A4")
        self.assertTrue(c["calibration"]["requires_visual_confirmation"])

    def test_recalibrate_repeats_without_early_write(self):
        status,before,after,count=self.run_wizard(["save","recalibrate","save","save"])
        self.assertEqual(status,0)
        self.assertEqual(count,4)

    def test_dom_failure_still_reaches_manual_picker_and_saves(self):
        status,before,after,count=self.run_wizard(["save","save"],dom_failure=True)
        self.assertEqual(status,0)
        self.assertEqual(count,2)
        self.assertIsNone(json.loads(after)["calibration"]["dom"])


if __name__=="__main__":
    unittest.main(verbosity=2)
