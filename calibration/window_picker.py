"""Explicit browser selection; readiness does not depend on foreground focus."""
import copy
import ctypes
from ctypes import wintypes as W
import tkinter as tk
from tkinter import ttk, messagebox


def inspect_window(gui, hwnd):
    old = gui.hwnd
    gui.hwnd = hwnd
    try:
        from .regions import browser_name
        exe = gui.process_executable()
        browser = browser_name(exe, gui.cfg.get("browser", "auto"))
        env = gui.environment()
        identity = gui.process_identity()
        reasons = []
        if not gui.user.IsWindowVisible(hwnd): reasons.append("nicht sichtbar")
        if gui.user.GetAncestor(hwnd, 2) != hwnd: reasons.append("kein Top-Level-Fenster")
        if gui.user.IsIconic(hwnd): reasons.append("minimiert")
        cloak = W.DWORD()
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmGetWindowAttribute.argtypes = [W.HWND, W.DWORD, ctypes.c_void_p, W.DWORD]
        if dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloak), ctypes.sizeof(cloak)) != 0:
            reasons.append("Sichtbarkeit unbekannt")
        elif cloak.value: reasons.append("ausgeblendet")
        if not env["monitor"]["primary"]: reasons.append("nicht auf Hauptmonitor")
        l,t,r,b = env["window_bounds"]
        if min(r,gui.size[0]) <= max(l,0) or min(b,gui.size[1]) <= max(t,0):
            reasons.append("keine nutzbaren Bounds")
        return {"hwnd":int(hwnd),"browser":browser,"title":gui.title(),"exe":exe,
                "identity":identity,"environment":env,"ready":not reasons,"reason":", ".join(reasons)}
    finally:
        gui.hwnd = old


def enumerate_windows(gui):
    result = []
    callback_type = ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    def visit(hwnd, _):
        try:
            result.append(inspect_window(gui,hwnd))
        except (OSError, RuntimeError, ValueError):
            pass  # unrelated windows/processes are not browser candidates
        return True
    callback = callback_type(visit)
    gui.user.EnumWindows.argtypes = [callback_type,W.LPARAM]
    if not gui.user.EnumWindows(callback,0):
        raise ctypes.WinError(ctypes.get_last_error())
    return result


def choose_window(gui):
    root = tk.Tk()
    root.title("RectoFlow: Zielbrowser waehlen")
    root.geometry("900x390")
    ttk.Label(root,text="Browserfenster ausdruecklich waehlen. READY bedeutet bereit fuer die Bindungspruefung.",padding=10).pack(fill="x")
    tree = ttk.Treeview(root,columns=("browser","title","size","state"),show="headings",selectmode="browse")
    for name,label,width in (("browser","Browser",95),("title","Fenstertitel",350),("size","Groesse",100),("state","Bereitschaft",260)):
        tree.heading(name,text=label); tree.column(name,width=width)
    tree.pack(fill="both",expand=True,padx=10)
    rows = {}
    result = None
    def refresh():
        tree.delete(*tree.get_children()); rows.clear()
        for row in enumerate_windows(gui):
            key = str(row["hwnd"]); rows[key] = row
            l,t,r,b=row["environment"]["window_bounds"]
            tree.insert("", "end",iid=key,values=(row["browser"],row["title"],f"{r-l}×{b-t}","READY" if row["ready"] else "NOT_READY: "+row["reason"]))
    def accept():
        nonlocal result
        if not tree.selection(): return
        selected=rows[tree.selection()[0]]
        try:
            live=inspect_window(gui,selected["hwnd"])
            if not live["ready"] or any(live[k]!=selected[k] for k in ("identity","exe","environment")):
                raise RuntimeError("Fenster hat sich geaendert oder ist nicht bereit. Liste aktualisieren.")
            result=copy.deepcopy(live); root.destroy()
        except Exception as error:
            messagebox.showerror("Ziel nicht bereit",str(error),parent=root)
    row=ttk.Frame(root,padding=10); row.pack(fill="x")
    ttk.Button(row,text="Aktualisieren",command=refresh).pack(side="left")
    ttk.Button(row,text="Abbrechen",command=root.destroy).pack(side="right")
    ttk.Button(row,text="Ziel bestaetigen",command=accept).pack(side="right",padx=5)
    root.bind("<Escape>",lambda e:root.destroy())
    try:
        refresh(); root.mainloop()
    finally:
        try: root.destroy()
        except tk.TclError: pass
    if result is None:
        raise RuntimeError("Fensterwahl abgebrochen; keine Aufnahme gestartet.")
    return result
