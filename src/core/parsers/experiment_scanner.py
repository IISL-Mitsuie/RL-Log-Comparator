"""
実験ログフォルダ走査・設定パースモジュール（Qt非依存）
"""

import os
import glob
import re
from dataclasses import dataclass, field
from typing import Any, Optional
import yaml

from src.core.parsers.image_pair import extract_prefix, select_latest_image, get_folder_images_dict
from src.core.parsers.safe_yaml import safe_load_yaml, find_config_file
from src.core.parsers.csv_metric import find_log_csv

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


def _parse_bool(val: Any) -> Optional[bool]:
    """様々な型（bool, str, int）の真偽値設定を安全に判定する"""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        s = val.strip().lower()
        if s in ("true", "1", "yes", "on"):
            return True
        elif s in ("false", "0", "no", "off"):
            return False
    return None


def _inspect_csv_for_continual(csv_path: Optional[str]) -> Optional[bool]:
    """CSVのヘッダー行を読み取り、継続学習（Total_EpisodeやTask_ID）か単一学習（Episodeのみ等）かを判定する"""
    if not csv_path or not os.path.isfile(csv_path):
        return None
    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            header_line = f.readline()
        if not header_line:
            return None
        headers = [h.strip().lower() for h in header_line.split(",")]
        if "total_episode" in headers or "task_id" in headers or "task_episode" in headers:
            return True
        if "episode" in headers:
            return False
    except Exception:
        pass
    return None


def _count_tasks_from_csv(csv_path: Optional[str]) -> int:
    """CSVからタスク数（Task_ID の一意な値の個数）を軽量にカウントする"""
    if not csv_path or not os.path.isfile(csv_path):
        return 0
    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            header_line = f.readline()
            if not header_line:
                return 0
            headers = [h.strip().lower() for h in header_line.split(",")]
            task_col_idx = -1
            for idx, h in enumerate(headers):
                if h == "task_id":
                    task_col_idx = idx
                    break
            if task_col_idx == -1:
                return 0
            tasks = set()
            for line in f:
                parts = line.split(",")
                if len(parts) > task_col_idx:
                    val = parts[task_col_idx].strip()
                    if val:
                        tasks.add(val)
            return len(tasks)
    except Exception:
        return 0


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

    # 2. CSV ファイルの先行検出（全タスク統合ログを最優先）
    csv_path: Optional[str] = find_log_csv(abs_path)

    # 3. 設定ファイル (YAML / JSON) の走査とパース
    config_file = find_config_file(abs_path)
    config_data: dict[str, Any] = safe_load_yaml(config_file) if config_file else {}

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
            use_shield = _parse_bool(raw_mode['use_shield'])
        elif 'shield' in raw_mode:
            use_shield = _parse_bool(raw_mode['shield'])
    elif isinstance(raw_mode, str):
        mode = raw_mode
    elif raw_mode is not None:
        mode = str(raw_mode)
    elif 'algorithm' in config_data:
        mode = str(config_data['algorithm'])

    # トップレベルに use_shield / shield がある場合のフォールバック
    if use_shield is None:
        if 'use_shield' in config_data:
            use_shield = _parse_bool(config_data['use_shield'])
        elif 'shield' in config_data:
            use_shield = _parse_bool(config_data['shield'])

    display_shield = "有効" if use_shield is True else ("無効" if use_shield is False else "-")

    # 4. 継続学習の判定 & 表示文字列
    # 優先順位:
    # 1. mode.continual_learning (True/False 明示設定を最優先)
    # 2. トップレベル continual_learning (bool値)
    # 3. continual_learning.enabled (bool値)
    # 4. フォールバック: CSVヘッダー構造 -> single_taskセクションの有無
    cl_flag: Optional[bool] = None

    if isinstance(raw_mode, dict) and 'continual_learning' in raw_mode:
        cl_flag = _parse_bool(raw_mode['continual_learning'])

    if cl_flag is None and 'continual_learning' in config_data:
        val = config_data['continual_learning']
        if not isinstance(val, dict):
            cl_flag = _parse_bool(val)

    cl_section = config_data.get('continual_learning')
    if cl_flag is None and isinstance(cl_section, dict) and 'enabled' in cl_section:
        cl_flag = _parse_bool(cl_section['enabled'])

    # 明示的なフラグがない場合のフォールバック
    if cl_flag is None:
        csv_is_cl = _inspect_csv_for_continual(csv_path)
        if csv_is_cl is not None:
            cl_flag = csv_is_cl
        elif isinstance(cl_section, dict) and 'goal_list' in cl_section:
            # single_task セクションがなく continual_learning セクションのみが存在する場合
            if 'single_task' not in config_data:
                cl_flag = True
            else:
                cl_flag = False

    is_continual = bool(cl_flag) if cl_flag is not None else False

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
            n_tasks = _count_tasks_from_csv(csv_path) if csv_path else 0
            if n_tasks > 0:
                display_cl = f"継続 ({n_tasks}タスク)"
            else:
                display_cl = "継続"
    else:
        single_section = config_data.get('single_task')
        max_ep = single_section.get('max_episodes') if isinstance(single_section, dict) else None
        if max_ep:
            display_cl = f"単一 ({max_ep}ep)"
        elif single_section is not None:
            display_cl = "単一"
        elif 'max_episodes' in config_data:
            display_cl = f"単一 ({config_data['max_episodes']}ep)"
        elif raw_mode is not None or config_file is not None or csv_path is not None:
            display_cl = "単一"

    config_flat = flatten_dict(config_data)

    # 5. 画像ファイルの検出（プレフィックスごとに最新1枚を選定）
    images: dict[str, str] = get_folder_images_dict(abs_path)

    # 実験フォルダ判定条件:
    # フォルダ名にタイムスタンプがある、または設定/CSV/画像が存在する
    if not match and not config_file and not csv_path and not images:
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
                else:
                    # 任意フォルダ名対応: 直下に CSV または設定ファイルが存在する場合は実験フォルダと判定
                    try:
                        files = os.listdir(full_path)
                        has_csv = any(f.lower().endswith(".csv") for f in files)
                        has_cfg = any(f.lower().endswith((".yaml", ".yml", ".json")) for f in files)
                        if has_csv and has_cfg:
                            candidate_folders.append(full_path)
                            dirs_to_remove.append(d)
                        elif has_csv:
                            candidate_folders.append(full_path)
                            dirs_to_remove.append(d)
                    except OSError:
                        pass
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
