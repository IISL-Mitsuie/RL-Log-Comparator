"""
pytest 設定および全テスト共通フィクスチャ (conftest.py)
QSettings をテスト専用の一時 INI ファイルへ差し替え、本番設定（レジストリ）を一切読み書きしない。
"""

import pytest
from src.core.settings import SETTINGS_FILE_ENV, create_settings
from tests.helpers import get_qapp


@pytest.fixture(scope="session", autouse=True)
def isolate_settings(tmp_path_factory):
    """どのウィジェットよりも先に、QSettings の保存先を一時 INI ファイルへ差し替える"""
    ini_path = tmp_path_factory.mktemp("settings") / "settings.ini"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv(SETTINGS_FILE_ENV, str(ini_path))
        yield ini_path


@pytest.fixture(scope="session", autouse=True)
def ensure_qapp(isolate_settings):
    """テストセッション全体で共有する QApplication を生成"""
    get_qapp()


@pytest.fixture(autouse=True)
def clear_settings_per_test(isolate_settings):
    """各テスト終了時に一時 INI の内容を消去し、テスト間の独立性を保つ"""
    yield
    s = create_settings()
    s.clear()
    s.sync()
