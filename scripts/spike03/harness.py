"""Standalone qualification spike. Never imports RectoFlow's capture engine."""
import argparse
import ctypes
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

import winjob

ROOT=Path(__file__).resolve().parents[2] if not getattr(sys,'frozen',False) else Path(sys.executable).parent

def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
def command():return [sys.executable,'--worker'] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve()),'--worker']
def verified(path,expected):
    raw=Path(path).read_bytes()
    assert sha(raw)==expected,'Input fixture changed'
    return raw

def provider_info():
    import importlib.metadata as m
    import cv2, numpy, pypdfium2 as pdf
    result={name:m.version(name) for name in ('pypdfium2','opencv-python-headless','numpy','Pillow','pyinstaller')}
    for name,expected in [('pypdfium2','5.14.0'),('opencv-python-headless','5.0.0.93'),('numpy','2.4.6')]:
        assert result[name]==expected,(name,result[name])
    assert not pdf.PDFIUM_INFO.flags,'V8/XFA build not permitted'
    result.update(pdfium=str(pdf.PDFIUM_INFO.version),pdfium_flags=list(pdf.PDFIUM_INFO.flags),opencv=cv2.__version__)
    return result

def worker(request):
    # Parent assigns Job Object before this process can import any native provider.
    assert winjob.in_job(),'Worker not assigned to a Job Object'
    mode=request['mode']
    if mode=='hang':
        if request.get('ready'):save(request['ready'],{'pid':os.getpid(),'owner_pid':request['owner_pid'],'in_job':True})
        time.sleep(120);return {}
    if mode=='crash':os._exit(17)
    if mode=='memory':
        blocks=[]
        try:
            for _ in range(100):blocks.append(bytearray(8*1024**2))
        except MemoryError:return {'memory_limit_triggered':True,'allocated_bytes':len(blocks)*8*1024**2}
        raise AssertionError('Memory allocation was not bounded')
    providers=provider_info()
    if mode=='providers':return {'providers':providers,'in_job':True}
    import cv2 as cv
    import numpy as np
    import pypdfium2 as pdf
    from PIL import Image
    from fixtures import container_proposals
    if mode=='pdf':
        raw=verified(request['path'],request['sha256'])
        result=[]
        doc=pdf.PdfDocument(raw,password=request.get('password'))
        try:
            assert len(doc)==4
            expected_sizes=[(340,260),(280,360),(400,200),(200,300)]
            expected_boxes=[(20,30,280,370),(10,20,290,380),(0,0,400,200),(0,0,200,300)]
            for i in range(len(doc)):
                page=doc[i];bitmap=None
                try:
                    size=page.get_size();box=page.get_bbox()
                    assert tuple(size)==expected_sizes[i],(i,size,expected_sizes[i])
                    assert tuple(box)==expected_boxes[i],(i,box)
                    bitmap=page.render(scale=1,draw_annots=True,fill_color=(255,255,255,255))
                    image=bitmap.to_pil().convert('RGB');image.load()
                    assert image.size==expected_sizes[i]
                    assert min(image.getextrema()[0])==0 and max(image.getextrema()[0])==255
                    output=BytesIO();image.save(output,format='PNG');raster=output.getvalue()
                    proposal=container_proposals('fixture',f'pdf-{i}',sha(raster),image.size)
                    assert proposal==container_proposals('fixture',f'pdf-{i}',sha(raster),image.size,[])[:1]
                    plus=container_proposals('fixture',f'pdf-{i}',sha(raster),image.size,[{'origin':'VISUAL','quad':[[20,20],[80,20],[80,80],[20,80]]}])
                    assert plus[0]==proposal[0] and len(plus)==2
                    result.append({'index':i,'bbox':box,'size_px':size,'rotation':page.get_rotation(),
                                   'raster_sha256':sha(raster),'raster_bytes':len(raster),'container_proposal':proposal[0]})
                finally:
                    if bitmap:bitmap.close()
                    page.close()
        finally:doc.close()
        return {'pages':result,'source_sha256':sha(raw),'resources_closed':True,
                'userunit_policy':'scale in PDF canvas units; /UserUnit=2 does not become physical-DPI certification'}
    if mode=='pdf_error':
        raw=Path(request['path']).read_bytes()
        try:
            doc=pdf.PdfDocument(raw,password=request.get('password'));doc.close()
        except pdf.PdfiumError as error:return {'refused':True,'error_code':error.err_code,'error_class':type(error).__name__}
        raise AssertionError('Malformed PDF or wrong password accepted')
    if mode=='tiff':
        raw=verified(request['path'],request['sha256']);result=[]
        with Image.open(BytesIO(raw)) as decoded:
            assert decoded.n_frames==3
            for index,(size,color) in enumerate([((128,96),(220,20,20)),((96,128),(20,220,20)),((160,96),(20,20,220))]):
                decoded.seek(index);decoded.load();frame=decoded.convert('RGB')
                assert frame.size==size and frame.getpixel((0,0))==color
                output=BytesIO();frame.save(output,format='PNG');raw_frame=output.getvalue()
                full=container_proposals('fixture',f'tiff-{index}',sha(raw_frame),size)
                assert full[0]['quad'][2]==[size[0]-1,size[1]-1]
                assert container_proposals('fixture',f'tiff-{index}',sha(raw_frame),size,[{'origin':'VISUAL'}])[0]==full[0]
                result.append({'index':index,'size':size,'sha256':sha(raw_frame),'container_proposal':full[0]})
        return {'frames':result,'source_sha256':sha(raw)}
    if mode=='image_error':
        try:
            with Image.open(BytesIO(Path(request['path']).read_bytes())) as im:im.load()
        except (OSError,ValueError) as e:return {'refused':True,'error_class':type(e).__name__}
        raise AssertionError('Corrupt image accepted')
    if mode=='geometry':
        width,height=480,640
        flat=np.full((height,width,3),255,np.uint8)
        for y in range(60,600,30):cv.line(flat,(40,y),(440,y),(0,0,0),2)
        for point,color in [((30,30),(255,0,0)),((450,30),(0,255,0)),((450,610),(0,0,255)),((30,610),(255,0,255))]:
            cv.circle(flat,point,12,color,-1)
        src=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
        quad=np.float32([[80,80],[580,40],[650,820],[40,850]])
        forward=cv.getPerspectiveTransform(src,quad);inverse=cv.getPerspectiveTransform(quad,src)
        photographed=cv.warpPerspective(flat,forward,(700,900),borderValue=(190,190,190))
        restored=cv.warpPerspective(photographed,inverse,(width,height),borderValue=(255,255,255))
        back=cv.perspectiveTransform(quad.reshape(1,4,2),inverse)[0]
        error=float(np.max(np.linalg.norm(back-src,axis=1)))
        mae=float(np.mean(np.abs(restored[8:-8,8:-8].astype(np.float32)-flat[8:-8,8:-8])))
        assert error<.001 and mae<5,(error,mae)
        rotated=cv.warpAffine(flat,cv.getRotationMatrix2D((width/2,height/2),7,1),(width,height),borderValue=(255,255,255))
        def angle(image):
            # Near-horizontal resampled lines can fragment below HoughLinesP's
            # minimum segment length. Standard Hough votes retain those edges.
            lines=cv.HoughLines(cv.Canny(cv.cvtColor(image,cv.COLOR_RGB2GRAY),40,100),1,np.pi/1800,180)
            assert lines is not None
            assert lines.size % 2 == 0
            values=[math.degrees(float(theta))-90 for rho,theta in lines.reshape(-1,2)]
            values=[a for a in values if abs(a)<15];assert values
            return float(np.median(values))
        measured=angle(rotated)
        corrected=cv.warpAffine(rotated,cv.getRotationMatrix2D((width/2,height/2),measured,1),(width,height),borderValue=(255,255,255))
        residual=angle(corrected)
        assert abs(measured+7)<.3 and abs(residual)<.3,(measured,residual)
        return {'corner_error_px':error,'pixel_mae':mae,'output_size':[width,height],
                'homography':inverse.tolist(),'deskew_ground_truth_deg':7,'estimated_correction_deg':measured,'residual_deg':residual}
    if mode=='resource':
        mp=request['megapixels'];width=int(math.sqrt(mp*1_000_000*4/3));height=int(mp*1_000_000/width)
        started=time.perf_counter()
        frame=np.random.default_rng(3103).integers(0,256,(height,width,3),dtype=np.uint8)
        gray=cv.cvtColor(frame,cv.COLOR_RGB2GRAY)
        quad=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
        matrix=cv.getPerspectiveTransform(quad,quad)
        output=cv.warpPerspective(frame,matrix,(width,height))
        assert np.array_equal(frame,output),'Identity transform changed pixels'
        dest=Path(request['output']);dest.parent.mkdir(parents=True,exist_ok=True)
        Image.fromarray(output).save(dest,format='PNG',compress_level=1)
        data=dest.read_bytes()
        return {'megapixels_requested':mp,'size_px':[width,height],'decoded_pixels':width*height,
                'output_bytes':len(data),'sha256':sha(data),'provider_seconds':time.perf_counter()-started}
    raise ValueError('Unknown own spike case')

def call(request,folder,timeout=60,memory=2*1024**3,cancel_after=None,exe=None):
    cmd=[str(exe),'--worker'] if exe else command()
    with winjob.Child(cmd,request,folder,memory=memory,clean_path=bool(exe or getattr(sys,'frozen',False))) as child:
        return child.wait(timeout,cancel_after)

def execute(output,exe=None,resources=True):
    from fixtures import create
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    fixtures=create(output/'fixtures')
    results=[]
    def case(name,request,validator=lambda r:True,**kw):
        started=time.perf_counter()
        try:
            record=call(request,output,exe=exe,**kw)
            assert record['exit_code']==0 and record['response'] is not None,record
            assert validator(record['response'])
            results.append({'case':name,'status':'PASS',**record})
        except Exception as error:
            # Do not serialize requests: they can carry the ephemeral password.
            results.append({'case':name,'status':'FAILED','error_class':type(error).__name__,
                            'error':str(error),'elapsed_seconds':time.perf_counter()-started})
    case('providers',{'mode':'providers'},lambda r:r['in_job'])
    case('pdf_bound_bytes_geometry',{'mode':'pdf','path':fixtures['pdf'],'sha256':fixtures['pdf_sha256']})
    case('pdf_password_private_pipe',{'mode':'pdf','path':fixtures['encrypted'],'sha256':fixtures['encrypted_sha256'],'password':fixtures['password']})
    case('pdf_wrong_password',{'mode':'pdf_error','path':fixtures['encrypted'],'password':'incorrect-synthetic-password'},lambda r:r['refused'])
    case('pdf_corrupt',{'mode':'pdf_error','path':fixtures['bad_pdf']},lambda r:r['refused'])
    case('tiff_frames_container_policy',{'mode':'tiff','path':fixtures['tiff'],'sha256':fixtures['tiff_sha256']})
    case('image_corrupt',{'mode':'image_error','path':fixtures['bad_image']},lambda r:r['refused'])
    case('perspective_deskew_goldens',{'mode':'geometry'})
    case('job_memory_limit',{'mode':'memory'},lambda r:r['memory_limit_triggered'],memory=128*1024**2)
    for name,kw in [('job_timeout',{'timeout':.5}),('job_cancel',{'timeout':10,'cancel_after':.5})]:
        try:
            result=call({'mode':'hang'},output,exe=exe,**kw)
            assert result['exit_code']==92 and result['termination']==('TIMEOUT' if name=='job_timeout' else 'CANCELLED')
            results.append({'case':name,'status':'PASS',**result})
        except Exception as e:results.append({'case':name,'status':'FAILED','error':str(e)})
    try:
        result=call({'mode':'crash'},output,exe=exe)
        assert result['exit_code']==17 and result['response'] is None
        results.append({'case':'worker_crash_contained','status':'PASS',**result})
    except Exception as e:results.append({'case':'worker_crash_contained','status':'FAILED','error':str(e)})
    # Terminate only this own test parent; retain a handle to its own child to avoid PID reuse.
    parent=None;childhandle=None;ownerhandle=None
    try:
        ready=output/'parent-death-ready.json'
        cmd=[str(exe),'--orphan-parent',str(ready)] if exe else ([sys.executable,'--orphan-parent',str(ready)] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve()),'--orphan-parent',str(ready)])
        env=dict(os.environ)
        for key in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'):env.pop(key,None)
        if exe or getattr(sys,'frozen',False):env['PATH']=str(Path(env['WINDIR'])/'System32')+os.pathsep+env['WINDIR']
        parent=subprocess.Popen(cmd,cwd=output,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
        deadline=time.monotonic()+30
        while not ready.exists():
            if parent.poll() is not None:raise RuntimeError('Own parent failed before ready')
            if time.monotonic()>deadline:raise TimeoutError('Own parent did not become ready')
            time.sleep(.05)
        ready_info=json.loads(ready.read_text());pid=ready_info['pid']
        childhandle=winjob.handle_for_owned_pid(pid)
        ownerhandle=winjob.handle_for_owned_pid(ready_info['owner_pid'],terminate=True)
        winjob.checked(winjob.K.TerminateProcess(ownerhandle,93));parent.wait(timeout=10)
        assert winjob.K.WaitForSingleObject(childhandle,10000)==0,'Worker survived owner parent death'
        results.append({'case':'job_parent_death','status':'PASS','own_child_pid':pid})
    except Exception as e:results.append({'case':'job_parent_death','status':'FAILED','error':str(e)})
    finally:
        if parent and parent.poll() is None:parent.terminate();parent.wait(timeout=10)
        if childhandle:winjob.K.CloseHandle(childhandle)
        if ownerhandle:winjob.K.CloseHandle(ownerhandle)
    if resources:
        for mp in (1,12,24,48,64):
            case(f'resource_{mp}MP',{'mode':'resource','megapixels':mp,'output':str(output/f'resource-{mp}MP.png')})
    report={'schema':1,'producer':'BUILDER','python':sys.version,'platform':platform.platform(),
            'environment':'FROZEN_RELOCATED' if exe or getattr(sys,'frozen',False) else 'SOURCE_LOCAL_OR_CI',
            'tests':results,'status':'PASS' if all(r['status']=='PASS' for r in results) else 'REQUIRED_CHANGE',
            'disk_bytes':sum(p.stat().st_size for p in output.rglob('*') if p.is_file()),
            'qualified_envelope':'See actual cases: synthetic RGB rasters only; no production ingestion/limits implemented',
            'unqualified_limits':['512MiB input file','2GiB source bytes/run','500-frame batch','10GiB run budget/free reserve','general hostile-input CPU budget'],
            'security_scope':'Job Object controls resources/lifetime, not a security sandbox'}
    serialized=json.dumps(report)
    assert fixtures['password'] not in serialized and fixtures['password'] not in '\0'.join(sys.argv)
    report['password_not_in_report_or_argv']=True
    save(output/'report.json',report)
    print(json.dumps({'status':report['status'],'report':str(output/'report.json'),'cases':len(results),'failed':[r['case'] for r in results if r['status']!='PASS']}))
    return 0 if report['status']=='PASS' else 2

def main():
    if sys.argv[1:]==['--worker']:
        raw=sys.stdin.buffer.readline(16385);assert len(raw)<=16384
        result=worker(json.loads(raw))
        result['worker_memory']=winjob.own_memory()
        print(json.dumps(result,allow_nan=False));return 0
    if len(sys.argv)>1 and sys.argv[1]=='--orphan-parent':
        ready=Path(sys.argv[2]).resolve()
        with winjob.Child(command(),{'mode':'hang','ready':str(ready),'owner_pid':os.getpid()},ready.parent):time.sleep(120)
        return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--exe',type=Path)
    parser.add_argument('--no-resources',action='store_true')
    args=parser.parse_args()
    return execute(args.output,args.exe,not args.no_resources)

if __name__=='__main__':
    raise SystemExit(main())
