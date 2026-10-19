"""
safe_yaml モジュールの単体テスト
"""

import os
import shutil
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

    def test_find_config_file(self):
        from src.core.parsers.safe_yaml import find_config_file
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 何もない場合
            self.assertIsNone(find_config_file(tmp_dir))

            # params.json を作成
            p_json = os.path.join(tmp_dir, "params.json")
            with open(p_json, "w") as f:
                f.write("{}")
            self.assertEqual(find_config_file(tmp_dir), p_json)

            # より優先度の高い config_used_123.yaml を作成
            c_yaml = os.path.join(tmp_dir, "config_used_123.yaml")
            with open(c_yaml, "w") as f:
                f.write("{}")
            self.assertEqual(find_config_file(tmp_dir), c_yaml)


class TestSafeLoadYamlWithError(unittest.TestCase):
    """解析の失敗と「設定なし」の区別 (ISSUE-07)"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write(self, name: str, text: str) -> str:
        path = os.path.join(self.test_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_valid_yaml_has_no_error(self):
        from src.core.parsers.safe_yaml import safe_load_yaml_with_error
        data, error = safe_load_yaml_with_error(self._write("ok.yaml", "a: 1\n"))
        self.assertEqual(data, {"a": 1})
        self.assertIsNone(error)

    def test_non_dict_or_empty_is_not_error(self):
        from src.core.parsers.safe_yaml import safe_load_yaml_with_error
        self.assertEqual(safe_load_yaml_with_error(self._write("list.yaml", "- 1\n- 2\n")), ({}, None))
        self.assertEqual(safe_load_yaml_with_error(self._write("empty.yaml", "")), ({}, None))
        self.assertEqual(safe_load_yaml_with_error(os.path.join(self.test_dir, "none.yaml")), ({}, None))

    def test_broken_yaml_returns_error(self):
        from src.core.parsers.safe_yaml import safe_load_yaml, safe_load_yaml_with_error
        path = self._write("broken.yaml", "a: [1, 2\nb: {\n")
        data, error = safe_load_yaml_with_error(path)
        self.assertEqual(data, {})
        self.assertTrue(error)
        # 既存の関数は戻り値の形を変えない
        self.assertEqual(safe_load_yaml(path), {})

    def test_broken_yaml_log_levels(self):
        """同じファイルが何度も読まれるため、トレースバックは safe_load_yaml_with_error でだけ記録する"""
        from src.core.parsers.safe_yaml import safe_load_yaml, safe_load_yaml_with_error
        path = self._write("broken.yaml", "a: [1, 2\nb: {\n")
        with self.assertLogs("src.core.parsers.safe_yaml", level="WARNING") as cm:
            safe_load_yaml(path)
        self.assertEqual(len(cm.records), 1)
        self.assertEqual(cm.records[0].levelname, "WARNING")
        self.assertIsNone(cm.records[0].exc_info)

        with self.assertLogs("src.core.parsers.safe_yaml", level="WARNING") as cm:
            safe_load_yaml_with_error(path)
        self.assertEqual(len(cm.records), 1)
        self.assertEqual(cm.records[0].levelname, "ERROR")
        self.assertIn("Traceback", cm.output[0])

    def test_sanitized_yaml_has_no_error(self):
        from src.core.parsers.safe_yaml import safe_load_yaml_with_error
        data, error = safe_load_yaml_with_error(self._write("win.yaml", 'path: "C:\\Users\\a"\n'))
        self.assertEqual(data, {"path": "C:/Users/a"})
        self.assertIsNone(error)


if __name__ == '__main__':
    unittest.main()

