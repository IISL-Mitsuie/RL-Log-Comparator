"""
ロギング基盤モジュール（Qt非依存）
アプリ起動時に 1 回だけ setup_logging() を呼び、ルートロガーにファイル出力を設定する。
各モジュールは logging.getLogger(__name__) を使い、ハンドラは設定しない。
"""

import logging
import os
import platform
import sys
import tempfile
import threading
from logging.handlers import RotatingFileHandler
from typing import Callable, Optional

from src.config import APP_VERSION

logger = logging.getLogger(__name__)

LOG_FILE_NAME = "app.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

# この環境変数が "1" のとき、ログレベルを DEBUG にする
DEBUG_ENV = "RL_LOG_COMPARATOR_DEBUG"

# setup_logging() が追加したハンドラの目印（二重に追加しないため）
_HANDLER_MARK = "_rl_log_comparator_handler"

# DEBUG 時にも大量のログを出す外部ライブラリは WARNING 以上に絞る
_NOISY_LOGGERS = ("matplotlib", "PIL")


def get_log_dir() -> str:
    """ログフォルダ（%LOCALAPPDATA%\\RL-Log-Comparator\\logs）を作成して返す"""
    local_appdata = os.environ.get('LOCALAPPDATA', tempfile.gettempdir())
    log_dir = os.path.join(local_appdata, 'RL-Log-Comparator', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_log_file_path() -> str:
    """ログファイルのパスを返す"""
    return os.path.join(get_log_dir(), LOG_FILE_NAME)


def setup_logging(level: int = logging.INFO, log_dir: Optional[str] = None) -> Optional[str]:
    """
    ルートロガーにログファイル（1MB × 3 世代のローテーション）と、開発時はコンソール出力を設定する。
    ログファイルのパスを返す。ログフォルダを作成できない場合は None を返す（アプリは継続する）。
    """
    if os.environ.get(DEBUG_ENV) == "1":
        level = logging.DEBUG

    root = logging.getLogger()
    root.setLevel(level)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    # 再設定時は、前回追加したハンドラを入れ替える
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARK, False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT)
    log_path: Optional[str] = None
    try:
        target_dir = log_dir if log_dir else get_log_dir()
        os.makedirs(target_dir, exist_ok=True)
        log_path = os.path.join(target_dir, LOG_FILE_NAME)
        file_handler = RotatingFileHandler(
            log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        setattr(file_handler, _HANDLER_MARK, True)
        root.addHandler(file_handler)
    except OSError:
        log_path = None

    # 配布版 (console=False) では sys.stderr が None になる
    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        setattr(stream_handler, _HANDLER_MARK, True)
        root.addHandler(stream_handler)

    if log_path is None:
        logger.warning("ログフォルダを作成できないため、ログをファイルに保存しません")

    logger.info(
        "起動: RL-Log-Comparator v%s / Python %s / %s / frozen=%s",
        APP_VERSION, platform.python_version(), platform.platform(), bool(getattr(sys, "frozen", False))
    )
    return log_path


def _format_summary(exc_type: type, exc_value: Optional[BaseException]) -> str:
    """ダイアログに表示する例外の要約"""
    return f"{exc_type.__name__}: {exc_value}"


def install_exception_hooks(show_dialog: Callable[[str], None]) -> None:
    """
    sys.excepthook と threading.excepthook を差し替え、未捕捉例外をログに記録してから
    show_dialog(要約メッセージ) を呼ぶ。
    show_dialog はワーカースレッドからも呼ばれるため、呼び出し側でメインスレッドに回すこと。
    """
    def _notify(summary: str) -> None:
        try:
            show_dialog(summary)
        except Exception:
            # 通知の失敗で例外処理が再帰しないよう、記録だけして終える
            logger.debug("エラーダイアログの表示に失敗しました", exc_info=True)

    def _sys_hook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical("未捕捉の例外が発生しました", exc_info=(exc_type, exc_value, exc_tb))
        _notify(_format_summary(exc_type, exc_value))

    def _threading_hook(args: threading.ExceptHookArgs) -> None:
        if issubclass(args.exc_type, SystemExit):
            return
        thread_name = args.thread.name if args.thread else "unknown"
        logger.critical(
            "スレッド %s で未捕捉の例外が発生しました", thread_name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )
        _notify(_format_summary(args.exc_type, args.exc_value))

    sys.excepthook = _sys_hook
    threading.excepthook = _threading_hook
