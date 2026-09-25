"""
YAML 設定ファイル読み込みおよび階層差分解析モジュール（Qt非依存）
"""

import os
import glob
from dataclasses import dataclass, field
from typing import Any, Optional
import yaml

from src.core.parsers.safe_yaml import safe_load_yaml


@dataclass
class DiffNode:
    """YAML 階層比較の1ノードを表すデータ構造"""
    key: str
    val_a_str: str
    val_b_str: str
    state_str: str
    is_different: bool
    bg_color_hex: Optional[str] = None
    children: list['DiffNode'] = field(default_factory=list)


def read_yaml_file(folder_path: str) -> dict:
    """フォルダ内の config_used_*.yaml (または *.yaml, *.yml, *.json) を安全に読み込んで辞書を返す"""
    if not folder_path or not os.path.isdir(folder_path):
        return {}

    # 優先順: config_used_*.yaml -> *.yaml -> *.yml -> config*.json -> params*.json -> *.json
    config_files = sorted(glob.glob(os.path.join(folder_path, "config_used_*.yaml")), reverse=True)
    if not config_files:
        config_files = sorted(glob.glob(os.path.join(folder_path, "*.yaml")), reverse=True)
    if not config_files:
        config_files = sorted(glob.glob(os.path.join(folder_path, "*.yml")), reverse=True)
    if not config_files:
        config_files = sorted(glob.glob(os.path.join(folder_path, "config*.json")), reverse=True)
    if not config_files:
        config_files = sorted(glob.glob(os.path.join(folder_path, "params*.json")), reverse=True)
    if not config_files:
        config_files = sorted(glob.glob(os.path.join(folder_path, "*.json")), reverse=True)

    if not config_files:
        return {}
    return safe_load_yaml(config_files[0])


def _compare_node(key: str, val_a: Any, val_b: Any, diff_only: bool) -> tuple[Optional[DiffNode], bool]:
    """再帰的にノードを比較して DiffNode と差分の有無を返す"""
    has_a = val_a is not None
    has_b = val_b is not None

    if isinstance(val_a, dict) or isinstance(val_b, dict):
        dict_a = val_a if isinstance(val_a, dict) else {}
        dict_b = val_b if isinstance(val_b, dict) else {}
        sub_keys = sorted(list(set(dict_a.keys()) | set(dict_b.keys())))

        child_nodes = []
        has_diff_in_children = False

        for skey in sub_keys:
            s_a = dict_a.get(skey)
            s_b = dict_b.get(skey)
            child_node, child_has_diff = _compare_node(str(skey), s_a, s_b, diff_only)
            if child_node is not None:
                child_nodes.append(child_node)
            if child_has_diff:
                has_diff_in_children = True

        if diff_only and not has_diff_in_children:
            return None, False

        node = DiffNode(
            key=str(key),
            val_a_str="",
            val_b_str="",
            state_str="階層",
            is_different=has_diff_in_children,
            bg_color_hex=None,
            children=child_nodes
        )
        return node, has_diff_in_children

    is_different = False
    state_str = "一致"
    bg_color_hex = None

    if not has_a and has_b:
        is_different = True
        state_str = "Bのみ存在"
        bg_color_hex = "#ffe6e6"
    elif has_a and not has_b:
        is_different = True
        state_str = "Aのみ存在"
        bg_color_hex = "#e6ffe6"
    elif val_a != val_b:
        is_different = True
        state_str = "差分あり"
        bg_color_hex = "#fff5c8"

    if diff_only and not is_different:
        return None, False

    str_a = str(val_a) if has_a else "(なし)"
    str_b = str(val_b) if has_b else "(なし)"

    node = DiffNode(
        key=str(key),
        val_a_str=str_a,
        val_b_str=str_b,
        state_str=state_str,
        is_different=is_different,
        bg_color_hex=bg_color_hex,
        children=[]
    )
    return node, is_different


def build_diff_tree(yaml_a: dict, yaml_b: dict, diff_only: bool = False) -> list[DiffNode]:
    """2つの YAML 辞書を比較し、DiffNode の階層ツリーリストを返す"""
    all_keys = sorted(list(set(yaml_a.keys()) | set(yaml_b.keys())))
    root_nodes: list[DiffNode] = []

    for key in all_keys:
        val_a = yaml_a.get(key)
        val_b = yaml_b.get(key)
        node, _ = _compare_node(str(key), val_a, val_b, diff_only)
        if node is not None:
            root_nodes.append(node)

    return root_nodes
