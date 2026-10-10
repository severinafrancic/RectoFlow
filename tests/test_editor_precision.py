"""Physical pixel precision, size locking and magnifier source/placement."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from PIL import Image
from calibration.geometry import magnifier_pixels, magnifier_position, canvas_transform, to_screen
from calibration.screenshot_picker import RectanglePicker


def picker():
    p=RectanglePicker.__new__(RectanglePicker)
    p.rects={"REGION_001":[20,30,40,50],"NEXT":None,"PROGRESS":None}
    p.selected="REGION_001";p.point=None;p.bounds=[0,0,320,240]
    p.locked=set();p.active_handle=None;p.magnifier_point=None;p.mode="edit"
    p.render=Mock();p.lock_var=Mock();p.lock_var.get.return_value=True
    return p


class PrecisionTests(unittest.TestCase):
    def key(self,p,key,shift=False):
        return p.key_move(SimpleNamespace(widget=Mock(),state=1 if shift else 0,keysym=key))

    def test_locked_size_move_keyboard_and_bounds(self):
        p=picker();p.toggle_lock()
        self.key(p,"Right");self.assertEqual(p.rects[p.selected],[21,30,40,50])
        self.key(p,"Down",True);self.assertEqual(p.rects[p.selected],[21,40,40,50])
        for _ in range(50):self.key(p,"Right",True)
        self.assertEqual(p.rects[p.selected],[280,40,40,50])
        p.draw_new();self.assertEqual(p.mode,"edit")
        p.fit_selected();p.align_selected("size")
        self.assertEqual(p.rects[p.selected],[280,40,40,50])

    def test_unlock_enables_handle_resize_and_keyboard(self):
        p=picker();p.toggle_lock();p.lock_var.get.return_value=False;p.toggle_lock()
        p.active_handle="se"
        self.key(p,"Right");self.key(p,"Down",True)
        self.assertEqual(p.rects[p.selected],[20,30,41,60])
        self.assertEqual(p.magnifier_point,(61,90))

    def test_mouse_locked_drag_moves_whole_rectangle(self):
        p=picker();p.locked.add(p.selected);p.canvas=Mock();p.transform=(1,0,0)
        p.press(SimpleNamespace(x=20,y=30))
        self.assertEqual(p.drag[2],"move")
        p.motion(SimpleNamespace(x=310,y=230))
        self.assertEqual(p.rects[p.selected],[280,190,40,50])
        p.release(Mock());self.assertIsNone(p.drag)

    def test_resize_handle_remains_active_for_keyboard(self):
        p=picker();p.canvas=Mock();p.transform=(1,0,0)
        p.press(SimpleNamespace(x=60,y=80));p.motion(SimpleNamespace(x=65,y=87));p.release(Mock())
        self.assertEqual(p.active_handle,"se")
        self.key(p,"Left");self.assertEqual(p.rects[p.selected],[20,30,44,57])

    def test_magnifier_nearest_neighbor_original_pixels_crosshair_and_padding(self):
        image=Image.new("RGB",(50,40))
        image.putpixel((23,17),(17,99,201))
        image.putpixel((24,17),(255,0,0))
        zoomed,crosshair=magnifier_pixels(image,(23,17))
        self.assertEqual(zoomed.size,(168,168));self.assertEqual(crosshair,(84,84))
        for x in range(80,88):
            for y in range(80,88):self.assertEqual(zoomed.getpixel((x,y)),(17,99,201))
        self.assertEqual(zoomed.getpixel((88,84)),(255,0,0))
        edge,_=magnifier_pixels(image,(0,0));self.assertEqual(edge.getpixel((0,0)),(0,0,0))

    def test_edge_placement_never_covers_active_corner(self):
        for point in ((0,0),(799,0),(0,599),(799,599),(400,300)):
            left,top=magnifier_position(point,(800,600))
            self.assertTrue(0<=left<=616 and 0<=top<=390)
            self.assertFalse(left<=point[0]<=left+184 and top<=point[1]<=top+210)
        self.assertIsNone(magnifier_position((10,10),(20,20)))

    def test_display_scaling_does_not_change_physical_coordinate(self):
        for canvas in ((800,600),(1200,900),(1600,1200)):
            transform=canvas_transform((1600,1200),canvas)
            s,ox,oy=transform
            physical=to_screen((ox+231*s,oy+177*s),transform)
            self.assertEqual(physical,[231,177])
