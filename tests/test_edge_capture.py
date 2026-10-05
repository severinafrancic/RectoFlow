import importlib.util
import json
from pathlib import Path
import sys
import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(os.environ.get("EDGE_CAPTURE_TEST_TMP", str(ROOT / "test-work")))
SCRATCH.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT))
spec = importlib.util.spec_from_file_location("capture", ROOT / "edge_capture.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def config():
    c = json.loads((ROOT / "config.json").read_text())
    c.pop("regions",None)  # regress the original two-region config contract
    c.update(left_rect=[10, 10, 40, 60], button_rect=[100, 20, 30, 20],
             next_point=[115, 30], park_point=[5, 5], poll_seconds=0.25,
             stable_seconds=0.5, disabled_seconds=1.0, min_after_click=0.5,
             timeout_seconds=5, max_spreads=10)
    return c


def picture(left="red", right="blue", indicator="white"):
    im = Image.new("RGB", (150, 100), "white")
    im.paste(left, (10, 10, 50, 70))
    im.paste(right, (50, 10, 90, 70))
    im.paste(indicator, (100, 80, 120, 90))
    return im


class FakeGUI:
    def __init__(self, phases):
        self.phases = phases
        self.phase = 0
        self.now = 0
        self.clicks = 0
        self.poll = 0

    def clock(self):
        return self.now

    def snapshot(self):
        return self.phases[self.phase][0]

    def button_state(self, image):
        state = self.phases[self.phase][1]
        return state(self.now) if callable(state) else state

    def guard(self):
        pass

    def pause(self, seconds):
        self.now += seconds

    def click_next(self):
        self.clicks += 1
        self.phase = min(self.phase + 1, len(self.phases) - 1)


class CaptureTests(unittest.TestCase):
    def wait(self, gui, cfg, previous=None):
        return m.wait_ready(gui, cfg, previous, clock=gui.clock)

    def test_config_rejects_offscreen_second_region(self):
        c = config()
        c["left_rect"] = [100, 10, 40, 60]
        with self.assertRaises(ValueError):
            m.validate(c, (150, 100))

    def test_config_rejects_parking_in_capture(self):
        c = config()
        c["park_point"] = [15, 15]
        with self.assertRaises(ValueError):
            m.validate(c, (150, 100))

    def test_disabled_initial_last_page_is_captured(self):
        c = config()
        gui = FakeGUI([(picture(), "disabled")])
        im, state, progress = self.wait(gui, c)
        self.assertEqual(state, "disabled")
        self.assertGreaterEqual(gui.now, c["disabled_seconds"])

    def test_no_change_after_click_times_out(self):
        c = config()
        gui = FakeGUI([(picture(), "enabled")])
        previous = picture().crop(m.box(m.spread_rect(c)))
        with self.assertRaises(m.StopRun):
            self.wait(gui, c, previous)
        self.assertEqual(gui.clicks, 0)

    def test_disabled_unchanged_after_click_is_not_success(self):
        c = config()
        gui = FakeGUI([(picture(), "disabled")])
        previous = picture().crop(m.box(m.spread_rect(c)))
        with self.assertRaises(m.StopRun):
            self.wait(gui, c, previous)

    def test_unknown_button_does_not_mean_end(self):
        gui = FakeGUI([(picture(), "unknown")])
        with self.assertRaises(m.StopRun):
            self.wait(gui, config())

    def test_temporary_disabled_button_is_waited_out(self):
        gui = FakeGUI([(picture(), lambda t: "disabled" if t < 0.5 else "enabled")])
        _, state, _ = self.wait(gui, config())
        self.assertEqual(state, "enabled")
        self.assertGreaterEqual(gui.now, 1.0)

    def test_identical_content_with_changed_page_indicator(self):
        c = config()
        c["progress_rect"] = [100, 80, 20, 10]
        gui = FakeGUI([(picture(indicator="black"), "disabled")])
        previous = picture(indicator="white").crop(m.box(c["progress_rect"]))
        _, state, _ = self.wait(gui, c, previous)
        self.assertEqual(state, "disabled")

    def test_loading_placeholder_returns_to_baseline_not_new_page(self):
        c = config()
        gui = FakeGUI([(picture(), "enabled")])
        gui.snapshot = lambda: picture("black", "black") if gui.now < 0.25 else picture()
        previous = picture().crop(m.box(m.spread_rect(c)))
        with self.assertRaises(m.StopRun):
            self.wait(gui, c, previous)

    def test_nearly_equal_templates_are_unknown(self):
        a = Image.new("RGB", (10, 10), (100, 100, 100))
        b = Image.new("RGB", (10, 10), (101, 101, 101))
        self.assertEqual(m.template_state(a, a, b, 5, 3), "unknown")

    def test_templates_classify_both_states(self):
        a = Image.new("RGB", (10, 10), "black")
        b = Image.new("RGB", (10, 10), "white")
        self.assertEqual(m.template_state(a, a, b, 5, 3), "enabled")
        self.assertEqual(m.template_state(b, a, b, 5, 3), "disabled")

    def execute(self, c, phases, folder):
        gui = FakeGUI(phases)
        manifest = {"pairs": [], "config": c}
        old_wait = m.wait_ready
        m.wait_ready = lambda g, cfg, previous=None: old_wait(g, cfg, previous, clock=g.clock)
        try:
            m.run_capture(gui, c, folder, manifest)
        finally:
            m.wait_ready = old_wait
        return gui, manifest

    def test_complete_flow_captures_final_page_and_left_right_order(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            folder = Path(tmp)
            gui, manifest = self.execute(config(), [(picture(), "enabled"),
                                        (picture("green", "yellow"), "disabled")], folder)
            self.assertEqual(gui.clicks, 1)
            self.assertEqual(len(manifest["pairs"]), 2)
            self.assertEqual([x["file"] for x in manifest["pairs"][0]["images"]],
                             ["000001_left.png", "000001_right.png"])
            with Image.open(folder / "000001_right.png") as im:
                self.assertEqual(im.getpixel((0, 0)), (0, 0, 255))
            m.build_pdf(folder, manifest, folder / "separate.pdf")
            self.assertEqual(len(PdfReader(folder / "separate.pdf").pages), 4)
            manifest["config"]["pdf_layout"] = "spread"
            m.build_pdf(folder, manifest, folder / "spread.pdf")
            pdf = PdfReader(folder / "spread.pdf")
            self.assertEqual(len(pdf.pages), 2)
            self.assertAlmostEqual(float(pdf.pages[0].mediabox.width), 48)

    def test_no_retry_or_duplicate_capture_after_failed_navigation(self):
        c = config()
        gui = FakeGUI([(picture(), "enabled")])
        manifest = {"pairs": [], "config": c}
        old_wait = m.wait_ready
        m.wait_ready = lambda g, cfg, previous=None: old_wait(g, cfg, previous, clock=g.clock)
        try:
            with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
                with self.assertRaises(m.StopRun):
                    m.run_capture(gui, c, Path(tmp), manifest)
                self.assertEqual(gui.clicks, 1)
                self.assertEqual(len(manifest["pairs"]), 1)
        finally:
            m.wait_ready = old_wait

    def test_expected_count_mismatch_fails(self):
        c = config()
        c["expected_spreads"] = 2
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            with self.assertRaises(m.StopRun):
                self.execute(c, [(picture(), "disabled")], Path(tmp))

    def test_max_limit_does_not_click_again(self):
        c = config()
        c["max_spreads"] = 1
        gui = FakeGUI([(picture(), "enabled")])
        manifest = {"pairs": [], "config": c}
        old_wait = m.wait_ready
        m.wait_ready = lambda g, cfg, previous=None: old_wait(g, cfg, previous, clock=g.clock)
        try:
            with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
                with self.assertRaises(m.StopRun):
                    m.run_capture(gui, c, Path(tmp), manifest)
                self.assertEqual(gui.clicks, 0)
        finally:
            m.wait_ready = old_wait

    def test_corrupt_image_is_rejected_and_no_final_pdf_appears(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            folder = Path(tmp)
            _, manifest = self.execute(config(), [(picture(), "disabled")], folder)
            (folder / "000001_left.png").write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                m.build_pdf(folder, manifest, folder / "bad.pdf")
            self.assertFalse((folder / "bad.pdf").exists())

    def test_reversed_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            folder = Path(tmp)
            _, manifest = self.execute(config(), [(picture(), "disabled")], folder)
            manifest["pairs"][0]["images"].reverse()
            with self.assertRaises(ValueError):
                m.build_pdf(folder, manifest, folder / "bad.pdf")

    def test_uia_queries_current_control_each_time(self):
        class Rect:
            left, top, right, bottom = 100, 20, 130, 40
        class Top:
            NativeWindowHandle = 123
        class Control:
            ControlTypeName = "ButtonControl"
            IsOffscreen = False
            Name = "Weiter"
            BoundingRectangle = Rect()
            def GetTopLevelControl(self):
                return Top()
        enabled = Control()
        enabled.IsEnabled = True
        disabled = Control()
        disabled.IsEnabled = False
        gui = m.WindowsGUI.__new__(m.WindowsGUI)
        gui.cfg, gui.hwnd = config(), 123
        gui.cfg["button_name"] = "Weiter"
        from unittest.mock import Mock
        gui.auto = Mock()
        gui.auto.ControlFromPoint.side_effect = [enabled, disabled]
        self.assertEqual(gui.button_state(picture()), "enabled")
        self.assertEqual(gui.button_state(picture()), "disabled")
        self.assertEqual(gui.auto.ControlFromPoint.call_count, 2)

    def test_uia_failure_is_unknown_not_disabled(self):
        from unittest.mock import Mock
        gui = m.WindowsGUI.__new__(m.WindowsGUI)
        gui.cfg, gui.hwnd = config(), 123
        gui.auto = Mock()
        gui.auto.ControlFromPoint.side_effect = RuntimeError("stale control")
        self.assertEqual(gui.button_state(picture()), "unknown")

    def test_focus_loss_stops_before_screenshot_or_click(self):
        from unittest.mock import Mock
        gui = m.WindowsGUI.__new__(m.WindowsGUI)
        gui.hwnd = 123
        gui.abort_check = lambda: None
        gui.user = Mock()
        gui.user.GetForegroundWindow.return_value = 124
        with self.assertRaises(m.StopRun):
            gui.guard()

    def test_native_click_constructs_two_correctly_sized_mouse_events(self):
        gui = m.WindowsGUI.__new__(m.WindowsGUI)
        gui.cfg = config()
        gui.guard = gui.park = lambda: None
        gui.snapshot = lambda: picture()
        gui.button_state = lambda image: "enabled"
        from unittest.mock import Mock
        gui.user = Mock()
        def send(count, events, size):
            expected_size = 40 if m.ctypes.sizeof(m.ctypes.c_void_p) == 8 else 28
            self.assertEqual(size, expected_size)
            self.assertEqual(count, 2)
            self.assertEqual(events[0].type, 0)
            self.assertEqual(events[0].data.mi.dwFlags, 0x0002)
            self.assertEqual(events[1].data.mi.dwFlags, 0x0004)
            return 2
        gui.user.SendInput.side_effect = send
        gui.click_next()

    def test_main_failure_writes_partial_pdf_and_stopped_manifest(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            folder = Path(tmp)
            cfg = config()
            cfg["output_dir"] = "runs"
            config_path = folder / "config.json"
            config_path.write_text(json.dumps(cfg))
            gui = FakeGUI([(picture(), "enabled")])
            gui.size = (150, 100)
            gui.bind = gui.park = gui.prepare_button = lambda: None
            gui.title = lambda: "synthetic test"
            old_wait = m.wait_ready
            with patch.object(m, "WindowsGUI", return_value=gui), patch.object(m.importlib.metadata, "version", return_value="test"), patch.object(m, "wait_ready", side_effect=lambda g, c, previous=None: old_wait(g, c, previous, clock=g.clock)), patch.object(sys, "argv", ["edge_capture.py", "--config", str(config_path)]):
                self.assertEqual(m.main(), 2)
            run = next((folder / "runs").iterdir())
            manifest = json.loads((run / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "STOPPED")
            self.assertEqual(len(PdfReader(run / "gesamt_TEILSTAND.pdf").pages), 2)
            self.assertFalse((run / "gesamt.pdf").exists())
            self.assertEqual(gui.clicks, 1)

    def test_rebuild_never_calls_windows_gui_or_overwrites_existing_pdf(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
            folder = Path(tmp)
            _, manifest = self.execute(config(), [(picture(), "disabled")], folder)
            manifest["status"] = "STOPPED"
            m.write_json(folder / "manifest.json", manifest)
            with patch.object(m, "WindowsGUI", side_effect=AssertionError("No GUI allowed")), patch.object(sys, "argv", ["edge_capture.py", "--rebuild", str(folder)]):
                self.assertEqual(m.main(), 0)
                self.assertEqual(len(PdfReader(folder / "gesamt_neu_TEILSTAND.pdf").pages), 2)
                with self.assertRaises(ValueError):
                    m.main()


if __name__ == "__main__":
    unittest.main(verbosity=2)
