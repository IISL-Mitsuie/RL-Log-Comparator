"""
画像ペアリング解析モジュール (src.core.parsers.image_pair) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
from src.core.parsers.image_pair import (
    extract_prefix, detect_image_pairs, ImagePairItem
)
from tests.helpers import create_dummy_experiment_folder


class TestParserImagePair(unittest.TestCase):
    """画像ペアリング抽出ロジックのテスト"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extract_prefix(self):
        self.assertEqual(extract_prefix("learning_rewards_00100_00500.png"), "learning_rewards")
        self.assertEqual(extract_prefix("trajectory_00100.png"), "trajectory")
        self.assertEqual(extract_prefix("custom_chart.png"), "custom_chart")
        self.assertEqual(extract_prefix("loss_step_10_20.png"), "loss_step")

    def test_detect_image_pairs(self):
        folder_a = create_dummy_experiment_folder(
            self.test_dir,
            folder_name="folder_a",
            images=["rewards_00100.png", "only_a_00100.png"]
        )
        folder_b = create_dummy_experiment_folder(
            self.test_dir,
            folder_name="folder_b",
            images=["rewards_00100.png", "only_b_00100.png"]
        )

        pairs = detect_image_pairs(folder_a, folder_b)
        self.assertEqual(len(pairs), 3)

        pair_dict = {p.prefix: p for p in pairs}

        # rewards (両方)
        self.assertIn("rewards", pair_dict)
        self.assertEqual(pair_dict["rewards"].display_text, "rewards (両方)")
        self.assertIsNotNone(pair_dict["rewards"].file_a)
        self.assertIsNotNone(pair_dict["rewards"].file_b)

        # only_a (Aのみ)
        self.assertIn("only_a", pair_dict)
        self.assertEqual(pair_dict["only_a"].display_text, "only_a (Aのみ)")
        self.assertIsNotNone(pair_dict["only_a"].file_a)
        self.assertIsNone(pair_dict["only_a"].file_b)

        # only_b (Bのみ)
        self.assertIn("only_b", pair_dict)
        self.assertEqual(pair_dict["only_b"].display_text, "only_b (Bのみ)")
        self.assertIsNone(pair_dict["only_b"].file_a)
        self.assertIsNotNone(pair_dict["only_b"].file_b)

    def test_empty_folders(self):
        self.assertEqual(detect_image_pairs("", ""), [])
        self.assertEqual(detect_image_pairs("non_existent", "non_existent"), [])


if __name__ == "__main__":
    unittest.main()
