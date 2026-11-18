import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication
from gasfix.ui import App


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_defaults_invalid_form_and_close_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            window = App(path)
            self.assertEqual(window.windowTitle(), 'VirtualGasFixer')
            self.assertEqual(window.read_settings().axis, 'ly')
            self.assertEqual(window.read_settings().speed, 100)
            window.show()
            self.qt.processEvents()
            window.refresh()
            self.assertIn('0', window.level_label.text())
            window.close()
            self.qt.processEvents()
            self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()
