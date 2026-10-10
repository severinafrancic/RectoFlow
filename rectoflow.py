"""Friendly portable launcher; CLI arguments forward to the capture engine."""
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

import edge_capture as core
from calibration.diagnostics import Diagnostic, current, scope


def show_workflow_error(diagnostic, code):
    if diagnostic.dialog_shown:
        return
    diagnostic.dialog_shown = True
    dialog = None
    try:
        dialog = tk.Tk()
        dialog.withdraw()
        messagebox.showerror("RectoFlow gestoppt", diagnostic.dialog_text(code), parent=dialog)
    except tk.TclError:
        # Last native fallback if Tk cannot create a dialog after launcher teardown.
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, diagnostic.dialog_text(code), "RectoFlow gestoppt", 0x10)
    finally:
        if dialog is not None:
            try: dialog.destroy()
            except tk.TclError: pass


def graphical_core():
    diagnostic = current() or Diagnostic(core.config_root(), core.VERSION, "gui")
    with scope(diagnostic):
        try:
            code = core.main()
        except (Exception, KeyboardInterrupt) as error:
            diagnostic.failure(error)
            code = 2
        diagnostic.finish(code)
        if code != 0:
            show_workflow_error(diagnostic, code)
        return code

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
    root.geometry("760x720")
    selected=tk.StringVar(value=str(core.config_root()/"config.json"))
    ttk.Label(root,text="RectoFlow",font=("Segoe UI",24,"bold"),padding=15).pack(anchor="w")
    ttk.Label(root,text="Ein Bereich oder beliebig viele — Brave, Edge, Firefox und Chrome.\nBereiche ordnen, mit Weiter aufnehmen, Papierformat am Ende waehlen.",padding=12,wraplength=600).pack(anchor="w")
    ttk.Label(root,textvariable=selected,wraplength=590,padding=10).pack(anchor="w")
    action=None
    from calibration.profiles import ProfileStore
    store=ProfileStore(core.config_root()/"data")
    profile_uuid=None
    profile_rows=[]
    profile_list=tk.Listbox(root,height=5)
    ttk.Label(root,text="Profile (oder direkte Config unten verwenden)",padding=8).pack(anchor="w")
    profile_list.pack(fill="x",padx=12)
    def refresh_profiles():
        nonlocal profile_rows
        try:
            profile_rows=store.enumerate();profile_list.delete(0,"end")
            for item in profile_rows:profile_list.insert("end",item["name"]+("" if item["ready"] else " — NICHT BEREIT: "+item["reason"]))
        except Exception as error:messagebox.showerror("Profile",str(error),parent=root)
    def selected_profile():
        if not profile_list.curselection():return None
        item=profile_rows[profile_list.curselection()[0]]
        if not item["ready"]:raise ValueError(item["reason"])
        return item["uuid"]
    def use_profile():
        nonlocal profile_uuid
        try:
            profile_uuid=selected_profile()
            if profile_uuid:selected.set(str(store.path(profile_uuid)/"config.json"))
        except Exception as error:messagebox.showerror("Profil nicht bereit",str(error),parent=root)
    profile_list.bind("<<ListboxSelect>>",lambda e:use_profile())
    def profile_operation(operation):
        try:
            identifier=selected_profile()
            name=simpledialog.askstring("Profilname","Name fuer das Profil:",parent=root)
            if not name:return
            if operation=="import":
                path=filedialog.askopenfilename(parent=root,title="Config importieren",filetypes=[("Config","*.json")])
                if path:store.import_config(path,name)
            elif operation=="create":
                cfg=json.loads((core.config_root()/"config.json").read_bytes())
                choice=simpledialog.askstring("Vorlage","einzeln / doppelt / eigene",initialvalue="einzeln",parent=root)
                if choice not in ("einzeln","doppelt","eigene"):return
                if choice=="doppelt":
                    first=core.capture_rects(cfg)[0];x,y,w,h=first;cfg["regions"]=[first,[x+w,y,w,h]]
                elif choice=="einzeln":cfg["regions"]=[core.capture_rects(cfg)[0]]
                store.create(name,cfg)
            elif identifier and operation=="duplicate":store.duplicate(identifier,name)
            elif identifier and operation=="rename":store.rename(identifier,name)
            refresh_profiles()
        except Exception as error:messagebox.showerror("Profil unveraendert",str(error),parent=root)
    controls=ttk.Frame(root,padding=8);controls.pack(fill="x")
    for label,operation in (("Neues Profil","create"),("Importieren","import"),("Duplizieren","duplicate"),("Umbenennen","rename")):
        ttk.Button(controls,text=label,command=lambda op=operation:profile_operation(op)).pack(side="left",padx=3)
    ttk.Button(controls,text="Aktualisieren",command=refresh_profiles).pack(side="left")
    refresh_profiles()
    def choose():
        nonlocal profile_uuid
        name=filedialog.askopenfilename(title="Konfiguration waehlen",filetypes=[("JSON-Konfiguration","*.json")],parent=root)
        if name:
            profile_uuid=None;profile_list.selection_clear(0,"end");selected.set(name)
    def run(mode):
        nonlocal action
        action=mode
        root.destroy()
    ttk.Button(root,text="Konfiguration waehlen",command=choose).pack(pady=5)
    def backup_dialog():
        from calibration.config_io import backups,restore
        path=Path(selected.get())
        win=tk.Toplevel(root);win.title("Config-Backups");win.geometry("680x330")
        entries=backups(path)[:10]
        ttk.Label(win,text="Die zehn neuesten Backups. Alle Backups bleiben auf der Festplatte erhalten.",padding=10).pack()
        listing=tk.Listbox(win);listing.pack(fill="both",expand=True)
        for item in entries:listing.insert("end",item.name)
        def apply():
            if not listing.curselection():return
            backup=entries[listing.curselection()[0]]
            if not messagebox.askyesno("Restore bestaetigen","Dieses Backup wiederherstellen? Die aktuelle Config wird vorher gesichert.",parent=win):return
            try:
                cfg=json.loads(backup.read_bytes().decode("utf-8-sig"))
                size=core.WindowsGUI(cfg,path.parent).size
                restore(path,backup,lambda c:core.validate(c,size))
                messagebox.showinfo("Restore abgeschlossen","Config wiederhergestellt. Vor Aufnahme erneut kontrollieren.",parent=win)
                win.destroy()
            except Exception as error:messagebox.showerror("Restore fehlgeschlagen",str(error),parent=win)
        ttk.Button(win,text="Ausgewaehltes Backup wiederherstellen",command=apply).pack(pady=8)
    ttk.Button(root,text="Config-Backups / Wiederherstellen",command=backup_dialog).pack(pady=3)
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
        if current():current().phase("EXPORT",run_path=str(Path(name).parent))
        from calibration.pdf_export import export_dialog
        path=Path(name)
        from calibration.exports import running_state
        state=running_state(path.parent)
        if state not in ("COMPLETE","STOPPED","PDF_FAILED"):
            if current():
                current().phase("EXPORT", run_path=str(path.parent))
                current().failure(ValueError(state+"\nOriginaldateien bleiben erhalten. Kein Resume in Version 0.2."))
            return 2
        result=export_dialog(path.parent,json.loads(path.read_text(encoding="utf-8")),core.build_pdf)
        if result:
            messagebox.showinfo("PDF fertig",f"Gespeichert:\n{path.parent/result['file']}")
        return 0
    sys.argv=[sys.argv[0]]+(["--profile",profile_uuid] if profile_uuid else ["--config",selected.get()])+([] if action=="--capture" else [action])
    return graphical_core()


def main():
    if sys.argv[1:]==["--self-check"]:
        return self_check()
    if len(sys.argv)==1 or sys.argv[1:]==["--gui"]:
        return launcher()
    if "--capture" in sys.argv:
        sys.argv.remove("--capture")
    return core.main()


def entrypoint():
    graphical = len(sys.argv)==1 or sys.argv[1:]==["--gui"]
    diagnostic = Diagnostic(core.config_root(), core.VERSION, "gui" if graphical else "cli")
    with scope(diagnostic):
        try:
            code = main()
        except (Exception,KeyboardInterrupt) as error:
            diagnostic.failure(error)
            print(f"STOPP: {type(error).__name__}: {error}",file=sys.stderr)
            code = 2
        diagnostic.finish(code)
        if graphical and code != 0:
            show_workflow_error(diagnostic, code)
        return code


if __name__=="__main__":
    raise SystemExit(entrypoint())
