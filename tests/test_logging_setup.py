"""
ロギング基盤モジュール (src.core.logging_setup) の単体テスト
ユーザーのログフォルダへ書き込まないよう、ログの出力先はすべて tmp_path にする。
"""

import logging
import os
import sys
import threading

import pytest

from src.config import APP_VERSION
from src.core import logging_setup
from src.core.logging_setup import (
    DEBUG_ENV, LOG_FILE_NAME, get_log_dir, install_exception_hooks, setup_logging
)


@pytest.fixture
def restore_root_logger():
    """テストで追加したハンドラ・ログレベルを元に戻す"""
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield root
    for handler in list(root.handlers):
        if handler not in handlers:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)


@pytest.fixture
def restore_hooks():
    """テストで差し替えた例外フックを元に戻す"""
    original_sys = sys.excepthook
    original_threading = threading.excepthook
    yield
    sys.excepthook = original_sys
    threading.excepthook = original_threading


def _read_log(log_dir) -> str:
    for handler in logging.getLogger().handlers:
        handler.flush()
    with open(os.path.join(str(log_dir), LOG_FILE_NAME), encoding="utf-8") as f:
        return f.read()


def test_get_log_dir_uses_localappdata(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    log_dir = get_log_dir()
    assert log_dir == os.path.join(str(tmp_path), "RL-Log-Comparator", "logs")
    assert os.path.isdir(log_dir)


def test_setup_logging_writes_startup_info(tmp_path, monkeypatch, restore_root_logger):
    monkeypatch.delenv(DEBUG_ENV, raising=False)
    log_path = setup_logging(log_dir=str(tmp_path))
    assert log_path == os.path.join(str(tmp_path), LOG_FILE_NAME)
    assert restore_root_logger.level == logging.INFO

    content = _read_log(tmp_path)
    startup_lines = [line for line in content.splitlines() if APP_VERSION in line]
    assert len(startup_lines) == 1
    assert "Python" in startup_lines[0]
    assert "frozen" in startup_lines[0]

    logging.getLogger("src.test").warning("テスト警告")
    assert "WARNING [src.test] テスト警告" in _read_log(tmp_path)


def test_setup_logging_is_idempotent(tmp_path, restore_root_logger):
    setup_logging(log_dir=str(tmp_path))
    count = len(restore_root_logger.handlers)
    setup_logging(log_dir=str(tmp_path))
    assert len(restore_root_logger.handlers) == count


def test_setup_logging_debug_env(tmp_path, monkeypatch, restore_root_logger):
    monkeypatch.setenv(DEBUG_ENV, "1")
    setup_logging(log_dir=str(tmp_path))
    assert restore_root_logger.level == logging.DEBUG


def test_setup_logging_survives_unwritable_dir(tmp_path, restore_root_logger):
    # ファイルをフォルダとして指定し、ログフォルダを作れない状況にする
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x")
    assert setup_logging(log_dir=str(not_a_dir / "logs")) is None


def test_sys_excepthook_logs_and_shows_dialog(tmp_path, restore_root_logger, restore_hooks):
    setup_logging(log_dir=str(tmp_path))
    messages = []
    install_exception_hooks(messages.append)

    try:
        raise ValueError("スロット内の想定外エラー")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    content = _read_log(tmp_path)
    assert "CRITICAL" in content
    assert "Traceback" in content
    assert "スロット内の想定外エラー" in content
    assert len(messages) == 1
    assert "ValueError" in messages[0]
    assert "スロット内の想定外エラー" in messages[0]


def test_sys_excepthook_passes_keyboard_interrupt(restore_hooks, monkeypatch):
    called = []
    monkeypatch.setattr(sys, "__excepthook__", lambda *args: called.append(args[0]))
    messages = []
    install_exception_hooks(messages.append)
    sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert called == [KeyboardInterrupt]
    assert messages == []


def test_threading_excepthook_logs_and_shows_dialog(tmp_path, restore_root_logger, restore_hooks):
    setup_logging(log_dir=str(tmp_path))
    messages = []
    install_exception_hooks(messages.append)

    def worker():
        raise RuntimeError("ワーカーの想定外エラー")

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert "ワーカーの想定外エラー" in _read_log(tmp_path)
    assert len(messages) == 1
    assert "RuntimeError" in messages[0]


def test_dialog_failure_does_not_raise(restore_hooks, caplog):
    def broken_dialog(message):
        raise RuntimeError("dialog failed")

    install_exception_hooks(broken_dialog)
    with caplog.at_level(logging.DEBUG, logger=logging_setup.__name__):
        sys.excepthook(ValueError, ValueError("x"), None)
    assert "dialog failed" in caplog.text
