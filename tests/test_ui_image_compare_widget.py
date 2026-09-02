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

        # 行選択のシミュレーション
        widget.list_images.setCurrentRow(0)
        self.assertFalse(widget.scene_a.itemsBoundingRect().isEmpty())
        self.assertFalse(widget.scene_b.itemsBoundingRect().isEmpty())

        # リセットボタンのテスト
        widget._reset_views()


if __name__ == "__main__":
    unittest.main()
