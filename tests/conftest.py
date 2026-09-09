"""
pytest 設定および全テスト共通フィクスチャ (conftest.py)
テスト実行による本番 QSettings の汚染を完全に防止し、テスト履歴を抹消する。
"""

import os
import pytest
from PySide6.QtCore import QSettings
from src.config import (
    SETTINGS_ORG, SETTINGS_APP,
    SETTINGS_KEY_RECENT_FOLDERS,
    SETTINGS_KEY_RECENT_ROOT_DIRS,
    SETTINGS_KEY_LAST_ROOT_DIR,
    SETTINGS_KEY_LAST_FOLDER_A,
    SETTINGS_KEY_LAST_FOLDER_B,
)
from tests.helpers import get_qapp


def _clean_test_records_from_production_settings():
    """本番 QSettings に混入した可能性のあるテスト用一時パス（pytest, Temp等）を抹消"""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)

    # 1. ルートフォルダ履歴の抹消
    roots = s.value(SETTINGS_KEY_RECENT_ROOT_DIRS, [])
    if isinstance(roots, list):
        cleaned_roots = [
            p for p in roots
            if isinstance(p, str) and not any(k in p for k in ["pytest", "Temp", "temp", "tmp", "dir_", "folder_"])
        ]
        if cleaned_roots != roots:
            s.setValue(SETTINGS_KEY_RECENT_ROOT_DIRS, cleaned_roots)

    # 2. 比較フォルダ履歴の抹消
    folders = s.value(SETTINGS_KEY_RECENT_FOLDERS, [])
    if isinstance(folders, list):
        cleaned_folders = [
            p for p in folders
            if isinstance(p, str) and not any(k in p for k in ["pytest", "Temp", "temp", "tmp", "dir_", "folder_"])
        ]
        if cleaned_folders != folders:
            s.setValue(SETTINGS_KEY_RECENT_FOLDERS, cleaned_folders)

    # 3. 終了時セッションパスの抹消
    for key in [SETTINGS_KEY_LAST_ROOT_DIR, SETTINGS_KEY_LAST_FOLDER_A, SETTINGS_KEY_LAST_FOLDER_B]:
        val = s.value(key, "")
        if isinstance(val, str) and any(k in val for k in ["pytest", "Temp", "temp", "tmp", "dir_", "folder_"]):
            s.remove(key)


@pytest.fixture(scope="session", autouse=True)
def ensure_qapp_and_clean_settings():
    """テストセッション全体の前後に実行されるクリーンアップフィクスチャ"""
    get_qapp()
    _clean_test_records_from_production_settings()
    yield
    _clean_test_records_from_production_settings()


@pytest.fixture(autouse=True)
def clean_per_test():
    """各テスト終了時にもテスト履歴の抹消を確認"""
    yield
    _clean_test_records_from_production_settings()
