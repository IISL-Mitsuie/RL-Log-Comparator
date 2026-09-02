"""
YAML 差分比較ビューウィジェット (YamlDiffWidget) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
from src.ui.widgets.yaml_diff_widget import YamlDiffWidget
from tests.helpers import get_qapp, create_dummy_experiment_folder


class TestUiYamlDiffWidget(unittest.TestCase):
    """YamlDiffWidget の UI 操作・描画テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_a = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_a", learning_rate=0.001
        )
        self.folder_b = create_dummy_experiment_folder(
            self.test_dir, folder_name="folder_b", learning_rate=0.002
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_yamls_and_tree_nodes(self):
        widget = YamlDiffWidget()
        widget.load_yamls(self.folder_a, self.folder_b)

        # 差分のみ表示（初期状態）
        self.assertTrue(widget.cb_diff_only.isChecked())
        root_count_diff_only = widget.tree.topLevelItemCount()
        self.assertTrue(root_count_diff_only > 0)
        self.assertIn("差分のあるパラメータを表示中", widget.lbl_status.text())

        # 全件表示に切り替え
        widget.cb_diff_only.setChecked(False)
        root_count_all = widget.tree.topLevelItemCount()
        self.assertGreaterEqual(root_count_all, root_count_diff_only)
        self.assertIn("全パラメータを表示中", widget.lbl_status.text())


if __name__ == "__main__":
    unittest.main()
