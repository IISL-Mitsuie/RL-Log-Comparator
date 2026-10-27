"""
image_diff モジュールの単体テスト
"""

import unittest
import numpy as np
from src.core.image_diff import compute_abs_diff, diff_ratio


class TestImageDiff(unittest.TestCase):
    """compute_abs_diff および diff_ratio のテスト"""

    def test_identical_images(self):
        a = np.full((10, 10, 4), 100, dtype=np.uint8)
        b = a.copy()

        diff = compute_abs_diff(a, b)
        self.assertEqual(diff.shape, (10, 10, 4))
        self.assertEqual(diff.dtype, np.uint8)
        # RGB は全て 0、Alpha は 255
        self.assertTrue(np.all(diff[..., :3] == 0))
        self.assertTrue(np.all(diff[..., 3] == 255))

        ratio = diff_ratio(a, b)
        self.assertEqual(ratio, 0.0)

    def test_gain_and_clipping(self):
        a = np.zeros((2, 2, 4), dtype=np.uint8)
        b = np.zeros((2, 2, 4), dtype=np.uint8)
        a[0, 0, 0] = 50  # 赤チャンネルのみ 50

        # gain = 1.0
        diff_1 = compute_abs_diff(a, b, gain=1.0)
        self.assertEqual(diff_1[0, 0, 0], 50)
        self.assertEqual(diff_1[0, 0, 1], 0)
        self.assertEqual(diff_1[0, 0, 3], 255)

        # gain = 2.0 -> 100
        diff_2 = compute_abs_diff(a, b, gain=2.0)
        self.assertEqual(diff_2[0, 0, 0], 100)

        # gain = 10.0 -> 500 -> 255 でクリップ
        diff_10 = compute_abs_diff(a, b, gain=10.0)
        self.assertEqual(diff_10[0, 0, 0], 255)

    def test_diff_ratio_threshold(self):
        # 4画素の画像 (2x2)
        a = np.zeros((2, 2, 4), dtype=np.uint8)
        b = np.zeros((2, 2, 4), dtype=np.uint8)

        # 1画素目: 差が 16 (threshold 16 では超えない)
        b[0, 0, 0] = 16
        # 2画素目: 差が 17 (超える)
        b[0, 1, 1] = 17
        # 3画素目: 差が 0
        # 4画素目: Alpha のみ差がある (255) -> RGB のみ評価されるべきなので差分と判定されない
        b[1, 1, 3] = 255

        ratio = diff_ratio(a, b, threshold=16)
        # 4画素中 1画素のみ差分
        self.assertEqual(ratio, 0.25)

        # threshold = 15 に下げると 1画素目も差分と判定され 2/4 = 0.5
        self.assertEqual(diff_ratio(a, b, threshold=15), 0.5)

    def test_shape_mismatch_raises(self):
        a = np.zeros((10, 10, 4), dtype=np.uint8)
        b = np.zeros((10, 20, 4), dtype=np.uint8)
        with self.assertRaises(ValueError):
            compute_abs_diff(a, b)
        with self.assertRaises(ValueError):
            diff_ratio(a, b)

    def test_channel_mismatch_raises(self):
        a = np.zeros((10, 10, 3), dtype=np.uint8)
        b = np.zeros((10, 10, 3), dtype=np.uint8)
        with self.assertRaises(ValueError):
            compute_abs_diff(a, b)
        with self.assertRaises(ValueError):
            diff_ratio(a, b)

    def test_empty_image(self):
        a = np.zeros((0, 0, 4), dtype=np.uint8)
        b = np.zeros((0, 0, 4), dtype=np.uint8)
        diff = compute_abs_diff(a, b)
        self.assertEqual(diff.shape, (0, 0, 4))
        self.assertEqual(diff_ratio(a, b), 0.0)


if __name__ == "__main__":
    unittest.main()
