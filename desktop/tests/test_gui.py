# SPDX-License-Identifier: GPL-3.0-only
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from passthrough.audio import Device
from passthrough.gui import Window


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_idle_ui_does_not_open_devices_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('passthrough.gui.list_devices', return_value=(
                    [Device('silence', 'Silence')], [Device('discard', 'Discard')])), \
                    patch('passthrough.gui.RelayServer') as server:
                window = Window(directory)
                self.assertIsNone(window.server)
                server.assert_not_called()
                self.assertEqual(len(window.fingerprint.text()), 64)
                window.mode.setCurrentIndex(1)
                self.assertEqual(window.bind.text(), '0.0.0.0')
                window.mode.setCurrentIndex(2)
                self.assertFalse(window.start.isEnabled())
                window.mode.setCurrentIndex(0)
                self.assertEqual(window.bind.text(), '127.0.0.1')
                window.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
