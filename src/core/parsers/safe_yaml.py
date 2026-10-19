r"""
堅牢なYAMLファイル読み込みモジュール（Qt非依存）
Windows環境のパス表記などでダブルクォート内にエスケープされないバックスラッシュ（\S, \a 等）が
含まれる場合でも、安全にサニタイズして構文エラーを回避する。
"""

import os
import glob
import logging
import re
import json
from typing import Any, Optional
import yaml

logger = logging.getLogger(__name__)


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
    data, error = _load_config(file_path)
    if error is not None:
        # 同じファイルが何度も読まれるため、ここでは 1 行だけ記録する（詳細は safe_load_yaml_with_error 側）
        logger.warning("設定ファイルを解析できませんでした: %s (%s)", file_path, error)
    return data


def safe_load_yaml_with_error(file_path: str) -> tuple[dict[str, Any], Optional[str]]:
    """
    safe_load_yaml と同じ規則で読み込み、(辞書, エラーメッセージ) を返す。
    サニタイズ後も解析できなかった場合だけエラーメッセージを返し、トレースバックをログに記録する。
    ファイルがない場合や、内容が辞書でない・空の場合はエラーとしない (None)。
    """
    data, error = _load_config(file_path)
    if error is not None:
        logger.error("サニタイズ後も設定ファイルを解析できませんでした: %s", file_path, exc_info=error)
        return data, str(error)
    return data, None


def _load_config(file_path: str) -> tuple[dict[str, Any], Optional[Exception]]:
    """設定ファイルを読み込み、(辞書, サニタイズ後も解析できなかった場合の例外) を返す"""
    if not file_path or not os.path.exists(file_path):
        return {}, None

    # 0. JSON ファイルの場合は標準の json.load を試行
    if file_path.lower().endswith(".json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data, None
                return {}, None
        except Exception:
            logger.debug("JSON として読み込めないため YAML として再試行します: %s", file_path, exc_info=True)

    # 1. 通常の yaml.safe_load を試みる (YAMLはJSONの上位互換)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data, None
            return {}, None
    except (yaml.YAMLError, UnicodeDecodeError):
        logger.debug("YAML の解析に失敗したため、サニタイズして再試行します: %s", file_path, exc_info=True)
    except Exception:
        logger.warning("YAML の読み込み中に想定外のエラーが発生しました: %s", file_path, exc_info=True)

    # 2. 構文エラー等が発生した場合、サニタイズしてリトライ
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw_content = f.read()

        sanitized_content = sanitize_yaml_text(raw_content)
        data = yaml.safe_load(sanitized_content)
        if isinstance(data, dict):
            return data, None
        return {}, None
    except Exception as e:
        return {}, e
