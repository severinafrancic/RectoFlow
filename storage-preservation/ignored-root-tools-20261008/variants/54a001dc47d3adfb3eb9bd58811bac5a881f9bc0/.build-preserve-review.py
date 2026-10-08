from pathlib import Path
import hashlib,json,shutil,zipfile
root=Path(__file__).resolve().parent
worktree=root/'.build-breaker-v02-final';out=root.parent
report=worktree/'.build-fresh-breaker-report.md'
assert hashlib.sha256(report.read_bytes()).hexdigest()=='67e1d371fd0a8d1facf2a1e8e239944f2273f2504b56239633d5d74263e77a5b'
saved=out/'RectoFlow-0.2.0-breaker-4166dd2.md'
assert not saved.exists();shutil.copyfile(report,saved)
archive=out/'RectoFlow-0.2.0-breaker-evidence-4166dd2.zip'
assert not archive.exists()
members={'.build-fresh-breaker-report.md':report}
for path in (worktree/'.build-breaker-fixtures').rglob('*'):
    if path.is_symlink() or getattr(path,'is_junction',lambda:False)():raise ValueError('Unexpected fixture redirection')
    if path.is_file():members['fixtures/'+path.relative_to(worktree/'.build-breaker-fixtures').as_posix()]=path
for path in (worktree/'.build-adversarial').rglob('*'):
    if path.is_symlink() or getattr(path,'is_junction',lambda:False)():raise ValueError('Unexpected archival redirection')
    if path.is_file():members['historical-extraction/'+path.relative_to(worktree/'.build-adversarial').as_posix()]=path
hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in members.items()}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for name,path in members.items():z.write(path,name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert set(z.namelist())==set(hashes)
    for name,digest in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
receipt={'subject':'4166dd2e1f2868daf90f22e6dd3172ed788b9b8a','verdict':'BREAKER_FAILED','report_sha256':hashes['.build-fresh-breaker-report.md'],'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'members':hashes,'retirement_trigger':'closed independent review; member-byte evidence preserved'}
with (out/'RectoFlow-0.2.0-breaker-retention-4166dd2.json').open('x',encoding='utf-8') as stream:stream.write(json.dumps(receipt,indent=2))
print(json.dumps({'report_sha256':receipt['report_sha256'],'archive_sha256':receipt['archive_sha256'],'members':len(hashes)},indent=2))
