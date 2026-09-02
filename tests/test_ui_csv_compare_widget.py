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

        # 指標数（4つ）の確認
        self.assertEqual(widget.list_metrics.count(), 4)

        # 各指標を切り替えて例外なく再描画されることを確認
        for i in range(widget.list_metrics.count()):
            widget.list_metrics.setCurrentRow(i)

        # スライダー変更時の更新
        widget.slider_ma.setValue(5)
        self.assertEqual(widget.lbl_ma_val.text(), "5 ep")

        # 生データチェックボックスの切替
        widget.cb_raw_data.setChecked(False)
        widget.cb_raw_data.setChecked(True)


if __name__ == "__main__":
    unittest.main()
