"""Generate exact NSIS file lists so uninstall never recursively deletes user files."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
payload = root / 'dist' / 'VirtualGasFixer'
destination = root / 'installer'
files = sorted(path for path in payload.rglob('*') if path.is_file())
if not files or not (payload / 'VirtualGasFixer.exe').is_file():
    raise SystemExit('Build the application first with build.ps1')


def quote(value):
    return str(value).replace('$', '$$').replace('"', '$\\"')


install = [f'!define PAYLOAD_KIB {(sum(p.stat().st_size for p in files) + 1023) // 1024}']
uninstall = []
directories = set()
previous = None
for file in files:
    if not file.resolve().is_relative_to(payload.resolve()):
        raise SystemExit(f'File escapes payload: {file}')
    relative = file.relative_to(payload)
    parent = str(relative.parent)
    if parent != previous:
        install.append(f'SetOutPath "$INSTDIR' + ('' if parent == '.' else '\\' + quote(parent)) + '"')
        previous = parent
    install.append(f'File "{quote(file)}"')
    target = f'$INSTDIR\\{quote(relative)}'
    uninstall.extend([
        '${If} ${FileExists} "' + target + '"',
        '  ClearErrors',
        f'  Delete "{target}"',
        '  IfErrors uninstall_failed',
        '${EndIf}',
    ])
    directories.update(p for p in relative.parents if str(p) != '.')
for directory in sorted(directories, key=lambda p: (-len(p.parts), str(p))):
    uninstall.append(f'RMDir "$INSTDIR\\{quote(directory)}"')
for name, lines in [('payload-install.nsh', install), ('payload-uninstall.nsh', uninstall)]:
    (destination / name).write_text('\n'.join(lines) + '\n', encoding='utf-8-sig')
print(f'Generated installer manifest: {len(files)} files, {len(directories)} directories')
