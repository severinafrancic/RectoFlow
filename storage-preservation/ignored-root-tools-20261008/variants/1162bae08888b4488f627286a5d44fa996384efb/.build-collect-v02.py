from pathlib import Path
import hashlib,json,shutil,subprocess,zipfile
import edge_capture as core

root=Path(__file__).resolve().parent;out=root.parent
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip()
assert sha=='e7627a6a3fcee822236c82777d451fbed963b9ea'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
source=root/'.build-ci-e7627a6/RectoFlow-0.2.0-windows-x64.zip'
with zipfile.ZipFile(source) as archive:
    assert archive.testzip() is None
    meta=json.loads(archive.read('RectoFlow/BUILD_METADATA.json'))
    assert meta['source_commit']==sha and not meta['working_tree_dirty']
    assert meta['code_tree_sha256']==core.code_identity()['sha256']
    for path,digest in meta['files'].items():
        assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest
        assert hashlib.sha256(archive.read('RectoFlow/_internal/'+path)).hexdigest()==digest
    check=json.loads(archive.read('RectoFlow/SELF_CHECK.json'))
    assert check['frozen'] and check['architecture']==64 and check['version']=='0.2.0'
target=out/'RectoFlow-0.2.0-candidate-e7627a6-windows-x64.zip'
assert not target.exists()
shutil.copyfile(source,target)
ci=json.loads((root/'.build-e7627a6-ci.json').read_text(encoding='utf-8-sig'))
assert ci['headSha']==sha and ci['conclusion']=='success'
receipts=[]
for mode in ('template','uia'):
    found=[]
    for path in (root/'.build-edge-fixture').glob('*/receipt.json'):
        data=json.loads(path.read_bytes())
        if data.get('button_mode')==mode and data.get('code_tree',{}).get('sha256')==meta['code_tree_sha256']:found.append((path.stat().st_mtime,data))
    assert found
    receipts.append(max(found,key=lambda pair:pair[0])[1])
qa=json.loads((root/'.build-pdf-qa/receipt.json').read_bytes())
assert qa['code_tree']['sha256']==meta['code_tree_sha256']
proof={'schema':1,'role':'BUILDER','lifecycle':'INDEPENDENT_REVIEW_PENDING','repository':'https://github.com/severinafrancic/RectoFlow',
    'branch':'integration/rectoflow-0.2','sha':sha,'tree':tree,'code_tree_sha256':meta['code_tree_sha256'],'package_sha256':core.sha256(target),
    'ci':ci,'build_metadata':meta,'self_check':check,'local_tests':{'suite':'124 unittest tests','result':'PASS','native_tk':['calibration picker PASS','review/export PASS']},
    'owned_edge_composition':receipts,'pdf_qa':qa,'visual_qa':['A4 portrait separate: all corners visible, proportional centered image','A5 landscape spread: original order, full borders','Original portrait separate: exact image aspect'],
    'ruleset':json.loads((root/'.build-e7627a6-ruleset.json').read_text(encoding='utf-8-sig')),
    'ruleset_smoke':{name:json.loads((root/f'.build-smoke-{name}.json').read_text(encoding='utf-8-sig')) for name in ('pending','success','closed')},
    'remediation':{'old_subjects':{'764dc1e39d7e1dd2fa961fcbf63ce55668cb7d8b':core.sha256(out/'RectoFlow-0.2.0-breaker-764dc1e.md'),'4166dd2e1f2868daf90f22e6dd3172ed788b9b8a':core.sha256(out/'RectoFlow-0.2.0-breaker-4166dd2.md')},'old_verdicts':'BREAKER_FAILED','findings':['FBR-02-001 malformed-profile isolation corrected','FBR-02-002 serialized positive finite PDF page dimensions enforced','FBR-02-003 shared template validation contains parser errors and checks dimensions before load','pyproject version agrees with0.2.0']},
    'browser_availability_at_typical_paths':json.loads((root/'.build-browser-availability.json').read_text(encoding='utf-8-sig')),
    'retirement_receipt':json.loads((out/'RectoFlow-0.2.0-retirement-4166dd2.json').read_bytes()),
    'limitations':['final downloaded artifact independent local execution recorded separately by Fresh Breaker','actual native browser coverage is owned Edge guest at96DPI only','interactive owner calibration and Chrome/Brave/Firefox/other physical DPI composition not established','Fresh Breaker/Owner acceptance separate; no main merge or final0.2release performed']}
with (out/'RectoFlow-0.2.0-builder-e7627a6.json').open('x',encoding='utf-8') as stream:stream.write(json.dumps(proof,ensure_ascii=False,indent=2))
print(json.dumps({'sha':sha,'tree':tree,'package':target.name,'package_sha256':core.sha256(target),'code_tree_sha256':meta['code_tree_sha256']},indent=2))
