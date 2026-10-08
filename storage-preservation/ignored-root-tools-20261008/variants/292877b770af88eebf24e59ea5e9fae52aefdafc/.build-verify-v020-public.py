from pathlib import Path
import json, urllib.request, hashlib, datetime, subprocess
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent
REPO='severinafrancic/RectoFlow'
SHA='05ae40615a5b62227857e3477cfd484a116f3a5a'
expected=json.loads((OUT/'RectoFlow-0.2-postmerge-verification-05ae406.json').read_text(encoding='utf-8'))
stage=Path(expected['stage'])
def read(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RectoFlow-public-release-verification','Accept':'application/vnd.github+json' if 'api.github.com' in url else '*/*'}),timeout=60) as response:
        assert response.status==200
        return response.read()
def api(path):return json.loads(read('https://api.github.com/'+path))
release=api(f'repos/{REPO}/releases/tags/v0.2.0')
assert not release['draft'] and release['prerelease'] and release['tag_name']=='v0.2.0'
assert release['body'].replace('\r\n','\n')==(stage/'release-notes.md').read_text(encoding='utf-8')
tag=api(f'repos/{REPO}/git/ref/tags/v0.2.0')
assert tag['object']['type']=='commit' and tag['object']['sha']==SHA
assert api(f'repos/{REPO}/branches/main')['commit']['sha']==SHA
assert {a['name'] for a in release['assets']}==set(expected['assets'])
verified=[]
for asset in release['assets']:
    data=read(asset['browser_download_url'])
    sha=hashlib.sha256(data).hexdigest()
    requirement=expected['assets'][asset['name']]
    assert len(data)==asset['size']==requirement['bytes']
    assert sha==requirement['sha256'] and data==(stage/asset['name']).read_bytes()
    if asset.get('digest'): assert asset['digest']=='sha256:'+sha
    assert asset['state']=='uploaded'
    verified.append({'name':asset['name'],'url':asset['browser_download_url'],'bytes':len(data),'sha256':sha,'public_download':'HTTP 200, exact bytes'})
receipt={'schema':1,'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'lifecycle':'POST_MERGE_VERIFIED','release_published':True,'public_release_url':release['html_url'],'release_id':release['id'],'prerelease':True,'source_commit':SHA,'tree':expected['tree'],'tag':tag,'assets':verified,'windows_ci':expected['ci']['url'],'public_body_verified':True,'working_tree':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(),'historical_reports_and_releases':'unchanged','compatibility':'Scoped Edge evidence; other browser real E2E and physical125/150DPI remain UNVERIFIED_RUNTIME; no production certification.'}
assert receipt['working_tree']==''
receipt['public_body_comparison']='Exact content after GitHub LF-to-CRLF newline conversion; raw public text SHA256 separately retained.'
receipt['public_body_sha256']=hashlib.sha256(release['body'].encode('utf-8')).hexdigest()
(OUT/'RectoFlow-0.2-publication-verification-05ae406.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
for name in ['START.de.txt','VERIFICATION-v0.2.0.txt','SHA256SUMS.txt']:
    (OUT/('RectoFlow-0.2-'+name)).write_bytes((stage/name).read_bytes())
for name in ['.build-postmerge-tests-05ae406.log','.build-postmerge-tests-05ae406-native.log']:
    (OUT/('RectoFlow'+name[6:])).write_bytes((ROOT/name).read_bytes())
print(json.dumps({'public_release_verified':release['html_url'],'source_commit':SHA,'assets_verified':len(verified),'working_tree':'clean'},indent=2))
