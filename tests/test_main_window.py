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

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_window_init_and_tabs(self):
        window = ExperimentCompareApp()
        self.assertEqual(window.tabs.count(), 4)
        self.assertIn("1. ハイパーパラメータ差分", window.tabs.tabText(0))
        self.assertIn("2. 画像目視比較", window.tabs.tabText(1))
        self.assertIn("3. 数値ログ比較グラフ", window.tabs.tabText(2))
        self.assertIn("4. ログ仕様ガイド", window.tabs.tabText(3))

    def test_load_folders(self):
        window = ExperimentCompareApp()
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
        window = ExperimentCompareApp()
        # 履歴への追加
        window._history = window.history_mgr.add_folder(self.folder_a)
        window._update_history_combos()

        self.assertIn(self.folder_a, [window.combo_folder_a.itemText(i) for i in range(window.combo_folder_a.count())])


if __name__ == "__main__":
    unittest.main()
