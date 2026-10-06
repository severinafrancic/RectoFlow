"""Shared identity/environment contracts and documentation fixture integrity.

Synthetic tests explicitly do not certify a real browser or physical desktop DPI.
"""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from PIL import Image
import edge_capture as core
from calibration.regions import BROWSERS, browser_name
from calibration.exports import view_images, analyze_view

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('demo_assets', ROOT / 'scripts' / 'generate_readme_assets.py')
demo = importlib.util.module_from_spec(spec); spec.loader.exec_module(demo)


class CompatibilityDemoTests(unittest.TestCase):
    def test_each_supported_identity_accepts_only_its_requested_browser(self):
        for exe, name in BROWSERS.items():
            self.assertEqual(browser_name('C:\\Synthetic\\' + exe, name), name)
            for other in BROWSERS.values():
                if other != name:
                    with self.subTest(exe=exe, requested=other), self.assertRaises(ValueError):
                        browser_name(exe, other)

    def test_physical_dpi_change_is_rejected_for_all_identities(self):
        for exe in BROWSERS:
            for dpi in (96, 120, 144):
                gui = core.WindowsGUI.__new__(core.WindowsGUI)
                gui.hwnd = 123; gui.bound_identity = [456, 789]; gui.bound_exe = exe
                gui.user = Mock(); gui.user.IsWindow.return_value = True
                gui.user.IsWindowVisible.return_value = True; gui.user.IsIconic.return_value = False
                gui.process_identity = lambda: [456, 789]
                gui.process_executable = lambda: exe
                gui.bound_environment = {'window_bounds': [0, 0, 1000, 700], 'screen_size': [1920, 1080],
                                         'dpi': dpi, 'monitor': {'primary': True}}
                gui.initial_geometry = (0, 0, 1000, 700)
                gui.window_property = 'synthetic-lifetime'; gui.user.GetPropW.return_value = 1
                gui.environment = lambda: copy.deepcopy(gui.bound_environment)
                gui.identity_environment_check()
                changed = copy.deepcopy(gui.bound_environment); changed['dpi'] = dpi + 24
                gui.environment = lambda: changed
                with self.subTest(exe=exe, dpi=dpi), self.assertRaises(core.StopRun):
                    gui.identity_environment_check()

    def test_fixture_produces_real_analysis_warning_without_export(self):
        with tempfile.TemporaryDirectory(prefix='rectoflow-demo-unit-') as temporary:
            folder = Path(temporary); manifest = demo.review_fixture(folder)
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            self.assertEqual(len(manifest['pairs']), 3)
            self.assertEqual(len(view_images(folder, manifest, 2)), 2)
            self.assertEqual(analyze_view(folder, manifest, 2)['similarity'], 1)
            self.assertIn('Aehnlich', ';'.join(analyze_view(folder, manifest, 2)['warnings']))
            self.assertFalse(analyze_view(folder, manifest, 3)['warnings'])
            self.assertFalse((folder / 'exports').exists())
            self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)

    def test_synthetic_document_is_deterministic_and_distinct(self):
        self.assertEqual(demo.document(1).tobytes(), demo.document(1).tobytes())
        self.assertNotEqual(demo.document(1).tobytes(), demo.document(3).tobytes())

    def test_committed_demo_assets_are_valid_png_clients_only(self):
        expected = {'rectoflow-calibration.png': (1280, 820), 'rectoflow-review.png': (1080, 780)}
        self.assertEqual({p.name for p in (ROOT / 'docs' / 'assets').iterdir()}, set(expected))
        for name, size in expected.items():
            with Image.open(ROOT / 'docs' / 'assets' / name) as image:
                self.assertEqual(image.format, 'PNG'); self.assertEqual(image.size, size)
                image.verify()


if __name__ == '__main__':
    unittest.main()
