"""Native Tk handle/loupe and pre-capture policy/fallback composition; no browser."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from calibration.screenshot_picker import RectanglePicker, HANDLE_ORDER
from calibration.page_layout import PolicyDialog, default_policy
from calibration import calibration as wizard


def widgets(root):
    yield root
    for child in root.winfo_children():yield from widgets(child)


def main():
    root=tk.Tk();root.withdraw();native=tk.Toplevel
    def hidden(master):
        win=native(master);win.withdraw();win.state=lambda *args:"withdrawn";return win
    try:
        with patch.object(tk,"Toplevel",side_effect=hidden):
            p=RectanglePicker(root,Image.new("RGB",(1200,900),"white"),{"REGION_001":[200,200,100,100],"NEXT":None,"PROGRESS":None},None,[0,0,1200,900],navigation_mode="none")
            assert p.canvas.bind("<Tab>") and p.canvas.bind("<Shift-Tab>")
            with patch.object(p.canvas,"winfo_width",return_value=900),patch.object(p.canvas,"winfo_height",return_value=650):
                seen=[]
                for _ in range(9):
                    p.cycle_handle(1);root.update_idletasks();seen.append(p.active_handle or "MOVE")
                    loupe=[p.canvas.itemcget(i,"text") for i in p.canvas.find_all() if p.canvas.type(i)=="text" and "4x | X" in p.canvas.itemcget(i,"text")]
                    assert bool(loupe)==bool(p.active_handle)
                assert tuple(seen)==HANDLE_ORDER
                p.activate_handle("SE");p.key_move(SimpleNamespace(widget=p.canvas,state=1,keysym="Right"));root.update_idletasks()
                assert p.rects[p.selected]==[200,200,110,100]
                assert p.active_handle=="se" and p.loupe_photo.width()==168
                assert "Handle: SE" in p.status.get()
                p.key_move(SimpleNamespace(widget=p.canvas,state=0,keysym="Down"));p.release(None)
                assert p.magnifier_point==(310,301)
                p.lock_var.set(True);p.toggle_lock();p.cycle_handle(1)
                assert p.active_handle is None and "MOVE" in p.status.get()
            p.cancel()
            for count in (2,12):
                dialog=PolicyDialog(root,count,max_views=8)
                assert dialog.policy==default_policy(count)
                dialog.view.set("3")
                for i,var in enumerate(dialog.masks["override"],1):var.set(i==count)
                dialog.set_override();dialog.listing.selection_set(0);dialog.select_override()
                assert dialog.view.get()=="3" and dialog.policy["overrides"]=={"3":[count]}
                dialog.accept();assert dialog.result["overrides"]=={"3":[count]}
            dialog=PolicyDialog(root,2);dialog.window.destroy();assert dialog.result is None
            for expected,label in (("retry","HTML-Auswahl erneut versuchen"),("manual","Manuell fortfahren"),("cancel","Abbrechen")):
                errors=[]
                def drive():
                    try:
                        button=next(w for w in widgets(root) if isinstance(w,ttk.Button) and w.cget("text")==label)
                        button.invoke()
                    except BaseException as error:
                        errors.append(error)
                        for child in root.winfo_children():child.destroy()
                root.after(50,drive)
                assert wizard.fallback_choice(root,ValueError("synthetic mapping"))==expected
                if errors:raise errors[0]
        print("NATIVE_OWNER_SMOKE_PASS: actual Tk Tab/handle bindings, persistent loupe, 1/10 physical px, lock; sparse policy defaults/override/save/cancel; retry/manual/cancel UI. Synthetic pixels only.")
    finally:root.destroy()


if __name__=="__main__":main()
