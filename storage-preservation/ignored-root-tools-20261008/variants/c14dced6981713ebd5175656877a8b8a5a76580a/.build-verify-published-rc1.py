from pathlib import Path
import datetime,hashlib,json,subprocess,urllib.request
root=Path.cwd();s=root/'.build-release-rc1';out=root.parent
prepared=json.loads((s/'prepared-assets.json').read_text(encoding='utf-8'))
def api(path):
 request=urllib.request.Request('https://api.github.com/'+path,headers={'User-Agent':'RectoFlow-release-verification','Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(request,timeout=60) as response:
  assert response.status==200
  return json.loads(response.read().decode('utf-8'))
release=api('repos/severinafrancic/RectoFlow/releases/tags/v0.2.0-rc.1')
assert release['draft'] is False and release['prerelease'] is True and release['published_at']
assert release['target_commitish']==prepared['subject'] and release['tag_name']==prepared['tag']
assert release['body'].replace('\r\n','\n')==(s/'release-notes.md').read_text(encoding='utf-8')
tag=api('repos/severinafrancic/RectoFlow/git/ref/tags/v0.2.0-rc.1')
assert tag['object']['type']=='commit' and tag['object']['sha']==prepared['subject']
main=api('repos/severinafrancic/RectoFlow/branches/main')
assert main['commit']['sha']=='b20beb920a5e1cdb4e42ff5552903ea701d3ee6a'
pr=api('repos/severinafrancic/RectoFlow/pulls/7')
assert pr['draft'] and pr['state']=='open' and pr['head']['sha']==prepared['subject']
assert {a['name'] for a in release['assets']}==set(prepared['assets'])
verified={}
for asset in release['assets']:
 wanted=prepared['assets'][asset['name']]
 request=urllib.request.Request(asset['browser_download_url'],headers={'User-Agent':'RectoFlow-release-verification'})
 with urllib.request.urlopen(request,timeout=60) as response:
  assert response.status==200
  data=response.read()
 digest=hashlib.sha256(data).hexdigest()
 assert asset['state']=='uploaded' and asset['size']==wanted['bytes']==len(data)
 assert digest==wanted['sha256']
 if asset.get('digest'):assert asset['digest']=='sha256:'+digest
 verified[asset['name']]={'bytes':len(data),'sha256':digest,'url':asset['browser_download_url'],'public_http_status':200}
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
receipt={'schema':1,'operation':'owner-authorized public prerelease transport','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'release_id':release['id'],'release_url':release['html_url'],'tag':release['tag_name'],'tag_commit':tag['object']['sha'],'draft':False,'prerelease':True,'published_at':release['published_at'],'public_verification':'unauthenticated GitHub API and all five asset downloads verified','assets':verified,'main_sha':main['commit']['sha'],'pr':{'number':7,'state':pr['state'],'draft':pr['draft'],'head':pr['head']['sha'],'base':pr['base']['sha']},'source_mutated':False,'builder_lifecycle':'INDEPENDENT_REVIEW_PENDING','independent_status':'BREAKER_BLOCKED','open_proof':'FBR-02-PROOF-004','stable_release_published':False,'main_merged':False,'owner_acceptance_issued':False}
with (out/'RectoFlow-v0.2.0-rc.1-publication-receipt.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
print(json.dumps({'release_url':receipt['release_url'],'published_at':release['published_at'],'tag_commit':tag['object']['sha'],'assets_public_byte_verified':len(verified),'main_unchanged':True,'source_unchanged':True},indent=2))
