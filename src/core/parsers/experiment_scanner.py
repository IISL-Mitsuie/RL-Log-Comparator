"""
実験ログフォルダ走査・設定パースモジュール（Qt非依存）
"""

import os
import glob
import re
from dataclasses import dataclass, field
from typing import Any, Optional
import yaml

from src.core.parsers.image_pair import extract_prefix, select_latest_image
from src.core.parsers.safe_yaml import safe_load_yaml

# 後方互換・エイリアス
_select_latest_image = select_latest_image


# 重要度の高いキー（カラム一覧で優先表示）
PRIORITY_CONFIG_KEYS = [
    "mode", "algorithm",
    "continual_learning.max_episodes_per_task",
    "continual_learning.goal_list",
    "continual_learning.unregistered_goal_list",
    "continual_learning.convergence.window_size",
    "single_task.max_episodes",
    "single_task.goal_position",
    "seed", "learning_rate", "lr", "gamma",
    "batch_size", "max_episodes", "episodes", "hidden_dim"
]


@dataclass
class ExperimentLogRecord:
    """走査された単一の実験ログ情報を表すデータ構造"""
    folder_path: str
    folder_name: str
    timestamp_key: str
    display_timestamp: str
    mode: str
    use_shield: Optional[bool] = None
    display_shield: str = "-"
    is_continual: bool = False
    display_cl: str = "-"
    config_flat: dict[str, Any] = field(default_factory=dict)
    images: dict[str, str] = field(default_factory=dict)
    csv_path: Optional[str] = None



def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict[str, Any]:
    """
    ネストされた辞書をドット記法でフラット化する。
    例: {"reward": {"goal": 100}} -> {"reward.goal": 100}
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def format_timestamp(timestamp_str: str) -> str:
    """
    'YYYYMMDD_HHMMSS' 形式の文字列を 'YYYY/MM/DD HH:MM:SS' に整形する。
    マッチしない場合は元の文字列を返す。
    """
    m = re.search(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', timestamp_str)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}"
    return timestamp_str


def parse_single_experiment(folder_path: str) -> Optional[ExperimentLogRecord]:
    """
    単一の実験出力フォルダを解析し、ExperimentLogRecord を生成する。
    実験ログと判定できない場合は None を返す。
    """
    if not os.path.isdir(folder_path):
        return None

    abs_path = os.path.abspath(folder_path)
    folder_name = os.path.basename(abs_path)
    parent_name = os.path.basename(os.path.dirname(abs_path))

    # 1. タイムスタンプの抽出 (マッチしない場合はフォルダ最終更新日時をフォールバック)
    match = re.search(r'(\d{8}_\d{6})', folder_name)
    if match:
        timestamp_key = match.group(1)
        display_timestamp = format_timestamp(timestamp_key)
    else:
        timestamp_key = folder_name
        try:
            from datetime import datetime
            mtime = os.path.getmtime(abs_path)
            display_timestamp = datetime.fromtimestamp(mtime).strftime("%Y/%m/%d %H:%M:%S")
        except Exception:
            display_timestamp = folder_name

    # 2. 設定ファイル (YAML / JSON) の走査とパース
    yaml_files = sorted(glob.glob(os.path.join(abs_path, "config_used_*.yaml")), reverse=True)
    if not yaml_files:
        yaml_files = sorted(glob.glob(os.path.join(abs_path, "*.yaml")), reverse=True)
    if not yaml_files:
        yaml_files = sorted(glob.glob(os.path.join(abs_path, "*.yml")), reverse=True)
    if not yaml_files:
        yaml_files = sorted(glob.glob(os.path.join(abs_path, "config*.json")), reverse=True)
    if not yaml_files:
        yaml_files = sorted(glob.glob(os.path.join(abs_path, "params*.json")), reverse=True)
    if not yaml_files:
        yaml_files = sorted(glob.glob(os.path.join(abs_path, "*.json")), reverse=True)

    config_data: dict[str, Any] = {}
    if yaml_files:
        config_data = safe_load_yaml(yaml_files[0])

    # モードおよび Shield の特定
    mode = parent_name
    use_shield: Optional[bool] = None

    raw_mode = config_data.get('mode')
    if isinstance(raw_mode, dict):
        if 'name' in raw_mode:
            mode = str(raw_mode['name'])
        elif 'algorithm' in raw_mode:
            mode = str(raw_mode['algorithm'])
        if 'use_shield' in raw_mode:
            use_shield = bool(raw_mode['use_shield'])
        elif 'shield' in raw_mode:
            use_shield = bool(raw_mode['shield'])
    elif isinstance(raw_mode, str):
        mode = raw_mode
    elif raw_mode is not None:
        mode = str(raw_mode)
    elif 'algorithm' in config_data:
        mode = str(config_data['algorithm'])

    # トップレベルに use_shield / shield がある場合のフォールバック
    if use_shield is None:
        if 'use_shield' in config_data:
            use_shield = bool(config_data['use_shield'])
        elif 'shield' in config_data:
            use_shield = bool(config_data['shield'])

    display_shield = "有効" if use_shield is True else ("無効" if use_shield is False else "-")

    # 継続学習の判定 & 表示文字列
    is_continual = False
    cl_section = config_data.get('continual_learning')
    if isinstance(raw_mode, dict) and raw_mode.get('continual_learning') is True:
        is_continual = True
    elif isinstance(cl_section, dict):
        if cl_section.get('enabled') is True or 'goal_list' in cl_section:
            is_continual = True

    display_cl = "-"
    if is_continual:
        goal_list = cl_section.get('goal_list', []) if isinstance(cl_section, dict) else []
        unreg_list = cl_section.get('unregistered_goal_list', []) if isinstance(cl_section, dict) else []
        n_reg = len(goal_list) if isinstance(goal_list, list) else 0
        n_unreg = len(unreg_list) if isinstance(unreg_list, list) else 0
        if n_unreg > 0:
            display_cl = f"継続 ({n_reg}+{n_unreg}タスク)"
        elif n_reg > 0:
            display_cl = f"継続 ({n_reg}タスク)"
        else:
            display_cl = "継続"
    else:
        single_section = config_data.get('single_task')
        max_ep = single_section.get('max_episodes') if isinstance(single_section, dict) else None
        if max_ep:
            display_cl = f"単一 ({max_ep}ep)"
        elif single_section is not None:
            display_cl = "単一"
        elif isinstance(raw_mode, dict) and raw_mode.get('continual_learning') is False:
            display_cl = "単一"
        elif 'max_episodes' in config_data:
            display_cl = f"単一 ({config_data['max_episodes']}ep)"

    config_flat = flatten_dict(config_data)

    # 3. 画像ファイルの検出（多形式対応、プレフィックスごとにグループ化し、最新1枚を選定）
    from src.core.parsers.image_pair import SUPPORTED_IMAGE_EXTENSIONS
    prefix_to_paths: dict[str, list[str]] = {}
    try:
        for entry in os.listdir(abs_path):
            p = os.path.join(abs_path, entry)
            if os.path.isfile(p):
                ext = os.path.splitext(entry)[1].lower()
                if ext in SUPPORTED_IMAGE_EXTENSIONS:
                    prefix = extract_prefix(p)
                    prefix_to_paths.setdefault(prefix, []).append(p)
    except OSError:
        pass

    images: dict[str, str] = {}
    for prefix, paths in prefix_to_paths.items():
        images[prefix] = _select_latest_image(paths)

    # 4. CSV ファイルの検出（全タスク統合ログを最優先）
    csv_candidates = sorted(glob.glob(os.path.join(abs_path, "learning_log_*.csv")))
    main_csvs = [p for p in csv_candidates if "_task_" not in os.path.basename(p)]
    if main_csvs:
        csv_path = main_csvs[0]
    elif csv_candidates:
        csv_path = csv_candidates[0]
    else:
        other_csvs = sorted(glob.glob(os.path.join(abs_path, "*.csv")))
        csv_path = other_csvs[0] if other_csvs else None

    # 実験フォルダ判定条件:
    # フォルダ名にタイムスタンプがある、またはYAML/CSV/画像が存在する
    if not match and not yaml_files and not csv_path and not images:
        return None

    return ExperimentLogRecord(
        folder_path=abs_path,
        folder_name=folder_name,
        timestamp_key=timestamp_key,
        display_timestamp=display_timestamp,
        mode=mode,
        use_shield=use_shield,
        display_shield=display_shield,
        is_continual=is_continual,
        display_cl=display_cl,
        config_flat=config_flat,
        images=images,
        csv_path=csv_path
    )



def scan_experiments_directory(
    root_dir: str,
    recursive: bool = True
) -> tuple[list[ExperimentLogRecord], list[str]]:
    """
    指定ディレクトリ配下の実験ログフォルダを走査し、
    (実験レコードのリスト, 全Configキーのソート済みリスト) を返す。
    レコードは timestamp_key の降順（新しい順）で並べられる。
    """
    if not root_dir or not os.path.isdir(root_dir):
        return [], []

    candidate_folders: list[str] = []

    if recursive:
        for root, dirs, _ in os.walk(root_dir):
            dirs_to_remove = []
            for d in dirs:
                full_path = os.path.join(root, d)
                if d.startswith("output_") or re.search(r'\d{8}_\d{6}', d):
                    candidate_folders.append(full_path)
                    dirs_to_remove.append(d)
            for d in dirs_to_remove:
                dirs.remove(d)
    else:
        for item in os.listdir(root_dir):
            full_path = os.path.join(root_dir, item)
            if os.path.isdir(full_path):
                candidate_folders.append(full_path)

    records: list[ExperimentLogRecord] = []
    seen_paths: set[str] = set()
    all_keys_set: set[str] = set()

    EXCLUDED_CONFIG_KEYS = {
        "mode", "algorithm",
        "mode.name", "mode.use_shield", "mode.algorithm", "mode.shield",
        "mode.continual_learning",
        "use_shield", "shield"
    }

    for folder in candidate_folders:
        norm = os.path.abspath(folder)
        if norm in seen_paths:
            continue
        seen_paths.add(norm)

        record = parse_single_experiment(norm)
        if record is not None:
            records.append(record)
            for k in record.config_flat.keys():
                if k not in EXCLUDED_CONFIG_KEYS:
                    all_keys_set.add(k)


    # タイムスタンプ降順（新しい順）にソート
    records.sort(key=lambda r: r.timestamp_key, reverse=True)

    # カラムのソート順決定:
    # 1. 優先キー（PRIORITY_CONFIG_KEYS に含まれるもの）
    # 2. その他のキー（アルファベット順）
    priority_keys = [k for k in PRIORITY_CONFIG_KEYS if k in all_keys_set]
    other_keys = sorted([k for k in all_keys_set if k not in PRIORITY_CONFIG_KEYS])
    sorted_keys = priority_keys + other_keys

    return records, sorted_keys
