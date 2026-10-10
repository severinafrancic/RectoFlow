"""Final capture review preserves persisted authority and diagnoses exact fields."""
import copy
import json
import sys
from pathlib import Path
import tempfile
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from calibration import calibration as wizard
from calibration.diagnostics import Diagnostic,scope
from calibration.geometry import CalibrationError,magnifier_pixels
from calibration.regions import selection
from calibration.screenshot_picker import RectanglePicker
from test_regions import config,SCRATCH
import edge_capture as core


class ConfirmationTests(unittest.TestCase):
    def test_all_fields_independently_detected_with_old_new_values(self):
        cfg=config(2,'next_button');saved=wizard.confirmation_state(cfg)
        changes={'region_order':list(reversed(saved['region_order'])),
                 'NEXT':[270,51,25,20],'PROGRESS':[1,2,3,4],'click_point':[281,60],
                 'paper':'A5','orientation':'landscape','navigation':'manual'}
        for field,value in changes.items():
            with self.subTest(field=field),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                observed=copy.deepcopy(saved);observed[field]=value
                d=Diagnostic(td,'test','capture')
                with scope(d),self.assertRaises(CalibrationError) as caught:
                    wizard.assert_confirmation_state(saved,observed,'review')
                self.assertEqual(caught.exception.failure_code,'CONFIRMATION_STATE_MISMATCH')
                self.assertEqual(caught.exception.metadata['mismatches'],[dict(field=field,old=saved[field],new=value)])
                events=[json.loads(line) for line in (d.attempt_dir/'events.jsonl').read_text().splitlines()]
                self.assertEqual(events[-1]['event'],'CONFIRMATION_FIELD_MISMATCH')
                self.assertEqual(events[-1]['old'],saved[field]);self.assertEqual(events[-1]['new'],value)
        changed=copy.deepcopy(saved);changed['region_rects']['REGION_001'][0]+=1
        with self.assertRaises(CalibrationError) as caught:wizard.assert_confirmation_state(saved,changed,'config')
        self.assertEqual(caught.exception.metadata['mismatches'][0]['field'],'region_rects.REGION_001')

    def test_external_config_change_during_readonly_review_fails_closed(self):
        cfg=config(2);original=copy.deepcopy(cfg)
        state=dict(action='save',rects=selection(cfg),point=cfg['next_point'],paper='A4',orientation='portrait',navigation='none')
        def change():cfg['regions'][0][0]+=1;return state
        gui=Mock();gui.target_metadata.return_value={'selection_bounds':[0,0,320,240]}
        with patch.object(wizard.tk,'Tk',return_value=Mock()),patch.object(wizard,'fresh_image',return_value=Image.new('RGB',(320,240))) as fresh,patch.object(wizard,'RectanglePicker',return_value=Mock(show=change)):
            with self.assertRaises(CalibrationError) as caught:wizard.confirm_capture(gui,cfg)
        self.assertEqual(caught.exception.failure_code,'CONFIRMATION_STATE_MISMATCH')
        self.assertEqual(caught.exception.metadata['source'],'config')
        self.assertEqual(fresh.call_count,1)
        self.assertEqual(original['regions'][0][0]+1,cfg['regions'][0][0])

    def test_actual_tk_readonly_owner_geometry_starts_without_normalizing(self):
        # Technical geometry from the confirmed Owner case, synthetic blank pixels.
        cfg=config(2,'next_button');cfg.update(regions=[[455,137,624,832],[1079,137,624,832]],
            button_rect=[1150,980,40,43],next_point=[1170,1001],progress_rect=[1074,980,67,49])
        before=copy.deepcopy(cfg);image=Image.new('RGB',(1920,1080),'white')
        gui=Mock();gui.target_metadata.return_value={'selection_bounds':[0,0,1920,1080]}
        native_top=tk.Toplevel
        def hidden(master):
            win=native_top(master);win.withdraw();win.state=lambda *args:'withdrawn';return win
        real_picker=RectanglePicker;reviews=[]
        def review(*args,**kwargs):
            p=real_picker(*args,**kwargs);reviews.append(p)
            self.assertTrue(p.read_only)
            self.assertEqual(p.rects,selection(before));self.assertEqual(p.point,before['next_point'])
            # All ordinary mutations, including keyboard/mouse and callable methods,
            # are inert; only Start, Recalibrate and Cancel buttons are constructed.
            for method,args in [('key_move',(SimpleNamespace(widget=Mock(),state=0,keysym='Right'),)),('press',(Mock(),)),('motion',(Mock(),)),('reorder',(1,)),('add_region',()),('delete',()),('set_point',()),('fit_selected',()),('undo',()),('redo',())]:getattr(p,method)(*args)
            self.assertEqual(p.rects,selection(before));self.assertEqual(p.point,before['next_point'])
            def buttons(node):
                found=[]
                for child in node.winfo_children():
                    if child.winfo_class()=='TButton':found.append(child)
                    found.extend(buttons(child))
                return found
            controls=buttons(p.window)
            self.assertEqual({b.cget('text') for b in controls},{'Aufnahme starten','Neu kalibrieren','Abbrechen'})
            p.window.after(1,lambda:next(b for b in controls if b.cget('text')=='Aufnahme starten').invoke())
            return p
        with patch('calibration.screenshot_picker.tk.Toplevel',side_effect=hidden),patch.object(wizard,'RectanglePicker',side_effect=review),patch.object(wizard,'fresh_image',return_value=image),patch('calibration.screenshot_picker.messagebox.askyesno') as prompt:
            self.assertIs(wizard.confirm_capture(gui,cfg),image)
        prompt.assert_not_called();self.assertEqual(cfg,before)

    def test_readonly_preserves_unused_point_in_manual_legacy_config(self):
        root=tk.Tk();root.withdraw()
        try:
            p=RectanglePicker(root,Image.new('RGB',(320,240)),selection(config(1)),[7,8],[0,0,320,240],navigation_mode='none',read_only=True)
            self.assertEqual(p.point,[7,8]);p.accept();self.assertEqual(p.result['point'],[7,8])
        finally:root.destroy()

    def test_recalibration_is_explicit_and_does_not_read_second_frame(self):
        cfg=config(1);gui=Mock();gui.target_metadata.return_value={'selection_bounds':[0,0,320,240]}
        with patch.object(wizard.tk,'Tk',return_value=Mock()),patch.object(wizard,'fresh_image',return_value=Image.new('RGB',(320,240))) as fresh,patch.object(wizard,'RectanglePicker',return_value=Mock(show=Mock(return_value={'action':'recalibrate'}))):
            self.assertIs(wizard.confirm_capture(gui,cfg),wizard.RECALIBRATE)
        self.assertEqual(fresh.call_count,1)

    def test_main_recalibrates_and_never_publishes_a_capture_run(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            root=Path(td);cfg=config(1);cfg['output_dir']='captures';path=root/'config.json';path.write_text(json.dumps(cfg))
            gui=Mock(size=(320,240),template_bytes={});d=Diagnostic(root,'test','capture')
            with patch.object(sys,'argv',['rectoflow','--config',str(path)]),patch.object(core,'WindowsGUI',return_value=gui),patch.object(wizard,'confirm_capture',return_value=wizard.RECALIBRATE),patch.object(wizard,'calibrate',return_value=0) as calibrate,patch.object(core,'publish_run') as publish:
                self.assertEqual(core.main(d),0)
            calibrate.assert_called_once();publish.assert_not_called()
            self.assertFalse(d.data['confirmation_accepted']);self.assertFalse(d.data['run_created'])

    def test_external_file_edits_are_field_specific_and_cannot_start_run(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            root=Path(td);cfg=config(1);cfg['output_dir']='captures';path=root/'config.json';raw=json.dumps(cfg).encode();path.write_bytes(raw)
            changed=copy.deepcopy(cfg);changed['next_point']=[7,8]
            path.write_text(json.dumps(changed))
            with self.assertRaises(CalibrationError) as error:wizard.assert_confirmation_file(path,raw)
            self.assertEqual(error.exception.failure_code,'CONFIRMATION_STATE_MISMATCH')
            self.assertEqual(error.exception.metadata['mismatches'][0]['field'],'click_point')
            path.write_bytes(raw)
            gui=Mock(size=(320,240),template_bytes={});d=Diagnostic(root,'test','capture')
            def edit(*args):path.write_text(json.dumps(changed));return Image.new('RGB',(320,240))
            with patch.object(sys,'argv',['rectoflow','--config',str(path)]),patch.object(core,'WindowsGUI',return_value=gui),patch.object(wizard,'confirm_capture',side_effect=edit),patch.object(core,'publish_run') as publish:
                with self.assertRaises(CalibrationError):core.main(d)
            publish.assert_not_called();self.assertFalse(d.data['run_created'])
            self.assertEqual(d.data['primary_failure']['code'],'CONFIRMATION_STATE_MISMATCH')

    def test_other_config_change_is_fail_closed_without_dumping_config(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            path=Path(td)/'config.json';cfg=config(1);raw=json.dumps(cfg).encode()
            cfg['unknown_private']='PRIVATE';path.write_text(json.dumps(cfg))
            with self.assertRaises(CalibrationError) as error:wizard.assert_confirmation_file(path,raw)
            self.assertEqual(error.exception.failure_code,'CONFIRMATION_STATE_MISMATCH')
            self.assertEqual(set(error.exception.metadata),{'old_sha256','new_sha256'})
            self.assertNotIn('PRIVATE',str(error.exception))

    def test_four_times_nearest_neighbor_halves_visual_step_but_not_pixels(self):
        image=Image.new('RGB',(50,50));image.putpixel((24,24),(255,255,255))
        four,c4=magnifier_pixels(image,(24,24));eight,c8=magnifier_pixels(image,(24,24),zoom=8)
        self.assertEqual(four.size,(84,84));self.assertEqual(eight.size,(168,168))
        self.assertEqual(c4,(42,42));self.assertEqual(c8,(84,84))
        for x in range(40,44):
            for y in range(40,44):self.assertEqual(four.getpixel((x,y)),(255,255,255))
        self.assertEqual(four.getpixel((44,42)),(0,0,0))
        self.assertEqual((c8[0]+8)-c8[0],2*((c4[0]+4)-c4[0]))
