r"""
堅牢なYAMLファイル読み込みモジュール（Qt非依存）
Windows環境のパス表記などでダブルクォート内にエスケープされないバックスラッシュ（\S, \a 等）が
含まれる場合でも、安全にサニタイズして構文エラーを回避する。
"""

import os
import glob
import re
import json
from typing import Any, Optional
import yaml


def find_config_file(folder_path: str) -> Optional[str]:
    """
    指定フォルダ配下から設定ファイル (YAML / JSON) を探索して最優先のファイルパスを返す。
    優先順: config_used_*.yaml -> *.yaml -> *.yml -> config*.json -> params*.json -> *.json
    見つからない場合は None を返す。
    """
    if not folder_path or not os.path.isdir(folder_path):
        return None

    patterns = [
        "config_used_*.yaml",
        "*.yaml",
        "*.yml",
        "config*.json",
        "params*.json",
        "*.json"
    ]
    for pattern in patterns:
        matched = sorted(glob.glob(os.path.join(folder_path, pattern)), reverse=True)
        if matched:
            return matched[0]
    return None


def sanitize_yaml_text(content: str) -> str:
    """
    ダブルクォートで囲まれた文字列内のWindowsバックスラッシュをスラッシュに置換し、
    YAML不正エスケープ文字エラー（ScannerError）を回避する。
    """
    def _replace_quoted(match: re.Match) -> str:
        inner = match.group(1)
        # バックスラッシュをスラッシュに置換
        return f'"{inner.replace("\\", "/")}"'

    # ダブルクォートで囲まれた文字列（改行を含まない）を対象にサニタイズ
    return re.sub(r'"([^"\r\n]*)"', _replace_quoted, content)


def safe_load_yaml(file_path: str) -> dict[str, Any]:
    """
    YAML または JSON ファイルを安全に読み込み、辞書として返す。
    読み込み失敗時や非辞書の場合は空辞書を返す。
    """
    if not file_path or not os.path.exists(file_path):
        return {}

    # 0. JSON ファイルの場合は標準の json.load を試行
    if file_path.lower().endswith(".json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
        except Exception:
            pass

    # 1. 通常の yaml.safe_load を試みる (YAMLはJSONの上位互換)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (yaml.YAMLError, UnicodeDecodeError):
        pass
    except Exception as e:
        print(f"[WARN] Unexpected error reading YAML ({file_path}): {e}")

    # 2. 構文エラー等が発生した場合、サニタイズしてリトライ
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw_content = f.read()

        sanitized_content = sanitize_yaml_text(raw_content)
        data = yaml.safe_load(sanitized_content)
        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"[ERROR] Failed to safe_load_yaml after sanitization ({file_path}): {e}")

    return {}
