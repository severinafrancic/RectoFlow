"""Inactive slots cannot fabricate a new or unstable book view."""
import unittest
from unittest.mock import Mock
from PIL import Image
from test_page_layout import sparse_config,frames
import edge_capture as core


class ActiveTransitionTests(unittest.TestCase):
    def ready(self,cfg,before,images,index,state='enabled'):
        cfg.update(stable_seconds=.04,disabled_seconds=.04,min_after_click=.04,poll_seconds=.01,timeout_seconds=.45)
        gui=Mock(capture_view_index=index,transition_frame_baseline=before)
        cursor={'i':0,'clock':0.0}
        def snapshot():
            im=images[cursor['i']%len(images)];cursor['i']+=1;return im
        def clock():cursor['clock']+=.02;return cursor['clock']
        gui.snapshot.side_effect=snapshot;gui.button_state.return_value=state
        return core.wait_ready(gui,cfg,previous=core.progress_image(before,cfg),clock=clock)

    def test_only_inactive_slot_changes_never_counts_as_new_view(self):
        cfg=sparse_config(False);cfg['page_layout_policy']['overrides']={'2':[2]}
        before=frames(cfg)[0];changed=before.copy();changed.paste('black',core.box(cfg['regions'][0]))
        with self.assertRaises(core.StopRun) as error:self.ready(cfg,before,[changed],2)
        self.assertEqual(error.exception.code,'VIEW_CHANGE_NOT_DETECTED')
        self.assertEqual(error.exception.metadata['active_slots'],[2])
        self.assertFalse(error.exception.metadata['change_detected'])

    def test_active_change_stabilizes_despite_inactive_flicker(self):
        cfg=sparse_config(False);cfg['page_layout_policy']['overrides']={'2':[2]}
        before=frames(cfg)[0];changed=before.copy();changed.paste('black',core.box(cfg['regions'][1]))
        flicker=changed.copy();flicker.paste('red',core.box(cfg['regions'][0]))
        result=self.ready(cfg,before,[changed,flicker],2)
        self.assertEqual(result[1],'enabled')
        self.assertEqual(result[2].size,tuple(cfg['regions'][1][2:]))

    def test_known_and_detected_unknown_last_use_last_mask(self):
        for known in (False,True):
            with self.subTest(known=known):
                cfg=sparse_config(known);before=frames(cfg)[2]
                final=before.copy();final.paste('black',core.box(cfg['regions'][0]))
                other=final.copy();other.paste('red',core.box(cfg['regions'][1]))
                result=self.ready(cfg,before,[final,other],4,state='disabled')
                self.assertEqual(result[1],'disabled')
                self.assertEqual(result[2].size,tuple(cfg['regions'][0][2:]))

    def test_progress_remains_explicit_advanced_mode(self):
        cfg=sparse_config(False);cfg['progress_rect']=[100,100,10,10]
        before=frames(cfg)[0];next_frame=frames(cfg)[1]
        with self.assertRaises(core.StopRun) as error:self.ready(cfg,before,[next_frame],2)
        self.assertEqual(error.exception.metadata['change_source'],'advanced_progress')
        self.assertEqual(error.exception.code,'VIEW_CHANGE_NOT_DETECTED')
        self.assertTrue(error.exception.metadata['content_change_detected'])
