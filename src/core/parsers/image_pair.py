"""
実験画像ファイル走査およびペアリング解析モジュール（Qt非依存）
"""

import os
import glob
from dataclasses import dataclass
from typing import Optional


@dataclass
class ImagePairItem:
    """左右比較対象の画像ペア情報を表すデータ構造"""
    prefix: str
    file_a: Optional[str]
    file_b: Optional[str]
    display_text: str


import re

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


def detect_image_pairs(folder_a: str, folder_b: str) -> list[ImagePairItem]:
    """
    フォルダAおよびフォルダB内の PNG 画像を走査し、
    画像種別プレフィックスごとにペアリングしたリストを返す。
    """
    imgs_a = glob.glob(os.path.join(folder_a, "*.png")) if folder_a and os.path.isdir(folder_a) else []
    imgs_b = glob.glob(os.path.join(folder_b, "*.png")) if folder_b and os.path.isdir(folder_b) else []

    prefixes_a = {extract_prefix(p): p for p in imgs_a}
    prefixes_b = {extract_prefix(p): p for p in imgs_b}

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
