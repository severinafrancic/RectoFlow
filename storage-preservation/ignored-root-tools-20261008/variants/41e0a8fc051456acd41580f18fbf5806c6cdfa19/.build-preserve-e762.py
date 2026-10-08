from pathlib import Path
import hashlib,json,os,shutil,zipfile
root=Path(__file__).resolve().parent
review=root/'.build-b3'; out=root.parent
report=review/'.build-fresh-breaker-report.md'
expected='baf57048a35cff1ce86f53b8c2b295914339e80b895279e2ed71ade4295cd81f'
assert hashlib.sha256(report.read_bytes()).hexdigest()==expected
for record in json.loads((review/'.build-breaker-fixtures/evidence-hashes.json').read_text()):
    assert hashlib.sha256((review/record['file']).read_bytes()).hexdigest()==record['sha256'], record['file']
members={'.build-fresh-breaker-report.md':report}
def walk(base,prefix):
    stack=[base]
    while stack:
        folder=stack.pop()
        for item in os.scandir(folder):
            path=Path(item.path)
            if path.is_symlink() or path.is_junction(): raise ValueError('Unexpected reparse path')
            if item.is_dir(follow_symlinks=False): stack.append(path)
            elif item.is_file(follow_symlinks=False): members[prefix+'/'+path.relative_to(base).as_posix()]=path
walk(review/'.build-breaker-fixtures','fixtures')
walk(review/'.build-edge-fixture','edge')
archive=out/'RectoFlow-0.2.0-breaker-evidence-e7627a6.zip'
hashes={}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for name,path in sorted(members.items()):
        data=path.read_bytes(); hashes[name]=hashlib.sha256(data).hexdigest(); z.writestr(name,data)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert set(z.namelist())==set(hashes)
    for name,digest in hashes.items(): assert hashlib.sha256(z.read(name)).hexdigest()==digest
saved=out/'RectoFlow-0.2.0-breaker-e7627a6.md'
with saved.open('xb') as f: f.write(report.read_bytes())
assert hashlib.sha256(saved.read_bytes()).hexdigest()==expected
receipt={'subject':'e7627a6a3fcee822236c82777d451fbed963b9ea','tree':'d6bd848ecf51a5088f59ac1bcc405e7a106e714d','verdict':'BREAKER_BLOCKED','report_sha256':expected,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'members':hashes,'retirement_trigger':'closed independent review; all member bytes preserved and verified'}
with (out/'RectoFlow-0.2.0-breaker-retention-e7627a6.json').open('x',encoding='utf-8') as f: json.dump(receipt,f,indent=2)
print(json.dumps({'report_sha256':expected,'archive_sha256':receipt['archive_sha256'],'members':len(hashes)},indent=2))
pr=root/'.build-final-pr.md'
body=pr.read_text()
body=body.replace('Acceptance remains gated by final independent review, required real browser/DPI/owner-calibration evidence and owner acceptance for this exact PR head/base. No main merge or final 0.2 release is performed by opening this PR.', 'The independent Fresh Breaker revalidated all three earlier defects as repaired on this exact subject and found no new confirmed product defect in its executed scope. It independently passed 124 source tests, 12 adversarial checks, both native Tk checks, both owned Edge modes at 96 DPI, and 11 actual downloaded EXE invocations; all 1,277 package members were byte-verified. Report SHA-256: baf57048a35cff1ce86f53b8c2b295914339e80b895279e2ed71ade4295cd81f.\n\nIndependent status is BREAKER_BLOCKED (FBR-02-PROOF-004): required real Chrome/Brave/Firefox, physical 125/150% scaling and full interactive calibration remain unproven. This draft is the concrete main integration boundary, not owner acceptance. Complete the missing compatibility proof, re-evaluate the unchanged exact PR head/base, and obtain owner acceptance before main merge and final release. No main merge or final 0.2 release is performed by opening this PR.')
pr.write_text(body,encoding='utf-8')
