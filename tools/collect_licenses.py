import importlib.metadata
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'licenses'
target.mkdir(exist_ok=True)
for distribution in importlib.metadata.distributions():
    for file in distribution.files or []:
        name = str(file).lower()
        if '.dist-info/' in name and ('license' in name or 'copying' in name):
            source = Path(distribution.locate_file(file))
            if source.is_file():
                destination = target / distribution.metadata['Name'] / Path(str(file).split('.dist-info/', 1)[1])
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
for name in ('LICENSE.txt', 'LICENSE'):
    source = Path(sys.base_prefix) / name
    if source.is_file():
        shutil.copyfile(source, target / 'Python.txt')
        break
print('Third party license notices collected.')
