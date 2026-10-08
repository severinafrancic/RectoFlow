from pathlib import Path
import datetime,hashlib,json,subprocess,zipfile
root=Path(__file__).resolve().parent;out=root.parent
sha='e7627a6a3fcee822236c82777d451fbed963b9ea';tree='d6bd848ecf51a5088f59ac1bcc405e7a106e714d';base='b20beb920a5e1cdb4e42ff5552903ea701d3ee6a'
def read(name):return json.loads((root/name).read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==sha
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip()==tree
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
pr=read('.build-final-pr-completed.json');ci=read('.build-final-pr-ci.json');merge=read('.build-final-pr-merge-tree.json');rules=read('.build-final-ruleset.json');main=read('.build-final-main.json')
assert pr['headRefOid']==sha and pr['baseRefOid']==base and pr['isDraft'] and pr['state']=='OPEN' and pr['mergeable']=='MERGEABLE'
assert ci['headSha']==sha and ci['status']=='completed' and ci['conclusion']=='success'
assert merge['tree']['sha']==tree and [x['sha'] for x in merge['parents']]==[base,sha]
assert main['commit']['sha']==base
assert rules['enforcement']=='active' and rules['bypass_actors']==[] and rules['current_user_can_bypass']=='never'
checks=next(x['parameters'] for x in rules['rules'] if x['type']=='required_status_checks')
assert checks['strict_required_status_checks_policy'] and checks['required_status_checks']==[{'context':'windows','integration_id':15368}]
pull=next(x['parameters'] for x in rules['rules'] if x['type']=='pull_request')
assert pull['required_review_thread_resolution']
assert {'deletion','non_fast_forward'}.issubset({x['type'] for x in rules['rules']})
package=out/'RectoFlow-0.2.0-candidate-e7627a6-windows-x64.zip';source=out/'RectoFlow-0.2.0-candidate-e7627a6-source.zip'
assert digest(package)=='febf2e1184ac8cdaeec8e952ef8726f7c78356721abfed3fe074d1f93baaa4f6'
with zipfile.ZipFile(source) as z: assert z.testzip() is None
receipt={'schema':1,'role':'BUILDER','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'subject':sha,'tree':tree,'branch':'integration/rectoflow-0.2','tracked_status':'CLEAN','main_sha':base,'pr':pr,'pr_ci':ci,'synthetic_merge':{'sha':merge['sha'],'tree':merge['tree']['sha'],'parents':[x['sha'] for x in merge['parents']],'same_tree_as_subject':True,'note':'GitHub PR test merge only; main has not been merged'},'ruleset':rules,'source_archive_sha256':digest(source),'package_sha256':digest(package),'independent_report_sha256':digest(out/'RectoFlow-0.2.0-breaker-e7627a6.md'),'independent_verdict':'BREAKER_BLOCKED','open_finding':'FBR-02-PROOF-004','owner_acceptance':False,'main_merged':False,'final_release_published':False,'builder_lifecycle':'INDEPENDENT_REVIEW_PENDING','raw_receipt_sha256':{name:digest(root/name) for name in ['.build-final-pr-completed.json','.build-final-pr-ci.json','.build-final-pr-merge-tree.json','.build-final-ruleset.json','.build-final-main.json','.build-final-pr-ci.log']}}
with (out/'RectoFlow-0.2.0-pr-boundary-e7627a6.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
report='''BUILDER STATUS
==============
Exact SHA: e7627a6a3fcee822236c82777d451fbed963b9ea
Git tree: d6bd848ecf51a5088f59ac1bcc405e7a106e714d
Repository: https://github.com/severinafrancic/RectoFlow
Canonical checkout: C:\\Users\\sever\\Documents\\Codex\\2026-10-05\\referenced-chatgpt-conversation-this-is-an\\outputs\\RectoFlow
Branch: integration/rectoflow-0.2

Scope:
The approved RectoFlow 0.2 calibration/profile/review slice is implemented: free one/two/many capture rectangles; explicit browser-window selection; identity/environment-before-activation then foreground checks; atomic config backup/restore; cooperative native cross-process locking using canonical Windows paths/file identity and stable profile lock locations; optional experimental one-use DOM result-file transport without clipboard changes.
Indexless UUID profiles have isolated config/templates, import/duplicate/rename/presets and region duplication/alignment. Config/template bytes are read under locks and used in memory through capture, with profile digests recorded.
Schema-3 capture manifests finalize COMPLETE/STOPPED with finished timestamp before immutable review. RUNNING remains recovery-required, never silently exported/finalized. Whole saved views can be excluded/reordered uniquely with thumbnail/similarity/contrast warnings. Every new schema-3 export, including rebuild, uses authoritative persisted ExportPlan bytes and verified same-buffer PNG hash/decode/dimension/render. Separate result records bind plan, manifest and PDF hashes; originals stay unchanged. Legacy exports remain supported. A0-A6/Letter/Legal/Original, portrait/landscape, separate/spread remain available.
MIT license, English/German README, documentation and Windows portable build/version are included. No OCR/multi-monitor/resume/browser plugin/grid/quality-profile/named-region expansion.

Result:
Implementation and exact-source portable Windows candidate prepared. Feature PRs #2/#3/#4 and remediation PRs #5/#6 merged only to integration. Final integration-to-main PR #7 is OPEN/DRAFT:
https://github.com/severinafrancic/RectoFlow/pull/7
Head e7627a6a3fcee822236c82777d451fbed963b9ea; base b20beb920a5e1cdb4e42ff5552903ea701d3ee6a. GitHub reports MERGEABLE/CLEAN and both required windows checks successful. This technical mergeability is not owner acceptance. Main remains at the base; no final v0.2 release/tag was published.

Tests:
- Builder and independent reruns: 124 source regression tests PASS on the exact subject.
- Fresh Breaker: 12 independently written adversarial boundary cases PASS.
- Native hidden Tk calibration and review smoke checks PASS, independently rerun.
- Owned fresh Edge guest localhost fixtures: template-snapshot and native UIA modes PASS at observed 96 DPI, independently rerun on exact e762. Each: 3 views, 2 regions, exactly 2 Next events, terminal disabled detection and PDF. Interactive selection was injected with the explicitly owned window; this is not owner-calibration proof.
- Independent downloaded final EXE: 11 actual invocations PASS, including relocated self-check, source/plan/legacy exports, PDF ordering/hash/pixel checks, RUNNING and extreme-DPI/template-bomb rejection.
- All 1,277 final ZIP members byte-verified independently; 15 runtime source members and packaged docs/config match source/build metadata.
- Builder export checks: all 40 paper/orientation/layout combinations PASS; three representative output layouts visually inspected. Renderer/runtime byte-tree bound in Builder receipt. Not all 40 layouts were visually inspected.
- Exact integrated push Windows CI 37382635215 / job 112008153613: SUCCESS.
- Final PR Windows CI 37383927244 / job 112012435822: SUCCESS. PR synthetic merge 06d4120dbdb5deb21634db3b82c3a5f1a69e63d5 has parents [base,head] above and identical Git tree d6bd848ecf51a5088f59ac1bcc405e7a106e714d. This is test-merge evidence, not a main merge or post-merge certification.
- Main ruleset active: PR + strict GitHub Actions windows + resolved conversations required; force push/delete blocked; no bypass. Dedicated smoke PR #1 was observed blocked while windows pending, clean/mergeable after success, then closed unmerged.

Evidence:
RectoFlow-0.2.0-builder-e7627a6.json: immutable Builder test/build/config/metadata receipt.
RectoFlow-0.2.0-breaker-e7627a6.md: exact-subject independent report; SHA256 baf57048a35cff1ce86f53b8c2b295914339e80b895279e2ed71ade4295cd81f.
RectoFlow-0.2.0-breaker-evidence-e7627a6.zip: 2,245 retained report/fixture/Edge evidence member bytes verified; SHA256 5ef903687eafb5bb9763ecd2639ee5bff99052dc49f6b0ca6e03e2a508998077.
RectoFlow-0.2.0-breaker-retention-e7627a6.json: full archive member digest registry.
RectoFlow-0.2.0-pr-boundary-e7627a6.json: hosted final head/base/check/ruleset/synthetic merge boundary.
RectoFlow-0.2.0-retirement-e7627a6.json: final registered review worktree retired through Git after byte retention; clean canonical state.
RectoFlow-0.2.0-SHA256SUMS-e7627a6.txt: delivery digests.
Historical failed reviews remain separately preserved; their verdicts do not prove this final subject.

Known limitations:
Native Windows 10/11 x64, primary monitor only; finite screen/memory/storage; unsigned portable candidate. Automatic Next depends on page/provider/button semantics; unknown or failed transition stops and is not retried. Optional DOM proposals can be blocked by CSP; screenshot selection remains default. No resume for hard-aborted RUNNING runs. External noncooperative file writers remain outside native cooperative locking guarantees.
A previous retired review folder .build-breaker-v02-final remains physically present and ignored after Git removal hit Windows long-path failure. Registration was removed; its evidence was already byte-preserved. No cleanup retry/raw deletion occurred. This residue is outside the source/portable deliverables. Final .build-b3 retirement succeeded.

Unproven assumptions:
Complete real Chrome/Brave/Firefox acquisition; physical 125/150% DPI/scaling; full interactive owner window/calibration/confirmation flow. Standard-path inventory found only Edge, not an exhaustive portable-browser inventory. Source adapter support and Edge/hidden UI tests do not prove the full compatibility matrix. Separate Fresh Breaker reasoning/worktree observed, same host/tool identity; independent human/host identity is not claimed.

Open blockers:
FBR-02-PROOF-004: required live four-browser/physical DPI/interactive calibration proof missing. Fresh Breaker verdict BREAKER_BLOCKED. No new confirmed product defect found in executed scope; prior FBR-02-001/002/003 repaired and independently revalidated. No owner waiver or acceptance exists for final PR head/base.

Recommended next action:
Complete the documented compatibility/calibration matrix on an authorized native Windows environment using this exact source/package. Preserve exact version/DPI/identity/ordered-image/Next/PDF evidence. Reconcile final PR head/base/checks again before requesting owner acceptance. A material change needs affected new independent proof. Only after the proof gate and exact-PR owner acceptance, merge main, verify resulting merge SHA/tree and build/targeted post-merge behavior, then publish the final Windows release. Do not infer acceptance from green CI.

Lifecycle: INDEPENDENT_REVIEW_PENDING (Builder ceiling).
Independent outcome: BREAKER_BLOCKED, solely FBR-02-PROOF-004.
'''
with (out/'RectoFlow-0.2.0-builder-report-e7627a6.txt').open('x',encoding='utf-8') as f:f.write(report)
matrix='''# RectoFlow 0.2 – noch offene Live-Verifikation

Prüfgegenstand: e7627a6a3fcee822236c82777d451fbed963b9ea; Windows-ZIP SHA256 febf2e1184ac8cdaeec8e952ef8726f7c78356721abfed3fe074d1f93baaa4f6; PR #7.
Dieser Bogen ist eine vorbereitete Prüfanleitung. Leere Felder sind kein PASS. Er verändert keine Windows-Einstellungen und erteilt keine Freigabe.

| Browser | 100% / 96 DPI | 125% / 120 DPI | 150% / 144 DPI |
| --- | --- | --- | --- |
| Edge | UIA/Vorlagen-Aufnahme in eigener Fixture geprüft; vollständige interaktive Kalibrierung offen | offen | offen |
| Chrome | offen | offen | offen |
| Brave | offen | offen | offen |
| Firefox | offen | offen | offen |

Für jede Zelle in einer dafür vorgesehenen Windows-Testumgebung festhalten:

1. Windows-/Browser-Version, tatsächliche Hauptmonitor-Skalierung/DPI, Paketdigest und Commit. Browser-Zoom getrennt notieren; Browser-Zoom ersetzt keine physische DPI-Verifikation.
2. Eigene lokale Testseite mit drei eindeutig unterschiedlichen Ansichten und terminal deaktiviertem Weiter-Button öffnen. Keine fremde/Owner-Sitzung automatisch übernehmen.
3. Profil anlegen, das Fenster interaktiv wählen, erst einen, dann zwei, dann weitere frei markierte Bereiche prüfen. Verschieben/Skalieren/Reihenfolge/Duplizieren/Rechtsplatzieren und explizite Bestätigungen kontrollieren. Papierformatwechsel darf Capture-Geometrie nicht verändern.
4. Navigation auf dieser Seite separat über UIA und Vorlagen prüfen, soweit der Browser/Control UIA bereitstellt. Unverfügbares UIA muss klar stoppen statt einen Endzustand zu erfinden; danach Vorlagen/Manuell eigenständig kalibrieren. Manuell und Einmal ebenfalls prüfen.
5. Drei Ansichten, jede Region in festgelegter Reihenfolge, genau zwei Weiter-Ereignisse und deaktiviertes Ende nachweisen. Fenster-/Fokus-/DPI-Änderung muss einen kontrollierten Stop ergeben; unsicheren Klick nicht erneut senden.
6. Finale Vorschau, Ansichtsausschluss/Umordnung, A4 Hochformat und A5 Querformat, proportionalen Export und erneut verwendbare Originale prüfen. Capture-Manifest/PNG-Hashes müssen unverändert bleiben; ExportPlan/result/PDF-Hashes abgleichen.
7. Logs, Manifest, ExportPlan/result, Testbilder/PDF und sichtbare Kontrollnachweise unter einer eigenen Run-ID aufbewahren. PASS/FAIL/BLOCKED mit konkretem Grund notieren. Keine Anerkennung allein aus Browser-Exe-Namen oder mockbasierten Tests ableiten.

Danach: Fresh Breaker ergänzt die fehlende Proof-Boundary am unveränderten Gegenstand. Finalen PR-Head/Base/CI/mergeability nochmals live prüfen. Owner Acceptance bezieht sich auf genau diesen PR-Zustand. Erst anschließend main-Merge, Prüfung des resultierenden Merge-SHA/Tree und finaler Release.
'''
with (out/'RectoFlow-0.2.0-live-matrix-e7627a6.de.md').open('x',encoding='utf-8') as f:f.write(matrix)
files=sorted(out.glob('RectoFlow-0.2.0-*-e7627a6*'))
checksums=out/'RectoFlow-0.2.0-SHA256SUMS-e7627a6.txt'
with checksums.open('x',encoding='utf-8') as f:
    for path in files:
        if path.is_file():f.write(digest(path)+'  '+path.name+'\n')
body=(root/'.build-final-pr.md').read_text()
body+='\n\nFinal PR boundary verified: head e7627a6a3fcee822236c82777d451fbed963b9ea, base b20beb920a5e1cdb4e42ff5552903ea701d3ee6a; MERGEABLE/CLEAN, draft retained. PR Windows run https://github.com/severinafrancic/RectoFlow/actions/runs/37383927244 (job 112012435822) succeeded. GitHub test-merge 06d4120dbdb5deb21634db3b82c3a5f1a69e63d5 has that base/head and the identical reviewed tree d6bd848ecf51a5088f59ac1bcc405e7a106e714d. This does not constitute a main merge, post-merge verification or owner acceptance.\n'
(root/'.build-final-pr.md').write_text(body)
print(json.dumps({'pr_head':sha,'base':base,'pr_ci':'SUCCESS','synthetic_merge_tree':tree,'source_zip_sha256':digest(source),'delivery_files':len(files),'verdict':'BREAKER_BLOCKED'},indent=2))
