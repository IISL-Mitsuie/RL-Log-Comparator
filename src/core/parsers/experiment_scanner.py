"""
実験ログフォルダ走査・設定パースモジュール（Qt非依存）
"""

import os
import glob
import re
from dataclasses import dataclass, field
from typing import Any, Optional
import yaml

from src.core.parsers.image_pair import extract_prefix


# 重要度の高いキー（カラム一覧で優先表示）
PRIORITY_CONFIG_KEYS = [
    "mode", "algorithm", "seed", "learning_rate", "lr", "gamma",
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

    # 1. タイムスタンプの抽出
    match = re.search(r'(\d{8}_\d{6})', folder_name)
    timestamp_key = match.group(1) if match else folder_name
    display_timestamp = format_timestamp(timestamp_key)

    # 2. YAML ファイルの走査とパース
    yaml_files = glob.glob(os.path.join(abs_path, "config_used_*.yaml"))
    if not yaml_files:
        yaml_files = glob.glob(os.path.join(abs_path, "*.yaml"))

    config_data: dict[str, Any] = {}
    if yaml_files:
        try:
            with open(yaml_files[0], 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    config_data = loaded
        except Exception:
            config_data = {}

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

    config_flat = flatten_dict(config_data)

    # 3. 画像ファイルの検出
    images: dict[str, str] = {}
    for img_path in glob.glob(os.path.join(abs_path, "*.png")):
        base = os.path.basename(img_path).lower()
        if "learning_rewards" in base:
            images["rewards"] = img_path
        elif "learning_steps" in base:
            images["steps"] = img_path
        elif "trajectory" in base:
            images["trajectory"] = img_path
        else:
            prefix = extract_prefix(img_path)
            images[prefix] = img_path

    # 4. CSV ファイルの検出
    csv_files = glob.glob(os.path.join(abs_path, "learning_log_*.csv"))
    if not csv_files:
        csv_files = glob.glob(os.path.join(abs_path, "*.csv"))
    csv_path = csv_files[0] if csv_files else None

    # 実験フォルダ判定条件:
    # フォルダ名にタイムスタンプがある、またはYAML/CSV/画像が存在する
    if not match and not yaml_files and not csv_files and not images:
        return None

    return ExperimentLogRecord(
        folder_path=abs_path,
        folder_name=folder_name,
        timestamp_key=timestamp_key,
        display_timestamp=display_timestamp,
        mode=mode,
        use_shield=use_shield,
        display_shield=display_shield,
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
            # 実験出力フォルダ（output_* やタイムスタンプ付きフォルダ）を検出
            # 自身が実験フォルダと判定された場合は、その配下の dirs を走査対象から除外
            dirs_to_remove = []
            for d in dirs:
                full_path = os.path.join(root, d)
                # output_ で始まるかタイムスタンプを持つフォルダを候補とする
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

    # フォルダごとにレコード生成
    records: list[ExperimentLogRecord] = []
    seen_paths: set[str] = set()
    all_keys_set: set[str] = set()

    EXCLUDED_CONFIG_KEYS = {
        "mode", "algorithm",
        "mode.name", "mode.use_shield", "mode.algorithm", "mode.shield",
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
