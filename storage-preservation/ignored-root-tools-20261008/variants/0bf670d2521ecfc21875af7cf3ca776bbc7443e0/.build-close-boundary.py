from pathlib import Path
import hashlib, json, subprocess
from datetime import datetime, timezone

repo = Path(__file__).resolve().parent
output = repo.parent
pr = json.loads((repo/'.build-closure-pr-final.json').read_text(encoding='utf-8-sig'))
main = json.loads((repo/'.build-closure-main-final.json').read_text(encoding='utf-8-sig'))
merge_ref = json.loads((repo/'.build-closure-merge-ref-final.json').read_text(encoding='utf-8-sig'))
head = '03ce0c82c3b7da489d49a5db82f6fb467e9c98a9'
base = 'b20beb920a5e1cdb4e42ff5552903ea701d3ee6a'
tree = '81f443ccd1409363c77caa5325557b30b1b59a28'
assert pr['headRefOid'] == head and pr['baseRefOid'] == main['commit']['sha'] == base
assert pr['state'] == 'OPEN' and not pr['isDraft'] and pr['mergeable'] == 'MERGEABLE' and pr['mergeStateStatus'] == 'CLEAN'
checks = [check for check in pr['statusCheckRollup'] if check['name'] == 'windows']
assert len(checks) == 2 and all(check['conclusion'] == 'SUCCESS' and check['status'] == 'COMPLETED' for check in checks)
assert pr['body'].strip() == (repo/'.build-closure-pr-body.md').read_text(encoding='utf-8').strip()
assert merge_ref['object']['sha'] == 'db52a64220d3ffa8bd2f1a8aca0c728da2599bbf'
merge = json.loads((repo/'.build-closure-test-merge.json').read_text(encoding='utf-8-sig'))
assert merge['tree']['sha'] == tree and [parent['sha'] for parent in merge['parents']] == [base, head]
def git(*args): return subprocess.check_output(['git', *args], cwd=repo, encoding='utf-8').strip()
assert git('rev-parse', 'HEAD') == head and git('rev-parse', 'HEAD^{tree}') == tree and not git('status', '--porcelain')
report = output/'RectoFlow-0.2-closure-fresh-breaker-03ce0c8.md'
report_hash = hashlib.sha256(report.read_bytes()).hexdigest()
assert report_hash == '3adc49ef4a0eb641f17a34ce7ec9e5d1312f09720ea41806f6378859e57a22fd'
assert 'Verdict: **READY_FOR_OWNER_ACCEPTANCE**' in report.read_text(encoding='utf-8')
record = {
    'producer_role': 'COORDINATOR_FINAL_BOUNDARY', 'observed_utc': datetime.now(timezone.utc).isoformat(),
    'pr': pr['url'], 'head_sha': head, 'base_sha': base, 'tree': tree, 'working_tree': 'clean',
    'draft': False, 'mergeability': 'MERGEABLE', 'conflicts': False,
    'windows_checks': checks, 'test_merge_sha': merge['sha'], 'test_merge_tree_matches': True,
    'fresh_breaker_report': report.name, 'fresh_breaker_report_sha256': report_hash,
    'builder_ceiling': 'INDEPENDENT_REVIEW_PENDING', 'fresh_breaker': 'READY_FOR_OWNER_ACCEPTANCE',
    'lifecycle': 'READY_FOR_OWNER_ACCEPTANCE',
    'independence': 'Fresh reasoning context/registered detached worktree, same host; no separate human/host claimed.',
    'pr_body_sha256': hashlib.sha256(pr['body'].encode()).hexdigest(),
    'owner_acceptance': False, 'main_merge': False, 'new_release_publication': False,
    'known_limit': 'Current local EXE startup blocked before execution by Windows AppControl4551; actual current hosted relocated EXE smoke passed and was independently bound. Source Edge96 passes; historical frozen interactive Edge remains original-SHA-bound.',
    'open_nonblocking_evidence': ['real Chrome/Brave/Firefox E2E', 'physical125/150% desktop', 'full live profile/DOM/provider matrix', 'later UIA own-topHWND mismatch', 'current frozen genuine interactive Edge acquisition', 'local current EXE AppControl restriction'],
    'recommended_next_action': 'Owner explicitly accepts exact PR head/base; merge is a separate boundary followed by resulting-tree verification.',
}
(output/'RectoFlow-0.2-closure-status-03ce0c8.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
print(json.dumps({key: record[key] for key in ('pr','head_sha','base_sha','tree','working_tree','draft','mergeability','conflicts','fresh_breaker','lifecycle')}, indent=2))
