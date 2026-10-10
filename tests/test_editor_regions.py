"""Editor state, ordering and persistence through the capture/PDF consumers."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from pypdf import PdfReader
from test_editor_precision import picker
from test_regions import config, SCRATCH
from calibration.geometry import adjacent_rect, CalibrationError
from calibration.regions import capture_names, selection, capture_rects
from calibration.config_io import updated_config, atomic_update, backups, restore
from calibration.profiles import ProfileStore
import edge_capture as core


class EditorRegionTests(unittest.TestCase):
    def editor(self):
        p=picker();p.rects={"REGION_001":[100,100,30,40],"REGION_002":[140,100,30,40],"REGION_003":[180,100,30,40],"NEXT":None,"PROGRESS":None}
        p.selected="REGION_002";p.gap=Mock();p.gap.get.return_value="0";p.window=Mock()
        p.drag=None
        return p

    def test_adjacent_four_directions_gap_exact_size(self):
        for gap in (0,7):
            for direction,xy in (("left",[70-gap,100]),("right",[130+gap,100]),("up",[100,60-gap]),("down",[100,140+gap])):
                self.assertEqual(adjacent_rect([100,100,30,40],direction,[0,0,320,240],gap),xy+[30,40])

    def test_adjacent_bounds_failure_is_not_clamped_or_resized(self):
        for direction in ("left","right","up","down"):
            with self.assertRaises(CalibrationError):adjacent_rect([0,0,320,240],direction,[0,0,320,240])
        for gap in (-1,1.5,True):
            with self.assertRaises(CalibrationError):adjacent_rect([100,100,30,40],"right",[0,0,320,240],gap)

    def test_adjacent_insert_order_identity_and_many_regions(self):
        p=self.editor();old=copy.deepcopy(p.rects)
        p.add_adjacent("down")
        self.assertEqual(capture_names(p.rects),["REGION_001","REGION_002","REGION_004","REGION_003"])
        self.assertEqual(p.selected,"REGION_004")
        for name in capture_names(old):self.assertEqual(p.rects[name],old[name])
        p.add_adjacent("down");self.assertEqual(len(capture_names(p.rects)),5)
        self.assertEqual(p.display_name(p.selected),"Bereich 4")

    def test_invalid_adjacent_preserves_state_and_history(self):
        p=self.editor();p.gap.get.return_value="1000";before=p.snapshot()
        with patch("calibration.screenshot_picker.messagebox.showwarning") as warning:p.add_adjacent("right")
        warning.assert_called_once();self.assertEqual(p.snapshot(),before)
        self.assertEqual(getattr(p,"undo_stack",[]),[])

    def test_reorder_and_undo_redo_preserve_geometry(self):
        p=self.editor();before=copy.deepcopy(p.rects)
        p.reorder(-1)
        self.assertEqual(capture_names(p.rects),["REGION_002","REGION_001","REGION_003"])
        self.assertEqual(p.rects,before)
        p.undo();self.assertEqual(capture_names(p.rects),capture_names(before))
        p.redo();self.assertEqual(capture_names(p.rects)[0],"REGION_002")

    def test_delete_last_guard_and_duplicate_not_coincident(self):
        p=self.editor();p.duplicate_region()
        self.assertNotEqual(p.rects[p.selected],[140,100,30,40])
        self.assertEqual(p.rects[p.selected][2:],[30,40])
        p.delete();p.undo();self.assertEqual(len(capture_names(p.rects)),4)
        p=picker();p.window=Mock();before=p.snapshot()
        with patch("calibration.screenshot_picker.messagebox.showwarning") as warning:p.delete()
        warning.assert_called_once();self.assertEqual(p.snapshot(),before)

    def test_duplicate_no_room_creates_nothing(self):
        p=picker();p.window=Mock();p.rects[p.selected]=[0,0,320,240];before=p.snapshot()
        with patch("calibration.screenshot_picker.messagebox.showwarning") as warning:p.duplicate_region()
        warning.assert_called_once();self.assertEqual(p.snapshot(),before)

    def test_canvas_click_selects_rectangle(self):
        p=self.editor();p.canvas=Mock();p.transform=(1,0,0)
        p.press(SimpleNamespace(x=115,y=120))
        self.assertEqual(p.selected,"REGION_001");self.assertEqual(p.drag[2],"move")

    def test_mouse_gesture_is_one_undo_move_resize_and_redo_invalidated(self):
        p=self.editor();p.canvas=Mock();p.transform=(1,0,0)
        before=p.snapshot()
        p.press(SimpleNamespace(x=155,y=120))
        for x in (156,157,158):p.motion(SimpleNamespace(x=x,y=120))
        p.release(Mock());self.assertEqual(len(p.undo_stack),1)
        p.undo();self.assertEqual(p.snapshot(),before)
        p.redo();self.assertEqual(p.rects[p.selected],[143,100,30,40])
        p.undo();p.key_move(SimpleNamespace(widget=Mock(),state=0,keysym="Down"))
        self.assertEqual(p.redo_stack,[])

    def test_id_not_reused_after_delete_or_undo(self):
        p=self.editor();p.add_adjacent("down");first=p.selected
        p.undo();p.add_adjacent("down")
        self.assertNotEqual(p.selected,first)

    def test_save_reload_capture_manifest_pdf_order_profiles_and_backups(self):
        p=self.editor();p.reorder(-1)
        cfg=config(3);target={"selection_bounds":p.bounds,"screen_size":[320,240]}
        cfg=updated_config(cfg,p.rects,None,target,None,"none")
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            root=Path(td);path=root/"config.json";raw=json.dumps(config(3)).encode();path.write_bytes(raw)
            atomic_update(path,cfg,hashlib.sha256(raw).hexdigest(),lambda c:core.validate(c,(320,240)))
            loaded=json.loads(path.read_bytes())
            self.assertEqual(capture_rects(loaded),[p.rects[n] for n in capture_names(p.rects)])
            self.assertEqual(capture_rects(loaded),capture_rects(cfg))
            store=ProfileStore(root/"data");identifier=store.create("ordered",loaded)
            self.assertEqual(store.snapshot(identifier)["config"]["regions"],loaded["regions"])
            duplicate=store.duplicate(identifier,"copy")
            self.assertEqual(store.snapshot(duplicate)["config"]["regions"],loaded["regions"])
            image=Image.new("RGB",(320,240),"white")
            colors=[(0,0,255),(255,0,0),(0,255,0)]
            for rect,color in zip(loaded["regions"],colors):image.paste(color,core.box(rect))
            record=core.save_pair(root,1,image,loaded)
            core.build_pdf(root,{"config":loaded,"pairs":[record]},root/"order.pdf")
            pdf=PdfReader(root/"order.pdf")
            self.assertEqual(len(pdf.pages),3)
            for entry,page,color in zip(record["images"],pdf.pages,colors):
                with Image.open(root/entry["file"]) as png:self.assertEqual(png.getpixel((0,0)),color)
                self.assertEqual(page.images[0].image.convert("RGB").getpixel((0,0)),color)
            restore(path,backups(path)[0],lambda c:core.validate(c,(320,240)))
            self.assertEqual(path.read_bytes(),raw)
