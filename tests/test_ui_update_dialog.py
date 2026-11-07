"""
UpdateDialog の UI 単体テスト (tests/test_ui_update_dialog.py)
"""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QWidget
from src.core.updater import UpdateInfo
from src.ui.dialogs.update_dialog import UpdateDialog
from tests.helpers import get_qapp


class TestUiUpdateDialog(unittest.TestCase):
    """UpdateDialog の UI テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def setUp(self):
        self.dummy_sha256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        self.dummy_update_info = UpdateInfo(
            version="1.1.0",
            tag_name="v1.1.0",
            title="RL-Log-Comparator v1.1.0",
            release_notes="## 新機能\n- 自動更新機能の追加\n- バグ修正",
            release_url="https://github.com/IISL-Mitsuie/RL-Log-Comparator/releases/tag/v1.1.0",
            published_at="2026-09-02T16:00:00Z",
            installer_download_url="https://github.com/IISL-Mitsuie/RL-Log-Comparator/releases/download/v1.1.0/RL_Log_Comparator_Setup_v1.1.0.exe",
            installer_name="RL_Log_Comparator_Setup_v1.1.0.exe",
            installer_size=62000000,
            installer_sha256=self.dummy_sha256,
            is_update_available=True
        )

    def test_dialog_init_ui(self):
        dialog = UpdateDialog(None, self.dummy_update_info, current_version="1.0.0")

        self.assertIn("アプリケーション アップデート", dialog.windowTitle())
        self.assertFalse(dialog.progress_container.isVisible())
        self.assertIsNotNone(dialog.btn_update)
        self.assertTrue(dialog.btn_update.isEnabled())
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

    def test_dialog_no_hash_disables_update_button(self):
        no_hash_info = UpdateInfo(
            version="1.1.0",
            tag_name="v1.1.0",
            title="v1.1.0",
            release_notes="Notes",
            release_url="https://github.com",
            published_at="2026-09-02",
            installer_download_url="https://example.com/Setup.exe",
            installer_name="RL_Log_Comparator_Setup_v1.1.0.exe",
            installer_size=1000,
            installer_sha256=None,
            is_update_available=True
        )
        dialog = UpdateDialog(None, no_hash_info, current_version="1.0.0")
        self.assertIsNotNone(dialog.btn_update)
        self.assertFalse(dialog.btn_update.isEnabled())
        expected_tooltip = "このリリースには検証用ハッシュがないため、自動インストールできません。GitHub から手動でダウンロードしてください"
        self.assertEqual(dialog.btn_update.toolTip(), expected_tooltip)

    @patch("PySide6.QtWidgets.QMessageBox.critical")
    def test_dialog_verification_error_shows_message(self, mock_msg_box):
        dialog = UpdateDialog(None, self.dummy_update_info, current_version="1.0.0")
        dialog._on_verification_failed("SHA-256 不一致")

        self.assertFalse(dialog.progress_container.isVisible())
        self.assertTrue(dialog.btn_update.isEnabled())
        self.assertEqual(dialog.btn_close.text(), "閉じる")
        mock_msg_box.assert_called_once()
        args = mock_msg_box.call_args[0]
        self.assertEqual(args[1], "検証エラー")
        self.assertEqual(
            args[2],
            "ダウンロードしたファイルの検証に失敗しました。通信環境を確認して再試行してください"
        )

    @patch("src.ui.dialogs.update_dialog.launch_installer")
    @patch("PySide6.QtWidgets.QApplication.quit")
    def test_dialog_apply_update_and_exit(self, mock_quit, mock_launch):
        parent = QWidget()
        parent_close_mock = MagicMock()
        parent.close = parent_close_mock
        dialog = UpdateDialog(parent, self.dummy_update_info, current_version="1.0.0")

        dummy_installer_path = "C:\\path\\to\\Setup.exe"
        dialog._apply_update_and_exit(dummy_installer_path)

        mock_launch.assert_called_once_with(dummy_installer_path)
        parent_close_mock.assert_called_once()
        mock_quit.assert_called_once()
        parent.deleteLater()
        dialog.deleteLater()

    @patch("src.ui.dialogs.update_dialog.launch_installer")
    @patch("PySide6.QtWidgets.QApplication.quit")
    def test_dialog_apply_update_calls_close_event_and_saves_session(self, mock_quit, mock_launch):
        from src.ui.main_window import ExperimentCompareApp

        window = ExperimentCompareApp()
        mock_session_mgr = MagicMock()
        window.session_mgr = mock_session_mgr
        window.combo_folder_a.setEditText("C:\\test\\folder_a")
        window.combo_folder_b.setEditText("C:\\test\\folder_b")

        dialog = UpdateDialog(window, self.dummy_update_info, current_version="1.0.0")
        dialog._apply_update_and_exit("C:\\dummy\\Setup.exe")

        mock_launch.assert_called_once_with("C:\\dummy\\Setup.exe")
        mock_session_mgr.save_last_paths.assert_called_once()
        mock_quit.assert_called_once()
        window.deleteLater()
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()

