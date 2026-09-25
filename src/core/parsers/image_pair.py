"""
実験画像ファイル走査およびペアリング解析モジュール（Qt非依存）
単一学習ログおよび継続学習ログ（タスク別報酬・ステップ、統合学習曲線、軌跡）に網羅的に対応
"""

import os
import glob
import re
from dataclasses import dataclass
from typing import Optional

from src.config import SUPPORTED_IMAGE_EXTENSIONS


@dataclass
class ImagePairItem:
    """左右比較対象の画像ペア情報を表すデータ構造"""
    prefix: str
    file_a: Optional[str]
    file_b: Optional[str]
    display_text: str


def extract_prefix(filepath: str) -> str:
    """
    ファイル名からタイムスタンプやエピソード番号等を除去し、論理的な画像種別プレフィックスを抽出する。
    例:
        'continual_learning_curve_20260924_181649.png' -> 'continual_learning_curve'
        'trajectory_20260924_181649.png' -> 'trajectory'
        'learning_rewards_20260924_181649_task_1.png' -> 'learning_rewards_task_1'
        'learning_rewards_20260924_181649_task_6_unregistered.png' -> 'learning_rewards_task_6_unregistered'
        'learning_steps_20260924_181649_task_2.png' -> 'learning_steps_task_2'
        'learning_rewards_20260909_145945.png' -> 'learning_rewards'
        'learning_steps_00100_00500.png' -> 'learning_steps'
        'trajectory_100.png' -> 'trajectory'
    """
    filename = os.path.basename(filepath)
    name_no_ext = os.path.splitext(filename)[0]

    # 1. タイムスタンプ (_YYYYMMDD_HHMMSS or _YYYYMMDD-HHMMSS) を位置を問わず除去
    cleaned = re.sub(r'_\d{8}[_-]\d{6}', '', name_no_ext)

    # 2. taskサフィックス (_task_1, _task_6_unregistered 等) を保護しながら数値サフィックスを除去
    # 例: learning_steps_00100_00500 -> learning_steps
    # 例: trajectory_100 -> trajectory
    parts = cleaned.split('_')
    if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
        cleaned = "_".join(parts[:-2])
    elif len(parts) >= 2 and parts[-1].isdigit():
        # 直前が "task" でない場合のみ末尾数値をトリム
        if not (len(parts) >= 3 and parts[-2] == "task"):
            cleaned = "_".join(parts[:-1])

    return cleaned


def get_image_display_title(prefix: str) -> str:
    """
    プレフィックスを人間向けの分かりやすい日本語表示名に変換する。
    """
    if prefix == "continual_learning_curve":
        return "統合学習曲線 (全タスク)"
    if prefix == "trajectory":
        return "ロボット走行軌跡"
    if prefix == "learning_rewards":
        return "報酬推移 (全体)"
    if prefix == "learning_steps":
        return "ステップ推移 (全体)"

    m_rew_unreg = re.match(r'^learning_rewards_task_(\d+)_unregistered$', prefix)
    if m_rew_unreg:
        return f"報酬推移 (Task {m_rew_unreg.group(1)} [非登録])"

    m_rew = re.match(r'^learning_rewards_task_(\d+)$', prefix)
    if m_rew:
        return f"報酬推移 (Task {m_rew.group(1)})"

    m_stp_unreg = re.match(r'^learning_steps_task_(\d+)_unregistered$', prefix)
    if m_stp_unreg:
        return f"ステップ推移 (Task {m_stp_unreg.group(1)} [非登録])"

    m_stp = re.match(r'^learning_steps_task_(\d+)$', prefix)
    if m_stp:
        return f"ステップ推移 (Task {m_stp.group(1)})"

    return prefix


def _get_prefix_sort_key(prefix: str) -> tuple[int, int, str]:
    """プレフィックスの自然な並び順キー（カテゴリ順、タスク番号順）"""
    # カテゴリ優先度:
    # 0: continual_learning_curve
    # 1: trajectory
    # 2: learning_rewards
    # 3: learning_rewards_task_*
    # 4: learning_steps
    # 5: learning_steps_task_*
    # 9: その他
    if prefix == "continual_learning_curve":
        return (0, 0, "")
    if prefix == "trajectory":
        return (1, 0, "")
    if prefix == "learning_rewards":
        return (2, 0, "")
    if prefix == "learning_steps":
        return (4, 0, "")

    m_task = re.search(r'_task_(\d+)', prefix)
    task_num = int(m_task.group(1)) if m_task else 999

    if prefix.startswith("learning_rewards"):
        return (3, task_num, prefix)
    if prefix.startswith("learning_steps"):
        return (5, task_num, prefix)

    return (9, 0, prefix)


def select_latest_image(img_paths: list[str]) -> str:
    """
    同一プレフィックスの複数画像から最新の1枚を選定。
    ファイル名の降順および更新日時をキーとする。
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


def get_folder_image_list(folder_path: str) -> list[tuple[str, str, str]]:
    """
    指定フォルダ配下の画像を走査（PNG, JPG, BMP, WebP等）し、
    [(プレフィックス, 表示名, 最新ファイルパス), ...] のリストをソート順で返す。
    """
    if not folder_path or not os.path.isdir(folder_path):
        return []

    imgs = []
    try:
        for entry in os.listdir(folder_path):
            full_path = os.path.join(folder_path, entry)
            if os.path.isfile(full_path):
                ext = os.path.splitext(entry)[1].lower()
                if ext in SUPPORTED_IMAGE_EXTENSIONS:
                    imgs.append(full_path)
    except OSError:
        pass

    prefix_to_paths: dict[str, list[str]] = {}
    for p in imgs:
        prefix = extract_prefix(p)
        prefix_to_paths.setdefault(prefix, []).append(p)

    results = []
    for prefix, paths in prefix_to_paths.items():
        latest_file = select_latest_image(paths)
        display_title = get_image_display_title(prefix)
        results.append((prefix, display_title, latest_file))

    results.sort(key=lambda item: _get_prefix_sort_key(item[0]))
    return results


def get_folder_images_dict(folder_path: str) -> dict[str, str]:
    """
    指定フォルダ配下の画像を走査し、プレフィックスをキー、最新画像パスを値とする辞書を返す。
    例: {"learning_rewards": "/path/to/learning_rewards_20260901_100000.png", ...}
    """
    image_list = get_folder_image_list(folder_path)
    return {prefix: file_path for prefix, _, file_path in image_list}


def detect_image_pairs(folder_a: str, folder_b: str) -> list[ImagePairItem]:
    """
    フォルダAおよびフォルダB内の PNG 画像を走査し、
    画像種別ごとにペアリングしたリストを返す。
    単一学習の learning_rewards と継続学習の continual_learning_curve のエイリアス対応（案A）も考慮。
    """
    list_a = get_folder_image_list(folder_a)
    list_b = get_folder_image_list(folder_b)

    dict_a = {prefix: path for prefix, _, path in list_a}
    dict_b = {prefix: path for prefix, _, path in list_b}

    used_prefixes_a = set()
    used_prefixes_b = set()
    pairs: list[ImagePairItem] = []

    # 1. 完全一致プレフィックスのペアリング
    common_prefixes = set(dict_a.keys()) & set(dict_b.keys())
    for prefix in sorted(list(common_prefixes), key=_get_prefix_sort_key):
        display_name = get_image_display_title(prefix)
        pairs.append(ImagePairItem(
            prefix=prefix,
            file_a=dict_a[prefix],
            file_b=dict_b[prefix],
            display_text=f"{display_name} (両方)"
        ))
        used_prefixes_a.add(prefix)
        used_prefixes_b.add(prefix)

    # 2. エイリアスペアリング（案A: 単一学習の rewards ⇔ 継続学習の continual_learning_curve）
    # Aが単一学習(learning_rewards)でBが継続(continual_learning_curve)の場合、またはその逆
    if "learning_rewards" in dict_a and "learning_rewards" not in dict_b and "continual_learning_curve" in dict_b and "continual_learning_curve" not in dict_a:
        if "learning_rewards" not in used_prefixes_a and "continual_learning_curve" not in used_prefixes_b:
            pairs.append(ImagePairItem(
                prefix="learning_rewards_vs_cl_curve",
                file_a=dict_a["learning_rewards"],
                file_b=dict_b["continual_learning_curve"],
                display_text="学習推移対比 (報酬推移 ⇔ 統合学習曲線)"
            ))
            used_prefixes_a.add("learning_rewards")
            used_prefixes_b.add("continual_learning_curve")
    elif "continual_learning_curve" in dict_a and "continual_learning_curve" not in dict_b and "learning_rewards" in dict_b and "learning_rewards" not in dict_a:
        if "continual_learning_curve" not in used_prefixes_a and "learning_rewards" not in used_prefixes_b:
            pairs.append(ImagePairItem(
                prefix="cl_curve_vs_learning_rewards",
                file_a=dict_a["continual_learning_curve"],
                file_b=dict_b["learning_rewards"],
                display_text="学習推移対比 (統合学習曲線 ⇔ 報酬推移)"
            ))
            used_prefixes_a.add("continual_learning_curve")
            used_prefixes_b.add("learning_rewards")

    # 3. Aのみに存在するプレフィックス
    for prefix, _, path in list_a:
        if prefix not in used_prefixes_a:
            display_name = get_image_display_title(prefix)
            pairs.append(ImagePairItem(
                prefix=prefix,
                file_a=path,
                file_b=None,
                display_text=f"{display_name} (Aのみ)"
            ))

    # 4. Bのみに存在するプレフィックス
    for prefix, _, path in list_b:
        if prefix not in used_prefixes_b:
            display_name = get_image_display_title(prefix)
            pairs.append(ImagePairItem(
                prefix=prefix,
                file_a=None,
                file_b=path,
                display_text=f"{display_name} (Bのみ)"
            ))

    # 全体ソート
    pairs.sort(key=lambda p: _get_prefix_sort_key(p.prefix))
    return pairs
