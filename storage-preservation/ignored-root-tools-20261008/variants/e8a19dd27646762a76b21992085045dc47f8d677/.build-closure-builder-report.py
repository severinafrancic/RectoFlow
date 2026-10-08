from pathlib import Path
import hashlib, json, subprocess
import edge_capture

repo = Path(__file__).resolve().parent
def git(*args):
    return subprocess.check_output(['git', *args], cwd=repo, encoding='utf-8').strip()
head = git('rev-parse', 'HEAD')
assert head == '03ce0c82c3b7da489d49a5db82f6fb467e9c98a9'
assert not git('status', '--porcelain')
identity = edge_capture.code_identity()
assert identity['sha256'] == '99ccfb5ab1c59c65b51ba7ab8fe70c71c72e7ae188eccfe1a9546f07835558fe'
for name, sha in identity['files'].items():
    previous = subprocess.check_output(['git', 'show', 'e7627a6:'+name], cwd=repo)
    assert hashlib.sha256(previous).hexdigest() == sha
record = {
    'producer_role': 'BUILDER', 'lifecycle': 'INDEPENDENT_REVIEW_PENDING',
    'head': head, 'tree': git('rev-parse', 'HEAD^{tree}'), 'working_tree': 'clean',
    'runtime_identity': identity, 'runtime_files_byte_identical_to': 'e7627a6a3fcee822236c82777d451fbed963b9ea',
    'affected_path': 'Compatibility/acceptance contracts, bilingual README, real Tk synthetic demo pipeline, Windows CI and own Edge fixture activation; runtime implementation/config/dependencies unchanged.',
    'sources_of_truth': 'Owner-authorized requirements; exact Git blobs; current saved test logs; original immutable independent reports/allowlisted evidence. The Builder does not close FBR-02-PROOF-004.',
    'tests': '129 unit/regression tests passed after commit; both native Tk smokes and two-pass demo check passed before commit on identical files. Own Edge UIA/template fixtures passed at96DPI before commit, using same runtime bytes; new independent exact-commit execution remains required.',
    'failure_recovery': 'Unknown button/no retry/identity/environment/focus/stale config/snapshot/locking/freeze/same-byte decode/RUNNING contracts unchanged. Demo temp fixtures close normally; failure is explicit; images are docs-only. Historical reports retained.',
    'assumption_challenge': [
        'The Owner explicitly superseded universal browser/physicalDPI certification as a merge gate; support still requires shared implementation and synthetic contracts, and unverified targets remain visible.',
        'UIA is provider/page-dependent for every browser; own top-level mismatch remains disclosed and fail-closed, not claimed repaired or passing.',
        'Physical120/144DPI logic tests do not prove real physical desktop composition; docs/README mark it UNVERIFIED_RUNTIME.',
        'Demo images contain a visible synthetic label, use actual production Tk components and analysis, and cannot be evidence of real browser/navigation/DPI execution.',
        'Historical frozen EXE evidence remains bound to e762/old ZIP. Runtime byte equality establishes continuity only; fresh current CI/package tests required.',
        'No profile/DOM/focus safety invariant is waived; independent reviewer must evaluate unexecuted live combinations versus tested correctness contracts and confirmed defect history.'
    ],
    'historical_report_digests': {},
    'log_digests': {},
    'owner_acceptance': False, 'main_merge': False, 'new_release': False,
}
for path in [repo.parent/'RectoFlow-0.2.0-breaker-e7627a6.md', repo.parent/'RectoFlow-v0.2.0-rc.1-Edge-live-fresh-breaker-20261006.md']:
    record['historical_report_digests'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
for name in ['.build-closure-03ce0c8-tests.log', '.build-closure-edge-template.log', '.build-closure-edge-template-retest.log', '.build-closure-edge-uia.log']:
    record['log_digests'][name] = hashlib.sha256((repo/name).read_bytes()).hexdigest()
(repo/'.build-closure-builder.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({key: record[key] for key in ('head','tree','working_tree','lifecycle','historical_report_digests')}, indent=2))
