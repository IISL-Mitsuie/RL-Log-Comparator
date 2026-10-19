"""
YAML 差分解析モジュール (src.core.parsers.yaml_diff) の単体テスト
"""

import datetime
import unittest
import tempfile
import shutil
from src.core.parsers.yaml_diff import (
    read_yaml_file, build_diff_tree
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

    def test_mixed_key_types(self):
        nodes = build_diff_tree({1: "a", "x": 2}, {"x": 3})
        node_dict = {n.key: n for n in nodes}
        self.assertEqual(node_dict["1"].state_str, "Aのみ存在")
        self.assertEqual(node_dict["x"].state_str, "差分あり")

    def test_mixed_key_types_nested(self):
        nodes = build_diff_tree({"m": {1: "a", "x": 2}}, {"m": {"x": 2}})
        sub_dict = {c.key: c for c in nodes[0].children}
        self.assertEqual(sub_dict["1"].state_str, "Aのみ存在")
        self.assertEqual(sub_dict["x"].state_str, "一致")

    def test_null_vs_value(self):
        node = build_diff_tree({"a": None}, {"a": 1})[0]
        self.assertEqual(node.state_str, "差分あり")
        self.assertEqual(node.val_a_str, "null")
        self.assertEqual(node.val_b_str, "1")

    def test_null_vs_missing(self):
        node = build_diff_tree({"a": None}, {})[0]
        self.assertEqual(node.state_str, "Aのみ存在")
        self.assertEqual(node.val_a_str, "null")
        self.assertEqual(node.val_b_str, "(なし)")

    def test_null_vs_null(self):
        node = build_diff_tree({"a": None}, {"a": None})[0]
        self.assertEqual(node.state_str, "一致")

    def test_bool_vs_int(self):
        node = build_diff_tree({"s": True}, {"s": 1})[0]
        self.assertEqual(node.state_str, "差分あり")
        node = build_diff_tree({"s": False}, {"s": 0})[0]
        self.assertEqual(node.state_str, "差分あり")

    def test_int_vs_float(self):
        node = build_diff_tree({"lr": 1}, {"lr": 1.0})[0]
        self.assertEqual(node.state_str, "一致")

    def test_nan_vs_nan(self):
        node = build_diff_tree({"x": float("nan")}, {"x": float("nan")})[0]
        self.assertEqual(node.state_str, "一致")

    def test_short_scalar_list(self):
        node = build_diff_tree({"g": [1, 2]}, {"g": [1, 3]})[0]
        self.assertEqual(node.state_str, "差分あり")
        self.assertEqual(node.children, [])
        self.assertEqual(node.val_a_str, "[1, 2]")
        self.assertEqual(node.val_b_str, "[1, 3]")

    def test_short_scalar_list_bool_vs_int(self):
        node = build_diff_tree({"g": [True]}, {"g": [1]})[0]
        self.assertEqual(node.state_str, "差分あり")

    def test_nested_list_expanded(self):
        yaml_a = {"g": [[11.0, 3.0], [15.0, 5.0]]}
        yaml_b = {"g": [[11.0, 3.0], [15.0, 6.0]]}

        node = build_diff_tree(yaml_a, yaml_b, diff_only=False)[0]
        self.assertEqual(node.state_str, "階層")
        self.assertTrue(node.is_different)
        child_dict = {c.key: c for c in node.children}
        self.assertEqual(child_dict["[0]"].state_str, "一致")
        self.assertEqual(child_dict["[1]"].state_str, "差分あり")

        node = build_diff_tree(yaml_a, yaml_b, diff_only=True)[0]
        self.assertEqual([c.key for c in node.children], ["[1]"])

    def test_long_scalar_list_expanded(self):
        yaml_a = {"g": list(range(11))}
        yaml_b = {"g": list(range(10)) + [99]}
        node = build_diff_tree(yaml_a, yaml_b, diff_only=True)[0]
        self.assertEqual(node.state_str, "階層")
        self.assertEqual([c.key for c in node.children], ["[10]"])

    def test_list_length_mismatch(self):
        node = build_diff_tree({"g": [{"x": 1}]}, {"g": [{"x": 1}, {"x": 2}]})[0]
        child_dict = {c.key: c for c in node.children}
        self.assertFalse(child_dict["[0]"].is_different)
        self.assertEqual(child_dict["[1]"].state_str, "Bのみ存在")

    def test_list_of_dicts_only_in_a(self):
        node = build_diff_tree({"g": [{"x": 1}]}, {})[0]
        self.assertEqual(node.state_str, "Aのみ存在")
        self.assertEqual(node.val_b_str, "(なし)")
        self.assertTrue(node.is_different)
        self.assertEqual(node.children[0].key, "[0]")

    def test_dict_only_in_b(self):
        node = build_diff_tree({}, {"m": {"x": 1}}, diff_only=True)[0]
        self.assertEqual(node.state_str, "Bのみ存在")
        self.assertEqual([c.key for c in node.children], ["x"])
        self.assertEqual(node.children[0].state_str, "Bのみ存在")

    def test_dict_vs_scalar(self):
        node = build_diff_tree({"m": {"x": 1}}, {"m": 5})[0]
        self.assertEqual(node.state_str, "差分あり")
        self.assertEqual(node.val_a_str, '{"x": 1}')
        self.assertEqual(node.val_b_str, "5")

    def test_list_vs_scalar(self):
        node = build_diff_tree({"g": [[1]]}, {"g": "none"})[0]
        self.assertEqual(node.state_str, "差分あり")

    def test_diff_only_identical(self):
        data = {"a": 1, "b": None, "m": {"x": [1, 2]}, "g": [[1.0, 2.0]]}
        self.assertEqual(build_diff_tree(data, dict(data), diff_only=True), [])

    def test_int_keys_numeric_order(self):
        nodes = build_diff_tree({1: "a", 2: "b", 10: "c"}, {})
        self.assertEqual([n.key for n in nodes], ["1", "2", "10"])

    def test_empty_dict_only_in_a(self):
        nodes = build_diff_tree({"opt": {}}, {}, diff_only=True)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].state_str, "Aのみ存在")
        self.assertTrue(nodes[0].is_different)

    def test_empty_long_list_only_in_b(self):
        nodes = build_diff_tree({"m": {}}, {"m": {"g": [[]]}}, diff_only=True)
        self.assertEqual(nodes[0].children[0].state_str, "Bのみ存在")

    def test_dict_with_date_keys_vs_scalar(self):
        node = build_diff_tree({"sched": {datetime.date(2024, 1, 1): 1}}, {"sched": 5})[0]
        self.assertEqual(node.state_str, "差分あり")
        self.assertIn("2024", node.val_a_str)

    def test_short_date_list_inline(self):
        dates = [datetime.date(2024, 1, 1), datetime.date(2024, 2, 1)]
        node = build_diff_tree({"d": dates}, {"d": list(dates)})[0]
        self.assertEqual(node.state_str, "一致")
        self.assertEqual(node.children, [])

if __name__ == "__main__":
    unittest.main()
