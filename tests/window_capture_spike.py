"""Isolated PrintWindow qualification on the existing owned Edge fixture.

Private pixels stay below .build-window-spike. The report contains only numbers.
This module is never imported by the product or its frozen executable.
"""
import ctypes
from ctypes import wintypes as W
import json
from pathlib import Path
import sys
import time
import uuid
import tkinter as tk
from unittest.mock import patch
from PIL import Image, ImageStat, ImageChops

import edge_fixture_smoke as fixture
import edge_capture as core


def print_window(hwnd, flags=2):
    user=ctypes.WinDLL("user32",use_last_error=True);gdi=ctypes.WinDLL("gdi32",use_last_error=True)
    user.GetWindowRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)];user.GetWindowRect.restype=W.BOOL
    user.GetDC.argtypes=[W.HWND];user.GetDC.restype=W.HDC
    user.ReleaseDC.argtypes=[W.HWND,W.HDC];user.ReleaseDC.restype=ctypes.c_int
    user.PrintWindow.argtypes=[W.HWND,W.HDC,W.UINT];user.PrintWindow.restype=W.BOOL
    gdi.CreateCompatibleDC.argtypes=[W.HDC];gdi.CreateCompatibleDC.restype=W.HDC
    gdi.CreateCompatibleBitmap.argtypes=[W.HDC,ctypes.c_int,ctypes.c_int];gdi.CreateCompatibleBitmap.restype=W.HBITMAP
    gdi.SelectObject.argtypes=[W.HDC,W.HANDLE];gdi.SelectObject.restype=W.HANDLE
    gdi.DeleteObject.argtypes=[W.HANDLE];gdi.DeleteObject.restype=W.BOOL
    gdi.DeleteDC.argtypes=[W.HDC];gdi.DeleteDC.restype=W.BOOL
    class Header(ctypes.Structure):
        _fields_=[("size",W.DWORD),("width",W.LONG),("height",W.LONG),("planes",W.WORD),
                  ("bits",W.WORD),("compression",W.DWORD),("image_size",W.DWORD),
                  ("x",W.LONG),("y",W.LONG),("used",W.DWORD),("important",W.DWORD)]
    gdi.GetDIBits.argtypes=[W.HDC,W.HBITMAP,W.UINT,W.UINT,ctypes.c_void_p,ctypes.POINTER(Header),W.UINT]
    gdi.GetDIBits.restype=ctypes.c_int
    rect=W.RECT()
    if not user.GetWindowRect(hwnd,ctypes.byref(rect)):raise ctypes.WinError(ctypes.get_last_error())
    width,height=rect.right-rect.left,rect.bottom-rect.top
    source=user.GetDC(hwnd);dest=gdi.CreateCompatibleDC(source);bitmap=gdi.CreateCompatibleBitmap(source,width,height)
    if not source or not dest or not bitmap:raise RuntimeError("Native bitmap allocation failed")
    old=gdi.SelectObject(dest,bitmap)
    try:
        started=time.monotonic();accepted=bool(user.PrintWindow(hwnd,dest,flags));elapsed=time.monotonic()-started
        gdi.SelectObject(dest,old);old=None
        header=Header(ctypes.sizeof(Header),width,-height,1,32,0,0,0,0,0,0)
        pixels=ctypes.create_string_buffer(width*height*4)
        if gdi.GetDIBits(dest,bitmap,0,height,pixels,ctypes.byref(header),0)!=height:raise ctypes.WinError(ctypes.get_last_error())
        return Image.frombytes("RGB",(width,height),pixels.raw,"raw","BGRX"),dict(api_accepted=accepted,seconds=elapsed,flags=flags)
    finally:
        if old:gdi.SelectObject(dest,old)
        gdi.DeleteObject(bitmap);gdi.DeleteDC(dest);user.ReleaseDC(hwnd,source)


def main():
    root=Path(core.__file__).parent;private=root/".build-window-spike"/uuid.uuid4().hex;private.mkdir(parents=True)
    report=dict(subject=core.code_identity(),producer_role="BUILDER",surface="owned local Edge fixture; fresh guest profile",samples=[],
                unproven=["real Klett rendering","other DPI/zoom settings","other Windows versions","Windows Graphics Capture implementation","frozen HWND backend"],
                recommendation="Retain ImageGrab. HWND backend not qualified across required states.")
    original=core.WindowsGUI.snapshot
    sampled=set()
    actual_server=fixture.ThreadingHTTPServer
    inspect=fixture.inspect_window
    native_sampled=False
    extra=b'''<canvas id="spike2d" width="100" height="60" style="position:fixed;right:20px;bottom:20px"></canvas>
<canvas id="spikegl" width="100" height="60" style="position:fixed;right:140px;bottom:20px"></canvas>
<script>const c=document.getElementById('spike2d').getContext('2d');c.fillStyle='rgb(211,5,181)';c.fillRect(0,0,100,60);
const gl=document.getElementById('spikegl').getContext('webgl');if(gl){gl.clearColor(5/255,181/255,211/255,1);gl.clear(gl.COLOR_BUFFER_BIT);}</script>'''
    def server(address,handler):
        class Enhanced(handler):
            def do_GET(self):
                original_stream=self.wfile
                class Stream:
                    def write(_,data):return original_stream.write(data+extra if data.startswith(b"<!doctype") else data)
                    def __getattr__(_,name):return getattr(original_stream,name)
                self.wfile=Stream()
                try:return super().do_GET()
                finally:self.wfile=original_stream
        return actual_server(address,Enhanced)
    def inspect_owned(gui,hwnd):
        nonlocal native_sampled
        selected=inspect(gui,hwnd)
        if not native_sampled and selected["ready"]:
            native_sampled=True
            time.sleep(1)
            live=inspect(gui,hwnd)
            if any(live[key]!=selected[key] for key in ("identity","exe","environment")):
                raise RuntimeError("Owned fixture changed before native-only sampling")
            # No foreground assumption and no desktop image: only this owned HWND.
            for flags in (0,2):
                for repeat in range(3):
                    candidate,metadata=print_window(hwnd,flags)
                    candidate.save(private/f"native-only-{flags}-{repeat}.png")
                    pixels=dict((color,count) for count,color in candidate.getcolors(candidate.width*candidate.height) or [])
                    report["samples"].append(dict(**metadata,state="native-only-visible",repeat=repeat,dpi=live["environment"]["dpi"],
                        width=candidate.width,height=candidate.height,fixture_color_pixels=pixels.get((239,17,19),0),
                        canvas_pixels=pixels.get((211,5,181),0),webgl_pixels=pixels.get((5,181,211),0),black_pixels=pixels.get((0,0,0),0)))
            cover=tk.Tk();cover.overrideredirect(True);cover.configure(background="#133751");cover.attributes("-topmost",True)
            l,t,r,b=live["environment"]["window_bounds"];cover.geometry(f"{r-l}x{b-t}+{max(0,l)}+{max(0,t)}");cover.update();time.sleep(.3)
            try:
                candidate,metadata=print_window(hwnd,2);candidate.save(private/"native-only-covered.png")
                pixels=dict((color,count) for count,color in candidate.getcolors(candidate.width*candidate.height) or [])
                report["samples"].append(dict(**metadata,state="native-only-occluded",width=candidate.width,height=candidate.height,fixture_color_pixels=pixels.get((239,17,19),0),canvas_pixels=pixels.get((211,5,181),0),webgl_pixels=pixels.get((5,181,211),0)))
            finally:cover.destroy()
            gui.user.ShowWindow.argtypes=[W.HWND,ctypes.c_int];gui.user.ShowWindow.restype=W.BOOL
            gui.user.ShowWindow(hwnd,6);time.sleep(.3)
            try:
                candidate,metadata=print_window(hwnd,2);candidate.save(private/"native-only-minimized.png")
                pixels=dict((color,count) for count,color in candidate.getcolors(candidate.width*candidate.height) or [])
                report["samples"].append(dict(**metadata,state="native-only-minimized",width=candidate.width,height=candidate.height,fixture_color_pixels=pixels.get((239,17,19),0)))
            finally:gui.user.ShowWindow(hwnd,9)
        return selected
    def snapshot(gui,*args,**kwargs):
        screen=original(gui,*args,**kwargs)
        colors=((239,17,19),(17,19,239),(239,131,17))
        rect=gui.initial_geometry
        baseline=screen.crop(rect)
        hist=dict((color,count) for count,color in baseline.getcolors(baseline.width*baseline.height) or [])
        page=next((color for color in colors if hist.get(color,0)>1000),None)
        if page is None or page in sampled:return screen
        sampled.add(page)
        # Compare only the retained own window. Never save the full desktop image.
        for flags in (0,2):
            for repeat in range(3):
                candidate,metadata=print_window(gui.hwnd,flags)
                candidate.save(private/f"window-{len(report['samples'])}.png")
                pixels=dict((color,count) for count,color in candidate.getcolors(candidate.width*candidate.height) or [])
                report["samples"].append(dict(**metadata,state="visible",page_rgb=list(page),repeat=repeat,dpi=gui.bound_environment["dpi"],
                    width=candidate.width,height=candidate.height,fixture_color_pixels=pixels.get(page,0),
                    baseline_color_pixels=hist[page],black_pixels=pixels.get((0,0,0),0),
                    canvas_pixels=pixels.get((211,5,181),0),baseline_canvas_pixels=hist.get((211,5,181),0),
                    webgl_pixels=pixels.get((5,181,211),0),baseline_webgl_pixels=hist.get((5,181,211),0),
                    mean_pixel_difference=sum(ImageStat.Stat(ImageChops.difference(candidate,baseline)).mean)/3))
        if len(sampled)==1:
            cover=tk.Tk();cover.configure(background="#133751");cover.overrideredirect(True);cover.attributes("-topmost",True)
            l,t,r,b=rect;cover.geometry(f"{r-l}x{b-t}+{max(0,l)}+{max(0,t)}");cover.update();time.sleep(.3)
            try:
                candidate,metadata=print_window(gui.hwnd,2)
                pixels=dict((color,count) for count,color in candidate.getcolors(candidate.width*candidate.height) or [])
                candidate.save(private/"covered-window.png")
                report["samples"].append(dict(**metadata,state="occluded-by-owned-window",fixture_color_pixels=pixels.get(page,0),baseline_color_pixels=hist[page],width=candidate.width,height=candidate.height))
            finally:cover.destroy();gui.activate_target()
            gui.user.ShowWindow.argtypes=[W.HWND,ctypes.c_int];gui.user.ShowWindow.restype=W.BOOL
            gui.user.ShowWindow(gui.hwnd,6);time.sleep(.3)
            try:
                candidate,metadata=print_window(gui.hwnd,2)
                pixels=dict((color,count) for count,color in candidate.getcolors(candidate.width*candidate.height) or [])
                candidate.save(private/"minimized-window.png")
                report["samples"].append(dict(**metadata,state="minimized",fixture_color_pixels=pixels.get(page,0),baseline_color_pixels=hist[page],width=candidate.width,height=candidate.height))
            finally:gui.user.ShowWindow(gui.hwnd,9);gui.activate_target()
        return screen
    try:
        with patch.object(core.WindowsGUI,"snapshot",snapshot),patch.object(fixture,"ThreadingHTTPServer",server),patch.object(fixture,"inspect_window",inspect_owned):fixture.main()
        report["owned_edge_capture_navigation"]="PASS"
    except Exception as error:
        report["owned_edge_capture_navigation"]="BLOCKED"
        report["error_type"]=type(error).__name__
        raise
    finally:
        (private/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print("PRIVATE_SPIKE_REPORT: "+str(private/"report.json"),flush=True)


if __name__=="__main__":main()
