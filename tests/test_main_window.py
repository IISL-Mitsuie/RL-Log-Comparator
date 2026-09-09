"""
メインウィンドウ (ExperimentCompareApp) の統合テスト
"""

import os
import unittest
import tempfile
import shutil
from src.ui.main_window import ExperimentCompareApp
from src.config import CLEAR_HISTORY_TEXT
from tests.helpers import get_qapp, create_dummy_experiment_folder


class TestMainWindow(unittest.TestCase):
    """ExperimentCompareApp の統合テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_a = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_a", mode="S-SAP"
        )
        self.folder_b = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_b", mode="Q-SAP"
        )

        from src.core.history import RecentFolderManager, SessionStateManager
        self.test_history_mgr = RecentFolderManager(org="IISL_Test", app="RL_Test_MainWindow")
        self.test_history_mgr.clear_history()
        self.test_session_mgr = SessionStateManager(org="IISL_Test", app="RL_Test_MainWindow")
        self.test_session_mgr.clear_last_paths()
        self.test_root_mgr = RecentFolderManager(org="IISL_Test", app="RL_Test_MainWindow", settings_key="test_root_dirs")
        self.test_root_mgr.clear_history()

    def tearDown(self):
        self.test_history_mgr.clear_history()
        self.test_session_mgr.clear_last_paths()
        self.test_root_mgr.clear_history()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_isolated_window(self) -> ExperimentCompareApp:
        """テスト専用のマネージャーを設定した隔離ウィンドウを生成"""
        window = ExperimentCompareApp()
        window.history_mgr = self.test_history_mgr
        window.session_mgr = self.test_session_mgr
        window._history = []
        window._update_history_combos()
        window.tab_explorer.history_mgr = self.test_root_mgr
        window.tab_explorer._history = []
        window.tab_explorer._update_history_combo()
        return window

    def test_window_init_and_tabs(self):
        window = self._create_isolated_window()
        self.assertEqual(window.tabs.count(), 5)
        self.assertIn("1. 実験ログ一覧・探索", window.tabs.tabText(0))
        self.assertIn("2. ハイパーパラメータ差分", window.tabs.tabText(1))
        self.assertIn("3. 画像目視比較", window.tabs.tabText(2))
        self.assertIn("4. 数値ログ比較グラフ", window.tabs.tabText(3))
        self.assertIn("5. ログ仕様ガイド", window.tabs.tabText(4))

    def test_set_folder_from_explorer(self):
        window = self._create_isolated_window()
        window._on_set_folder_a_from_explorer(self.folder_a)
        self.assertEqual(window.combo_folder_a.currentText(), self.folder_a)

        window._on_set_folder_b_from_explorer(self.folder_b)
        self.assertEqual(window.combo_folder_b.currentText(), self.folder_b)
        self.assertEqual(window._last_loaded_a, self.folder_a)
        self.assertEqual(window._last_loaded_b, self.folder_b)

    def test_load_folders(self):
        window = self._create_isolated_window()
        window.load_folders(self.folder_a, self.folder_b)

        self.assertEqual(window.combo_folder_a.currentText(), self.folder_a)
        self.assertEqual(window.combo_folder_b.currentText(), self.folder_b)
        self.assertEqual(window._last_loaded_a, self.folder_a)
        self.assertEqual(window._last_loaded_b, self.folder_b)

        # 各タブへの伝播を確認
        self.assertTrue(window.tab_yaml.tree.topLevelItemCount() > 0)
        self.assertTrue(window.tab_images.list_images.count() > 0)
        self.assertIsNotNone(window.tab_csv.df_a)
        self.assertIsNotNone(window.tab_csv.df_b)

    def test_history_addition_and_combos(self):
        window = self._create_isolated_window()
        # 履歴への追加
        window._history = window.history_mgr.add_folder(self.folder_a)
        window._update_history_combos()

        self.assertIn(self.folder_a, [window.combo_folder_a.itemText(i) for i in range(window.combo_folder_a.count())])

    def test_update_header_button(self):
        window = self._create_isolated_window()
        self.assertIsNotNone(window.btn_update_header)
        self.assertIn("更新を確認", window.btn_update_header.text())

        # 更新情報を適用した際のUI変化
        from src.core.updater import UpdateInfo
        dummy_info = UpdateInfo(
            version="1.2.0",
            tag_name="v1.2.0",
            title="v1.2.0",
            release_notes="Notes",
            release_url="https://github.com",
            published_at="2026-09-02",
            is_update_available=True
        )
        window._apply_update_info(dummy_info)
        self.assertIn("v1.2.0 更新可能", window.btn_update_header.text())

    def test_session_save_and_restore(self):
        from PySide6.QtGui import QCloseEvent
        window = self._create_isolated_window()

        # パス設定
        window.tab_explorer.set_root_directory(self.test_dir)
        window.combo_folder_a.setEditText(self.folder_a)
        window.combo_folder_b.setEditText(self.folder_b)

        # アプリ終了イベントをシミュレート
        event = QCloseEvent()
        window.closeEvent(event)

        # テスト用 QSettings に保存されたか確認
        saved = self.test_session_mgr.load_last_paths()
        self.assertEqual(saved.get("root_dir"), os.path.abspath(self.test_dir))
        self.assertEqual(saved.get("folder_a"), os.path.abspath(self.folder_a))
        self.assertEqual(saved.get("folder_b"), os.path.abspath(self.folder_b))

        # 別のウィンドウインスタンスで復元をテスト
        new_window = self._create_isolated_window()
        new_window._restore_last_session()

        self.assertEqual(new_window.tab_explorer.get_root_directory(), os.path.abspath(self.test_dir))
        self.assertEqual(new_window.combo_folder_a.currentText(), os.path.abspath(self.folder_a))
        self.assertEqual(new_window.combo_folder_b.currentText(), os.path.abspath(self.folder_b))
        self.assertEqual(new_window._last_loaded_a, os.path.abspath(self.folder_a))
        self.assertEqual(new_window._last_loaded_b, os.path.abspath(self.folder_b))


if __name__ == "__main__":
    unittest.main()



