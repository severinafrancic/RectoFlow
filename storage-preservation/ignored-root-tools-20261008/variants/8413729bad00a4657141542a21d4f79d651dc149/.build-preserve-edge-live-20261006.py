from pathlib import Path, PurePosixPath
import hashlib
import json
import stat
import zipfile
from datetime import datetime, timezone

repo = Path(__file__).resolve().parent
source = repo / '.build-live-edge-rc1-20261006'
output = repo.parent
prefix = 'RectoFlow-v0.2.0-rc.1-Edge-live-'
expected = {
    'LIVE_EVIDENCE_ALLOWLIST.json': 'a12d24130164d241fee9c5a1eea5dd593e80cb552d39e6141522c31ea93d3570',
    'LIVE_EVIDENCE_DIGESTS.json': '4125fee00a21a4aaa019241768b94fa3598358afcfda1485f015ea0968831581',
    'EDGE_FRESH_BREAKER_LIVE.md': '5267f556c33f8771fa052b2a867381e8145fd11b083ee8f04fac5236e5c2d324',
    'EDGE_LIVE_MATRIX.md': 'cac4fda823ec403301b333af0f64df1a078a6bc8f7c0b08c87279a750e7f3da5',
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_member(name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name:
        raise ValueError(f'Unsafe relative path: {name}')
    path = source.joinpath(*rel.parts)
    path.resolve(strict=True).relative_to(source.resolve(strict=True))
    current = path
    while current != source.parent:
        info = current.lstat()
        if current.is_symlink() or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f'Reparse path: {name}')
        current = current.parent
    return path.read_bytes()

controls = {name: read_member(name) for name in ('LIVE_EVIDENCE_ALLOWLIST.json', 'LIVE_EVIDENCE_DIGESTS.json')}
for name, data in controls.items():
    assert digest(data) == expected[name], name
allowlist = json.loads(controls['LIVE_EVIDENCE_ALLOWLIST.json'])
registry = json.loads(controls['LIVE_EVIDENCE_DIGESTS.json'])
assert registry['source_sha'] == 'e7627a6a3fcee822236c82777d451fbed963b9ea'
assert registry['tree'] == 'd6bd848ecf51a5088f59ac1bcc405e7a106e714d'
names = sorted(set(allowlist['files']) | set(allowlist['required_control_files']))
assert len(names) == 976, len(names)
assert set(names) == set(registry['files']) | {'LIVE_EVIDENCE_DIGESTS.json'}
assert registry['member_count'] == 975
members = {}
for name in names:
    data = controls.get(name)
    if data is None:
        data = read_member(name)
    if name in registry['files']:
        record = registry['files'][name]
        assert len(data) == record['size'], name
        assert digest(data) == record['sha256'], name
    else:
        assert digest(data) == expected[name], name
    if name in expected:
        assert digest(data) == expected[name], name
    members[name] = data

archive = output / (prefix + 'evidence-20261006.zip')
if not archive.exists():
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in members.items():
            zipped.writestr(name, data)
with zipfile.ZipFile(archive) as zipped:
    assert sorted(zipped.namelist()) == names
    for name, data in members.items():
        saved = zipped.read(name)
        assert len(saved) == len(data) and digest(saved) == digest(data), name

def publish_exact(path, data):
    if path.exists():
        assert path.read_bytes() == data, str(path)
    else:
        with path.open('xb') as handle:
            handle.write(data)
    assert path.read_bytes() == data

for name, suffix in [('EDGE_FRESH_BREAKER_LIVE.md', 'fresh-breaker-20261006.md'), ('EDGE_LIVE_MATRIX.md', 'matrix-20261006.md')]:
    publish_exact(output / (prefix + suffix), members[name])
receipt = {
    'schema': 1,
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'producer_role': 'BUILDER_COORDINATOR_RETENTION_ONLY',
    'authority': 'Preservation of independent evidence; no acceptance or product change',
    'source_sha': registry['source_sha'],
    'source_tree': registry['tree'],
    'source_directory': str(source),
    'source_control_sha256': {name: expected[name] for name in controls},
    'report_sha256': expected['EDGE_FRESH_BREAKER_LIVE.md'],
    'matrix_sha256': expected['EDGE_LIVE_MATRIX.md'],
    'archive': str(archive),
    'archive_sha256': digest(archive.read_bytes()),
    'archive_member_count': len(names),
    'archive_uncompressed_bytes': sum(map(len, members.values())),
    'verification': 'Every archived member was reread from ZIP and compared by SHA-256 and size to the bound source bytes; exact allowlist membership verified.',
    'github_upload': False,
}
receipt_path = output / (prefix + 'retention-20261006.json')
if receipt_path.exists():
    existing = json.loads(receipt_path.read_bytes())
    for key in ('archive_sha256', 'archive_member_count', 'source_sha', 'source_control_sha256'):
        assert existing[key] == receipt[key], key
else:
    publish_exact(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps(receipt, ensure_ascii=True, indent=2))
