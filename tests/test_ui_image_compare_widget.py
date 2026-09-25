"""
画像並列比較ビューウィジェット (ImageCompareWidget) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
from src.ui.widgets.image_compare_widget import ImageCompareWidget
from tests.helpers import get_qapp, create_dummy_experiment_folder


class TestUiImageCompareWidget(unittest.TestCase):
    """ImageCompareWidget の UI 操作・描画テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.folder_a = create_dummy_experiment_folder(
            self.test_dir,
            folder_name="folder_a",
            images=["rewards_001.png", "steps_001.png"]
        )
        self.folder_b = create_dummy_experiment_folder(
            self.test_dir,
            folder_name="folder_b",
            images=["rewards_001.png", "trajectory_001.png"]
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_folders_and_selection(self):
        widget = ImageCompareWidget()
        widget.load_folders(self.folder_a, self.folder_b)

        # 3種類の画像ペア（rewards, steps, trajectory）がリストに追加される
        self.assertEqual(widget.list_images.count(), 3)

        # 両方に存在する行 (rewards) を見つけて選択
        target_row = -1
        for row in range(widget.list_images.count()):
            item = widget.list_images.item(row)
            if "両方" in item.text() or "rewards" in item.text():
                target_row = row
                break

        self.assertNotEqual(target_row, -1)
        widget.list_images.setCurrentRow(target_row)
        self.assertFalse(widget.scene_a.itemsBoundingRect().isEmpty())
        self.assertFalse(widget.scene_b.itemsBoundingRect().isEmpty())

        # 左右自由選択モードの切替テスト
        widget.cb_manual_mode.setChecked(True)
        self.assertFalse(widget.combo_img_a.isHidden())
        self.assertFalse(widget.combo_img_b.isHidden())
        widget.cb_manual_mode.setChecked(False)
        self.assertTrue(widget.combo_img_a.isHidden())
        self.assertTrue(widget.combo_img_b.isHidden())

        # リセットボタンのテスト
        widget._reset_views()


if __name__ == "__main__":
    unittest.main()
