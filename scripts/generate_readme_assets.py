"""Render real Tk client windows with synthetic data, never acquire the desktop."""
import argparse
import ctypes
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, font
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from calibration.screenshot_picker import RectanglePicker
from calibration.pdf_export import export_dialog
from calibration.regions import image_names
from calibration.exports import analyze_view

NAMES = ('rectoflow-calibration.png', 'rectoflow-review.png')
BANNER = 'SYNTHETIC DEMO - real RectoFlow UI / not browser or DPI verification'
REGIONS = [[36, 100, 440, 340], [520, 100, 440, 340]]


def document(page=1):
    image = Image.new('RGB', (1000, 560), '#e8edf3')
    draw = ImageDraw.Draw(image)
    face = ImageFont.load_default(size=24)
    small = ImageFont.load_default(size=16)
    draw.text((36, 25), 'Synthetic Document - local demo content', fill='#203b53', font=face)
    for side, rect in zip(('A', 'B'), REGIONS):
        x, y, width, height = rect
        draw.rectangle((x, y, x+width-1, y+height-1), fill='white', outline='#7894b0', width=3)
        draw.text((x+24, y+45), f'Page {page:02d} / {side}', fill='#203b53', font=face)
        draw.text((x+24, y+95), 'Demo content - no real document', fill='#46617a', font=small)
        for row in range(6):
            draw.rectangle((x+24, y+145+row*23, x+width-35-(row%3)*25, y+152+row*23), fill='#c5d4e4')
        draw.rectangle((x+24, y+298, x+width-25, y+316), fill=('#397fbd' if page == 1 else '#bc7641'))
    draw.rectangle((36, 475, 270, 515), fill='white', outline='#7894b0')
    draw.text((48, 484), f'View {page:02d} / 03', fill='#203b53', font=small)
    draw.rectangle((790, 475, 960, 525), fill='#287645')
    draw.text((835, 490), 'Weiter', fill='white', font=small)
    return image


def style(root):
    root.tk.call('tk', 'scaling', 1.0)
    ttk.Style(root).theme_use('clam')
    for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont', 'TkCaptionFont'):
        font.nametofont(name, root=root).configure(family='Arial', size=10)


def banner(root):
    children = root.winfo_children()
    label = ttk.Label(root, text=BANNER, padding=8, foreground='#284e76')
    label.pack(side='top', fill='x', before=children[0] if children else None)


def widgets(root):
    yield root
    for child in root.winfo_children():
        yield from widgets(child)


def render_client(root, path):
    """PrintWindow asks only this process's own client to paint into a memory DC."""
    user = ctypes.WinDLL('user32', use_last_error=True)
    gdi = ctypes.WinDLL('gdi32', use_last_error=True)
    user.GetAncestor.argtypes = [W.HWND, W.UINT]; user.GetAncestor.restype = W.HWND
    user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    user.GetClientRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
    user.GetDC.argtypes = [W.HWND]; user.GetDC.restype = W.HDC
    user.ReleaseDC.argtypes = [W.HWND, W.HDC]
    user.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]; user.PrintWindow.restype = W.BOOL
    gdi.CreateCompatibleDC.argtypes = [W.HDC]; gdi.CreateCompatibleDC.restype = W.HDC
    gdi.CreateCompatibleBitmap.argtypes = [W.HDC, ctypes.c_int, ctypes.c_int]; gdi.CreateCompatibleBitmap.restype = W.HBITMAP
    gdi.SelectObject.argtypes = [W.HDC, W.HANDLE]; gdi.SelectObject.restype = W.HANDLE
    gdi.DeleteObject.argtypes = [W.HANDLE]; gdi.DeleteDC.argtypes = [W.HDC]
    gdi.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, ctypes.c_void_p, ctypes.c_void_p, W.UINT]
    class Header(ctypes.Structure):
        _fields_ = [('size', W.DWORD), ('width', W.LONG), ('height', W.LONG), ('planes', W.WORD),
                    ('bits', W.WORD), ('compression', W.DWORD), ('image_size', W.DWORD),
                    ('xppm', W.LONG), ('yppm', W.LONG), ('used', W.DWORD), ('important', W.DWORD)]
    import os
    root.update_idletasks()
    hwnd = user.GetAncestor(root.winfo_id(), 2)
    pid = W.DWORD(); user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value != os.getpid():
        raise RuntimeError('Refusing any window outside the demo process')
    rect = W.RECT()
    if not user.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError(ctypes.get_last_error())
    width, height = rect.right, rect.bottom
    if (width, height) != (root.winfo_width(), root.winfo_height()):
        raise RuntimeError('Unexpected client/DPI dimensions')
    dc = user.GetDC(hwnd); memory = gdi.CreateCompatibleDC(dc)
    bitmap = gdi.CreateCompatibleBitmap(dc, width, height)
    old = gdi.SelectObject(memory, bitmap)
    try:
        if not user.PrintWindow(hwnd, memory, 3):
            raise RuntimeError('Own client rendering failed')
        gdi.SelectObject(memory, old)
        header = Header(ctypes.sizeof(Header), width, -height, 1, 32, 0, width*height*4, 0, 0, 0, 0)
        pixels = ctypes.create_string_buffer(width*height*4)
        if gdi.GetDIBits(memory, bitmap, 0, height, pixels, ctypes.byref(header), 0) != height:
            raise RuntimeError('Own client pixel read failed')
        image = Image.frombytes('RGB', (width, height), pixels.raw, 'raw', 'BGRX')
        if image.getextrema() == ((0, 0), (0, 0), (0, 0)):
            raise RuntimeError('Blank client render')
        image.save(path, format='PNG', compress_level=9)
    finally:
        gdi.SelectObject(memory, old); gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory); user.ReleaseDC(hwnd, dc)


def calibration_asset(output):
    root = tk.Tk(); root.withdraw(); style(root)
    actual_top = tk.Toplevel
    def normal(master):
        window = actual_top(master)
        native_state = window.state
        window.state = lambda value=None: native_state('normal' if value == 'zoomed' else value) if value else native_state()
        return window
    try:
        rects = {'REGION_001': REGIONS[0], 'REGION_002': REGIONS[1],
                 'NEXT': [790, 475, 170, 50], 'PROGRESS': [36, 475, 234, 40]}
        with patch('calibration.screenshot_picker.tk.Toplevel', side_effect=normal):
            picker = RectanglePicker(root, document(), rects, [875, 500], [0, 0, 1000, 560], final=True)
        picker.window.geometry('1280x820+0+0'); banner(picker.window)
        picker.window.update(); picker.render(); picker.window.update()
        assert len(picker.handles(REGIONS[0])) == 8
        assert picker.selector['values'] == ('Bereich 1', 'Bereich 2', 'Weiter-Button', 'Fortschritt')
        render_client(picker.window, output / NAMES[0])
        picker.cancel()
    finally:
        root.destroy()


def review_fixture(folder):
    # Deliberately no user config, capture engine, timestamps or runtime output directory.
    cfg = {'regions': REGIONS, 'paper_format': 'A5', 'paper_orientation': 'landscape', 'pdf_layout': 'separate'}
    pairs = []
    for index, page in enumerate((1, 1, 3), 1):
        image = document(page); entries = []
        for name, rect in zip(image_names(cfg, index), REGIONS):
            x, y, width, height = rect
            crop = image.crop((x, y, x+width, y+height))
            path = folder / name; crop.save(path, format='PNG')
            entries.append({'file': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        pairs.append({'index': index, 'images': entries})
    manifest = {'schema': 3, 'version': '0.2.0', 'status': 'COMPLETE', 'finished': 'synthetic-demo-only',
                'profile': None, 'config': cfg, 'pairs': pairs}
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    assert analyze_view(folder, manifest, 2)['similarity'] == 1.0
    assert analyze_view(folder, manifest, 3)['similarity'] < .995
    return manifest


def review_asset(output):
    actual_tk = tk.Tk; errors = []
    with tempfile.TemporaryDirectory(prefix='rectoflow-synthetic-demo-') as temporary:
        folder = Path(temporary); manifest = review_fixture(folder)
        originals = {p.name: p.read_bytes() for p in folder.iterdir()}
        def own_root():
            root = actual_tk(); style(root)
            def drive():
                try:
                    root.geometry('1080x780+0+0'); banner(root); root.update()
                    listing = next(w for w in widgets(root) if isinstance(w, ttk.Treeview))
                    for index in ('1', '3', '2'):
                        listing.selection_set(index); listing.focus(index)
                        listing.event_generate('<<TreeviewSelect>>'); root.update_idletasks()
                    assert 'Aehnlich' in str(listing.item('2', 'values'))
                    assert 'Geprueft' in str(listing.item('3', 'values'))
                    assert any(isinstance(w, ttk.Button) and w.cget('text') == 'PDF bestaetigen und erstellen' for w in widgets(root))
                    render_client(root, output / NAMES[1])
                except BaseException as error:
                    errors.append(error)
                finally:
                    root.destroy()
            root.after(150, drive)
            return root
        with patch('calibration.pdf_export.tk.Tk', side_effect=own_root):
            assert export_dialog(folder, manifest, None) is None
        if errors:
            raise errors[0]
        assert {p.name: p.read_bytes() for p in folder.iterdir()} == originals


def generate(output):
    if sys.platform != 'win32':
        raise RuntimeError('Demo rendering requires a native Windows Tk desktop')
    user = ctypes.WinDLL('user32')
    user.SetProcessDpiAwarenessContext.argtypes = [W.HANDLE]
    user.SetProcessDpiAwarenessContext(W.HANDLE(-4))
    output.mkdir(parents=True, exist_ok=True)
    calibration_asset(output); review_asset(output)
    for name in NAMES:
        with Image.open(output / name) as image:
            image.verify()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs' / 'assets')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix='rectoflow-demo-check-') as temporary:
            a, b = Path(temporary) / 'a', Path(temporary) / 'b'
            generate(a); generate(b)
            assert set(p.name for p in a.iterdir()) == set(NAMES)
            for name in NAMES:
                assert (a / name).read_bytes() == (b / name).read_bytes(), f'Non-repeatable: {name}'
                with Image.open(ROOT / 'docs' / 'assets' / name) as image:
                    image.verify()
        print('README_ASSETS_CHECK_PASS: two real-component renders byte-identical; PNGs valid; no capture/export; temporary fixtures closed.')
    else:
        generate(args.output)
        print('README_ASSETS_GENERATED: ' + str(args.output))


if __name__ == '__main__':
    main()
