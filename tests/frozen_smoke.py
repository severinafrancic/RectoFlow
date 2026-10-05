"""Actual relocated EXE imports and PDF export, no browser/desktop acquisition."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from PIL import Image,ImageDraw
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import edge_capture as core


def run(exe,*args):
    env=dict(os.environ)
    for key in ("PYTHONPATH","PYTHONHOME","VIRTUAL_ENV"):
        env.pop(key,None)
    env["PATH"]=os.path.join(env["WINDIR"],"System32")+os.pathsep+env["WINDIR"]
    return subprocess.run([str(exe),*map(str,args)],cwd=exe.parent,env=env,capture_output=True,text=True,check=True,timeout=45).stdout


def main():
    scratch=ROOT/".build-release-smoke"
    scratch.mkdir(exist_ok=True)
    archive=ROOT/"artifacts"/f"RectoFlow-{core.VERSION}-windows-x64.zip"
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        folder=Path(tmp)
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not name.startswith("RectoFlow/") or ".." in Path(name).parts:
                    raise ValueError("Invalid owned release ZIP path.")
            z.extractall(folder)
        exe=folder/"RectoFlow"/"RectoFlow.exe"
        check=json.loads(run(exe,"--self-check"))
        assert check["frozen"] and check["architecture"]==64
        assert Path(check["config_root"])==exe.parent
        assert run(exe,"--version").strip()==f"RectoFlow {core.VERSION}"
        assert "--rebuild" in run(exe,"--help")
        cfg=json.loads((ROOT/"config.json").read_text())
        cfg.update(regions=[[20,50,180,250],[240,50,200,210],[480,50,160,240]],navigation_mode="none",paper_format="A4")
        screen=Image.new("RGB",(800,400),"white")
        draw=ImageDraw.Draw(screen)
        for i,(r,color) in enumerate(zip(cfg["regions"],("#ffaaaa","#aaffaa","#aaaaff")),1):
            draw.rectangle(core.box(r),fill=color)
            draw.text((r[0]+12,r[1]+12),f"REGION {i}",fill="black")
        captured=folder/"saved-run"
        captured.mkdir()
        record=core.save_pair(captured,1,screen,cfg)
        manifest={"schema":2,"status":"COMPLETE","config":cfg,"pairs":[record]}
        core.write_json(captured/"manifest.json",manifest)
        before=(captured/"manifest.json").read_bytes()
        output=Path(run(exe,"--rebuild",captured,"--paper","A5","--orientation","landscape").strip().splitlines()[-1])
        pdf=PdfReader(output)
        assert len(pdf.pages)==3
        for page,entry in zip(pdf.pages,record["images"]):
            assert abs(float(page.mediabox.width)*25.4/72-210)<.001
            assert abs(float(page.mediabox.height)*25.4/72-148)<.001
            with Image.open(captured/entry["file"]) as original:
                assert page.images[0].image.convert("RGB").tobytes()==original.convert("RGB").tobytes()
        spread=Path(run(exe,"--rebuild",captured,"--paper","A4","--orientation","portrait","--layout","spread").strip().splitlines()[-1])
        assert len(PdfReader(spread).pages)==1
        assert (captured/"manifest.json").read_bytes()==before
        for entry in record["images"]:assert core.sha256(captured/entry["file"])==entry["sha256"]
        manifest.update(schema=3,version=core.VERSION,finished="2026-10-05T00:00:00+00:00",profile=None)
        core.write_json(captured/"manifest.json",manifest)
        before=(captured/"manifest.json").read_bytes()
        frozen_pdf=Path(run(exe,"--rebuild",captured,"--paper","A5").strip().splitlines()[-1])
        result=json.loads((frozen_pdf.parent/"result.json").read_bytes())
        assert result["status"]=="COMPLETE" and result["pdf_sha256"]==core.sha256(frozen_pdf)
        assert result["source_manifest_sha256"]==core.sha256(captured/"manifest.json")
        assert result["export_plan_sha256"]==core.sha256(frozen_pdf.parent/"export_plan.json")
        from calibration.exports import create_plan
        plan=create_plan(captured,[1],{"paper_format":"A4","pdf_layout":"spread"})
        planned_pdf=Path(run(exe,"--rebuild",captured,"--export-plan",plan).strip().splitlines()[-1])
        assert len(PdfReader(planned_pdf).pages)==1
        assert (captured/"manifest.json").read_bytes()==before
        manifest["status"]="RUNNING";core.write_json(captured/"manifest.json",manifest)
        interrupted_bytes=(captured/"manifest.json").read_bytes()
        try:run(exe,"--rebuild",captured)
        except subprocess.CalledProcessError:pass
        else:raise AssertionError("RUNNING was exported")
        assert (captured/"manifest.json").read_bytes()==interrupted_bytes
        print("FROZEN_SMOKE_PASS: relocated Windows x64 EXE; clean PATH; Tcl/UIA/Pillow/ReportLab imports; version/help; 3 ordered pixel-exact A5 landscape pages; A4 spread; unchanged PNGs/manifest.")


if __name__=="__main__":main()
