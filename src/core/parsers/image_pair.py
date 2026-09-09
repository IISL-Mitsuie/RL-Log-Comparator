"""
実験画像ファイル走査およびペアリング解析モジュール（Qt非依存）
"""

import os
import glob
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ImagePairItem:
    """左右比較対象の画像ペア情報を表すデータ構造"""
    prefix: str
    file_a: Optional[str]
    file_b: Optional[str]
    display_text: str


def extract_prefix(filepath: str) -> str:
    """
    ファイル名からエピソード番号やステップ数、タイムスタンプ等のサフィックスを除去し、画像種別プレフィックスを抽出する。
    例: 'learning_rewards_00100_00500.png' -> 'learning_rewards'
        'learning_rewards_20260909_145945.png' -> 'learning_rewards'
        'trajectory_100.png' -> 'trajectory'
    """
    filename = os.path.basename(filepath)
    name_no_ext = os.path.splitext(filename)[0]

    # 1. タイムスタンプサフィックス (_YYYYMMDD_HHMMSS or _YYYYMMDD-HHMMSS) の除去
    m_ts = re.sub(r'_\d{8}[_-]\d{6}$', '', name_no_ext)
    if m_ts != name_no_ext:
        return m_ts

    # 2. アンダースコア区切りの数値サフィックス (_00100_00500 等) の除去
    parts = name_no_ext.split('_')
    if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
        return "_".join(parts[:-2])
    elif len(parts) >= 2 and parts[-1].isdigit():
        return "_".join(parts[:-1])
    return name_no_ext


def select_latest_image(img_paths: list[str]) -> str:
    """
    同一プレフィックスの複数画像から最新の1枚を選定（方針A）。
    ファイル名の降順（エピソード番号・ステップ数・タイムスタンプの最大値）および更新日時をキーとする。
    """
    if len(img_paths) == 1:
        return img_paths[0]

    def sort_key(p: str):
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            mtime = 0.0
        return (os.path.basename(p), mtime)

    sorted_paths = sorted(img_paths, key=sort_key, reverse=True)
    return sorted_paths[0]


def detect_image_pairs(folder_a: str, folder_b: str) -> list[ImagePairItem]:
    """
    フォルダAおよびフォルダB内の PNG 画像を走査し、
    画像種別プレフィックスごとにペアリングしたリストを返す。
    同一プレフィックスの画像が複数存在する場合は最新の1枚を選定する。
    """
    imgs_a = glob.glob(os.path.join(folder_a, "*.png")) if folder_a and os.path.isdir(folder_a) else []
    imgs_b = glob.glob(os.path.join(folder_b, "*.png")) if folder_b and os.path.isdir(folder_b) else []

    def group_by_prefix(paths: list[str]) -> dict[str, str]:
        prefix_to_paths: dict[str, list[str]] = {}
        for p in paths:
            prefix = extract_prefix(p)
            prefix_to_paths.setdefault(prefix, []).append(p)
        return {prefix: select_latest_image(group) for prefix, group in prefix_to_paths.items()}

    prefixes_a = group_by_prefix(imgs_a)
    prefixes_b = group_by_prefix(imgs_b)

    all_prefixes = sorted(list(set(prefixes_a.keys()) | set(prefixes_b.keys())))
    pairs: list[ImagePairItem] = []

    for prefix in all_prefixes:
        has_in_a = prefix in prefixes_a
        has_in_b = prefix in prefixes_b
        tag = ""
        if has_in_a and has_in_b:
            tag = " (両方)"
        elif has_in_a:
            tag = " (Aのみ)"
        else:
            tag = " (Bのみ)"

        pair = ImagePairItem(
            prefix=prefix,
            file_a=prefixes_a.get(prefix),
            file_b=prefixes_b.get(prefix),
            display_text=f"{prefix}{tag}"
        )
        pairs.append(pair)

    return pairs
