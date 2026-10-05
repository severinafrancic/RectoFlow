"""Friendly portable launcher; CLI arguments forward to the capture engine."""
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import edge_capture as core

def self_check():
    import importlib.metadata
    import struct
    import uiautomation
    from PIL import ImageGrab
    from calibration import pdf_export, screenshot_picker, dom_picker
    print(json.dumps({"tool":"RectoFlow","version":core.VERSION,"architecture":struct.calcsize("P")*8,
        "frozen":bool(getattr(sys,"frozen",False)),"config_root":str(core.config_root()),
        "tcl":tk.Tcl().eval("info patchlevel"),
        "dependencies":{name:importlib.metadata.version(name) for name in ("Pillow","reportlab","uiautomation")}},indent=2))
    return 0


def launcher():
    root=tk.Tk()
    root.title("RectoFlow — Bereiche aufnehmen, PDF erstellen")
    root.geometry("640x440")
    selected=tk.StringVar(value=str(core.config_root()/"config.json"))
    ttk.Label(root,text="RectoFlow",font=("Segoe UI",24,"bold"),padding=15).pack(anchor="w")
    ttk.Label(root,text="Ein Bereich oder beliebig viele — Brave, Edge, Firefox und Chrome.\nBereiche ordnen, mit Weiter aufnehmen, Papierformat am Ende waehlen.",padding=12,wraplength=600).pack(anchor="w")
    ttk.Label(root,textvariable=selected,wraplength=590,padding=10).pack(anchor="w")
    action=None
    def choose():
        name=filedialog.askopenfilename(title="Konfiguration waehlen",filetypes=[("JSON-Konfiguration","*.json")],parent=root)
        if name:selected.set(name)
    def run(mode):
        nonlocal action
        action=mode
        root.destroy()
    ttk.Button(root,text="Konfiguration waehlen",command=choose).pack(pady=5)
    buttons=ttk.Frame(root,padding=10)
    buttons.pack(fill="x")
    for title,mode in (("1. Bereiche kalibrieren","--calibrate"),("2. Vorschau pruefen","--preview"),("3. Aufnahme starten","--capture"),("Gespeicherte Bilder als PDF","export")):
        ttk.Button(buttons,text=title,command=lambda m=mode:run(m)).pack(fill="x",pady=4)
    root.mainloop()
    if not action:return 0
    if action=="export":
        dialog=tk.Tk()
        dialog.withdraw()
        try:
            name=filedialog.askopenfilename(title="manifest.json eines Aufnahmelaufs waehlen",filetypes=[("Aufnahmemanifest","manifest.json")],parent=dialog)
        finally:dialog.destroy()
        if not name:return 0
        from calibration.pdf_export import export_dialog
        path=Path(name)
        result=export_dialog(path.parent,json.loads(path.read_text(encoding="utf-8")),core.build_pdf)
        if result:
            messagebox.showinfo("PDF fertig",f"Gespeichert:\n{path.parent/result['file']}")
        return 0
    sys.argv=[sys.argv[0],"--config",selected.get()]+([] if action=="--capture" else [action])
    return core.main()


def main():
    if sys.argv[1:]==["--self-check"]:
        return self_check()
    if len(sys.argv)==1 or sys.argv[1:]==["--gui"]:
        return launcher()
    if "--capture" in sys.argv:
        sys.argv.remove("--capture")
    return core.main()


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (Exception,KeyboardInterrupt) as error:
        print(f"STOPP: {type(error).__name__}: {error}",file=sys.stderr)
        if getattr(sys,"frozen",False):
            messagebox.showerror("RectoFlow gestoppt",str(error))
        raise SystemExit(2)
