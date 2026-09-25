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


if __name__ == "__main__":
    unittest.main()

