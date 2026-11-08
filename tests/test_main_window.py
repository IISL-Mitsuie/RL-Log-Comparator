"""
メインウィンドウ (ExperimentCompareApp) の統合テスト
"""

import os
import unittest
import tempfile
import shutil
from unittest.mock import patch
from src.ui.main_window import ExperimentCompareApp
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

    def test_init_does_not_check_update_over_network(self):
        # テスト中はウィンドウ生成時に GitHub API へ更新確認を行わない
        with patch("src.ui.main_window.fetch_latest_release_info") as mock_fetch:
            window = self._create_isolated_window()
            bg_thread = getattr(window, "_bg_thread", None)
            if bg_thread is not None:
                bg_thread.join(timeout=5)
            mock_fetch.assert_not_called()

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
        window.tab_explorer.set_root_directory(self.test_dir, blocking=True)
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

    def test_close_event_saves_explorer_view_state(self):
        """closeEvent 実行時に Explorer の表示設定が保存され、次回復元されることの検証 (ISSUE-13)"""
        from PySide6.QtGui import QCloseEvent
        window = self._create_isolated_window()
        window.tab_explorer.cb_diff_columns_only.setChecked(True)
        window.tab_explorer.cb_recursive.setChecked(False)

        event = QCloseEvent()
        window.closeEvent(event)

        new_window = self._create_isolated_window()
        self.assertTrue(new_window.tab_explorer.cb_diff_columns_only.isChecked())
        self.assertFalse(new_window.tab_explorer.cb_recursive.isChecked())

    def test_load_all_continues_when_one_tab_fails(self):
        """1 つのタブの反映が失敗しても、残りのタブは反映され、ステータスバーに表示される (ISSUE-05 / ISSUE-07)"""
        window = self._create_isolated_window()
        window.combo_folder_a.setEditText(self.folder_a)
        window.combo_folder_b.setEditText(self.folder_b)

        with patch.object(window.tab_yaml, "apply_data", side_effect=TypeError("YAML の想定外エラー")), \
                patch.object(window.tab_images, "apply_data", wraps=window.tab_images.apply_data) as mock_images, \
                patch.object(window.tab_csv, "apply_data", wraps=window.tab_csv.apply_data) as mock_csv, \
                self.assertLogs("src.ui.main_window", level="ERROR") as logs:
            window.load_all(blocking=True)

        self.assertEqual(mock_images.call_count, 1)
        self.assertEqual(mock_csv.call_count, 1)
        self.assertIsNotNone(window.tab_csv.df_a)
        message = window.statusBar().currentMessage()
        self.assertIn("ハイパーパラメータ差分", message)
        self.assertIn("YAML の想定外エラー", message)
        self.assertIn("Traceback", logs.output[0])

    def test_menu_bar_actions_and_shortcuts(self):
        """メニューバーの構築とショートカットキーの設定検証 (ISSUE-16)"""
        window = self._create_isolated_window()
        self.assertIsNotNone(window.menuBar())
        self.assertEqual(window.menu_file.title(), "ファイル(&F)")
        self.assertEqual(window.menu_view.title(), "表示(&V)")
        self.assertEqual(window.menu_help.title(), "ヘルプ(&H)")

        # ファイルメニュー ショートカット
        self.assertEqual(window.act_open_a.shortcut().toString(), "Ctrl+O")
        self.assertEqual(window.act_open_b.shortcut().toString(), "Ctrl+Shift+O")
        self.assertEqual(window.act_swap.shortcut().toString(), "Ctrl+Shift+X")
        self.assertEqual(window.act_exit.shortcut().toString(), "Ctrl+Q")

        # 表示メニュー ショートカット
        self.assertEqual(window.act_tab_1.shortcut().toString(), "Ctrl+1")
        self.assertEqual(window.act_tab_2.shortcut().toString(), "Ctrl+2")
        self.assertEqual(window.act_tab_3.shortcut().toString(), "Ctrl+3")
        self.assertEqual(window.act_tab_4.shortcut().toString(), "Ctrl+4")
        self.assertEqual(window.act_tab_5.shortcut().toString(), "Ctrl+5")

        # ヘルプメニュー ショートカット
        self.assertEqual(window.act_spec_guide.shortcut().toString(), "F1")

        # 表示メニューのアクションによるタブ切り替え
        window.act_tab_2.trigger()
        self.assertEqual(window.tabs.currentIndex(), 1)
        window.act_tab_3.trigger()
        self.assertEqual(window.tabs.currentIndex(), 2)
        window.act_tab_4.trigger()
        self.assertEqual(window.tabs.currentIndex(), 3)
        window.act_tab_5.trigger()
        self.assertEqual(window.tabs.currentIndex(), 4)
        window.act_tab_1.trigger()
        self.assertEqual(window.tabs.currentIndex(), 0)

    def test_swap_folders_action(self):
        """「A と B を入れ替え」でパスが反転し、YAML・画像・CSVの各ビューが入れ替わり、読み込みが1回のみ行われる (ISSUE-16)"""
        from PySide6.QtCore import QThreadPool

        window = self._create_isolated_window()
        window.load_folders(self.folder_a, self.folder_b, blocking=True)

        # 読み込み前の初期状態検証
        self.assertEqual(window.combo_folder_a.currentText(), self.folder_a)
        self.assertEqual(window.combo_folder_b.currentText(), self.folder_b)
        self.assertEqual(window.tab_yaml.yaml_a.get("mode"), "S-SAP")
        self.assertEqual(window.tab_yaml.yaml_b.get("mode"), "Q-SAP")
        self.assertEqual(window.tab_images.folder_a, self.folder_a)
        self.assertEqual(window.tab_images.folder_b, self.folder_b)
        self.assertIn("S-SAP", window.tab_images.box_a.title())
        self.assertIn("Q-SAP", window.tab_images.box_b.title())
        self.assertEqual(window.tab_csv.folder_a, self.folder_a)
        self.assertEqual(window.tab_csv.folder_b, self.folder_b)
        self.assertIn("S-SAP", window.tab_csv.info_a)
        self.assertIn("Q-SAP", window.tab_csv.info_b)

        # A と B を入れ替え実行 (スレッド完了まで同期的に待機し、GUIイベントを処理)
        with patch.object(window, "load_all", wraps=window.load_all) as spy_load:
            window.act_swap.trigger()
            QThreadPool.globalInstance().waitForDone(5000)
            self.app.processEvents()

        # 重複なく 1 回だけ読み込みが走ったこと
        spy_load.assert_called_once()
        # lineEdit のシグナル遮断によりデバウンスタイマーが起動していないこと
        self.assertFalse(window._debounce_timer.isActive())

        # コンボボックスのテキストおよび内部追跡パスが入れ替わっていること
        self.assertEqual(window.combo_folder_a.currentText(), self.folder_b)
        self.assertEqual(window.combo_folder_b.currentText(), self.folder_a)
        self.assertEqual(window._last_loaded_a, self.folder_b)
        self.assertEqual(window._last_loaded_b, self.folder_a)

        # 1. YAML 差分の A/B 列が入れ替わっていること
        self.assertEqual(window.tab_yaml.yaml_a.get("mode"), "Q-SAP")
        self.assertEqual(window.tab_yaml.yaml_b.get("mode"), "S-SAP")
        self.assertIn("Q-SAP", window.tab_yaml.info_a)
        self.assertIn("S-SAP", window.tab_yaml.info_b)
        mode_item = None
        for i in range(window.tab_yaml.tree.topLevelItemCount()):
            item = window.tab_yaml.tree.topLevelItem(i)
            if item.text(0) == "mode":
                mode_item = item
                break
        self.assertIsNotNone(mode_item)
        self.assertEqual(mode_item.text(1), "Q-SAP")
        self.assertEqual(mode_item.text(2), "S-SAP")

        # 2. 画像比較の左右表示が入れ替わっていること
        self.assertEqual(window.tab_images.folder_a, self.folder_b)
        self.assertEqual(window.tab_images.folder_b, self.folder_a)
        self.assertIn("Q-SAP", window.tab_images.box_a.title())
        self.assertIn("S-SAP", window.tab_images.box_b.title())

        # 3. CSV 比較グラフの凡例およびデータが入れ替わっていること
        self.assertEqual(window.tab_csv.folder_a, self.folder_b)
        self.assertEqual(window.tab_csv.folder_b, self.folder_a)
        self.assertIn("Q-SAP", window.tab_csv.info_a)
        self.assertIn("S-SAP", window.tab_csv.info_b)
        self.assertIn("Q-SAP", window.tab_csv.txt_legend_a.placeholderText())
        self.assertIn("S-SAP", window.tab_csv.txt_legend_b.placeholderText())

    def test_about_action_and_version(self):
        """バージョン情報ダイアログに APP_VERSION が含まれることの検証 (ISSUE-16)"""
        from src.config import APP_VERSION
        from PySide6.QtWidgets import QMessageBox

        window = self._create_isolated_window()
        with patch.object(QMessageBox, "about") as mock_about:
            window.act_about.trigger()
            mock_about.assert_called_once()
            args, _ = mock_about.call_args
            text = args[2]
            self.assertIn(f"v{APP_VERSION}", text)

    def test_theme_menu_sync(self):
        """テーマメニューの切り替えが ThemeManager およびヘッダーコンボと連動する検証 (ISSUE-16)"""
        from src.ui.theme import get_theme_manager
        tm = get_theme_manager()
        orig_pref = tm.get_preference()

        window = self._create_isolated_window()
        try:
            # メニューから「ダーク」を選択
            window.act_theme_dark.trigger()
            self.assertEqual(tm.get_preference(), "dark")
            self.assertEqual(window.combo_theme.currentData(), "dark")
            self.assertTrue(window.act_theme_dark.isChecked())
            self.assertFalse(window.act_theme_light.isChecked())

            # ヘッダーコンボボックスから「ライト」を選択
            idx = window.combo_theme.findData("light")
            window.combo_theme.setCurrentIndex(idx)
            self.assertEqual(tm.get_preference(), "light")
            self.assertTrue(window.act_theme_light.isChecked())
            self.assertFalse(window.act_theme_dark.isChecked())
        finally:
            tm.set_preference(orig_pref)

    def test_help_menu_actions(self):
        """ヘルプメニューの各アクション（仕様ガイド、ログフォルダ、GitHub、更新確認）の検証 (ISSUE-16)"""
        from src.config import GITHUB_REPO_OWNER, GITHUB_REPO_NAME
        from src.core.logging_setup import get_log_dir

        window = self._create_isolated_window()

        # 1. 仕様ガイド
        window.tabs.setCurrentIndex(0)
        window.act_spec_guide.trigger()
        self.assertEqual(window.tabs.currentWidget(), window.tab_spec)

        # 2. ログフォルダを開く
        with patch("src.ui.main_window.QDesktopServices.openUrl") as mock_open:
            window.act_open_log_dir.trigger()
            mock_open.assert_called_once()
            url = mock_open.call_args[0][0]
            log_dir = os.path.abspath(get_log_dir())
            self.assertTrue(os.path.isdir(log_dir))
            self.assertEqual(os.path.abspath(url.toLocalFile()), log_dir)

        # 3. GitHub リポジトリを開く
        with patch("src.ui.main_window.QDesktopServices.openUrl") as mock_open:
            window.act_open_repo.trigger()
            mock_open.assert_called_once()
            url = mock_open.call_args[0][0]
            expected_url = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
            self.assertEqual(url.toString(), expected_url)

        # 4. 更新を確認
        with patch.object(window, "_on_manual_check_update") as mock_update:
            window.act_check_update.trigger()
            mock_update.assert_called_once()

if __name__ == "__main__":
    unittest.main()



