"""Opt-in native Edge composition on an owned local fixture and fresh profile.

Never adopt another browser session, inspect user pages, or change desktop DPI.
Run manually on an interactive native Windows host; not part of headless CI.
"""
import ctypes
from ctypes import wintypes as W
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import edge_capture as core
from calibration.window_picker import inspect_window
from calibration.dom_picker import marker_bounds
from calibration.exports import create_plan,execute_plan


def main():
    edge=Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    if not edge.exists():raise RuntimeError("Edge fehlt am geprueften Installationspfad.")
    token=uuid.uuid4().hex;title="RectoFlow-owned-fixture-"+token
    folder=ROOT/".build-edge-fixture"/token;folder.mkdir(parents=True)
    events=[]
    html=('''<!doctype html><meta charset="utf-8"><title>'''+title+'''</title>
<style>body{margin:30px;background:white}#left,#right{display:inline-block;width:150px;height:180px;background:rgb(239,17,19);margin-right:30px}
button{display:block;width:100px;height:60px;background:rgb(17,239,19);border:0;margin:30px 0}button:disabled{background:rgb(131,17,239)}</style>
<div id="left"></div><div id="right"></div><button id="next">Weiter</button>
<script>let page=1;const button=document.getElementById('next');button.onclick=()=>{page++;document.getElementById('left').style.background=page===2?'rgb(17,19,239)':'rgb(239,131,17)';document.getElementById('right').style.background=page===2?'rgb(17,19,239)':'rgb(239,131,17)';button.disabled=page===3;fetch('/event/'+page)};</script>''').encode()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/event/"):events.append(self.path)
            self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.end_headers();self.wfile.write(html)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    proc=subprocess.Popen([str(edge),"--guest","--user-data-dir="+str(folder/"profile"),"--no-first-run","--no-default-browser-check",
        "--disable-features=msEdgeSidebarV2","--new-window","--window-position=0,0","--window-size=1000,900",f"http://127.0.0.1:{server.server_port}/{token}"])
    mode="uia" if "--uia" in sys.argv else "template"
    cfg=json.loads((ROOT/"config.json").read_bytes());cfg.update(start_delay=.1,stable_seconds=.4,disabled_seconds=.5,min_after_click=.5,timeout_seconds=12,max_spreads=5,expected_spreads=3,confirm_pdf_export=False,button_mode=mode)
    gui=core.WindowsGUI(cfg,folder);hwnd=None
    try:
        callback_type=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        gui.user.EnumWindows.argtypes=[callback_type,W.LPARAM]
        deadline=time.monotonic()+20
        while hwnd is None and time.monotonic()<deadline:
            matches=[]
            def visit(candidate,_):
                text=ctypes.create_unicode_buffer(4096);pid=W.DWORD()
                gui.user.GetWindowTextW(candidate,text,len(text));gui.user.GetWindowThreadProcessId(candidate,ctypes.byref(pid))
                if title in text.value and pid.value==proc.pid:matches.append(candidate)
                return True
            cb=callback_type(visit);gui.user.EnumWindows(cb,0)
            if len(matches)==1:hwnd=matches[0]
            else:time.sleep(.2)
        if hwnd is None:raise RuntimeError("Eigenes Edge-Fenster nicht eindeutig an gestartete PID bindbar.")
        selected=inspect_window(gui,hwnd)
        if not selected["ready"]:raise RuntimeError(selected["reason"])
        with patch("calibration.window_picker.choose_window",return_value=selected):gui.bind(check_config=False,check_calibration=False)
        gui.pause(1)
        first=gui.snapshot(areas=False)
        r=marker_bounds(first,[239,17,19]);button=marker_bounds(first,[17,239,19])
        if r is None or button is None:
            l,t,rr,b=gui.initial_geometry
            first.crop((max(0,l),max(0,t),min(gui.size[0],rr),min(gui.size[1],b))).save(folder/"fixture-window.png")
            raise RuntimeError("Fixture-Farbbereiche fehlen; nur eigenes Fenster gespeichert: "+str(folder/"fixture-window.png"))
        left,top,right,bottom=r;middle=(left+right)//2
        # White gap separates the two rectangles; use exact physical color runs.
        row=[x for x in range(left,right) if first.getpixel((x,(top+bottom)//2))==(239,17,19)]
        cut=next(i for i in range(1,len(row)) if row[i]>row[i-1]+1)
        cfg["regions"]=[[row[0],top,row[cut-1]-row[0]+1,bottom-top],[row[cut],top,row[-1]-row[cut]+1,bottom-top]]
        l,t,rr,b=button;cfg["button_rect"]=[l,t,rr-l,b-t];cfg["next_point"]=[(l+rr)//2,(t+b)//2]
        cfg["park_point"]=[max(5,selected["environment"]["window_bounds"][0]+15),max(5,selected["environment"]["window_bounds"][1]+15)]
        core.validate(cfg,gui.size)
        gui.enabled=first.crop(core.box(cfg["button_rect"]))
        from PIL import Image
        gui.disabled=Image.new("RGB",gui.enabled.size,(131,17,239))
        if mode=="uia":gui.prepare_button()
        gui.park();gui.pause(.2)
        cfg["calibration"]={"schema":1,"coordinate_space":"primary_screen_physical_pixels","target":gui.target_metadata()}
        run=folder/"run";run.mkdir()
        manifest={"schema":3,"version":core.VERSION,"status":"RUNNING","config":cfg,"pairs":[],"profile":None}
        core.run_capture(gui,cfg,run,manifest)
        manifest.update(status="COMPLETE",finished="fixture-complete");core.write_json(run/"manifest.json",manifest)
        output=execute_plan(run,create_plan(run))
        if len(manifest["pairs"])!=3 or events!=["/event/2","/event/3"]:raise AssertionError("Capture/input order incorrect.")
        receipt={"status":"PASS","fixture":"owned local HTTP + fresh Edge guest profile","button_mode":mode,"code_tree":core.code_identity(),
                 "views":3,"regions":2,"next_events":events,"dpi":gui.bound_environment["dpi"],"pdf_sha256":core.sha256(output),
                 "not_established":["other browsers","other physical DPI settings","interactive picker/owner acceptance"]}
        core.write_json(folder/"receipt.json",receipt)
        print(json.dumps(receipt,indent=2))
    finally:
        # Only our retained process handle/window, never terminate all browser processes.
        if hwnd and gui.user.IsWindow(hwnd) and gui.process_identity()[0]==proc.pid:
            gui.user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
            gui.user.PostMessageW(hwnd,0x10,0,0)
        server.shutdown();server.server_close()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=10)


if __name__=="__main__":main()
