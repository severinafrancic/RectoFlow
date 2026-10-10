"""Native hidden Tk editor/helper composition with synthetic pixels only."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from calibration.screenshot_picker import RectanglePicker
from calibration.regions import capture_names
from calibration import calibration as wizard
import edge_capture


def widgets(root):
    yield root
    for child in root.winfo_children():yield from widgets(child)


def main():
    root=tk.Tk();root.withdraw();native_top=tk.Toplevel
    def hidden(master):
        win=native_top(master);win.withdraw();win.state=lambda *args:"withdrawn";return win
    try:
        with patch("calibration.screenshot_picker.tk.Toplevel",side_effect=hidden):
            rects={"REGION_001":[200,200,100,100],"REGION_002":[400,200,100,100],"REGION_003":[600,200,100,100],"NEXT":None,"PROGRESS":None}
            p=RectanglePicker(root,Image.new("RGB",(1200,900),"white"),rects,None,[0,0,1200,900],navigation_mode="none")
            root.update_idletasks()
            p.region_list.selection_clear(0,"end");p.region_list.selection_set(1)
            assert p.region_list.bind("<<ListboxSelect>>")
            # Hidden widgets do not receive desktop input events; invoke the bound handler.
            p.list_selected(SimpleNamespace(widget=p.region_list));root.update_idletasks()
            assert p.selected=="REGION_002"
            p.lock_var.set(True);p.toggle_lock()
            assert "fixiert" in p.region_list.get(1)
            p.key_move(SimpleNamespace(widget=p.canvas,state=1,keysym="Down"))
            assert p.rects[p.selected]==[400,210,100,100]
            p.lock_var.set(False);p.toggle_lock();p.active_handle="se"
            p.key_move(SimpleNamespace(widget=p.canvas,state=0,keysym="Right"))
            assert p.rects[p.selected]==[400,210,101,100]
            # Actual Tk PhotoImage and Canvas primitives, deterministic display dimensions.
            with patch.object(p.canvas,"winfo_width",return_value=900),patch.object(p.canvas,"winfo_height",return_value=650):
                p.render()
                assert p.loupe_photo.width()==168
                texts=[p.canvas.itemcget(i,"text") for i in p.canvas.find_all() if p.canvas.type(i)=="text"]
                assert any("8x | X 501 Y 310" in text for text in texts)
            p.active_handle=None;p.reorder(-1)
            assert capture_names(p.rects)==["REGION_002","REGION_001","REGION_003"]
            assert p.region_list.get(0)=="1. Bereich"
            p.add_adjacent("down");assert p.selected=="REGION_004"
            assert capture_names(p.rects)[:3]==["REGION_002","REGION_004","REGION_001"]
            p.undo();assert len(capture_names(p.rects))==3
            p.redo();assert len(capture_names(p.rects))==4
            assert p.window.bind("<Control-z>") and p.window.bind("<Control-Shift-Z>")
            gap_entry=next(w for w in widgets(p.window) if isinstance(w,ttk.Entry))
            before=p.snapshot()
            p.key_move(SimpleNamespace(widget=gap_entry,state=0,keysym="Down"))
            p.editor_shortcut(SimpleNamespace(widget=gap_entry),p.delete)
            p.editor_shortcut(SimpleNamespace(widget=gap_entry),p.accept)
            p.history_key(SimpleNamespace(widget=gap_entry),False)
            assert p.snapshot()==before
            p.cancel()
        with tempfile.TemporaryDirectory(prefix="rectoflow-native-helper-") as td:
            folder=Path(td);invalid=folder/"invalid.json";invalid.write_text("{}")
            for mode in ("manual","cancel","invalid"):
                errors=[];warnings=[]
                def drive():
                    try:
                        buttons={w.cget("text"):w for w in widgets(root) if isinstance(w,ttk.Button)}
                        if mode=="invalid":
                            buttons["HTML-Hilfsseite"].invoke()
                            buttons["Ergebnis importieren"].invoke()
                            assert warnings
                        buttons["Manuell ohne HTML" if mode in ("manual","invalid") else "Abbrechen"].invoke()
                    except BaseException as error:
                        errors.append(error)
                        for child in root.winfo_children():child.destroy()
                root.after(100,drive)
                with patch.object(wizard.webbrowser,"open",return_value=True),patch.object(edge_capture,"config_root",return_value=folder), \
                     patch.object(wizard.filedialog,"askopenfilename",return_value=str(invalid)), \
                     patch.object(wizard.messagebox,"showwarning",side_effect=lambda *a,**k:warnings.append(a)), \
                     patch.object(wizard.tk,"Toplevel",side_effect=hidden):
                    result=wizard.choose_dom(root,"unused")
                if errors:raise errors[0]
                assert result["mode"]==("cancel" if mode=="cancel" else "manual")
        print("NATIVE_EDITOR_SMOKE_PASS: real Tk list/selection/lock/keyboard/loupe/order/adjacent/undo; HTML manual/cancel/invalid-import fallback; synthetic pixels only.")
    finally:root.destroy()


if __name__=="__main__":main()
