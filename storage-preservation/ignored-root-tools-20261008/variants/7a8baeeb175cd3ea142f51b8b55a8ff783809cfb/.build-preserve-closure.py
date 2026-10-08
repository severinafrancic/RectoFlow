from pathlib import Path, PurePosixPath
import hashlib, json, stat, zipfile

repo = Path(__file__).resolve().parent
source = repo / '.build-closure-fresh-breaker'
output = repo.parent
bound = {
    '.build-evidence/ALLOWLIST.json': '8b816bd7c01ae3e371abb1a2521829662d950e2142e07f05a12055a36d37eedf',
    '.build-evidence/DIGESTS.json': 'c875cb727ffdb8602e53711938b748319617ed945254e48a1638f91f0e6fb843',
    '.build-evidence/FRESH_BREAKER_REPORT.md': '3adc49ef4a0eb641f17a34ce7ec9e5d1312f09720ea41806f6378859e57a22fd',
}
def sha(data): return hashlib.sha256(data).hexdigest()
def member(name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
        raise ValueError(name)
    path = source.joinpath(*relative.parts)
    path.resolve(strict=True).relative_to(source.resolve(strict=True))
    current = path
    while current != source.parent:
        info = current.lstat()
        if current.is_symlink() or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Reparse member: ' + name)
        current = current.parent
    return path.read_bytes()
controls = {name: member(name) for name in list(bound)[:2]}
for name, data in controls.items(): assert sha(data) == bound[name], name
allowlist = json.loads(controls['.build-evidence/ALLOWLIST.json'])
registry = json.loads(controls['.build-evidence/DIGESTS.json'])
assert allowlist['subject_sha'] == registry['subject_sha'] == '03ce0c82c3b7da489d49a5db82f6fb467e9c98a9'
assert allowlist['subject_tree'] == registry['subject_tree'] == '81f443ccd1409363c77caa5325557b30b1b59a28'
names = sorted(set(allowlist['files']) | set(allowlist['required_control_files']))
assert len(names) == 81
assert set(names) == set(registry['files']) | set(controls)
contents = {}
for name in names:
    data = controls.get(name)
    if data is None: data = member(name)
    if name in registry['files']:
        entry = registry['files'][name]
        assert len(data) == entry['size'] and sha(data) == entry['sha256'], name
    if name in bound: assert sha(data) == bound[name], name
    contents[name] = data
def publish(path, data):
    if path.exists(): assert path.read_bytes() == data, str(path)
    else:
        with path.open('xb') as handle: handle.write(data)
    assert path.read_bytes() == data
archive = output / 'RectoFlow-0.2-closure-evidence-03ce0c8.zip'
if not archive.exists():
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as zipped:
        for name, data in contents.items(): zipped.writestr(name, data)
with zipfile.ZipFile(archive) as zipped:
    assert sorted(zipped.namelist()) == names
    for name, data in contents.items():
        archived = zipped.read(name)
        assert len(archived) == len(data) and sha(archived) == sha(data), name
publish(output / 'RectoFlow-0.2-closure-fresh-breaker-03ce0c8.md', contents['.build-evidence/FRESH_BREAKER_REPORT.md'])
package = contents['.build-evidence/ci-package/RectoFlow-0.2.0-windows-x64.zip']
assert sha(package) == '356676ddd394f1e27c060c146c580d3d2f65fa25d0e5a7c61fb66010f818dff2'
publish(output / 'RectoFlow-0.2.0-PR7-03ce0c8-windows-x64.zip', package)
receipt = {
    'producer_role': 'BUILDER_COORDINATOR_RETENTION_ONLY',
    'subject_sha': allowlist['subject_sha'], 'subject_tree': allowlist['subject_tree'],
    'source_worktree': str(source), 'archive': str(archive), 'archive_sha256': sha(archive.read_bytes()),
    'member_count': len(names), 'uncompressed_bytes': sum(map(len, contents.values())),
    'source_bound_sha256': bound,
    'portable_zip_sha256': sha(package),
    'verified': 'Exact allowlist; each selected source buffer hash/size checked; each ZIP member reopened and hash/size compared; report and candidate package separately byte-exact retained.',
    'acceptance': False, 'merge': False, 'release_publication': False,
}
publish(output / 'RectoFlow-0.2-closure-retention-03ce0c8.json', (json.dumps(receipt, indent=2)+'\n').encode())
print(json.dumps(receipt, indent=2))
