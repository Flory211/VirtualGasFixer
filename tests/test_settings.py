import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gasfix.core import Settings
from gasfix.settings import default_path, load, save


class SettingsTests(unittest.TestCase):
    def test_renamed_app_restores_legacy_settings_without_overwriting_them(self):
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ', {'LOCALAPPDATA': d}):
            legacy = Path(d) / 'DJIVirtualGasFixer' / 'settings.json'
            settings = Settings(on_start='hold', speed=150)
            save(legacy, settings, .61)
            original = legacy.read_bytes()
            current = default_path()
            self.assertEqual(current, Path(d) / 'VirtualGasFixer' / 'settings.json')
            restored, level, warning = load(current)
            self.assertEqual((restored.speed, level, warning), (150, .61, ''))
            save(current, Settings(on_start='hold', speed=200), .72)
            self.assertEqual(load(current)[1], .72)
            self.assertEqual(legacy.read_bytes(), original)

    def test_roundtrip_and_start_policy(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'settings.json'
            save(path, Settings(on_start='hold', on_loss='hold', speed=200), .61)
            settings, level, warning = load(path)
            self.assertEqual((settings.speed, settings.on_loss, level, warning), (200, 'hold', .61, ''))
            save(path, Settings(), .61)
            self.assertEqual(load(path)[1], 0)

    def test_missing_corrupt_and_nonfinite_use_safe_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'settings.json'
            self.assertEqual(load(path)[1:], (0, ''))
            for bad in ('{', '[]', '{"settings":{"speed":NaN}}',
                        '{"settings":{"on_start":"hold"},"level":NaN}',
                        '{"settings":{"speed":' + '1' + '0' * 400 + '}}',
                        '{"level":' + '1' + '0' * 400 + '}'):
                path.write_text(bad)
                settings, level, warning = load(path)
                self.assertEqual(level, 0)
                self.assertTrue(warning)


if __name__ == '__main__':
    unittest.main()
