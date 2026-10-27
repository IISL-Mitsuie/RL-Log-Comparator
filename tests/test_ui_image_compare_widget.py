"""
画像並列・重ね合わせ比較ビューウィジェット (ImageCompareWidget) の単体テスト
"""

import unittest
import tempfile
import shutil
import os
from PIL import Image
from PySide6.QtCore import Qt

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

    def _find_row_by_text(self, widget: ImageCompareWidget, substring: str) -> int:
        for row in range(widget.list_images.count()):
            item = widget.list_images.item(row)
            if substring in item.text():
                return row
        return -1

    def test_load_folders_and_selection(self):
        widget = ImageCompareWidget()
        widget.load_folders(self.folder_a, self.folder_b)

        # 3種類の画像ペア（rewards, steps, trajectory）がリストに追加される
        self.assertEqual(widget.list_images.count(), 3)

        # 両方に存在する行 (rewards) を見つけて選択
        target_row = self._find_row_by_text(widget, "rewards")
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

    def test_mode_switching_and_availability(self):
        widget = ImageCompareWidget()
        widget.load_folders(self.folder_a, self.folder_b)

        # 1. 両方存在する行 (rewards) を選択
        row_both = self._find_row_by_text(widget, "rewards")
        row_single = self._find_row_by_text(widget, "steps")

        self.assertNotEqual(row_both, -1)
        self.assertNotEqual(row_single, -1)

        # 両方存在する画像を選択 -> 重ねるモードが有効
        widget.list_images.setCurrentRow(row_both)
        model = widget.combo_mode.model()
        item_diff = model.item(3)  # 差分
        self.assertTrue(item_diff.flags() & Qt.ItemFlag.ItemIsEnabled)

        # 差分モードに切り替え
        widget.combo_mode.setCurrentIndex(3)
        self.assertEqual(widget.right_stack.currentIndex(), 1)  # overlay_view
        self.assertFalse(widget.widget_diff_ctrl.isHidden())
        self.assertTrue(widget.widget_overlay_ctrl.isHidden())
        self.assertEqual(widget.lbl_diff_ratio.text(), "差分画素: 0.0%")

        # 2. 片側しか存在しない画像 (steps) に変更 -> 自動的に並列に戻る
        widget.list_images.setCurrentRow(row_single)
        self.assertEqual(widget.combo_mode.currentIndex(), 0)  # 並列
        self.assertEqual(widget.right_stack.currentIndex(), 0)  # parallel splitter
        self.assertFalse(item_diff.flags() & Qt.ItemFlag.ItemIsEnabled)

        # 片側しかない状態で重ねるモードを選択しようとしても並列のまま
        widget.combo_mode.setCurrentIndex(1)
        self.assertEqual(widget.combo_mode.currentIndex(), 0)

    def test_overlay_mode_slider(self):
        widget = ImageCompareWidget()
        widget.load_folders(self.folder_a, self.folder_b)

        row_both = self._find_row_by_text(widget, "rewards")
        self.assertNotEqual(row_both, -1)
        widget.list_images.setCurrentRow(row_both)

        widget.combo_mode.setCurrentIndex(1)  # オーバーレイ

        self.assertEqual(widget.right_stack.currentIndex(), 1)
        self.assertFalse(widget.widget_overlay_ctrl.isHidden())

        # スライダーを動かす
        widget.slider_opacity.setValue(80)
        self.assertEqual(widget.lbl_opacity.text(), "不透明度 (B): 80%")
        self.assertAlmostEqual(widget.overlay_view.item_b.opacity(), 0.8)

    def test_swipe_mode_slider(self):
        widget = ImageCompareWidget()
        widget.load_folders(self.folder_a, self.folder_b)

        row_both = self._find_row_by_text(widget, "rewards")
        self.assertNotEqual(row_both, -1)
        widget.list_images.setCurrentRow(row_both)

        widget.combo_mode.setCurrentIndex(2)  # スワイプ

        self.assertEqual(widget.right_stack.currentIndex(), 1)
        self.assertFalse(widget.widget_swipe_ctrl.isHidden())

        # スライダー操作
        widget.slider_swipe.setValue(30)
        self.assertEqual(widget.lbl_swipe.text(), "スワイプ境界位置: 30%")
        self.assertAlmostEqual(widget.overlay_view._swipe_ratio, 0.3)

        # ビューからのスワイプ通知
        widget.overlay_view.swipe_position_changed.emit(0.75)
        self.assertEqual(widget.slider_swipe.value(), 75)
        self.assertEqual(widget.lbl_swipe.text(), "スワイプ境界位置: 75%")

    def test_diff_gain_control(self):
        widget = ImageCompareWidget()
        widget.load_folders(self.folder_a, self.folder_b)

        row_both = self._find_row_by_text(widget, "rewards")
        self.assertNotEqual(row_both, -1)
        widget.list_images.setCurrentRow(row_both)

        widget.combo_mode.setCurrentIndex(3)  # 差分
        widget.combo_diff_gain.setCurrentIndex(2)  # ×3
        self.assertAlmostEqual(widget.overlay_view._diff_gain, 3.0)

    def test_different_sizes_notice(self):
        # フォルダ A に 100x100、フォルダ B に 200x200 のペア画像を作成
        diff_a = os.path.join(self.folder_a, "diff_size.png")
        diff_b = os.path.join(self.folder_b, "diff_size.png")
        img_a = Image.new("RGB", (100, 100), color=(50, 50, 50))
        img_b = Image.new("RGB", (200, 200), color=(50, 50, 50))
        img_a.save(diff_a)
        img_b.save(diff_b)

        widget = ImageCompareWidget()
        widget.load_folders(self.folder_a, self.folder_b)

        # diff_size の行を選択
        target_row = self._find_row_by_text(widget, "diff_size")
        self.assertNotEqual(target_row, -1)
        widget.list_images.setCurrentRow(target_row)

        # オーバーレイモードに切り替え
        widget.combo_mode.setCurrentIndex(1)
        self.assertFalse(widget.lbl_resize_notice.isHidden())
        notice_text = widget.lbl_resize_notice.text()
        self.assertIn("200×200", notice_text)
        self.assertIn("100×100", notice_text)
        self.assertIn("縮小", notice_text)

        # 並列モードに戻すと注記は非表示
        widget.combo_mode.setCurrentIndex(0)
        self.assertTrue(widget.lbl_resize_notice.isHidden())

        # ズームリセットテスト
        widget._reset_views()

    def test_manual_mode_with_overlay(self):
        widget = ImageCompareWidget()
        widget.load_folders(self.folder_a, self.folder_b)

        widget.cb_manual_mode.setChecked(True)
        self.assertEqual(widget.combo_img_a.count(), 2)
        self.assertEqual(widget.combo_img_b.count(), 2)

        # rewards_001.png を両方で選択
        widget.combo_img_a.setCurrentIndex(0)
        widget.combo_img_b.setCurrentIndex(0)

        # 差分モード
        widget.combo_mode.setCurrentIndex(3)
        self.assertEqual(widget.right_stack.currentIndex(), 1)
        self.assertEqual(widget.lbl_diff_ratio.text(), "差分画素: 0.0%")


if __name__ == "__main__":
    unittest.main()
