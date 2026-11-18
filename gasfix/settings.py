"""Validated, atomic settings persistence."""
import json
import math
import os
from dataclasses import asdict
from pathlib import Path

from .core import Settings


def default_path():
    return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'VirtualGasFixer' / 'settings.json'


def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        settings = Settings(**data.get('settings', {})).validate()
        level = data.get('level', 0)
        if type(level) not in (float, int) or not 0 <= level <= 1 or not math.isfinite(level):
            raise ValueError('Неверный сохранённый уровень')
        return settings, level if settings.on_start == 'hold' else 0, ''
    except FileNotFoundError:
        # Read the old file only when the new default has never been saved.
        # The first normal save writes the new location; the old file stays intact.
        if Path(path) == default_path():
            legacy = default_path().parent.parent / 'DJIVirtualGasFixer' / 'settings.json'
            return load(legacy)
        return Settings(), 0, ''
    except (OSError, ValueError, TypeError, AttributeError) as error:
        return Settings(), 0, f'Не удалось прочитать настройки: {error}. Использованы начальные значения.'


def save(path, settings, level):
    settings.validate()
    if not math.isfinite(level) or not 0 <= level <= 1:
        raise ValueError('Неверный уровень газа')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as file:
            json.dump({'settings': asdict(settings), 'level': level}, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
