"""
YAML 設定ファイル読み込みおよび階層差分解析モジュール（Qt非依存）
"""

import datetime
import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from src.core.parsers.safe_yaml import safe_load_yaml, find_config_file


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


def read_yaml_file(folder_path: str) -> dict[str, Any]:
    """フォルダ内の config_used_*.yaml (または *.yaml, *.yml, *.json) を安全に読み込んで辞書を返す"""
    if not folder_path or not os.path.isdir(folder_path):
        return {}

    config_file = find_config_file(folder_path)
    if not config_file:
        return {}
    return safe_load_yaml(config_file)


# キーが存在しないことを表す番兵（YAML の null = None と区別するため）
_MISSING = object()

# この長さ以下のスカラーのみのリストは 1 ノードとして比較する
_INLINE_LIST_MAX_LEN = 10


def _sort_key(key: Any) -> tuple[str, str]:
    """型が混在するキー（文字列と数値など）でも並べ替えられるキー"""
    return (type(key).__name__, str(key))


def _sorted_keys(keys: set) -> list:
    """キーを並べ替える。型が混在して比較できない場合は、型名と文字列表現で並べる"""
    try:
        return sorted(keys)
    except TypeError:
        return sorted(keys, key=_sort_key)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str, datetime.date))


def _is_inline_list(value: Any) -> bool:
    """要素がすべてスカラーかつ短いリストか（1 ノードとして表示するか）"""
    return (
        isinstance(value, list)
        and len(value) <= _INLINE_LIST_MAX_LEN
        and all(_is_scalar(v) for v in value)
    )


def _values_equal(a: Any, b: Any) -> bool:
    """値の等価判定。bool と数値は型が違うものとして扱い、NaN 同士は一致とみなす"""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def _format_value(value: Any) -> str:
    """表示用の文字列に変換する"""
    if value is _MISSING:
        return "(なし)"
    if value is None:
        return "null"
    if isinstance(value, (list, dict)):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            # 辞書のキーに日付などがあると json.dumps できない
            return str(value)
    return str(value)


def _make_branch_node(
    key: str, has_a: bool, has_b: bool, children: list[tuple[str, Any, Any]], diff_only: bool
) -> tuple[Optional[DiffNode], bool]:
    """子要素 (キー, Aの値, Bの値) を再帰的に比較し、辞書・リストの親ノードを作る"""
    child_nodes = []
    # 片側にしか存在しなければ、子要素が空でも差分とする
    has_diff = not (has_a and has_b)

    for ckey, c_a, c_b in children:
        child_node, child_has_diff = _compare_node(ckey, c_a, c_b, diff_only)
        if child_node is not None:
            child_nodes.append(child_node)
        if child_has_diff:
            has_diff = True

    if diff_only and not has_diff:
        return None, False

    # 片側にしか存在しない場合は、親ノードの状態にもそれを表示する
    state_str = "階層"
    bg_color_hex = None
    if not has_a:
        state_str = "Bのみ存在"
        bg_color_hex = "#ffe6e6"
    elif not has_b:
        state_str = "Aのみ存在"
        bg_color_hex = "#e6ffe6"

    node = DiffNode(
        key=key,
        val_a_str="" if has_a else _format_value(_MISSING),
        val_b_str="" if has_b else _format_value(_MISSING),
        state_str=state_str,
        is_different=has_diff,
        bg_color_hex=bg_color_hex,
        children=child_nodes
    )
    return node, has_diff


def _compare_node(key: str, val_a: Any, val_b: Any, diff_only: bool) -> tuple[Optional[DiffNode], bool]:
    """再帰的にノードを比較して DiffNode と差分の有無を返す（存在しない側は _MISSING）"""
    has_a = val_a is not _MISSING
    has_b = val_b is not _MISSING

    # 存在する側がすべて辞書なら、キーごとに展開する
    if (
        any(isinstance(v, dict) for v in (val_a, val_b))
        and all(isinstance(v, dict) or v is _MISSING for v in (val_a, val_b))
    ):
        dict_a = val_a if has_a else {}
        dict_b = val_b if has_b else {}
        sub_keys = _sorted_keys(set(dict_a.keys()) | set(dict_b.keys()))
        children = [
            (str(skey), dict_a.get(skey, _MISSING), dict_b.get(skey, _MISSING))
            for skey in sub_keys
        ]
        return _make_branch_node(str(key), has_a, has_b, children, diff_only)

    # 存在する側がすべてリストで、短いスカラーのリストでないものを含むなら、要素ごとに展開する
    if (
        any(isinstance(v, list) and not _is_inline_list(v) for v in (val_a, val_b))
        and all(isinstance(v, list) or v is _MISSING for v in (val_a, val_b))
    ):
        list_a = val_a if has_a else []
        list_b = val_b if has_b else []
        children = [
            (
                f"[{i}]",
                list_a[i] if i < len(list_a) else _MISSING,
                list_b[i] if i < len(list_b) else _MISSING,
            )
            for i in range(max(len(list_a), len(list_b)))
        ]
        return _make_branch_node(str(key), has_a, has_b, children, diff_only)

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
    elif not _values_equal(val_a, val_b):
        is_different = True
        state_str = "差分あり"
        bg_color_hex = "#fff5c8"

    if diff_only and not is_different:
        return None, False

    node = DiffNode(
        key=str(key),
        val_a_str=_format_value(val_a),
        val_b_str=_format_value(val_b),
        state_str=state_str,
        is_different=is_different,
        bg_color_hex=bg_color_hex,
        children=[]
    )
    return node, is_different


def build_diff_tree(yaml_a: dict, yaml_b: dict, diff_only: bool = False) -> list[DiffNode]:
    """2つの YAML 辞書を比較し、DiffNode の階層ツリーリストを返す"""
    all_keys = _sorted_keys(set(yaml_a.keys()) | set(yaml_b.keys()))
    root_nodes: list[DiffNode] = []

    for key in all_keys:
        val_a = yaml_a.get(key, _MISSING)
        val_b = yaml_b.get(key, _MISSING)
        node, _ = _compare_node(str(key), val_a, val_b, diff_only)
        if node is not None:
            root_nodes.append(node)

    return root_nodes
