"""Real hidden Tk Review widgets; reordered/excluded views reach persisted plan."""
import json
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"tests"))
from test_workflow_v02 import ExportTests,SCRATCH
from calibration.pdf_export import export_dialog
from pypdf import PdfReader


def widgets(root):
    yield root
    for child in root.winfo_children():yield from widgets(child)


def main():
    actual_tk=tk.Tk
    with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
        folder=Path(td);manifest=ExportTests().fixture(folder)
        before=(folder/"manifest.json").read_bytes()
        errors=[]
        def hidden():
            root=actual_tk();root.withdraw()
            def drive():
                try:
                    allwidgets=list(widgets(root));listing=next(w for w in allwidgets if isinstance(w,ttk.Treeview))
                    buttons={w.cget("text"):w for w in allwidgets if isinstance(w,ttk.Button)}
                    listing.selection_set("3");root.update_idletasks();buttons["Frueher"].invoke();buttons["Frueher"].invoke()
                    listing.selection_set("2");buttons["Ein-/Ausschliessen"].invoke()
                    buttons["PDF bestaetigen und erstellen"].invoke()
                except BaseException as error:errors.append(error);root.destroy()
            root.after(100,drive);root.after(10000,root.destroy)
            return root
        with patch("calibration.pdf_export.tk.Tk",side_effect=hidden),patch("calibration.pdf_export.messagebox.askyesno",return_value=True):
            result=export_dialog(folder,manifest,None)
        if errors:raise errors[0]
        assert result is not None
        output=folder/result["file"];plan=json.loads((output.parent/"export_plan.json").read_bytes())
        assert plan["selected_view_indices"]==[3,1]
        assert len(PdfReader(output).pages)==4
        assert (folder/"manifest.json").read_bytes()==before
        print("NATIVE_REVIEW_SMOKE_PASS: real hidden Tk thumbnails/analysis; reorder [3,1]; exclude 2; persisted plan and 4-page PDF; frozen manifest unchanged.")


if __name__=="__main__":main()
