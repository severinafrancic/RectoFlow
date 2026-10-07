"""Build only the standalone spike bundle, never RectoFlow's product release."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    output=Path(sys.argv[1]).resolve();prepared=Path(sys.argv[2]).resolve()
    output.mkdir(parents=True,exist_ok=False)
    argv=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--console','--name','RectoFlowSpike03',
          '--distpath',str(output/'dist'),'--workpath',str(output/'work'),'--specpath',str(output/'spec')]
    for package in ('cv2','numpy','pypdfium2','pypdfium2_raw','reportlab'):
        argv+=['--collect-all',package]
    for name in ('pypdfium2','opencv-python-headless','numpy','Pillow','pyinstaller'):
        argv+=['--copy-metadata',name]
    for path in sorted(HERE.glob('*.py')):argv+=['--add-data',str(path)+';.']
    argv.append(str(HERE/'harness.py'))
    subprocess.run(argv,check=True,cwd=ROOT)
    folder=output/'dist'/'RectoFlowSpike03'
    shutil.copytree(prepared/'licenses',folder/'licenses')
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    assert python_license.is_file(),'CPython license missing'
    shutil.copyfile(python_license,folder/'licenses'/'CPython-LICENSE.txt')
    wheels=json.loads((prepared/'wheel-inventory.json').read_text())
    files={p.relative_to(folder).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}
           for p in sorted(folder.rglob('*')) if p.is_file()}
    native={name:info for name,info in files.items() if Path(name).suffix.lower() in ('.dll','.pyd','.exe')}
    assert any('pdfium' in name.lower() and name.endswith('.dll') for name in native)
    assert any('cv2' in name.lower() and name.endswith('.pyd') for name in native)
    assert any('numpy' in name.lower() for name in native)
    git=lambda *a:subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
    assert not git('status','--porcelain'),'Commit spike subject before execution/build'
    metadata={'producer':'BUILDER','subject_sha':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),
              'python':sys.version,'source_files':{p.name:sha(p.read_bytes()) for p in sorted(HERE.glob('*.py'))},
              'wheels':wheels,'native':native,'files':files,'license_material_policy':'All license/notice/copying wheel members plus CPython license; no blanket legal certification'}
    (folder/'SPIKE_BUILD_METADATA.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    archive=output/'RectoFlowSpike03-windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():z.write(p,'RectoFlowSpike03/'+p.relative_to(folder).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
        relocated=output/'relocated';z.extractall(relocated)
    for name,info in files.items():assert sha((relocated/'RectoFlowSpike03'/name).read_bytes())==info['sha256']
    summary={'subject_sha':metadata['subject_sha'],'tree':metadata['tree'],'zip_bytes':archive.stat().st_size,
             'zip_sha256':sha(archive.read_bytes()),'extracted_bytes':sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()),
             'native_count':len(native),'exe':str(relocated/'RectoFlowSpike03'/'RectoFlowSpike03.exe')}
    (output/'build-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))

if __name__=='__main__':main()
