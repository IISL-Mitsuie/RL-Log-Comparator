"""
pytest 設定および全テスト共通フィクスチャ (conftest.py)
QSettings をテスト専用の一時 INI ファイルへ差し替え、本番設定（レジストリ）を一切読み書きしない。
また、テスト中は起動時の更新確認を止め、モックしていない urllib.request.urlopen を遮断する。
"""

import urllib.request
import pytest
from PySide6.QtCore import QEvent
from src.core.settings import SETTINGS_FILE_ENV, create_settings
from tests.helpers import get_qapp, blocked_requests, deny_urlopen


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
    app = get_qapp()
    yield
    # 残ったウィジェットをインタプリタ終了前に破棄する（終了時の破棄順序によるクラッシュを防ぐ）
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


@pytest.fixture(scope="session", autouse=True)
def disable_background_update_check():
    """
    ウィンドウ生成時の更新確認スレッドを起動しない。
    スレッドがウィンドウ破棄後に Signal を emit し、pytest 終了時にクラッシュするのを防ぐ。
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "src.ui.main_window.ExperimentCompareApp._start_background_update_check",
            lambda self: None,
        )
        yield


@pytest.fixture(scope="session", autouse=True)
def block_network():
    """モックしていない urlopen を遮断する（各テストの @patch による差し替えはこれより優先される）"""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(urllib.request, "urlopen", deny_urlopen)
        yield


@pytest.fixture(autouse=True)
def fail_on_network_access(block_network):
    """テスト中に遮断した urlopen の呼び出しがあれば、そのテストを失敗させる"""
    blocked_requests.clear()
    yield
    if blocked_requests:
        urls = list(blocked_requests)
        blocked_requests.clear()
        pytest.fail(f"テスト中にネットワークへアクセスしようとしました: {urls}")


@pytest.fixture(autouse=True)
def clear_settings_per_test(isolate_settings):
    """各テスト終了時に一時 INI の内容を消去し、テスト間の独立性を保つ"""
    yield
    s = create_settings()
    s.clear()
    s.sync()
