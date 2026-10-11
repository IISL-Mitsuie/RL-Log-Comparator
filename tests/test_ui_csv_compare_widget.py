"""
CSV 重ね合わせ比較グラフビューウィジェット (CsvCompareWidget) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
from src.ui.widgets.csv_compare_widget import CsvCompareWidget
from tests.helpers import get_qapp, create_dummy_experiment_folder


class TestUiCsvCompareWidget(unittest.TestCase):
    """CsvCompareWidget の UI 操作・チャート描画テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_a = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_a", episodes=20
        )
        self.folder_b = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_b", episodes=20
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_csvs_and_change_metrics(self):
        widget = CsvCompareWidget()
        widget.load_csvs(self.folder_a, self.folder_b)

        # 動的に抽出された指標が存在することを確認
        self.assertGreaterEqual(widget.list_metrics.count(), 1)

        # タスクコンボボックスの確認
        self.assertGreaterEqual(widget.combo_task.count(), 1)

        # 各指標を切り替えて例外なく再描画されることを確認
        for i in range(widget.list_metrics.count()):
            widget.list_metrics.setCurrentRow(i)

        # スライダー変更時の更新
        widget.slider_ma.setValue(5)
        self.assertEqual(widget.lbl_ma_val.text(), "5 ep")

        # 生データチェックボックスの切替
        widget.cb_raw_data.setChecked(False)
        widget.cb_raw_data.setChecked(True)

    def test_asymmetric_csv_columns_rendering(self):
        """片方のCSVにしか存在しない指標列（例: Aのみlossあり）の安全な描画テスト"""
        import pandas as pd
        folder_asym_a = os.path.join(self.test_dir, "asym_a")
        folder_asym_b = os.path.join(self.test_dir, "asym_b")
        os.makedirs(folder_asym_a, exist_ok=True)
        os.makedirs(folder_asym_b, exist_ok=True)

        # Aには reward と custom_loss が存在
        pd.DataFrame({
            "step": [1, 2, 3],
            "reward": [10.0, 20.0, 30.0],
            "custom_loss": [0.5, 0.3, 0.1]
        }).to_csv(os.path.join(folder_asym_a, "learning_log_test.csv"), index=False)

        # Bには reward のみ存在 (custom_loss は無し)
        pd.DataFrame({
            "step": [1, 2, 3],
            "reward": [5.0, 15.0, 25.0]
        }).to_csv(os.path.join(folder_asym_b, "learning_log_test.csv"), index=False)

        widget = CsvCompareWidget()
        widget.load_csvs(folder_asym_a, folder_asym_b)

        # custom_loss が指標一覧に含まれていることを確認
        found_loss_row = -1
        for row in range(widget.list_metrics.count()):
            item = widget.list_metrics.item(row)
            if item and item.text().startswith("custom_loss"):
                found_loss_row = row
                break

        self.assertNotEqual(found_loss_row, -1, "custom_loss should be listed in metrics")

        # custom_loss を選択して描画しても例外が発生しないことを確認
        widget.list_metrics.setCurrentRow(found_loss_row)
        widget.update_chart()

    def test_independent_task_mode_same_folder_different_tasks(self):
        """同一実験ログフォルダで異なるタスク（Task 1 vs Task 2）を選択・比較描画するテスト"""
        import pandas as pd
        folder_cl = os.path.join(self.test_dir, "continual_exp")
        os.makedirs(folder_cl, exist_ok=True)

        # 2つのタスクを含む統合CSVを作成
        df_cl = pd.DataFrame({
            "Task_ID": [1, 1, 1, 2, 2, 2],
            "Task_Episode": [1, 2, 3, 1, 2, 3],
            "Total_Episode": [1, 2, 3, 4, 5, 6],
            "Goal_X": [11.0, 11.0, 11.0, 15.0, 15.0, 15.0],
            "Goal_Y": [3.0, 3.0, 3.0, 5.0, 5.0, 5.0],
            "Steps": [100, 80, 60, 120, 90, 70],
            "TotalReward": [50.0, 70.0, 90.0, 20.0, 40.0, 60.0],
            "Is_Converged": [False, False, True, False, False, True]
        })
        df_cl.to_csv(os.path.join(folder_cl, "learning_log_20261011_120000.csv"), index=False)

        widget = CsvCompareWidget()
        # フォルダAとフォルダBに同一の実験ログフォルダを設定
        widget.load_csvs(folder_cl, folder_cl)

        # 個別タスク選択モードを有効化
        self.assertTrue(widget.cb_independent_tasks.isEnabled())
        widget.cb_independent_tasks.setChecked(True)

        # A側・B側のコンボボックスが表示・設定されていることを確認
        self.assertFalse(widget.combo_task_a.isHidden())
        self.assertFalse(widget.combo_task_b.isHidden())
        self.assertTrue(widget.combo_task.isHidden())

        # タスク候補数が 2 (Task 1, Task 2) であることを確認
        self.assertEqual(widget.combo_task_a.count(), 2)
        self.assertEqual(widget.combo_task_b.count(), 2)

        # A側に Task 1 (index 0), B側に Task 2 (index 1) を設定
        widget.combo_task_a.setCurrentIndex(0)
        widget.combo_task_b.setCurrentIndex(1)

        # 再描画
        widget.update_chart()

        # グラフのタイトルに対比タスク名が含まれていることを確認
        ax = widget.figure.axes[0]
        title = ax.get_title()
        self.assertIn("A: Task 1", title)
        self.assertIn("B: Task 2", title)

        # X軸ラベルが Task Episode となっていることを確認
        self.assertEqual(ax.get_xlabel(), "Task Episode (エピソード [1..N])")

        # 境界線オプションが無効化されていることを確認
        self.assertFalse(widget.cb_task_boundaries.isEnabled())

        # モードをOFFに戻した時の連動動作を確認
        widget.cb_independent_tasks.setChecked(False)
        self.assertFalse(widget.combo_task.isHidden())
        self.assertTrue(widget.combo_task_a.isHidden())
        self.assertTrue(widget.combo_task_b.isHidden())


if __name__ == "__main__":
    unittest.main()

