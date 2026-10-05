#!/usr/bin/env python3
"""RectoFlow: geordnete Bildschirmbereiche je Ansicht, dann Weiter.

Koordinaten in config.json sind physische Pixel des HAUPTMONITORS.
Keine Browser-Neustarts, keine Erweiterungen, kein automatischer Wiederanlauf.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as W
from datetime import datetime
import hashlib
import importlib.metadata
import json
import math
import os
import platform
from pathlib import Path
import sys
import time
import uuid

from PIL import Image, ImageChops, ImageDraw, ImageStat
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from calibration.geometry import right_rect, PAPER_MM, assert_same_selection
from calibration.regions import capture_rects, selection, image_names, navigation, browser_name

VERSION = "0.2.0"


def configure_console():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,"reconfigure"):
            stream.reconfigure(errors="backslashreplace")

def config_root():
    return Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parent


class StopRun(RuntimeError):
    """Unklarer Zustand oder Benutzerabbruch; niemals als Erfolg behandeln."""


def box(rect):
    x, y, w, h = rect
    return x, y, x + w, y + h


def inside(point, rect):
    x, y = point
    l, t, r, b = box(rect)
    return l <= x < r and t <= y < b


def spread_rect(cfg):
    regions=capture_rects(cfg)
    x,y=min(r[0] for r in regions),min(r[1] for r in regions)
    return [x,y,max(r[0]+r[2] for r in regions)-x,max(r[1]+r[3] for r in regions)-y]


def content_image(image, cfg):
    """Vergleiche nur die echten Ausschnitte, keine wechselnden Inhalte im Abstand."""
    images=[image.crop(box(r)) for r in capture_rects(cfg)]
    joined = Image.new("RGB", (sum(im.width for im in images),max(im.height for im in images)), "white")
    offset=0
    for im in images:
        joined.paste(im,(offset,0))
        offset+=im.width
    return joined


def progress_image(image,cfg):
    return image.crop(box(cfg["progress_rect"])) if cfg["progress_rect"] else content_image(image,cfg)


def difference(a, b):
    """Mittlere RGB-Abweichung 0..255, ohne Verkleinerung/OCR."""
    if a.size != b.size:
        raise ValueError("Bildgroessen unterscheiden sich.")
    return sum(ImageStat.Stat(ImageChops.difference(a.convert("RGB"),
                                                  b.convert("RGB"))).mean) / 3


def template_state(image, enabled, disabled, tolerance, margin):
    a, d = difference(image, enabled), difference(image, disabled)
    if a <= tolerance and d - a >= margin:
        return "enabled"
    if d <= tolerance and a - d >= margin:
        return "disabled"
    return "unknown"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_identity():
    root=Path(__file__).resolve().parent
    paths=[Path(__file__).resolve(),root/"rectoflow.py"]+sorted((root/"calibration").glob("*.py"))+sorted((root/"calibration").glob("*.js"))
    hashes={p.relative_to(root).as_posix():sha256(p) for p in paths}
    digest=hashlib.sha256("".join(f"{name}\t{hashes[name]}\n" for name in sorted(hashes)).encode()).hexdigest()
    return {"sha256":digest,"files":hashes}


def write_json(path, data):
    from calibration.storage import atomic_json
    atomic_json(path,data)


def validate(cfg, size):
    def positive(key):
        value = cfg[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} muss eine positive endliche Zahl sein.")

    def rect(value, name):
        if not isinstance(value, list) or len(value) != 4 or any(type(v) is not int for v in value):
            raise ValueError(f"{name}: [x, y, Breite, Hoehe] mit ganzen Zahlen.")
        x, y, w, h = value
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > size[0] or y + h > size[1]:
            raise ValueError(f"{name} liegt nicht vollstaendig auf dem Hauptmonitor {size}.")

    regions=capture_rects(cfg)
    for index,value in enumerate(regions,1):
        rect(value,f"Bereich {index}")
    if len({tuple(r) for r in regions})!=len(regions):
        raise ValueError("Aufnahmebereiche duerfen nicht identisch sein.")
    mode=navigation(cfg)
    if mode=="next_button" or cfg.get("button_rect") is not None:
        rect(cfg["button_rect"], "button_rect")
    if cfg["progress_rect"] is not None:
        rect(cfg["progress_rect"], "progress_rect")
    for key in ("next_point", "park_point"):
        p = cfg[key]
        if key=="next_point" and mode!="next_button" and p is None:
            continue
        if not isinstance(p, list) or len(p) != 2 or any(type(v) is not int for v in p):
            raise ValueError(f"{key}: [x, y] mit ganzen Zahlen.")
        if not (0 < p[0] < size[0] - 1 and 0 < p[1] < size[1] - 1):
            raise ValueError(f"{key} liegt ausserhalb des Bildschirms oder in einer Ecke.")
    if mode=="next_button" and not inside(cfg["next_point"], cfg["button_rect"]):
        raise ValueError("next_point muss innerhalb button_rect liegen.")
    for r in [*regions,cfg.get("button_rect"),cfg["progress_rect"]]:
        if r is not None and inside(cfg["park_point"], r):
            raise ValueError("park_point muss ausserhalb Aufnahme, Fortschrittsanzeige und Button liegen.")
    for key in ("start_delay", "poll_seconds", "stable_seconds", "disabled_seconds",
                "min_after_click", "timeout_seconds", "pdf_dpi", "change_threshold",
                "template_tolerance", "template_margin"):
        positive(key)
    if isinstance(cfg["stable_tolerance"], bool) or not isinstance(cfg["stable_tolerance"], (int, float)) or not math.isfinite(cfg["stable_tolerance"]) or not 0 <= cfg["stable_tolerance"] < cfg["change_threshold"]:
        raise ValueError("0 <= stable_tolerance < change_threshold erforderlich.")
    if cfg["timeout_seconds"] <= max(cfg["disabled_seconds"], cfg["stable_seconds"]) + cfg["min_after_click"]:
        raise ValueError("timeout_seconds ist fuer die Wartezeiten zu kurz.")
    if type(cfg["max_spreads"]) is not int or cfg["max_spreads"] <= 0:
        raise ValueError("max_spreads muss eine positive ganze Zahl sein.")
    expected = cfg["expected_spreads"]
    if expected is not None and (type(expected) is not int or not 0 < expected <= cfg["max_spreads"]):
        raise ValueError("expected_spreads: null oder 1..max_spreads.")
    if cfg["button_mode"] not in ("uia", "template"):
        raise ValueError("button_mode: uia oder template.")
    if cfg["pdf_layout"] not in ("separate", "spread"):
        raise ValueError("pdf_layout: separate oder spread.")
    if cfg.get("paper_format","Original") not in (*PAPER_MM,"Original") or cfg.get("paper_orientation","portrait") not in ("portrait","landscape"):
        raise ValueError("Ungueltiges Papierformat/Orientierung.")
    if cfg.get("browser","auto") not in ("auto","Edge","Chrome","Brave","Firefox"):
        raise ValueError("browser: auto, Edge, Chrome, Brave oder Firefox.")


class WindowsGUI:
    """Native Windows-Steuerung; bindet sich an das gewaehlte Edge-Fenster."""
    def __init__(self, cfg, config_dir):
        configure_console()
        if sys.platform != "win32":
            raise RuntimeError("Dieses Skript braucht natives Windows.")
        self.cfg = cfg
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user.GetForegroundWindow.restype = W.HWND
        self.user.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
        self.user.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
        self.user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
        self.user.GetAncestor.argtypes = [W.HWND, W.UINT]
        self.user.GetAncestor.restype = W.HWND
        self.user.WindowFromPoint.argtypes = [W.POINT]
        self.user.WindowFromPoint.restype = W.HWND
        self.user.GetCursorPos.argtypes = [ctypes.POINTER(W.POINT)]
        self.user.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.user.GetAsyncKeyState.restype = ctypes.c_short
        self.kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.kernel.OpenProcess.restype = W.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
        self.kernel.CloseHandle.argtypes = [W.HANDLE]
        self.kernel.GetProcessTimes.argtypes = [W.HANDLE] + [ctypes.POINTER(W.FILETIME)]*4
        self.user.GetDpiForWindow.argtypes = [W.HWND]
        self.user.GetDpiForWindow.restype = W.UINT
        self.user.MonitorFromWindow.argtypes = [W.HWND,W.DWORD]
        self.user.MonitorFromWindow.restype = W.HANDLE
        self.user.SetForegroundWindow.argtypes = [W.HWND]
        self.user.IsWindow.argtypes = [W.HWND]
        self.user.IsWindowVisible.argtypes = [W.HWND]
        self.user.IsIconic.argtypes = [W.HWND]
        self.user.SetPropW.argtypes = [W.HWND,W.LPCWSTR,W.HANDLE]
        self.user.GetPropW.argtypes = [W.HWND,W.LPCWSTR]
        self.user.GetPropW.restype = W.HANDLE
        # DPI-Kontext vor ImageGrab/UIA/Koordinatenabfragen setzen.
        try:
            self.user.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            self.user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except AttributeError:
            self.user.SetProcessDPIAware()
        # Auch bei bereits festgelegter Prozess-DPI den aktuellen Thread umstellen.
        if hasattr(self.user, "SetThreadDpiAwarenessContext"):
            self.user.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            self.user.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
            if not self.user.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4)):
                raise ctypes.WinError(ctypes.get_last_error())
        self.size = (self.user.GetSystemMetrics(0), self.user.GetSystemMetrics(1))
        self.hwnd = None
        self.auto = None
        self.enabled = self.disabled = None
        self.config_dir = config_dir

    def abort_check(self):
        if self.user.GetAsyncKeyState(0x1B) & 0x8001:
            raise StopRun("ESC: Benutzerabbruch.")
        p = W.POINT()
        if not self.user.GetCursorPos(ctypes.byref(p)):
            raise ctypes.WinError(ctypes.get_last_error())
        if p.x <= 2 and p.y <= 2:
            raise StopRun("Maus oben links: Benutzerabbruch.")

    def pause(self, seconds, *, check_abort=True):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if check_abort:
                self.abort_check()
            time.sleep(min(0.05, max(0, end - time.monotonic())))

    def title(self):
        text = ctypes.create_unicode_buffer(4096)
        self.user.GetWindowTextW(self.hwnd, text, len(text))
        return text.value

    def geometry(self):
        r = W.RECT()
        if not self.user.GetWindowRect(self.hwnd, ctypes.byref(r)):
            raise ctypes.WinError(ctypes.get_last_error())
        return (r.left, r.top, r.right, r.bottom)

    def bind(self, check_config=True, check_calibration=True):
        from calibration.window_picker import choose_window, inspect_window
        selected = choose_window(self)
        self.hwnd = selected["hwnd"]
        live = inspect_window(self,self.hwnd)
        if not live["ready"] or any(live[k]!=selected[k] for k in ("identity","exe","environment")):
            raise StopRun("TARGET_WINDOW_LOST: Auswahl ist nicht mehr aktuell.")
        self.browser = live["browser"]
        self.bound_exe = live["exe"]
        self.initial_geometry = tuple(live["environment"]["window_bounds"])
        self.bound_identity = live["identity"]
        self.bound_environment = live["environment"]
        self.window_property = "RectoFlow-" + uuid.uuid4().hex
        if not self.user.SetPropW(self.hwnd,self.window_property,W.HANDLE(1)):
            raise StopRun("TARGET_WINDOW_LOST: Fenster-Lebensdauer nicht bindbar.")
        calibrated = self.cfg.get("calibration")
        if check_calibration and calibrated:
            if calibrated.get("coordinate_space") != "primary_screen_physical_pixels" or calibrated.get("schema") != 1:
                raise StopRun("RECALIBRATION_REQUIRED: unbekanntes Kalibrierungsformat.")
            old = calibrated["target"]
            if any(old[key] != self.bound_environment[key] for key in ("window_bounds","screen_size","dpi","monitor")):
                raise StopRun("RECALIBRATION_REQUIRED: Fenster, Monitor oder DPI weichen von der Kalibrierung ab.")
        self.activate_target()
        self.guard(areas=check_config)
        print("Gebunden an",self.browser,":",self.title(),flush=True)

    def process_executable(self):
        pid = W.DWORD()
        self.user.GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
        handle = self.kernel.OpenProcess(0x1000, False, pid.value)
        if not handle:
            raise StopRun("Prozess des aktiven Fensters nicht pruefbar.")
        try:
            exe = ctypes.create_unicode_buffer(32768)
            length = W.DWORD(len(exe))
            if not self.kernel.QueryFullProcessImageNameW(handle, 0, exe, ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.kernel.CloseHandle(handle)
        return exe.value

    def process_identity(self):
        pid = W.DWORD()
        self.user.GetWindowThreadProcessId(self.hwnd,ctypes.byref(pid))
        handle = self.kernel.OpenProcess(0x1000,False,pid.value)
        if not handle:
            raise StopRun("TARGET_WINDOW_LOST: Fensterprozess nicht mehr pruefbar.")
        times = [W.FILETIME() for _ in range(4)]
        try:
            if not self.kernel.GetProcessTimes(handle,*(ctypes.byref(t) for t in times)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.kernel.CloseHandle(handle)
        return [pid.value,(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime]

    def environment(self):
        class MonitorInfo(ctypes.Structure):
            _fields_=[("cbSize",W.DWORD),("rcMonitor",W.RECT),("rcWork",W.RECT),("dwFlags",W.DWORD),("szDevice",W.WCHAR*32)]
        monitor=self.user.MonitorFromWindow(self.hwnd,2)
        info=MonitorInfo()
        info.cbSize=ctypes.sizeof(info)
        self.user.GetMonitorInfoW.argtypes=[W.HANDLE,ctypes.POINTER(MonitorInfo)]
        if not self.user.GetMonitorInfoW(monitor,ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        dpi=self.user.GetDpiForWindow(self.hwnd)
        if not dpi:
            raise StopRun("TARGET_WINDOW_LOST: Fenster-DPI ist unbekannt.")
        r=info.rcMonitor
        return {"window_bounds":list(self.geometry()),"screen_size":list(self.size),"dpi":dpi,
                "monitor":{"device":info.szDevice,"bounds":[r.left,r.top,r.right,r.bottom],"primary":bool(info.dwFlags&1)}}

    def target_metadata(self):
        data=self.environment()
        l,t,r,b=data["window_bounds"]
        data.update(hwnd=int(self.hwnd),pid=self.bound_identity[0],process_created=self.bound_identity[1],
                    selection_bounds=[max(0,l),max(0,t),min(self.size[0],r),min(self.size[1],b)])
        return data

    def activate_target(self, *, cleanup=False):
        if not self.user.IsWindow(self.hwnd) or self.process_identity()!=self.bound_identity:
            raise StopRun("TARGET_WINDOW_LOST: Ziel-Fenster wurde geschlossen/ersetzt.")
        self.identity_environment_check()
        self.user.SetForegroundWindow(self.hwnd)
        self.pause(.3,check_abort=not cleanup)
        self.guard(areas=False,check_abort=not cleanup)

    def identity_environment_check(self):
        if not self.user.IsWindow(self.hwnd):
            raise StopRun("TARGET_WINDOW_LOST: Ziel geschlossen.")
        if hasattr(self,"bound_identity") and self.process_identity()!=self.bound_identity:
            raise StopRun("TARGET_WINDOW_LOST: Prozessidentitaet geaendert.")
        if hasattr(self,"bound_exe") and self.process_executable()!=self.bound_exe:
            raise StopRun("TARGET_WINDOW_LOST: Executable geaendert.")
        if hasattr(self,"bound_exe") and (not self.user.IsWindowVisible(self.hwnd) or self.user.IsIconic(self.hwnd)):
            raise StopRun("TARGET_WINDOW_LOST: Fenster ist nicht mehr sichtbar/bereit.")
        if hasattr(self,"window_property") and not self.user.GetPropW(self.hwnd,self.window_property):
            raise StopRun("TARGET_WINDOW_LOST: HWND-Lebensdauer geaendert.")
        if hasattr(self,"bound_environment") and self.environment()!=self.bound_environment:
            raise StopRun("RECALIBRATION_REQUIRED: Fenster, DPI oder Monitor geaendert.")

    def __del__(self):
        # Property dies with HWND; remove our own live marker when this adapter closes.
        try:
            if getattr(self,"window_property",None) and self.user.IsWindow(self.hwnd):
                self.user.RemovePropW.argtypes=[W.HWND,W.LPCWSTR]
                self.user.RemovePropW(self.hwnd,self.window_property)
        except Exception:
            pass

    def remove_dom_picker(self):
        # ESC beendet die Auswahl, darf die eigene lokale Bereinigung aber nicht
        # verhindern. Fensteridentitaet/Fokus/Monitor werden weiterhin geprueft.
        self.guard(areas=False,check_abort=False)
        self.user.keybd_event(0x77,0,0,0)  # F8: eigene Picker-Cleanup-Taste
        self.user.keybd_event(0x77,0,2,0)
        time.sleep(.1)

    def guard(self, areas=True, *, check_abort=True):
        if check_abort:
            self.abort_check()
        self.identity_environment_check()
        if self.user.GetForegroundWindow() != self.hwnd:
            raise StopRun("Zielbrowser hat den Fokus verloren. Keine weiteren Klicks.")
        if self.geometry() != self.initial_geometry or self.size != (self.user.GetSystemMetrics(0), self.user.GetSystemMetrics(1)):
            raise StopRun("Fensterposition oder Bildschirmgroesse wurde geaendert.")
        if hasattr(self,"bound_identity") and self.process_identity()!=self.bound_identity:
            raise StopRun("TARGET_WINDOW_LOST: Fensterhandle/Prozessidentitaet wurde ersetzt.")
        if hasattr(self,"bound_environment") and self.environment()!=self.bound_environment:
            raise StopRun("RECALIBRATION_REQUIRED: DPI oder Monitor wurden geaendert.")
        required = self.cfg["window_title_contains"]
        if required and required.casefold() not in self.title().casefold():
            raise StopRun("Fenstertitel passt nicht mehr zum gewaehlten Dokument.")
        # Stichproben gegen fremde Fenster ueber den relevanten Bereichen.
        if not areas:
            return
        for r in [*capture_rects(self.cfg),self.cfg.get("button_rect"),self.cfg["progress_rect"]]:
            if r is None:
                continue
            l, t, rr, bb = box(r)
            for x, y in ((l, t), (rr - 1, t), (l, bb - 1), (rr - 1, bb - 1), ((l + rr) // 2, (t + bb) // 2)):
                hit = self.user.WindowFromPoint(W.POINT(x, y))
                if self.user.GetAncestor(hit, 2) != self.hwnd:
                    raise StopRun("Aufnahmebereich/Button liegt ausserhalb des Zielbrowsers oder ist verdeckt.")

    def park(self):
        self.guard()
        self.user.SetCursorPos(*self.cfg["park_point"])

    def snapshot(self, areas=True, *, check_abort=True):
        from PIL import ImageGrab
        self.guard(areas=areas,check_abort=check_abort)
        try:
            image = ImageGrab.grab(bbox=(0, 0, *self.size), include_layered_windows=True).convert("RGB")
        except Exception as error:
            raise StopRun(f"SCREENSHOT_FAILED: {error}") from error
        if image.size != self.size:
            raise StopRun("SCREENSHOT_FAILED: Screenshot-Abmessungen passen nicht zum Hauptmonitor.")
        self.guard(areas=areas,check_abort=check_abort)
        return image

    def prepare_button(self):
        if navigation(self.cfg)!="next_button":
            return
        if self.cfg["button_mode"] == "uia":
            import uiautomation
            self.auto = uiautomation
        else:
            for attr, filename in (("enabled", "button_enabled.png"), ("disabled", "button_disabled.png")):
                from io import BytesIO
                if not hasattr(self,"template_bytes") or filename not in self.template_bytes:
                    raise StopRun("Button-Template-Snapshot fehlt; Lauf neu vorbereiten.")
                with Image.open(BytesIO(self.template_bytes[filename])) as im:
                    setattr(self, attr, im.convert("RGB"))
            expected = tuple(self.cfg["button_rect"][2:])
            if self.enabled.size != expected or self.disabled.size != expected:
                raise ValueError("Button-Vorlagen passen nicht zu button_rect. Neu kalibrieren.")
            if difference(self.enabled, self.disabled) < self.cfg["template_margin"] * 2:
                raise ValueError("Aktive/inaktive Vorlage sind nicht deutlich unterscheidbar.")

    def button_state(self, image):
        if navigation(self.cfg)!="next_button":
            return "disabled" if navigation(self.cfg)=="none" else "manual"
        if self.cfg["button_mode"] == "template":
            return template_state(image.crop(box(self.cfg["button_rect"])), self.enabled, self.disabled,
                                  self.cfg["template_tolerance"], self.cfg["template_margin"])
        # Frische Abfrage bei jedem Poll; keine gecachten IsEnabled-Werte.
        try:
            control = self.auto.ControlFromPoint(*self.cfg["next_point"])
            for _ in range(12):
                if control is None:
                    break
                if control.ControlTypeName in ("ButtonControl", "HyperlinkControl"):
                    top = control.GetTopLevelControl()
                    if top is None or top.NativeWindowHandle != self.hwnd or control.IsOffscreen:
                        return "unknown"
                    wanted = self.cfg["button_name"]
                    if wanted and control.Name != wanted:
                        return "unknown"
                    r = control.BoundingRectangle
                    x, y = self.cfg["next_point"]
                    if not (r.left <= x < r.right and r.top <= y < r.bottom):
                        return "unknown"
                    return "enabled" if control.IsEnabled else "disabled"
                control = control.GetParentControl()
        except Exception as error:
            # Unerreichbar/stale darf nicht als 'deaktiviert' gelten.
            self.last_uia_error = str(error)
        return "unknown"

    def click_next(self):
        if navigation(self.cfg)!="next_button":
            raise StopRun("Keine automatischen Klicks in diesem Navigationsmodus.")
        self.guard()
        # Zustand kurz vor dem Klick erneut pruefen.
        if self.button_state(self.snapshot()) != "enabled":
            raise StopRun("Weiter ist unmittelbar vor dem Klick nicht sicher aktiv.")
        x, y = self.cfg["next_point"]
        if not self.user.SetCursorPos(x, y):
            raise ctypes.WinError(ctypes.get_last_error())
        self.guard()
        class MouseInput(ctypes.Structure):
            _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                        ("dwFlags", W.DWORD), ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
        class KeyboardInput(ctypes.Structure):
            _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                        ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
        class HardwareInput(ctypes.Structure):
            _fields_ = [("uMsg", W.DWORD), ("wParamL", W.WORD), ("wParamH", W.WORD)]
        class InputUnion(ctypes.Union):
            _fields_ = [("mi", MouseInput), ("ki", KeyboardInput), ("hi", HardwareInput)]
        class Input(ctypes.Structure):
            _fields_ = [("type", W.DWORD), ("data", InputUnion)]
        events = (Input * 2)()
        events[0].data.mi.dwFlags = 0x0002  # LEFTDOWN
        events[1].data.mi.dwFlags = 0x0004  # LEFTUP
        self.user.SendInput.argtypes = [W.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.user.SendInput.restype = W.UINT
        inserted = self.user.SendInput(2, events, ctypes.sizeof(Input))
        if inserted != 2:
            if inserted == 1:
                # Maus loslassen, aber den Weiter-Klick keinesfalls wiederholen.
                self.user.SendInput(1, ctypes.pointer(events[1]), ctypes.sizeof(Input))
            raise StopRun("Windows hat den Klick nicht vollstaendig angenommen. Kein Wiederholungsversuch.")
        self.park()

    def manual_transition(self):
        import tkinter as tk
        from tkinter import messagebox
        root=tk.Tk()
        root.withdraw()
        try:
            answer=messagebox.askyesnocancel("RectoFlow: naechste Ansicht",
                "Weitere Ansicht aufnehmen?\n\nJa: Dialog schliessen, im gebundenen Browser weiterblaettern und den Countdown abwarten.\nNein: Aufnahme beenden und PDF-Format waehlen.\nAbbrechen: Lauf mit Zwischenstand stoppen.",parent=root)
        finally:
            root.destroy()
        if answer is None:
            raise StopRun("Manuelle Aufnahme abgebrochen.")
        if not answer:
            return False
        print(f"{self.cfg['start_delay']} Sekunden fuer die naechste Ansicht.",flush=True)
        self.pause(self.cfg["start_delay"])
        self.activate_target()
        self.park()
        return True


def wait_ready(gui, cfg, previous=None, clock=time.monotonic):
    """Nur einen stabilen, gegenueber dem Ausgangsbild veraenderten Zustand liefern.

    previous ist das Fortschrittsbild VOR dem Klick. Ein Timeout fuehrt nie
    zu einem erneuten Klick. 'unknown' fuehrt niemals zum normalen Ende.
    """
    started = clock()
    anchor = None
    state_anchor = None
    stable_since = started
    while clock() - started < cfg["timeout_seconds"]:
        image = gui.snapshot()
        content = content_image(image,cfg)
        progress = progress_image(image,cfg)
        state = gui.button_state(image)
        now = clock()
        fresh = previous is None or difference(progress, previous) >= cfg["change_threshold"]
        stable = anchor is not None and difference(content, anchor[0]) <= cfg["stable_tolerance"] and difference(progress, anchor[1]) <= cfg["stable_tolerance"]
        if not fresh or not stable or state != state_anchor or state == "unknown":
            anchor = (content, progress)
            state_anchor = state
            stable_since = now
        dwell = max(cfg["stable_seconds"], cfg["disabled_seconds"] if state == "disabled" else 0)
        minimum = cfg["min_after_click"] if previous is not None else cfg["stable_seconds"]
        if fresh and state != "unknown" and now - stable_since >= dwell and now - started >= minimum:
            gui.guard()
            return image, state, progress
        gui.pause(cfg["poll_seconds"])
    raise StopRun("Zeitlimit: keine sicher neue, ruhige Ansicht mit bekanntem Button-Zustand. "
                  "Kein erneuter Klick. progress_rect/Button-Erkennung pruefen.")


def save_pair(folder, index, screenshot, cfg):
    """Ein Screenshot, alle Crops in expliziter Reihenfolge (legacy: links/rechts)."""
    files = []
    for filename,rect in zip(image_names(cfg,index),capture_rects(cfg)):
        path = folder / filename
        tmp = path.with_suffix(".png.tmp")
        screenshot.crop(box(rect)).save(tmp, format="PNG")
        os.replace(tmp, path)
        files.append({"file": filename, "sha256": sha256(path)})
    return {"index": index, "images": files}


def run_capture(gui, cfg, folder, manifest, confirmed_image=None):
    image, state, progress = wait_ready(gui, cfg)
    if confirmed_image is not None:
        assert_same_selection(confirmed_image,image,selection(cfg))
    for index in range(1, cfg["max_spreads"] + 1):
        # Nur komplett gespeicherte Paare ins Manifest aufnehmen.
        manifest["pairs"].append(save_pair(folder, index, image, cfg))
        write_json(folder / "manifest.json", manifest)
        print(f"Ansicht {index}: {len(capture_rects(cfg))} Bereiche gespeichert; Weiter={state}.", flush=True)
        if state == "disabled":
            if cfg["expected_spreads"] is not None and index != cfg["expected_spreads"]:
                raise StopRun(f"Weiter deaktiviert nach {index} Ansichten; erwartet: {cfg['expected_spreads']}.")
            return
        if navigation(cfg)=="manual":
            if not gui.manual_transition():
                if cfg["expected_spreads"] is not None and index!=cfg["expected_spreads"]:
                    raise StopRun("Manuell beendet vor der erwarteten Ansichtsanzahl.")
                return
            if index==cfg["max_spreads"] or index==cfg["expected_spreads"]:
                raise StopRun("Ansichtslimit erreicht.")
            image,state,progress=wait_ready(gui,cfg)
            continue
        if index == cfg["max_spreads"] or index == cfg["expected_spreads"]:
            raise StopRun("Ansichtslimit erreicht, aber Weiter ist noch aktiv.")
        # Ausgangsbild direkt vor dem Klick muss immer noch passen.
        current = gui.snapshot()
        if difference(content_image(current,cfg),content_image(image,cfg)) > cfg["stable_tolerance"] or difference(progress_image(current,cfg), progress) > cfg["stable_tolerance"]:
            raise StopRun("Ansicht hat sich zwischen Speicherung und Klick veraendert.")
        gui.click_next()  # genau EIN Klick pro bestaetigtem Uebergang
        image, state, progress = wait_ready(gui, cfg, previous=progress)


def build_pdf(folder, manifest, output):
    """Legacy export API. Schema 3 must use the persisted ExportPlan renderer."""
    if manifest.get("schema")==3:
        raise ValueError("Schema 3 erfordert einen gespeicherten ExportPlan.")
    return _render_pdf(folder,manifest,output)


def _render_pdf(folder,manifest,output,selected=None):
    from calibration.exports import readable_manifest, view_images, pdf_options
    readable_manifest(manifest)
    pdf_options(manifest["config"])
    if not manifest["pairs"]:
        return False
    cfg = manifest["config"]
    factor = 72.0 / cfg["pdf_dpi"]
    output = Path(output)
    tmp = output.with_suffix(output.suffix + ".tmp")
    pdf = canvas.Canvas(str(tmp), pageCompression=1)
    pdf.setTitle("RectoFlow Capture")
    for expected_index in (selected if selected is not None else range(1,len(manifest["pairs"])+1)):
        images=view_images(folder,manifest,expected_index)
        if cfg["pdf_layout"] == "spread":
            joined = Image.new("RGB", (sum(im.width for im in images),max(im.height for im in images)), "white")
            offset=0
            for im in images:
                joined.paste(im,(offset,0))
                offset+=im.width
            images = [joined]
        for im in images:
            w, h = im.size
            paper=cfg.get("paper_format","Original")
            pw,ph=(w*factor,h*factor) if paper=="Original" else tuple(v*72/25.4 for v in PAPER_MM[paper])
            if paper!="Original" and cfg.get("paper_orientation","portrait")=="landscape":
                pw,ph=ph,pw
            scale=min(pw/w,ph/h)
            pdf.setPageSize((pw,ph))
            pdf.drawImage(ImageReader(im),(pw-w*scale)/2,(ph-h*scale)/2,width=w*scale,height=h*scale)
            pdf.showPage()
    pdf.save()
    with tmp.open("r+b") as stream:os.fsync(stream.fileno())
    os.replace(tmp, output)
    return True


def main():
    configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version",action="version",version=f"RectoFlow {VERSION}")
    parser.add_argument("--config", type=Path, default=config_root()/"config.json")
    parser.add_argument("--paper",choices=[*PAPER_MM,"Original"],help="Papierformat bei --rebuild; keine Aenderung der Aufnahmebereiche")
    parser.add_argument("--orientation",choices=["portrait","landscape"])
    parser.add_argument("--layout",choices=["separate","spread"])
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--position", action="store_true", help="Mauspositionen anzeigen, keine Klicks")
    modes.add_argument("--preview", action="store_true", help="Bereiche pruefen, keine Weiter-Klicks")
    modes.add_argument("--calibrate", nargs="?", const="interactive", choices=["interactive","enabled","disabled"], help="Interaktive Kalibrierung; enabled/disabled: bisherige Button-Bildvorlagen")
    modes.add_argument("--rebuild", type=Path, metavar="RUN_ORDNER", help="PDF ohne Browsersteuerung neu erzeugen")
    parser.add_argument("--profile",metavar="UUID",help="Gespeichertes Profil verwenden")
    parser.add_argument("--export-plan",type=Path,help="Gespeicherten ExportPlan bei --rebuild verwenden")
    args = parser.parse_args()
    if args.export_plan and (not args.rebuild or any((args.paper,args.orientation,args.layout))):
        parser.error("--export-plan erfordert --rebuild und darf nicht mit Format-Overrides kombiniert werden.")
    if args.rebuild:
        folder = args.rebuild.resolve()
        from calibration.exports import source_snapshot, create_plan, execute_plan
        manifest,manifest_hash=source_snapshot(folder)
        overrides={key:value for key,value in (("paper_format",args.paper),("paper_orientation",args.orientation),("pdf_layout",args.layout)) if value is not None}
        if manifest.get("schema")==3 or args.export_plan:
            plan=args.export_plan or create_plan(folder,options=overrides,expected_manifest_hash=manifest_hash)
            print(execute_plan(folder,plan))
            return 0
        import copy
        manifest=copy.deepcopy(manifest)
        for key,value in (("paper_format",args.paper),("paper_orientation",args.orientation),("pdf_layout",args.layout)):
            if value is not None:
                manifest["config"][key]=value
        suffix = "" if manifest["status"] == "COMPLETE" else "_TEILSTAND"
        output = folder / f"gesamt_neu{suffix}_{uuid.uuid4().hex[:8]}.pdf" if any((args.paper,args.orientation,args.layout)) else folder / f"gesamt_neu{suffix}.pdf"
        if output.exists():
            raise ValueError(f"Datei existiert bereits: {output}")
        if not build_pdf(folder, manifest, output):
            raise ValueError("Keine vollstaendigen Bildpaare vorhanden.")
        print(output)
        return 0
    if any((args.paper,args.orientation,args.layout)):
        parser.error("--paper/--orientation/--layout sind fuer --rebuild. Aufnahmeauswahl in --calibrate aendern.")
    profile_snapshot=None
    if args.profile:
        from calibration.profiles import ProfileStore
        profile_snapshot=ProfileStore(config_root()/"data").snapshot(args.profile)
        config_path=profile_snapshot["config_path"]
        config_bytes=profile_snapshot["config_bytes"]
        cfg=profile_snapshot["config"]
    else:
        from calibration.storage import config_transaction
        config_path = args.config.resolve()
        with config_transaction(config_path):
            config_bytes = config_path.read_bytes()
            cfg = json.loads(config_bytes.decode("utf-8-sig"))
            template_bytes={name:(config_path.parent/name).read_bytes() for name in ("button_enabled.png","button_disabled.png")} if not args.calibrate and cfg["button_mode"]=="template" and navigation(cfg)=="next_button" else {}
    gui = WindowsGUI(cfg, config_path.parent)
    gui.template_bytes={"button_"+key+".png":data for key,data in profile_snapshot["templates"].items()} if profile_snapshot else template_bytes
    if args.calibrate == "interactive":
        from calibration.calibration import calibrate
        return calibrate(gui,cfg,config_path,hashlib.sha256(config_bytes).hexdigest(),validate)
    if args.position:
        print("Maus an gewuenschte Position bewegen. ESC / oben links beendet.")
        while True:
            p = W.POINT()
            gui.user.GetCursorPos(ctypes.byref(p))
            print(f"x={p.x:5d} y={p.y:5d}", end="\r", flush=True)
            gui.pause(0.15)
    validate(cfg, gui.size)
    gui.bind()
    gui.park()
    gui.pause(0.5)
    if args.calibrate in ("enabled","disabled"):
        path = config_path.parent / f"button_{args.calibrate}.png"
        if path.exists():
            raise ValueError(f"Vorlage existiert bereits: {path}. Fuer Neukalibrierung manuell umbenennen.")
        gui.snapshot().crop(box(cfg["button_rect"])).save(path)
        print("Vorlage gespeichert:", path)
        return 0
    output_root = profile_snapshot["output_root"] if profile_snapshot else (config_path.parent / cfg["output_dir"]).resolve()
    folder = output_root / ("run_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    if args.preview:
        image = gui.snapshot()
        save_pair(folder, 1, image, cfg)
        draw = ImageDraw.Draw(image)
        for label, rect in selection(cfg).items():
            color="lime" if label=="NEXT" else "yellow" if label=="PROGRESS" else "red"
            if rect is None:
                continue
            l, t, rr, bb = box(rect)
            draw.rectangle((l, t, rr-1, bb-1), outline=color, width=3)
            draw.text((l+5, t+5), label, fill=color)
        if cfg.get("next_point"):
            px,py=cfg["next_point"]
            draw.line((px-8,py,px+8,py),fill="lime",width=2)
            draw.line((px,py-8,px,py+8),fill="lime",width=2)
        image.save(folder / "vorschau.png")
        gui.prepare_button()
        state = gui.button_state(gui.snapshot())
        print("Button-Zustand:", state, "; Vorschau:", folder / "vorschau.png")
        return 0 if state != "unknown" else 2
    confirmed_image=None
    if "regions" in cfg or cfg.get("calibration",{}).get("requires_visual_confirmation"):
        from calibration.calibration import confirm_capture
        confirmed_image=confirm_capture(gui,cfg)
    manifest = {"schema": 3, "version":VERSION,"status": "RUNNING", "reason": "", "pairs": [], "config": cfg,
                "script_sha256": sha256(Path(__file__)), "started": datetime.now().astimezone().isoformat(),
                "window_title": gui.title(), "screen_size": gui.size,
                "python": sys.version, "platform": platform.platform(),
                "dependencies": {name: importlib.metadata.version(name) for name in ("Pillow", "reportlab", "uiautomation")},
                "config_sha256": hashlib.sha256(config_bytes).hexdigest(),"code_tree":code_identity(),
                "profile":profile_snapshot["profile"] if profile_snapshot else None}
    if cfg["button_mode"] == "template":
        manifest["template_sha256"] = {name:hashlib.sha256(data).hexdigest() for name,data in gui.template_bytes.items()}
    from calibration.storage import exclusive
    from calibration.exports import source_snapshot, create_plan, execute_plan
    exit_code = 2
    with exclusive(folder/".writer.lock"):
        write_json(folder / "manifest.json", manifest)
        try:
            gui.prepare_button()
            run_capture(gui,cfg,folder,manifest,confirmed_image=confirmed_image)
            manifest["status"]="COMPLETE";exit_code=0
        except (Exception, KeyboardInterrupt) as error:
            manifest["status"]="STOPPED";manifest["reason"]=f"{type(error).__name__}: {error}"
            print("ABBRUCH:",manifest["reason"],flush=True)
        finally:
            manifest["finished"]=datetime.now().astimezone().isoformat()
            write_json(folder/"manifest.json",manifest)
    frozen,manifest_hash=source_snapshot(folder)  # capture manifest is now frozen
    try:
        if frozen["pairs"]:
            if cfg.get("confirm_pdf_export",False):
                from calibration.pdf_export import export_dialog
                exported=export_dialog(folder,frozen,build_pdf)
                if exported:print("PDF:",folder/exported["file"])
                else:print("Export aufgeschoben; Originalaufnahmen bleiben erhalten.")
            else:
                plan=create_plan(folder,expected_manifest_hash=manifest_hash)
                print("PDF:",execute_plan(folder,plan))
    except (Exception,KeyboardInterrupt) as error:
        exit_code=2;print("PDF fehlgeschlagen; Capture bleibt eingefroren:",error,flush=True)
    print("Status:",frozen["status"],"; Ordner:",folder,flush=True)
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(f"STOPP: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(2)
