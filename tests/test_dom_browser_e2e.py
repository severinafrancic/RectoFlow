"""Actual Edge HTML render -> production payload -> actual raster -> measured mapping.

Only owned synthetic fixtures and fresh temporary headless profiles; no desktop
pixels, owner tab, network session, real URLs, or book assets are read. Standard
loopback browser-test instrumentation captures export and raster in one viewport.
"""
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from PIL import Image,ImageDraw
from calibration.dom_picker import DOMSession,snippet,parse_payload,suggestions
from calibration.geometry import CalibrationError,css_to_screen
from calibration import calibration as wizard
from test_regions import SCRATCH,config
from calibration.regions import selection,capture_names


def edge_path():
    paths=[Path(os.environ.get('PROGRAMFILES(X86)',r'C:\Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
           Path(os.environ.get('PROGRAMFILES',r'C:\Program Files'))/'Microsoft/Edge/Application/msedge.exe']
    return next((p for p in paths if p.is_file()),None)


class BrowserImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.browser=edge_path()
        if cls.browser is None:raise RuntimeError('Native Edge required for real synthetic HTML import E2E')

    def render(self,view,dpr):
        with tempfile.TemporaryDirectory(dir=SCRATCH,prefix='dom-browser-') as td:
            folder=Path(td);session=DOMSession()
            try:
                template=(Path(__file__).parent/'fixtures/dom_book.html').read_text(encoding='utf-8')
                fixture=folder/'fixture.html';fixture.write_text(template.replace('__VIEW__',view).replace('__BOOKMARKLET__',snippet(session.token,session.created_ms)),encoding='utf-8')
                screenshot=folder/'browser.png'
                result=subprocess.run([shutil.which('node'),str(Path(__file__).with_name('browser_fixture_driver.js')),str(self.browser),
                    str(folder/'profile'),fixture.as_uri(),str(dpr),str(screenshot)],capture_output=True,timeout=40)
                self.assertEqual(result.returncode,0,result.stderr.decode('utf-8',errors='replace')[-1200:])
                text=result.stdout.decode('utf-8');self.assertTrue(text,'Browser did not produce actual bookmarklet payload')
                payload=json.loads(text)
                self.assertEqual(payload['schema'],3);self.assertAlmostEqual(payload['dpr'],dpr)
                path=folder/f'result.{session.token}.json'
                # Actual production file/session validator, not only JSON parsing.
                imported=session.import_file(path)
                with self.assertRaises(CalibrationError):session.import_file(path)
                with Image.open(screenshot) as opened:image=opened.convert('RGB')
                return payload,imported,image
            finally:session.cancel()

    def verify_import(self,payload,imported,image,count):
        self.assertEqual(len(payload['candidates']),count)
        self.assertIn('NEXT',payload['rects'])
        # Compose the actual browser raster at a known physical screen offset to
        # exercise Browser-Chrome/content origin recovery (never guessed in product).
        ox,oy=37,83
        screen=Image.new('RGB',(image.width+ox+41,image.height+oy+39),'#334455');screen.paste(image,(ox,oy))
        rects,meta=suggestions(imported,screen,[0,0,*screen.size])
        self.assertEqual([n for n in rects if n.startswith('PAGE_CANDIDATE_')],[f'PAGE_CANDIDATE_{i}' for i in range(1,count+1)])
        sx,sy,mx,my=meta['mapping'];dpr=payload['dpr']
        self.assertAlmostEqual(sx,dpr,delta=.003);self.assertAlmostEqual(sy,dpr,delta=.003)
        self.assertAlmostEqual(mx,ox,delta=1);self.assertAlmostEqual(my,oy,delta=1)
        for i,css in enumerate(payload['candidates'],1):
            expected=css_to_screen(css,(dpr,dpr,ox,oy),payload['viewport'])
            self.assertTrue(all(abs(a-b)<=1 for a,b in zip(rects[f'PAGE_CANDIDATE_{i}'],expected)),(rects,expected))
            x,y,w,h=rects[f'PAGE_CANDIDATE_{i}']
            self.assertEqual(screen.getpixel((x+w//2,y+h//2)),(186,218,85))
        expected_next=css_to_screen(payload['rects']['NEXT'],(dpr,dpr,ox,oy),payload['viewport'])
        self.assertTrue(all(abs(a-b)<=1 for a,b in zip(rects['NEXT'],expected_next)))
        proposal=wizard.apply_proposal(selection(config(2)),rects)
        self.assertEqual(len(capture_names(proposal)),count)
        return screen,rects,meta

    def test_first_normal_last_actual_browser_import_at_four_scales(self):
        for dpr in (1,1.25,1.5,2):
            for view,count in [('first',1),('normal',2),('last',1)]:
                with self.subTest(view=view,dpr=dpr):
                    self.verify_import(*self.render(view,dpr),count)

    def test_actual_opacity_hidden_offscreen_scroll_and_open_shadow_visibility(self):
        for view,count in [('visibility',2),('scroll',2),('shadow',1),('many',3)]:
            with self.subTest(view=view):
                payload,imported,image=self.render(view,1.25)
                if view=='scroll':self.assertEqual(payload['scroll'][1],300)
                self.verify_import(payload,imported,image,count)

    def test_specific_failures_and_session_bound_codes_on_actual_raster(self):
        payload,imported,image=self.render('normal',1)
        screen,_,_=self.verify_import(payload,imported,image,2)
        bounds=[0,0,*screen.size]
        # A solid color look-alike has no session code; it never disambiguates a
        # missing fiducial. No broad color/geometry tolerance is introduced.
        missing=screen.copy();m=payload['markers'][0]['css_center'];x,y=m
        missing.paste('white',(37+x-16,83+y-16,37+x+16,83+y+16))
        ImageDraw.Draw(missing).rectangle((10,10,41,41),fill=tuple(payload['markers'][0]['color']))
        with self.assertRaises(CalibrationError) as e:suggestions(imported,missing,bounds)
        self.assertEqual(e.exception.failure_code,'DOM_MARKERS_MISSING')
        wrong=json.loads(json.dumps(imported));wrong['token']='f'*32
        with self.assertRaises(CalibrationError) as e:suggestions(wrong,screen,bounds)
        self.assertEqual(e.exception.failure_code,'DOM_MARKERS_MISSING')
        doubled=Image.new('RGB',(screen.width,screen.height*2),'white');doubled.paste(screen,(0,0));doubled.paste(screen,(0,screen.height))
        with self.assertRaises(CalibrationError) as e:suggestions(imported,doubled,[0,0,*doubled.size])
        self.assertEqual(e.exception.failure_code,'DOM_MARKERS_AMBIGUOUS')
        invalid=screen.copy();last=payload['markers'][3]['css_center'];x,y=last
        tile=screen.crop((37+x-16,83+y-16,37+x+16,83+y+16));invalid.paste('white',(37+x-16,83+y-16,37+x+16,83+y+16));invalid.paste(tile,(37+x-16-10,83+y-16))
        with self.assertRaises(CalibrationError) as e:suggestions(imported,invalid,bounds)
        self.assertEqual(e.exception.failure_code,'DOM_MAPPING_INVALID')
        broken=json.loads(json.dumps(imported));broken['rects']['PAGE_CANDIDATE_1']['left']=99999
        with self.assertRaises(CalibrationError) as e:suggestions(broken,screen,bounds)
        self.assertEqual(e.exception.failure_code,'DOM_RECT_TRANSFORM_FAILED')
