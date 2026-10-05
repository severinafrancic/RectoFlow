"""Real hidden Tk widgets with synthetic pixels; no owner desktop is acquired."""
from pathlib import Path
import copy
import sys
import tkinter as tk
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from calibration.screenshot_picker import RectanglePicker
from calibration.regions import capture_names
from calibration.pdf_export import paper_preview


def main():
    root=tk.Tk();root.withdraw()
    native_top=tk.Toplevel
    def hidden(master):
        win=native_top(master);win.withdraw();win.state=lambda *args:"withdrawn";return win
    try:
        with patch("calibration.screenshot_picker.tk.Toplevel",side_effect=hidden):
            rects={"REGION_001":[100,100,567,801],"REGION_002":[700,100,567,801],"NEXT":None,"PROGRESS":None}
            p=RectanglePicker(root,Image.new("RGB",(1600,1000),"white"),rects,None,[20,20,1580,980],final=True,navigation_mode="none")
            root.update_idletasks();p.render()
            assert p.photo and p.window.bind("<Escape>")
            assert p.selector.get()=="Bereich 1"
            p.add_region();p.rects[p.selected]=[1300,200,100,140];p.reorder(-1)
            assert p.selector.get()==p.display_name(p.selected)=="Bereich 2"
            assert capture_names(p.rects)==["REGION_001","REGION_003","REGION_002"]
            p.delete();p.select("REGION_002");p.delete()
            assert len(capture_names(p.rects))==1
            approved=copy.deepcopy(p.rects);p.cancel()
            q=RectanglePicker(root,Image.new("RGB",(1600,1000),"white"),approved,None,[20,20,1580,980],final=True,navigation_mode="none")
            assert q.rects==approved
            with patch("calibration.screenshot_picker.messagebox.askyesno",return_value=True):q.accept()
            assert q.result["navigation"]=="none" and q.result["point"] is None
            assert len(capture_names(q.result["rects"]))==1
        print("NATIVE_UI_SMOKE_PASS: hidden real Tk canvas/image; dynamic add/delete/reorder selector; one region; paper-stable reopen; explicit acceptance without Next.")
    finally:root.destroy()


if __name__=="__main__":main()
