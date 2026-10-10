"""Builder evidence for one clean subject and its unpublished native Windows ZIP."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(["git",*args],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()


def main():
    if sys.platform!="win32":raise RuntimeError("Native Windows required")
    if git("status","--porcelain"):raise RuntimeError("Clean committed subject required")
    subject=git("rev-parse","HEAD");tree=git("rev-parse","HEAD^{tree}")
    evidence=ROOT/".build-v021"/"evidence"/subject
    evidence.mkdir(parents=True,exist_ok=True)
    receipt=dict(repository=str(ROOT),branch=git("branch","--show-current"),subject_sha=subject,tree=tree,
                 producer="scripts/verify_owner_test.py",producer_role="BUILDER",authority_mode="builder-only",
                 python=sys.version,platform=platform.platform(),runs=[],lifecycle="BUILDING")
    def save():
        (evidence/"receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    def run(name,*args,timeout=600):
        if git("rev-parse","HEAD")!=subject or git("status","--porcelain"):
            raise RuntimeError("Evidence subject changed")
        log=evidence/(name+".log")
        started=datetime.now(timezone.utc).isoformat()
        with log.open("w",encoding="utf-8") as stream:
            result=subprocess.run([sys.executable,"-B",*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
        receipt["runs"].append(dict(id=name,started=started,finished=datetime.now(timezone.utc).isoformat(),
                                    command=[sys.executable,"-B",*args],return_code=result.returncode,
                                    log=str(log),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
        save()
        print(f"{name}: {'PASS' if result.returncode==0 else 'FAIL'}",flush=True)
        if result.returncode:raise RuntimeError(f"{name} failed; inspect {log}")
    try:
        run("full-regression","-m","unittest","discover","-s","tests","-p","test_*.py","-v")
        for name in ("native_ui_smoke","native_review_smoke","native_editor_smoke"):
            run(name,"tests/"+name+".py")
        run("readme-assets","scripts/generate_readme_assets.py","--check")
        run("source-self-check","rectoflow.py","--self-check")
        run("owner-build","scripts/build_windows.py","--owner-test")
        archive=ROOT/".build-v021"/"owner-test"/"RectoFlow-owner-test-windows-x64.zip"
        run("frozen-relocated-smoke","tests/frozen_smoke.py","--archive",str(archive))
        exe=archive.parent/"RectoFlow"/"RectoFlow.exe"
        receipt["artifacts"]={"zip":str(archive),"zip_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
                              "exe":str(exe),"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest()}
        receipt["lifecycle"]="BUILDER_LOCAL_VERIFIED_CI_PENDING"
        receipt["independent_review"]="PENDING; no Fresh Breaker requested yet"
        receipt["windows_ci"]="PENDING; requires exact-subject workflow_dispatch"
        if git("rev-parse","HEAD")!=subject or git("status","--porcelain"):
            raise RuntimeError("Subject changed after verification")
        save();print(json.dumps(receipt["artifacts"],indent=2))
    except BaseException:
        receipt["lifecycle"]="BUILD_VERIFICATION_FAILED";save();raise


if __name__=="__main__":main()
