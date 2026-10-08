from pathlib import Path
import hashlib,json,os,subprocess,zipfile
root=Path.cwd();review=root/'.build-live-fbr-rc1-20261006';out=root.parent
sha='e7627a6a3fcee822236c82777d451fbed963b9ea';tree='d6bd848ecf51a5088f59ac1bcc405e7a106e714d'
def digest(data):return hashlib.sha256(data).hexdigest()
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==sha
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()==tree
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
report=review/'FRESH_BREAKER.md';registry=review/'evidence-digests.json'
assert digest(report.read_bytes())=='facf635efa3227d00e12f8c68beaac3b1880ad5f4a9dc0527f3d222cc01ced01'
assert digest(registry.read_bytes())=='bdae2f8867780058210cb90c3461ceb33a4b1ba337e03b736aa011b49220df8d'
records=json.loads(registry.read_text(encoding='utf-8'))
for item in records['files']:
 data=(review/item['path']).read_bytes()
 assert len(data)==item['size'] and digest(data)==item['sha256'], item['path']
report_out=out/'RectoFlow-v0.2.0-rc.1-live-fresh-breaker-20261006.md'
with report_out.open('xb') as f:f.write(report.read_bytes())
archive=out/'RectoFlow-v0.2.0-rc.1-live-evidence-20261006.zip'
files={};stack=[review]
while stack:
 folder=stack.pop()
 for item in os.scandir(folder):
  path=Path(item.path)
  if path.is_symlink() or path.is_junction():raise ValueError('Unexpected evidence redirection')
  if item.is_dir(follow_symlinks=False):stack.append(path)
  elif item.is_file(follow_symlinks=False):files[path.relative_to(review).as_posix()]=path
hashes={}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for name,path in sorted(files.items()):
  data=path.read_bytes();hashes[name]=digest(data);z.writestr(name,data)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and set(z.namelist())==set(hashes)
 for name,expected in hashes.items():assert digest(z.read(name))==expected
receipt={'schema':1,'subject_sha':sha,'subject_tree':tree,'rc_zip_sha256':'febf2e1184ac8cdaeec8e952ef8726f7c78356721abfed3fe074d1f93baaa4f6','review_producer':'independent Fresh Breaker reasoning context; same host','retention_producer':'parent coordination; no independent acceptance','report_sha256':digest(report_out.read_bytes()),'archive_sha256':digest(archive.read_bytes()),'member_count':len(hashes),'members':hashes,'verdict':'BREAKER_BLOCKED','open_proof':'FBR-02-PROOF-004','desktop_tests_executed':False,'source_unchanged':True,'scale_changed':False,'restore':'NOT_NEEDED_NO_CHANGE','retirement':'No worktree/process created; dedicated evidence retained'}
with (out/'RectoFlow-v0.2.0-rc.1-live-retention-20261006.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
print(json.dumps({k:receipt[k] for k in ('report_sha256','archive_sha256','member_count','verdict','source_unchanged','scale_changed')},indent=2))
