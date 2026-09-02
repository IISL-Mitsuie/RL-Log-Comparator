"""
実験情報・メタデータ抽出モジュール
"""

import os
import glob
import re
import yaml


def get_experiment_info(folder_path: str) -> str:
    """
    フォルダパスから学習モード（RL, S-SAP, Q-SAP等）とタイムスタンプを抽出して整形文字列を返す。
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
    yaml_files = glob.glob(os.path.join(abs_path, "config_used_*.yaml"))
    if yaml_files:
        try:
            with open(yaml_files[0], 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                if 'mode' in data:
                    mode = str(data['mode'])
                elif 'algorithm' in data:
                    mode = str(data['algorithm'])
        except Exception:
            pass

    return f"[{mode}] {timestamp}"
