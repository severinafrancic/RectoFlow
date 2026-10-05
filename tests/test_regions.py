"""One-to-many producer/consumer and browser/export regression coverage."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

from PIL import Image
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import edge_capture as core
from calibration.regions import capture_rects,selection,browser_name,capture_names,image_names
from calibration.geometry import CalibrationError,validate_selection,PAPER_MM,assert_same_selection
from calibration.config_io import updated_config
from calibration.screenshot_picker import RectanglePicker
from calibration.pdf_export import paper_preview,preview_images
from calibration import calibration as wizard

SCRATCH=Path(os.environ.get("EDGE_CAPTURE_TEST_TMP",str(ROOT/"test-work")))
SCRATCH.mkdir(parents=True,exist_ok=True)


def config(count=1,mode="none"):
    c=json.loads((ROOT/"config.json").read_text())
    c.update(regions=[[10+i*20,30,15,40+i] for i in range(count)],navigation_mode=mode,
             button_rect=None if mode!="next_button" else [270,50,25,20],next_point=None if mode!="next_button" else [280,60],
             progress_rect=None,park_point=[5,5],paper_format="A4",paper_orientation="portrait")
    return c


class RegionTests(unittest.TestCase):
    def test_start_confirmation_binds_order_before_second_snapshot(self):
        for count in (2,5):
            c=config(count)
            rects=selection(c)
            names=capture_names(rects)
            image=Image.new("RGB",(320,240),"white")
            gui=Mock()
            gui.target_metadata.return_value={"selection_bounds":[0,0,320,240]}
            for changed in (False,True):
                order=list(reversed(names)) if changed else names
                returned={name:copy.deepcopy(rects[name]) for name in order+["NEXT","PROGRESS"]}
                self.assertEqual(returned,rects)  # geometry equality cannot bind order
                result={"action":"save","rects":returned,"point":c["next_point"],"paper":"A4",
                        "orientation":"portrait","navigation":"none"}
                with self.subTest(count=count,reordered=changed),patch.object(wizard.tk,"Tk",return_value=Mock()),patch.object(wizard,"fresh_image",return_value=image) as fresh,patch.object(wizard,"RectanglePicker",return_value=Mock(show=Mock(return_value=result))):
                    if changed:
                        with self.assertRaises(CalibrationError) as error:wizard.confirm_capture(gui,c)
                        self.assertEqual(error.exception.code,"INVALID_RECTANGLE")
                        self.assertEqual(fresh.call_count,1)
                    else:
                        self.assertIs(wizard.confirm_capture(gui,c),image)
                        self.assertEqual(fresh.call_count,2)

    def test_one_two_twelve_regions_capture_pdf_order(self):
        for count in (1,2,12):
            c=config(count)
            core.validate(c,(320,240))
            image=Image.new("RGB",(320,240),"white")
            colors=[(i*17%255,80,100) for i in range(count)]
            for r,color in zip(c["regions"],colors):image.paste(color,core.box(r))
            with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                folder=Path(td)
                record=core.save_pair(folder,1,image,c)
                self.assertEqual([e["file"] for e in record["images"]],image_names(c,1))
                for entry,r,color in zip(record["images"],c["regions"],colors):
                    with Image.open(folder/entry["file"]) as saved:
                        self.assertEqual(saved.size,tuple(r[2:]))
                        self.assertEqual(saved.getpixel((0,0)),color)
                manifest={"pairs":[record],"config":c}
                core.build_pdf(folder,manifest,folder/"separate.pdf")
                self.assertEqual(len(PdfReader(folder/"separate.pdf").pages),count)
                c["pdf_layout"]="spread"
                core.build_pdf(folder,manifest,folder/"spread.pdf")
                self.assertEqual(len(PdfReader(folder/"spread.pdf").pages),1)

    def test_regions_authoritative_over_stale_legacy_fields(self):
        c=config(1)
        c["left_rect"]=[9000,9000,800,800]
        self.assertEqual(capture_rects(c),c["regions"])
        core.validate(c,(320,240))

    def test_empty_duplicate_invalid_region_rejected(self):
        for regions in ([],None,[[1,1,0,10]],[[10,10,10,10]]*2):
            with self.subTest(regions=regions),self.assertRaises(ValueError):
                c=config();c["regions"]=regions;core.validate(c,(320,240))

    def test_content_gap_does_not_count_as_progress_for_many(self):
        c=config(3)
        a=Image.new("RGB",(320,240),"white")
        b=a.copy();b.putpixel((27,40),(255,0,0))
        self.assertEqual(core.difference(core.content_image(a,c),core.content_image(b,c)),0)
        b.putpixel((55,40),(0,0,0))
        self.assertGreater(core.difference(core.content_image(a,c),core.content_image(b,c)),0)

    def test_one_region_single_shot_no_button_no_click(self):
        c=config(1,"none")
        gui=Mock();manifest={"pairs":[]}
        image=Image.new("RGB",(320,240),"white")
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td,patch.object(core,"wait_ready",return_value=(image,"disabled",image)):
            core.run_capture(gui,c,Path(td),manifest,confirmed_image=image)
        self.assertEqual(len(manifest["pairs"]),1)
        gui.click_next.assert_not_called()

    def test_manual_multiple_views_no_automatic_click(self):
        c=config(3,"manual")
        gui=Mock();gui.manual_transition.side_effect=[True,False]
        image=Image.new("RGB",(320,240),"white")
        manifest={"pairs":[]}
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td,patch.object(core,"wait_ready",return_value=(image,"manual",image)):
            core.run_capture(gui,c,Path(td),manifest)
        self.assertEqual(len(manifest["pairs"]),2)
        gui.click_next.assert_not_called()

    def test_next_mode_requires_button_point_and_unknown_cannot_finish(self):
        c=config(1,"next_button");c["button_rect"]=None
        with self.assertRaises(ValueError):core.validate(c,(320,240))
        gui=core.WindowsGUI.__new__(core.WindowsGUI)
        gui.cfg=config(1,"manual")
        with self.assertRaises(core.StopRun):gui.click_next()

    def test_modern_config_preserves_order_and_unknown_fields(self):
        c=config(2);c["future"]={"keep":True}
        rects=selection(c)
        ordered={"REGION_002":rects["REGION_002"],"REGION_001":rects["REGION_001"],"NEXT":None,"PROGRESS":None}
        target={"selection_bounds":[0,0,320,240],"screen_size":[320,240]}
        updated=updated_config(c,ordered,None,target,None,"none")
        self.assertEqual(updated["regions"],list(reversed(c["regions"])))
        self.assertEqual(updated["future"],c["future"])
        self.assertTrue(updated["confirm_pdf_export"])

    def test_selector_add_delete_reorder_including_legacy_to_single(self):
        p=RectanglePicker.__new__(RectanglePicker)
        p.rects={"LEFT":[10,30,15,40],"RIGHT":[30,30,15,40],"NEXT":None,"PROGRESS":None}
        p.selected="RIGHT";p.render=Mock()
        p.delete()
        self.assertEqual(capture_names(p.rects),["REGION_001"])
        p.add_region()
        p.rects[p.selected]=[50,30,15,40]
        p.reorder(-1)
        self.assertEqual(capture_names(p.rects)[0],p.selected)
        self.assertTrue(validate_selection(p.rects,None,[0,0,320,240],"none") is False)

    def test_confirmation_checks_all_regions(self):
        c=config(12)
        a=Image.new("RGB",(320,240),"white")
        b=a.copy();b.putpixel((c["regions"][-1][0],30),(0,0,0))
        with self.assertRaises(CalibrationError):assert_same_selection(a,b,selection(c))

    def test_browser_executable_allowlist_four_and_mismatch(self):
        for exe,name in (("msedge.exe","Edge"),("chrome.exe","Chrome"),("brave.exe","Brave"),("firefox.exe","Firefox")):
            self.assertEqual(browser_name("C:\\Browser\\"+exe),name)
            self.assertEqual(browser_name("C:\\Browser\\"+exe.upper(),name),name)
        with self.assertRaises(ValueError):browser_name("notepad.exe")
        with self.assertRaises(ValueError):browser_name("chrome.exe","Firefox")

    def test_end_paper_export_changes_dimensions_without_mutating_capture(self):
        c=config(3)
        image=Image.new("RGB",(320,240),"white")
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);record=core.save_pair(folder,1,image,c)
            original={"status":"COMPLETE","pairs":[record],"config":c}
            bytes_before=json.dumps(original,sort_keys=True)
            for paper in ("A4","A5","A3","A6","Letter"):
                for direction in ("portrait","landscape"):
                    candidate=copy.deepcopy(original)
                    candidate["config"].update(paper_format=paper,paper_orientation=direction)
                    path=folder/(paper+direction+".pdf")
                    core.build_pdf(folder,candidate,path)
                    w,h=PAPER_MM[paper]
                    if direction=="landscape":w,h=h,w
                    page=PdfReader(path).pages[0]
                    self.assertAlmostEqual(float(page.mediabox.width)*25.4/72,w,places=3)
                    self.assertAlmostEqual(float(page.mediabox.height)*25.4/72,h,places=3)
            self.assertEqual(json.dumps(original,sort_keys=True),bytes_before)
            for entry in record["images"]:self.assertEqual(core.sha256(folder/entry["file"]),entry["sha256"])

    def test_saved_preview_rejects_path_traversal_and_tampering(self):
        c=config()
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            folder=Path(td);record=core.save_pair(folder,1,Image.new("RGB",(320,240)),c)
            m={"pairs":[record],"config":c}
            self.assertEqual(len(preview_images(folder,m)),1)
            record["images"][0]["file"]="../private.png"
            with self.assertRaises(ValueError):preview_images(folder,m)

    def test_paper_preview_separate_spread_proportional_orientation(self):
        images=[Image.new("RGB",(30,60),"red"),Image.new("RGB",(50,50),"blue")]
        a=paper_preview(images,"A4","portrait","separate")
        b=paper_preview(images,"A5","landscape","spread")
        self.assertLess(a.width,a.height)
        self.assertGreater(b.width,b.height)
        self.assertIn((255,0,0),[color for count,color in a.getcolors(a.width*a.height)])
        self.assertIn((0,0,255),[color for count,color in b.getcolors(b.width*b.height)])

    def test_partial_many_region_write_is_not_a_committed_capture(self):
        c=config(3)
        image=Image.new("RGB",(320,240),"white")
        original_save=Image.Image.save
        def fail_second(im,path,*args,**kwargs):
            if "region_002" in str(path):raise OSError("synthetic disk failure")
            return original_save(im,path,*args,**kwargs)
        manifest={"pairs":[]};gui=Mock()
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td,patch.object(core,"wait_ready",return_value=(image,"disabled",image)),patch.object(Image.Image,"save",fail_second):
            with self.assertRaises(OSError):core.run_capture(gui,c,Path(td),manifest)
            self.assertEqual(manifest["pairs"],[])
            self.assertTrue((Path(td)/"000001_region_001.png").exists())
            self.assertFalse(core.build_pdf(Path(td),manifest|{"config":c},Path(td)/"invalid.pdf"))
            gui.click_next.assert_not_called()

    def test_unknown_manifest_schema_fails_before_export(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            with self.assertRaises(ValueError):core.build_pdf(Path(td),{"schema":99,"pairs":[],"config":config()},Path(td)/"wrong.pdf")


if __name__=="__main__":unittest.main(verbosity=2)
