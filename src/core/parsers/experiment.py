"""
実験情報・メタデータ抽出モジュール
"""

import os
import re
from typing import Optional

from src.core.parsers.yaml_diff import read_yaml_file


def get_experiment_info(folder_path: Optional[str]) -> str:
    """
    フォルダパスから学習モード（RL, S-SAP, Q-SAP, PPO等）とタイムスタンプを抽出して整形文字列を返す。
    例: '[S-SAP] 20260801_235449'
    """
    if not folder_path or not os.path.exists(folder_path):
        return "未選択 / 存在しないフォルダ"

    abs_path = os.path.abspath(folder_path)
    folder_name = os.path.basename(abs_path)
    parent_name = os.path.basename(os.path.dirname(abs_path))

    timestamp = folder_name
    match = re.search(r'(\d{8}_\d{6})', folder_name)
    if match:
        timestamp = match.group(1)

    mode = parent_name
    data = read_yaml_file(abs_path)
    if data:
        if 'mode' in data:
            raw_mode = data['mode']
            if isinstance(raw_mode, dict):
                mode = str(raw_mode.get('name', raw_mode.get('algorithm', parent_name)))
            elif isinstance(raw_mode, str):
                mode = raw_mode
            elif raw_mode is not None:
                mode = str(raw_mode)
        elif 'algorithm' in data:
            mode = str(data['algorithm'])

    return f"[{mode}] {timestamp}"
