"""
UpdateDialog の UI 単体テスト (tests/test_ui_update_dialog.py)
"""

import unittest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication

from src.core.updater import UpdateInfo
from src.ui.dialogs.update_dialog import UpdateDialog
from tests.helpers import get_qapp


class TestUiUpdateDialog(unittest.TestCase):
    """UpdateDialog の UI テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def setUp(self):
        self.dummy_update_info = UpdateInfo(
            version="1.1.0",
            tag_name="v1.1.0",
            title="RL-Log-Comparator v1.1.0",
            release_notes="## 新機能\n- 自動更新機能の追加\n- バグ修正",
            release_url="https://github.com/IISL-Mitsuie/RL-Log-Comparator/releases/tag/v1.1.0",
            published_at="2026-09-02T16:00:00Z",
            installer_download_url="https://github.com/IISL-Mitsuie/RL-Log-Comparator/releases/download/v1.1.0/Setup.exe",
            installer_name="RL_Log_Comparator_Setup_v1.1.0.exe",
            installer_size=62000000,
            is_update_available=True
        )

    def test_dialog_init_ui(self):
        dialog = UpdateDialog(None, self.dummy_update_info, current_version="1.0.0")

        self.assertIn("アプリケーション アップデート", dialog.windowTitle())
        self.assertFalse(dialog.progress_container.isVisible())
        self.assertIsNotNone(dialog.btn_update)
        self.assertEqual(dialog.btn_update.text(), "今すぐアップデート (自動インストール)")
        self.assertEqual(dialog.btn_close.text(), "閉じる")
        self.assertIn("自動更新機能の追加", dialog.notes_browser.toPlainText())

    def test_dialog_no_installer_url(self):
        no_installer_info = UpdateInfo(
            version="1.1.0",
            tag_name="v1.1.0",
            title="v1.1.0",
            release_notes="Notes",
            release_url="https://github.com",
            published_at="2026-09-02",
            installer_download_url=None,
            is_update_available=True
        )
        dialog = UpdateDialog(None, no_installer_info, current_version="1.0.0")
        self.assertIsNone(dialog.btn_update)


if __name__ == "__main__":
    unittest.main()
