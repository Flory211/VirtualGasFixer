"""Fetch DLL/data only; never run vgamepad's driver installer or setup.py."""
import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
info = json.load(urllib.request.urlopen('https://pypi.org/pypi/vgamepad/0.2.0/json'))
source = next(x for x in info['urls'] if x['packagetype'] == 'sdist')
data = urllib.request.urlopen(source['url']).read()
assert hashlib.sha256(data).hexdigest() == source['digests']['sha256']
target = root / 'vendor'
target.mkdir(exist_ok=True)
licenses = root / 'licenses'
licenses.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
    dll = next(x for x in archive.getmembers() if x.name.endswith('x64/ViGEmClient.dll'))
    (target / 'ViGEmClient.dll').write_bytes(archive.extractfile(dll).read())
    for member in archive.getmembers():
        if member.isfile() and ('license' in member.name.lower() or 'copying' in member.name.lower()):
            filename = member.name.replace('/', '_')
            (licenses / filename).write_bytes(archive.extractfile(member).read())
(licenses / 'DJI-RC-Emulator.txt').write_bytes(urllib.request.urlopen(
    'https://raw.githubusercontent.com/deviverr/DJI-RC-Emulator/main/LICENSE').read())
for name, url in {
    'ViGEmClient.txt': 'https://raw.githubusercontent.com/nefarius/ViGEmClient/master/LICENSE',
    'LGPL-3.0.txt': 'https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/LGPL-3.0-only.txt',
    'LGPL-2.1.txt': 'https://raw.githubusercontent.com/libusb/libusb/v1.0.30/COPYING',
    'GPL-3.0.txt': 'https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/GPL-3.0-only.txt',
}.items():
    (licenses / name).write_bytes(urllib.request.urlopen(url).read())
(target / 'source.json').write_text(json.dumps({'url': source['url'], 'sha256': source['digests']['sha256']}, indent=2))
print('Downloaded and verified ViGEmClient DLL; no package setup or driver installer executed.')
