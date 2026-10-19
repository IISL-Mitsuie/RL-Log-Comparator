"""
テスト中のネットワーク遮断 (conftest.py の block_network) のテスト
"""

import urllib.error
import urllib.request
import pytest
from tests.helpers import blocked_requests


def _take_blocked_requests() -> list[str]:
    """記録を取り出して消去する（意図的なアクセスのため、テスト終了時の検査で失敗させない）"""
    recorded = list(blocked_requests)
    blocked_requests.clear()
    return recorded


def test_urlopen_is_blocked_and_recorded():
    """モックしていない urlopen は外部へ接続せず、URLError を送出して記録される"""
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen("https://api.github.com/", timeout=1)
    assert _take_blocked_requests() == ["https://api.github.com/"]


def test_urlopen_request_object_is_recorded_by_url():
    """Request オブジェクトで呼ばれた場合も URL を記録する"""
    req = urllib.request.Request("https://example.com/api")
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(req)
    assert _take_blocked_requests() == ["https://example.com/api"]
