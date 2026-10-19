"""
Python バージョンガードの単体テスト (Qt 非依存)
"""

import ctypes
import pytest
from src_bootstrap import ensure_supported_python, exit_if_unsupported_python


def test_ensure_supported_python_supported():
    """3.12 以上のバージョンでは None が返ることを確認"""
    assert ensure_supported_python((3, 12, 0)) is None
    assert ensure_supported_python((3, 13, 3)) is None


def test_ensure_supported_python_unsupported():
    """3.12 未満のバージョンでは 3.12 と指定バージョンを含むメッセージ文字列が返ることを確認"""
    msg_311 = ensure_supported_python((3, 11, 9))
    assert msg_311 is not None
    assert "3.12" in msg_311
    assert "3.11.9" in msg_311

    msg_310 = ensure_supported_python((3, 10, 0))
    assert msg_310 is not None
    assert "3.12" in msg_310
    assert "3.10.0" in msg_310


def test_exit_if_unsupported_python_exits(capsys):
    """3.12 未満で show_dialog=False の場合、SystemExit(1) と stderr 出力が発生することを確認"""
    with pytest.raises(SystemExit) as exc_info:
        exit_if_unsupported_python((3, 11, 9), show_dialog=False)
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "3.12" in captured.err
    assert "3.11.9" in captured.err


def test_exit_if_unsupported_python_supported_does_nothing():
    """3.12 以上の場合、例外を送出せず正常終了することを確認"""
    exit_if_unsupported_python((3, 12, 0), show_dialog=False)


def test_exit_if_unsupported_python_no_dialog_env(monkeypatch, capsys):
    """RL_LOG_COMPARATOR_NO_DIALOG=1 の場合、show_dialog=True でも MessageBoxW が呼ばれず stderr に出力されることを確認"""
    monkeypatch.setenv("RL_LOG_COMPARATOR_NO_DIALOG", "1")

    def fail_if_dialog_called(*args, **kwargs):
        pytest.fail("MessageBoxW should not be called when RL_LOG_COMPARATOR_NO_DIALOG is set")

    if hasattr(ctypes, "windll"):
        monkeypatch.setattr(ctypes.windll.user32, "MessageBoxW", fail_if_dialog_called)

    with pytest.raises(SystemExit) as exc_info:
        exit_if_unsupported_python((3, 11, 9), show_dialog=True)
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "3.12" in captured.err
    assert "3.11.9" in captured.err
