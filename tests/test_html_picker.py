"""Click-only helper clipboard behavior and proposal/editor boundary."""
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import unquote
from PIL import Image
from test_regions import config, SCRATCH
from calibration.dom_picker import DOMSession, helper_html
from calibration import calibration as wizard
from calibration.regions import selection
import edge_capture as core


class HTMLPickerTests(unittest.TestCase):
    def test_helper_code_is_complete_and_no_required_bookmarkbar(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            session=DOMSession()
            try:
                text=session.write_helper(td).read_text(encoding="utf-8")
                code=html.unescape(re.search(r'<textarea[^>]*>(.*?)</textarea>',text,re.S).group(1))
                self.assertTrue(code.startswith("javascript:"))
                self.assertIn(session.token,unquote(code))
                self.assertIn("Favoritenmenue",text)
                self.assertIn("Manuell ohne HTML",text)
                self.assertIn('id="copy"',text)
            finally:session.cancel()

    def test_javascript_copy_only_after_click_success_fallback_and_denied(self):
        node=shutil.which("node")
        self.assertIsNotNone(node,"Node is required to execute the helper clipboard contract test")
        script=re.search(r'<script>(.*?)</script>',helper_html("javascript:test"),re.S).group(1)
        harness='''const vm=require('vm');
(async()=>{
for (const mode of ['clipboard','fallback','denied']) {
 let clicked, writes=0, copies=0, selected=0;
 const code={value:'javascript:test',focus(){},select(){selected++;}};
 const status={textContent:''};
 const context={navigator: mode==='fallback'?{}:{clipboard:{writeText:async value=>{
   if(value!=='javascript:test')throw Error('wrong code');writes++;if(mode==='denied')throw Error('denied');}}},
 document:{getElementById:id=>id==='copy'?{addEventListener:(name,fn)=>{if(name!=='click')throw Error('event');clicked=fn;}}:id==='code'?code:status,
 execCommand:name=>{if(name!=='copy')throw Error('command');copies++;return true;}}};
 vm.runInNewContext(SCRIPT,context);
 if(writes||copies||selected||!clicked)throw Error('automatic clipboard activity');
 await clicked();
 if(mode==='clipboard' && (writes!==1||copies||selected||!status.textContent.startsWith('Kopiert')))throw Error('clipboard path');
 if(mode==='fallback' && (copies!==1||selected!==1||!status.textContent.startsWith('Kopiert')))throw Error('fallback path');
 if(mode==='denied' && (copies||selected!==1||!status.textContent.includes('Strg+C')))throw Error('denied path');
}
console.log('CLICK_ONLY_COPY_PASS');
})().catch(e=>{console.error(e);process.exit(1);});'''.replace("SCRIPT",json.dumps(script))
        result=subprocess.run([node],input=harness,text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("CLICK_ONLY_COPY_PASS",result.stdout)

    def test_html_proposal_must_pass_editor_and_final_confirmation(self):
        cfg=config(2);rects=selection(cfg);proposed={"LEFT":[12,30,15,40],"RIGHT":[35,30,15,41]}
        target={"selection_bounds":[0,0,320,240],"screen_size":[320,240]}
        gui=Mock(size=(320,240));gui.target_metadata.return_value=target
        image=Image.new("RGB",(320,240),"white")
        for cancel in (False,True):
            with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                path=Path(td)/"config.json";path.write_text(json.dumps(cfg));before=path.read_bytes()
                expected=selection(cfg);expected["REGION_001"]=proposed["LEFT"];expected["REGION_002"]=proposed["RIGHT"]
                edited=dict(expected);edited["REGION_001"]=[13,31,15,40]
                results=[{"action":"cancel"}] if cancel else [{"action":"save","rects":edited,"point":None,"paper":"A4","orientation":"portrait","navigation":"none"}]*2
                with patch.object(wizard.tk,"Tk",return_value=Mock()), \
                     patch.object(wizard,"choose_dom",return_value={"mode":"dom","copied":True,"payload":{}}), \
                     patch.object(wizard,"suggestions",return_value=(proposed,{"mapping":[1,1,0,0]})), \
                     patch.object(wizard,"fresh_image",return_value=image), \
                     patch.object(wizard,"clean_dom",return_value=image), \
                     patch.object(wizard,"RectanglePicker",side_effect=[Mock(show=Mock(return_value=r)) for r in results]) as editor:
                    status=wizard.calibrate(gui,cfg,path,hashlib.sha256(before).hexdigest(),core.validate)
                self.assertEqual(editor.call_args_list[0].args[2],expected)
                if cancel:
                    self.assertEqual(status,2);self.assertEqual(path.read_bytes(),before)
                else:
                    self.assertEqual(status,0);self.assertEqual(editor.call_count,2)
                    self.assertEqual(json.loads(path.read_bytes())["regions"][0],[13,31,15,40])
