from pathlib import Path
import subprocess, json, hashlib, zipfile, io, datetime

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent
SHA = '05ae40615a5b62227857e3477cfd484a116f3a5a'
HEAD = '03ce0c82c3b7da489d49a5db82f6fb467e9c98a9'
BASE = 'b20beb920a5e1cdb4e42ff5552903ea701d3ee6a'
TREE = '81f443ccd1409363c77caa5325557b30b1b59a28'
RUN = 37462432311
REPO = 'severinafrancic/RectoFlow'
def command(*args):
    return subprocess.check_output(args, cwd=ROOT)
def gh(*args): return command('gh', *args)
def git(*args): return command('git', *args).decode().strip()
def digest(data): return hashlib.sha256(data).hexdigest()
def save(path, value): path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

assert git('rev-parse','HEAD') == SHA
assert git('rev-parse','HEAD^{tree}') == TREE
assert git('show','--no-patch','--format=%P','HEAD').split() == [BASE,HEAD]
assert not git('status','--porcelain')
assert json.loads(gh('api',f'repos/{REPO}/branches/main'))['commit']['sha'] == SHA
pr = json.loads(gh('pr','view','7','--repo',REPO,'--json','state,mergedAt,mergeCommit,headRefOid,baseRefOid'))
assert pr['state']=='MERGED' and pr['mergeCommit']['oid']==SHA and pr['headRefOid']==HEAD and pr['baseRefOid']==BASE
ci = json.loads(gh('run','view',str(RUN),'--repo',REPO,'--json','status,conclusion,headSha,jobs,url'))
assert ci['status']=='completed' and ci['conclusion']=='success' and ci['headSha']==SHA
assert all(j['conclusion']=='success' for j in ci['jobs'])
artifacts = json.loads(gh('api',f'repos/{REPO}/actions/runs/{RUN}/artifacts'))['artifacts']
assert len(artifacts)==1
artifact = artifacts[0]
assert artifact['workflow_run']['head_sha']==SHA and not artifact['expired']
stage = ROOT/'.build-release-v020-05ae406'
stage.mkdir(exist_ok=False)
wrapper = gh('api',f'repos/{REPO}/actions/artifacts/{artifact["id"]}/zip')
assert 'sha256:'+digest(wrapper)==artifact['digest']
(stage/'ci-artifact-wrapper.zip').write_bytes(wrapper)
with zipfile.ZipFile(io.BytesIO(wrapper)) as z:
    assert z.namelist()==['RectoFlow-0.2.0-windows-x64.zip'] and z.testzip() is None
    portable=z.read(z.namelist()[0])
windows=stage/'RectoFlow-0.2.0-windows-x64.zip'
windows.write_bytes(portable)
with zipfile.ZipFile(io.BytesIO(portable)) as z:
    names=z.namelist()
    assert len(names)==len(set(names)) and z.testzip() is None
    assert all(not n.startswith('/') and '..' not in Path(n).parts for n in names)
    metadata=json.loads(z.read('RectoFlow/BUILD_METADATA.json'))
    assert metadata['source_commit']==SHA and not metadata['working_tree_dirty']
    assert metadata['code_tree_sha256']=='99ccfb5ab1c59c65b51ba7ab8fe70c71c72e7ae188eccfe1a9546f07835558fe'
    for name, expected in metadata['files'].items():
        actual=z.read('RectoFlow/_internal/'+name)
        assert digest(actual)==expected==digest((ROOT/name).read_bytes())
    for name in ['LICENSE','config.json','README.de.md','THIRD_PARTY_NOTICES.md',*git('ls-files','docs').splitlines()]:
        assert z.read('RectoFlow/'+name)==(ROOT/name).read_bytes(), name
    exe_sha=digest(z.read('RectoFlow/RectoFlow.exe'))
source=stage/'RectoFlow-0.2.0-source.zip'
command('git','archive','--format=zip','--prefix=RectoFlow-0.2.0/','--output',str(source),SHA)
with zipfile.ZipFile(source) as z:
    assert z.testzip() is None
    tracked=git('ls-files').splitlines()
    assert {n for n in z.namelist() if not n.endswith('/')}=={'RectoFlow-0.2.0/'+n for n in tracked}
    for name in tracked:
        assert z.read('RectoFlow-0.2.0/'+name)==command('git','show',SHA+':'+name)
ci_log=gh('run','view',str(RUN),'--repo',REPO,'--log')
(OUT/'RectoFlow-0.2-postmerge-windows-ci-05ae406.log').write_bytes(ci_log)
log_text=ci_log.decode(errors='replace')
for token in ['Ran 129 tests','NATIVE_UI_SMOKE_PASS','NATIVE_REVIEW_SMOKE_PASS','README_ASSETS_CHECK_PASS']:
    assert token in log_text, token
local_log=ROOT/'.build-postmerge-tests-05ae406-native.log'
assert 'Ran 129 tests' in local_log.read_text(encoding='utf-8-sig')
report=OUT/'RectoFlow-0.2-closure-fresh-breaker-03ce0c8.md'
assert digest(report.read_bytes())=='3adc49ef4a0eb641f17a34ce7ec9e5d1312f09720ea41806f6378859e57a22fd'
start='''RectoFlow 0.2.0 - Windows x64 (fruehe Vorabversion)

1. RectoFlow-0.2.0-windows-x64.zip vollstaendig in einen beschreibbaren Ordner entpacken.
2. RectoFlow.exe starten. Der Ordner _internal muss daneben bleiben.
3. Browser-Dokument auf dem Hauptmonitor oeffnen, Profil/Config waehlen und Bereiche kalibrieren.
4. Ein oder mehrere freie Rechtecke und bei automatischer Navigation den Weiter-Bereich einstellen.
5. Aufnahme pruefen, Ansichten auswaehlen/ordnen und PDF-Format (A0-A6, Letter, Legal, Original), Orientierung und Layout festlegen.

Kein zusaetzliches Python erforderlich. MIT-Lizenz; keine Cloud/Telemetrie.
Browser: Edge nur fuer dokumentierte Pfade real getestet. Chrome/Brave/Firefox implementiert,
aber reale E2E-Pruefung offen. Reale 125/150-%-DPI-Laeufe offen.
Unsignierte Vorabversion: Windows-App-Control kann den Start blockieren. Keine Schutzrichtlinien umgehen.
Dokumentation: docs/USER_GUIDE.md, docs/COMPATIBILITY.md; README.de.md.
https://github.com/severinafrancic/RectoFlow
'''
(stage/'START.de.txt').write_text(start,encoding='utf-8')
verification=f'''RectoFlow 0.2.0 release verification
Repository: https://github.com/{REPO}
PR: https://github.com/{REPO}/pull/7 (MERGED)
Owner acceptance: direct human instruction, recorded for head {HEAD} / base {BASE}.
Merge/source/tag commit: {SHA}
Tree: {TREE}
Merge parents: {BASE} {HEAD}
Independent Fresh Breaker subject: {HEAD}; READY_FOR_OWNER_ACCEPTANCE.
Independent report SHA256: {digest(report.read_bytes())}
Merge tree is byte-identical to independently reviewed tree; no conflict resolution or material changes.
Post-merge coordinator/Builder checks do not constitute a new independent review.
Windows CI: https://github.com/{REPO}/actions/runs/{RUN} SUCCESS.
Hosted Windows execution: 129 tests, native Tk selection/review, reproducible demo check,
portable EXE self-check and relocated frozen EXE/PDF/provenance smoke passed.
Local post-merge: 129 tests, native Tk selection/review and demo check passed.
Initial restricted sandbox attempt failed with native filesystem WinError 5; separately authorized
native Windows execution passed. Both logs retained; failure not hidden.
Package artifact ID: {artifact['id']}; wrapper SHA256: {digest(wrapper)}
Windows ZIP SHA256: {digest(portable)}
EXE SHA256: {exe_sha}
Source ZIP SHA256: {digest(source.read_bytes())}
Embedded source metadata: exact merge SHA, clean tree, all runtime files verified against Git source.
Compatibility: Edge real runtime evidence is limited to documented owned-fixture UIA/template,
96-DPI capture/export paths. Historical real frozen EXE Edge evidence remains bound to the old RC
and its hashes, not transferred to this new EXE. Current EXE execution is established on hosted CI;
local current frozen EXE execution is NOT_EXECUTED (Windows App Control WinError 4551), no bypass.
Chrome/Brave/Firefox: IMPLEMENTED, SYNTHETICALLY_VERIFIED, UNVERIFIED_RUNTIME.
Physical 125/150-percent DPI: UNVERIFIED_RUNTIME; coordinate/DPI contracts tested.
Full live profile/DOM provider combinations and current frozen interactive Edge capture remain open.
Historical live UIA top-window identity mismatch remains disclosed and fail-closed, not claimed fixed.
README screenshots: actual Tk components with synthetic local fixtures; not runtime browser/DPI proof.
No all-browser/DPI production certification. Unsigned early Windows prerelease.
Historical reports/releases unchanged. Main protection not bypassed.
'''
(stage/'VERIFICATION-v0.2.0.txt').write_text(verification,encoding='utf-8')
notes=f'''RectoFlow 0.2.0 ist veröffentlicht: freie Aufnahmebereiche, explizite Browserfenster-Auswahl, Profile, Config-Backups und eine getrennte Kontrolle vor dem PDF-Export.

**Frühe, unsignierte Windows-Vorabversion.** Edge ist für die [dokumentierten Testpfade](https://github.com/{REPO}/blob/v0.2.0/docs/COMPATIBILITY.md) real geprüft. Chrome, Brave und Firefox sind implementiert und durch Vertragstests abgesichert; ihre realen E2E-Läufe sind weiterhin **UNVERIFIED_RUNTIME**. Physische 125/150-%-DPI-Läufe bleiben ebenfalls offen. Keine Produktionszertifizierung über alle Browser-/DPI-Kombinationen.

- Einen, zwei oder beliebig viele Bereiche verschieben, skalieren, duplizieren und ordnen; Papierformat unabhängig wählen.
- Fensterbindung, Profile mit isolierten Config-/Template-Snapshots, prozessübergreifende Sperren sowie atomare Backups/Restore.
- Unveränderte Capture-Originale, Thumbnail-Kontrolle, Ähnlichkeitswarnungen und persistierte ExportPlan-/PDF-Provenance.
- A0–A6, Letter, Legal und Original; Hoch-/Querformat, getrennte Seiten oder horizontale Zusammenstellung.
- README-Demos aus den echten Tk-Komponenten mit deutlich markierten synthetischen Daten.

**Windows starten:** `RectoFlow-0.2.0-windows-x64.zip` vollständig entpacken und `RectoFlow.exe` öffnen. `_internal` daneben behalten. Kein zusätzliches Python erforderlich. Windows App Control kann die unsignierte EXE blockieren; auf dem lokalen Prüfhost wurde die aktuelle Frozen-EXE deshalb nicht ausgeführt. Es wurde keine Schutzrichtlinie umgangen.

**Verifikation:** [PR #7](https://github.com/{REPO}/pull/7) gemergt nach Owner-Freigabe. Unabhängiger Fresh Breaker: READY_FOR_OWNER_ACCEPTANCE am Head `{HEAD}`, Tree `{TREE}`. Der Merge `{SHA}` enthält exakt diesen Tree. [Windows-CI auf dem Merge-SHA](https://github.com/{REPO}/actions/runs/{RUN}) erfolgreich: 129 Tests, native Tk-Smokes, reproduzierbare Demo-Bilder, Portable-Build und tatsächlicher relocated Frozen-EXE/PDF-Smoke. Lokale Post-Merge-Tests und Tk-/Demo-Prüfungen ebenfalls erfolgreich. Die aktuellen hosted EXE-Smokes ersetzen keinen realen interaktiven Browserlauf mit dieser EXE.

Details, Hashes und offene Nachweise: `VERIFICATION-v0.2.0.txt`. Integrität: `SHA256SUMS.txt`. Quellcode: `RectoFlow-0.2.0-source.zip`, MIT-Lizenz. Diese Ausgabe folgt auf `v0.2.0-rc.1`; historische Reports und RC-Assets bleiben erhalten.
'''
(stage/'release-notes.md').write_text(notes,encoding='utf-8')
assets=[windows,source,stage/'START.de.txt',stage/'VERIFICATION-v0.2.0.txt']
(stage/'SHA256SUMS.txt').write_text(''.join(f'{digest(p.read_bytes())}  {p.name}\n' for p in assets),encoding='ascii')
assets.append(stage/'SHA256SUMS.txt')
receipt={'schema':1,'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'lifecycle':'POST_MERGE_VERIFIED','repository':REPO,'pr':pr,'source_commit':SHA,'tree':TREE,'reviewed_head':HEAD,'reviewed_tree_identical':True,'ci':ci,'artifact':artifact,'metadata':metadata,'exe_sha256':exe_sha,'assets':{p.name:{'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())} for p in assets},'stage':str(stage),'known_limitations':'See VERIFICATION-v0.2.0.txt; local frozen EXE not executed, cross-browser/physical DPI evidence open; old cleanup residue untouched.'}
save(OUT/'RectoFlow-0.2-postmerge-verification-05ae406.json',receipt)
(OUT/windows.name).write_bytes(portable)
(OUT/source.name).write_bytes(source.read_bytes())
print(json.dumps({'status':'PREPARED_VERIFIED','stage':str(stage),'windows_sha256':digest(portable),'exe_sha256':exe_sha,'source_sha256':digest(source.read_bytes()),'members':len(names)},indent=2))
