"""Spike-only wheel verification and offline installation. No provider fallback."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def sha(data): return hashlib.sha256(data).hexdigest()

def main():
    target = Path(sys.argv[1]).resolve()
    target.mkdir(parents=True, exist_ok=True)
    wheels = target / 'wheels'
    wheels.mkdir(exist_ok=True)
    subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
                    '-r', str(Path(__file__).with_name('requirements.txt')),
                    '-d', str(wheels)], check=True, cwd=ROOT)
    records = []
    for path in sorted(wheels.glob('*.whl')):
        parts = path.name.split('-')
        name, version = parts[0], parts[1]
        with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
            info = json.load(response)
        matches = [item for item in info['urls'] if item['filename'] == path.name]
        assert len(matches) == 1 and not matches[0]['yanked'], path.name
        raw = path.read_bytes()
        assert sha(raw) == matches[0]['digests']['sha256'] and len(raw) == matches[0]['size'], path.name
        licenses = []
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if member.endswith('/') or not any(word in member.lower() for word in ('license', 'copying', 'notice')):
                    continue
                data = archive.read(member)
                dest = target / 'licenses' / path.stem / member
                assert '..' not in Path(member).parts and not Path(member).is_absolute()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                licenses.append({'wheel_member': member, 'bytes': len(data), 'sha256': sha(data)})
        assert licenses, 'No license materials in ' + path.name
        records.append({'file': path.name, 'package': name, 'version': version,
                        'bytes': len(raw), 'sha256': sha(raw), 'pypi_match': True, 'licenses': licenses})
    actual = {r['package'].replace('_','-'): r['version'] for r in records}
    for name, version in [('pypdfium2','5.14.0'),('opencv-python-headless','5.0.0.93'),('numpy','2.4.6')]:
        assert actual[name] == version
    (target / 'wheel-inventory.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--find-links', str(wheels),
                    '-r', str(Path(__file__).with_name('requirements.txt'))], check=True, cwd=ROOT)
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
    print('VERIFIED_WHEELS_OFFLINE_INSTALL_PASS')

if __name__ == '__main__': main()
