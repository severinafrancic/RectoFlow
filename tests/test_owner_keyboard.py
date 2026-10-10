"""Persistent handle navigation and physical pixel edits, including edge axes."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_editor_precision import picker
from test_regions import config, SCRATCH
from calibration.screenshot_picker import HANDLE_ORDER
from calibration.config_io import updated_config, atomic_update
import edge_capture as core


class HandleTests(unittest.TestCase):
    def key(self,p,key,shift=False):
        p.key_move(SimpleNamespace(widget=Mock(),keysym=key,state=1 if shift else 0))

    def test_tab_all_handles_and_reverse_without_geometry_changes(self):
        p=picker();before=p.rects.copy();seen=[]
        for _ in range(9):
            self.assertEqual(p.cycle_handle(1),"break");seen.append(p.active_handle or "MOVE")
            self.assertEqual(p.magnifier_point,p.handles(p.rects[p.selected])[p.active_handle] if p.active_handle else None)
        self.assertEqual(tuple(seen),HANDLE_ORDER);self.assertEqual(p.rects,before)
        back=[]
        for _ in range(9):p.cycle_handle(-1);back.append(p.active_handle or "MOVE")
        self.assertEqual(back,["w","sw","s","se","e","ne","n","nw","MOVE"])

    def test_corner_one_and_ten_pixels_and_persistent_magnifier(self):
        for handle,one,ten in (("NW",[21,31,39,49],[31,41,29,39]),("SE",[20,30,41,51],[20,30,51,61])):
            with self.subTest(handle=handle):
                p=picker();p.activate_handle(handle)
                self.key(p,"Right");self.key(p,"Down");self.assertEqual(p.rects[p.selected],one)
                self.key(p,"Right",True);self.key(p,"Down",True);self.assertEqual(p.rects[p.selected],ten)
                self.assertEqual(p.active_handle,handle.lower());self.assertEqual(p.magnifier_point,p.handles(ten)[handle.lower()])
                p.release(Mock());self.assertIsNotNone(p.magnifier_point)

    def test_edges_ignore_orthogonal_arrow_without_history_entry(self):
        for handle,orthogonal,axis,expected in (("N","Right","Up",[20,29,40,51]),("S","Left","Down",[20,30,40,51]),
                                               ("E","Up","Right",[20,30,41,50]),("W","Down","Left",[19,30,41,50])):
            with self.subTest(handle=handle):
                p=picker();p.activate_handle(handle);before=p.snapshot()
                self.key(p,orthogonal);self.assertEqual(p.snapshot(),before)
                self.assertFalse(getattr(p,"undo_stack",[]))
                self.key(p,axis);self.assertEqual(p.rects[p.selected],expected)
                self.assertEqual(p.magnifier_point,p.handles(expected)[handle.lower()])

    def test_move_lock_bounds_unlock_and_handle_corner_hit_priority(self):
        p=picker();p.activate_handle("MOVE");self.key(p,"Right");self.key(p,"Down",True)
        self.assertEqual(p.rects[p.selected],[21,40,40,50]);p.toggle_lock()
        for _ in range(9):p.cycle_handle(1);self.assertIsNone(p.active_handle)
        for _ in range(50):self.key(p,"Left",True);self.key(p,"Up",True)
        self.assertEqual(p.rects[p.selected],[0,0,40,50]);self.assertIsNone(p.magnifier_point)
        p.lock_var.get.return_value=False;p.toggle_lock();p.activate_handle("SE");self.key(p,"Right")
        self.assertEqual(p.rects[p.selected],[0,0,41,50])
        p.canvas=Mock();p.transform=(1,0,0);p.mode="edit"
        p.press(SimpleNamespace(x=40,y=50));self.assertEqual(p.active_handle,"se")

    def test_exact_pixel_save_reload_and_undo_redo(self):
        p=picker();p.activate_handle("SE");self.key(p,"Right");self.key(p,"Down",True)
        exact=p.rects[p.selected][:];p.drag=None;p.undo();p.redo();self.assertEqual(p.rects[p.selected],exact)
        cfg=config(1);target={"selection_bounds":[0,0,320,240],"screen_size":[320,240]}
        candidate=updated_config(cfg,p.rects,None,target,None,"none")
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            path=Path(td)/"config.json";path.write_text(json.dumps(cfg));raw=path.read_bytes()
            atomic_update(path,candidate,hashlib.sha256(raw).hexdigest(),lambda c:core.validate(c,(320,240)))
            self.assertEqual(json.loads(path.read_bytes())["regions"],[exact])
