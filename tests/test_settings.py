"""
QSettings 生成の一元化モジュール (src.core.settings) の単体テスト
"""

from PySide6.QtCore import QSettings
from src.core.settings import SETTINGS_FILE_ENV, create_settings


def test_create_settings_uses_ini_when_env_set(tmp_path, monkeypatch):
    """環境変数が設定されている場合は INI 形式の設定を返す"""
    ini_path = tmp_path / "settings.ini"
    monkeypatch.setenv(SETTINGS_FILE_ENV, str(ini_path))

    settings = create_settings()
    assert settings.format() == QSettings.Format.IniFormat
    assert settings.fileName() == str(ini_path).replace("\\", "/")


def test_create_settings_uses_native_without_env(monkeypatch):
    """環境変数が設定されていない場合はネイティブ形式（Windows ではレジストリ）を返す"""
    monkeypatch.delenv(SETTINGS_FILE_ENV, raising=False)

    # 生成するだけで読み書きはしない（本番設定に触れない）
    settings = create_settings()
    assert settings.format() == QSettings.Format.NativeFormat


def test_create_settings_separates_org_app_groups(tmp_path, monkeypatch):
    """異なる org/app の設定が同じ INI の中で衝突しない"""
    ini_path = tmp_path / "settings.ini"
    monkeypatch.setenv(SETTINGS_FILE_ENV, str(ini_path))

    s1 = create_settings("OrgA", "AppA")
    s2 = create_settings("OrgB", "AppB")
    s1.setValue("same_key", "value_a")
    s2.setValue("same_key", "value_b")
    s1.sync()
    s2.sync()

    assert create_settings("OrgA", "AppA").value("same_key") == "value_a"
    assert create_settings("OrgB", "AppB").value("same_key") == "value_b"
