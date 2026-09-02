"""
YAML 差分解析モジュール (src.core.parsers.yaml_diff) の単体テスト
"""

import os
import unittest
import tempfile
import shutil
import yaml
from src.core.parsers.yaml_diff import (
    read_yaml_file, build_diff_tree, DiffNode
)
from tests.helpers import create_dummy_experiment_folder


class TestParserYamlDiff(unittest.TestCase):
    """YAML 差分抽出ロジックのテスト"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_read_yaml_file(self):
        folder = create_dummy_experiment_folder(self.test_dir, learning_rate=0.005)
        data = read_yaml_file(folder)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("learning_rate"), 0.005)

    def test_read_nonexistent_yaml(self):
        self.assertEqual(read_yaml_file(""), {})
        self.assertEqual(read_yaml_file("non_existent_path"), {})

    def test_build_diff_tree_full(self):
        yaml_a = {
            "lr": 0.01,
            "batch": 32,
            "only_a": "val_a",
            "model": {"layers": 3, "units": 64}
        }
        yaml_b = {
            "lr": 0.02,
            "batch": 32,
            "only_b": "val_b",
            "model": {"layers": 4, "units": 64}
        }

        nodes = build_diff_tree(yaml_a, yaml_b, diff_only=False)
        node_dict = {n.key: n for n in nodes}

        # lr は差分あり
        self.assertIn("lr", node_dict)
        self.assertEqual(node_dict["lr"].state_str, "差分あり")
        self.assertTrue(node_dict["lr"].is_different)
        self.assertEqual(node_dict["lr"].bg_color_hex, "#fff5c8")

        # batch は一致
        self.assertIn("batch", node_dict)
        self.assertEqual(node_dict["batch"].state_str, "一致")
        self.assertFalse(node_dict["batch"].is_different)

        # only_a は Aのみ存在
        self.assertIn("only_a", node_dict)
        self.assertEqual(node_dict["only_a"].state_str, "Aのみ存在")
        self.assertEqual(node_dict["only_a"].bg_color_hex, "#e6ffe6")

        # only_b は Bのみ存在
        self.assertIn("only_b", node_dict)
        self.assertEqual(node_dict["only_b"].state_str, "Bのみ存在")
        self.assertEqual(node_dict["only_b"].bg_color_hex, "#ffe6e6")

        # model は階層
        self.assertIn("model", node_dict)
        self.assertEqual(node_dict["model"].state_str, "階層")
        sub_dict = {c.key: c for c in node_dict["model"].children}
        self.assertEqual(sub_dict["layers"].state_str, "差分あり")
        self.assertEqual(sub_dict["units"].state_str, "一致")

    def test_build_diff_tree_diff_only(self):
        yaml_a = {
            "identical_key": 100,
            "diff_key": "val_a",
            "model": {"same_sub": 1, "diff_sub": 10}
        }
        yaml_b = {
            "identical_key": 100,
            "diff_key": "val_b",
            "model": {"same_sub": 1, "diff_sub": 20}
        }

        diff_nodes = build_diff_tree(yaml_a, yaml_b, diff_only=True)
        keys = [n.key for n in diff_nodes]

        self.assertNotIn("identical_key", keys)
        self.assertIn("diff_key", keys)
        self.assertIn("model", keys)

        model_node = next(n for n in diff_nodes if n.key == "model")
        sub_keys = [c.key for c in model_node.children]
        self.assertNotIn("same_sub", sub_keys)
        self.assertIn("diff_sub", sub_keys)


if __name__ == "__main__":
    unittest.main()
