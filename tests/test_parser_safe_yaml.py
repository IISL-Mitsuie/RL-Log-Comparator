"""
safe_yaml モジュールの単体テスト
"""

import os
import tempfile
import unittest
from src.core.parsers.safe_yaml import safe_load_yaml, sanitize_yaml_text


class TestSafeYaml(unittest.TestCase):

    def test_sanitize_yaml_text(self):
        bad_yaml = 'path: "output\\S-SAP_continual\\output_123\\policy.npy"\ncount: 5'
        sanitized = sanitize_yaml_text(bad_yaml)
        self.assertIn('"output/S-SAP_continual/output_123/policy.npy"', sanitized)

    def test_safe_load_yaml_with_bad_escapes(self):
        bad_yaml = """
mode:
  name: S-SAP
  continual_learning: true
continual_learning:
  files:
    - "output_robotino_rl_control\\S-SAP_continual\\output_20260924_181649\\acquired_policies_20260924_181649\\policy_task1.npy"
"""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yaml", delete=False) as f:
            f.write(bad_yaml)
            tmp_path = f.name

        try:
            data = safe_load_yaml(tmp_path)
            self.assertEqual(data["mode"]["name"], "S-SAP")
            self.assertTrue(data["mode"]["continual_learning"])
            self.assertEqual(len(data["continual_learning"]["files"]), 1)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_safe_load_yaml_nonexistent(self):
        self.assertEqual(safe_load_yaml("nonexistent_file_xyz.yaml"), {})

    def test_safe_load_json(self):
        json_content = '{"learning_rate": 0.001, "batch_size": 64, "algorithm": "PPO"}'
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as f:
            f.write(json_content)
            tmp_path = f.name

        try:
            data = safe_load_yaml(tmp_path)
            self.assertEqual(data["learning_rate"], 0.001)
            self.assertEqual(data["batch_size"], 64)
            self.assertEqual(data["algorithm"], "PPO")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == '__main__':
    unittest.main()

