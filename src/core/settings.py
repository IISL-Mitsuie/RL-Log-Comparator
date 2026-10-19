"""
QSettings 生成の一元化モジュール
環境変数 RL_LOG_COMPARATOR_SETTINGS_FILE が設定されている場合は INI ファイルを使用する（テスト分離用）
"""

import os
from PySide6.QtCore import QSettings
from src.config import SETTINGS_ORG, SETTINGS_APP

SETTINGS_FILE_ENV = "RL_LOG_COMPARATOR_SETTINGS_FILE"


def create_settings(org: str = SETTINGS_ORG, app: str = SETTINGS_APP) -> QSettings:
    """アプリ共通の QSettings を生成する"""
    override = os.environ.get(SETTINGS_FILE_ENV)
    if override:
        # org/app ごとにグループを分けて同一 INI 内で衝突しないようにする
        settings = QSettings(override, QSettings.Format.IniFormat)
        settings.beginGroup(f"{org}/{app}")
        return settings
    return QSettings(org, app)
