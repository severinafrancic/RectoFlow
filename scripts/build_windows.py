"""Build and validate a portable Windows ZIP inside the canonical checkout."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION="0.2.0"


def notices(destination):
    target=destination/"third_party_licenses"
    target.mkdir(exist_ok=True)
    inventory=[]
    for name in ("Pillow","reportlab","charset-normalizer","uiautomation","comtypes","pyinstaller"):
        dist=importlib.metadata.distribution(name)
        included=[]
        for member in dist.files or []:
            path=Path(str(member))
            if any(word in path.name.lower() for word in ("license","notice","copying")) and path.suffix.lower() not in (".py",".pyc"):
                source=Path(dist.locate_file(member))
                if source.is_file():
                    out=target/name/path
                    out.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source,out)
                    included.append(out.relative_to(destination).as_posix())
        if not included:
            raise RuntimeError(f"No original dependency license found: {name}")
        inventory.append({"name":name,"version":dist.version,"notices":included})
    python_license=Path(sys.base_prefix)/"LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("CPython LICENSE.txt missing; do not publish an incomplete bundle.")
    shutil.copyfile(python_license,target/"CPython-LICENSE.txt")
    tk_files=list(destination.rglob("license.terms"))
    if not tk_files:
        raise RuntimeError("Tcl/Tk license terms missing from frozen bundle.")
    (destination/"DEPENDENCIES.json").write_text(json.dumps(inventory,indent=2),encoding="utf-8")


def main():
    if sys.platform!="win32":raise RuntimeError("Windows build requires native Windows.")
    dist=ROOT/".build-dist"
    arguments=[sys.executable,"-m","PyInstaller","--noconfirm","--onedir","--console","--name","RectoFlow",
        "--distpath",str(dist),"--workpath",str(ROOT/".build-windows"),"--specpath",str(ROOT/".build-spec"),
        "--collect-submodules","uiautomation","--collect-all","reportlab",
        "--hidden-import","PIL._imagingtk","--hidden-import","PIL.ImageGrab"]
    arguments += ["--icon",str(ROOT/"assets"/"rectoflow.ico"),"--version-file",str(ROOT/"assets"/"windows_version_info.txt")]
    for module in ("Pillow","reportlab","uiautomation","comtypes","charset-normalizer"):
        arguments += ["--copy-metadata",module]
    for path in [ROOT/"edge_capture.py",ROOT/"rectoflow.py",*sorted((ROOT/"calibration").glob("*.py")),*sorted((ROOT/"calibration").glob("*.js"))]:
        parent=path.parent.relative_to(ROOT).as_posix()
        arguments += ["--add-data",str(path)+";"+parent]
    arguments.append(str(ROOT/"rectoflow.py"))
    subprocess.run(arguments,cwd=ROOT,check=True)
    folder=dist/"RectoFlow"
    for name in ("config.json","LICENSE","README.de.md","THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(ROOT/name,folder/name)
    shutil.copytree(ROOT/"docs",folder/"docs",dirs_exist_ok=True)
    notices(folder)
    check=subprocess.run([str(folder/"RectoFlow.exe"),"--self-check"],cwd=folder,check=True,capture_output=True,text=True)
    info=json.loads(check.stdout)
    if not info["frozen"] or info["architecture"]!=64:
        raise RuntimeError("Invalid Windows release architecture/runtime.")
    public_info=dict(info)
    public_info["config_root"]="<portable directory>"
    (folder/"SELF_CHECK.json").write_text(json.dumps(public_info,indent=2),encoding="utf-8")
    source_files=[ROOT/"edge_capture.py",ROOT/"rectoflow.py",*sorted((ROOT/"calibration").glob("*.py")),*sorted((ROOT/"calibration").glob("*.js"))]
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    code_hash=hashlib.sha256("".join(f"{n}\t{hashes[n]}\n" for n in sorted(hashes)).encode()).hexdigest()
    revision=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True)
    dirty=subprocess.run(["git","status","--porcelain"],cwd=ROOT,capture_output=True,text=True,check=True)
    (folder/"BUILD_METADATA.json").write_text(json.dumps({"version":VERSION,"source_commit":revision.stdout.strip() if revision.returncode==0 else None,
        "working_tree_dirty":bool(dirty.stdout.strip()),"code_tree_sha256":code_hash,"files":hashes,"python":sys.version.split()[0]},indent=2),encoding="utf-8")
    artifacts=ROOT/"artifacts"
    artifacts.mkdir(exist_ok=True)
    output=artifacts/f"RectoFlow-{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob("*")):
            if path.is_file():z.write(path,arcname="RectoFlow/"+path.relative_to(folder).as_posix())
    with zipfile.ZipFile(output) as z:
        if z.testzip():raise RuntimeError("ZIP integrity failed.")
    print(json.dumps({"artifact":str(output),"sha256":hashlib.sha256(output.read_bytes()).hexdigest(),"self_check":info},indent=2))


if __name__=="__main__":main()
