"""
実験情報抽出モジュール (src.core.parsers.experiment) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
from src.core.parsers.experiment import get_experiment_info
from tests.helpers import create_dummy_experiment_folder


class TestParserExperiment(unittest.TestCase):
    """get_experiment_info のテスト"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extract_mode_and_timestamp(self):
        folder = create_dummy_experiment_folder(
            self.test_dir,
            folder_name="output_20260801_123456",
            mode="S-SAP"
        )
        info = get_experiment_info(folder)
        self.assertIn("[S-SAP]", info)
        self.assertIn("20260801_123456", info)

    def test_extract_algorithm_fallback(self):
        folder = os.path.join(self.test_dir, "output_20260802_235959")
        os.makedirs(folder, exist_ok=True)
        import yaml
        with open(os.path.join(folder, "config_used_test.yaml"), "w", encoding="utf-8") as f:
            yaml.dump({"algorithm": "PPO_Lagrangian"}, f)

        info = get_experiment_info(folder)
        self.assertIn("[PPO_Lagrangian]", info)
        self.assertIn("20260802_235959", info)

    def test_extract_mode_dict_with_shield(self):
        folder = os.path.join(self.test_dir, "output_20260909_145945")
        os.makedirs(folder, exist_ok=True)
        import yaml
        with open(os.path.join(folder, "config_used_20260909_145945.yaml"), "w", encoding="utf-8") as f:
            yaml.dump({
                "mode": {
                    "name": "S-SAP",
                    "use_shield": False
                }
            }, f)

        info = get_experiment_info(folder)
        self.assertIn("[S-SAP]", info)
        self.assertIn("20260909_145945", info)


    def test_invalid_and_empty_folder(self):
        self.assertEqual(get_experiment_info(""), "未選択 / 存在しないフォルダ")
        self.assertEqual(get_experiment_info("non_existent_folder_xyz"), "未選択 / 存在しないフォルダ")


if __name__ == "__main__":
    unittest.main()
