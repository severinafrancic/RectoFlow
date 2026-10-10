"""Single/multiple candidates and strict measured CSS→physical-pixel mapping."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image, ImageDraw
from test_calibration import payload
from test_regions import config, SCRATCH
from calibration.dom_picker import parse_payload, suggestions, snippet, DOMSession
from calibration.geometry import CalibrationError
from calibration.regions import selection, capture_names
from calibration import calibration as wizard
import edge_capture as core


def proposal(count=1,dpr=1):
    data=payload(dpr);data["schema"]=2
    data["candidates"]=[{"left":20+i*100,"top":120,"right":100+i*100,"bottom":300,"width":80,"height":180} for i in range(count)]
    data["rects"]={}
    return data


def marked(data,size=(1600,1300),origin=(100,150),delta=0):
    image=Image.new("RGB",size,"white");draw=ImageDraw.Draw(image);dpr=data["dpr"]
    for marker in data["markers"]:
        x,y=marker["css_center"];ox,oy=origin
        draw.rectangle([round(ox+(x-10)*dpr),round(oy+(y-10)*dpr),round(ox+(x+10)*dpr)-1,round(oy+(y+10)*dpr)-1],
                       fill=tuple(v+delta for v in marker["color"]))
    return image


class OwnerHTMLTests(unittest.TestCase):
    def test_one_two_four_candidates_are_ordered_valid_proposals(self):
        for count in (1,2,4):
            with self.subTest(count=count):
                data=proposal(count);clean=parse_payload(json.dumps(data),data["token"])
                rects,diagnostic=suggestions(clean,marked(data),[0,0,1600,1300])
                self.assertEqual(list(rects),[f"PAGE_CANDIDATE_{i}" for i in range(1,count+1)])
                self.assertEqual(len(capture_names(wizard.apply_proposal(selection(config(2)),rects))),count)
                self.assertEqual([r[0] for r in rects.values()],[120+i*100 for i in range(count)])

    def test_zero_candidate_unsafe_proposal_and_malformed_data_rejected(self):
        data=proposal(0)
        with self.assertRaises(CalibrationError):suggestions(parse_payload(json.dumps(data),data["token"]),marked(data),[0,0,1600,1300])
        for key,value in (("candidates",True),("candidates",[{}]),("candidates",[{}]*65),("visual_scale",1.1)):
            bad=proposal();bad[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(CalibrationError):parse_payload(json.dumps(bad),bad["token"])

    def test_dpr_zoom_color_rounding_scroll_and_viewport_edge(self):
        for dpr in (1,1.25,1.5,2,1.875):
            for delta in (0,4,8):
                with self.subTest(dpr=dpr,delta=delta):
                    data=proposal(1,dpr);data["scroll"]=[200,600]
                    data["candidates"][0]={"left":-10,"top":380,"right":50,"bottom":430,"width":60,"height":50}
                    clean=parse_payload(json.dumps(data),data["token"])
                    rects,meta=suggestions(clean,marked(data,delta=delta),[0,0,1600,1300])
                    result=rects["PAGE_CANDIDATE_1"]
                    self.assertLessEqual(abs(result[0]-100),1)
                    self.assertLessEqual(abs(result[1]-(150+380*dpr)),1)
                    self.assertLessEqual(abs(result[2]-50*dpr),2);self.assertLessEqual(abs(result[3]-20*dpr),2)
                    self.assertEqual(meta["scroll"],[200,600])  # viewport rect: scroll is never added twice

    def test_multiple_same_color_clusters_disambiguated_geometrically(self):
        data=proposal(2);image=marked(data);draw=ImageDraw.Draw(image)
        for i,marker in enumerate(data["markers"]):
            draw.rectangle((1200+i*30,50,1219+i*30,69),fill=tuple(marker["color"]))
        rects,_=suggestions(parse_payload(json.dumps(data),data["token"]),image,[0,0,1600,1300])
        self.assertEqual(rects["PAGE_CANDIDATE_1"],[120,270,80,180])

    def test_two_complete_marker_triangles_are_ambiguous_and_fail_closed(self):
        data=proposal();image=marked(data,origin=(0,0));other=marked(data,origin=(200,650))
        # Paste only the three second marker components, preserving the first set.
        for marker in data["markers"]:
            x,y=marker["css_center"];image.paste(other.crop((200+x-10,650+y-10,200+x+10,650+y+10)),(200+x-10,650+y-10))
        with self.assertRaises(CalibrationError):suggestions(data,image,[0,0,1600,1300])

    def test_missing_wrong_color_shape_and_scale_never_guess_mapping(self):
        data=proposal()
        for kind in ("missing","color","shape","scale"):
            image=marked(data,delta=9 if kind=="color" else 0)
            if kind=="missing":image.paste("white",(126,224,146,244))
            if kind=="shape":
                image.paste("white",(126,224,146,244));ImageDraw.Draw(image).rectangle((126,224,155,233),fill=(239,17,131))
            if kind=="scale":data=proposal(dpr=2)
            with self.subTest(kind=kind),self.assertRaises(CalibrationError):suggestions(data,image,[0,0,1600,1300])

    def test_actual_single_candidate_wizard_editor_final_save_and_cancel(self):
        for count in (1,2,4):
            for cancel in (False,True):
                with self.subTest(count=count,cancel=cancel),tempfile.TemporaryDirectory(dir=SCRATCH) as td:
                    folder=Path(td);cfg=config(2);path=folder/"config.json";path.write_text(json.dumps(cfg));raw=path.read_bytes()
                    # This test executes the real suggestions mapping and proposal adapter.
                    data=proposal(count);image=marked(data)
                    data=parse_payload(json.dumps(data),data["token"])
                    target={"selection_bounds":[0,0,1600,1300],"screen_size":[1600,1300]}
                    gui=Mock(size=(1600,1300));gui.target_metadata.return_value=target
                    candidates,_=suggestions(data,image,target["selection_bounds"])
                    rects=wizard.apply_proposal(selection(cfg),candidates)
                    rects["REGION_001"][0]+=1
                    result={"action":"cancel" if cancel else "save","rects":rects,"point":None,"paper":"A4","orientation":"portrait","navigation":"none"}
                    with patch.object(wizard.tk,"Tk",return_value=Mock()),patch.object(wizard,"choose_dom",return_value={"mode":"dom","copied":True,"payload":data}), \
                         patch.object(wizard,"fresh_image",return_value=image),patch.object(wizard,"clean_dom",return_value=image), \
                         patch.object(wizard,"RectanglePicker",return_value=Mock(show=Mock(return_value=result))) as editor:
                        status=wizard.calibrate(gui,cfg,path,hashlib.sha256(raw).hexdigest(),core.validate)
                    self.assertEqual(len(capture_names(editor.call_args_list[0].args[2])),count)
                    if cancel:self.assertEqual(status,2);self.assertEqual(path.read_bytes(),raw)
                    else:
                        self.assertEqual(status,0);self.assertEqual(editor.call_count,2)
                        stored=json.loads(path.read_bytes());self.assertEqual(len(stored["regions"]),count)
                        self.assertEqual(stored["regions"][0][0],121)

    def test_retry_sessions_are_independent_and_single_use(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as td:
            a,b=DOMSession(),DOMSession();self.assertNotEqual(a.token,b.token)
            data=proposal();data.update(token=b.token,created_ms=b.created_ms)
            path=Path(td)/"payload.json";path.write_text(json.dumps(data))
            try:
                with self.assertRaises(CalibrationError):a.import_file(path)
                self.assertEqual(b.import_file(path)["schema"],2)
                with self.assertRaises(CalibrationError):b.import_file(path)
            finally:a.cancel();b.cancel()

    def test_real_bookmarklet_execution_candidates_and_marker_stacking(self):
        node=shutil.which("node");self.assertIsNotNone(node)
        harness=r'''const vm=require('vm');
for(const count of [1,2,4]) {
 const nodes=[];let target;
 class El {constructor(tag){this.tag=tag;this.style={};this.children=[];this.events={};nodes.push(this);}
 append(...children){this.children.push(...children);} attachShadow(){this.shadow=new El('shadow');return this.shadow;}
 addEventListener(name,fn){this.events[name]=fn;} remove(){} getBoundingClientRect(){return target;} contains(){return true;} querySelectorAll(){return [];}}
 const doc=new El('document');doc.documentElement=new El('html');doc.createElement=tag=>new El(tag);doc.elementFromPoint=()=>new El('page');
 const win=new El('window');win.top=win;
 const context={window:win,document:doc,Element:El,Date,AbortController,setTimeout:()=>1,clearTimeout(){},innerWidth:800,innerHeight:600,
                devicePixelRatio:1.25,scrollX:0,scrollY:200,visualViewport:{scale:1},getComputedStyle:()=>({opacity:'1',display:'block',visibility:'visible'})};
 vm.runInNewContext(SCRIPT,context);
 const shield=nodes.find(n=>n.style.cssText?.includes('background:transparent'));
 const skip=nodes.find(n=>n.tag==='button'&&n.textContent.includes('Seiten fertig'));
 const event={preventDefault(){},stopImmediatePropagation(){},clientX:50,clientY:150};
 for(let i=0;i<count;i++) {target={left:10+i*100,top:120,right:90+i*100,bottom:300,width:80,height:180};shield.events.click(event);}
 for(let i=0;i<3;i++)skip.events.click(event);
 const result=JSON.parse(nodes.find(n=>n.tag==='textarea').value);
 if(result.schema!==3||result.candidates.length!==count||'LEFT' in result.rects||'RIGHT' in result.rects)throw Error('candidate contract');
 const markers=nodes.filter(n=>n.style.cssText?.includes('width:32px'));
 const panel=nodes.find(n=>n.style.cssText?.includes('max-width:440px'));
 if(markers.length!==4||markers.some(m=>m.children.length!==36)||panel.style.zIndex!=='3'||markers.some(m=>!m.style.cssText.includes('z-index:5!important')))throw Error('marker behind panel');
}
console.log('DOM_CANDIDATES_AND_MARKER_STACKING_PASS');'''.replace("SCRIPT",json.dumps(snippet("tests",int(core.time.time()*1000))))
        result=subprocess.run([node],input=harness,text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
