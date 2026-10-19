"""
RL-Log-Comparator ブートストラップ用モジュール

Python 3.12 未満のバージョンで実行された場合に、
構文エラー（PEP 701 f-string 等）を起こす前に
必要なバージョンを伝えるメッセージを表示して終了するための軽量ガード。
古い Python でも構文エラーにならない書き方を維持する。
"""

import os
import sys

MIN_PYTHON = (3, 12)


def ensure_supported_python(version_info=None):
    """
    Python バージョンを検証する。

    version_info が None の場合は sys.version_info を使用する。
    (version_info[0], version_info[1]) >= MIN_PYTHON なら None を返す。
    満たさないときは案内メッセージ（2行の文字列）を返す。
    """
    if version_info is None:
        version_info = sys.version_info

    if (version_info[0], version_info[1]) >= MIN_PYTHON:
        return None

    min_ver_str = "{}.{}".format(MIN_PYTHON[0], MIN_PYTHON[1])
    current_ver_str = ".".join(str(part) for part in version_info[:3])
    line1 = "RL-Log-Comparator には Python {} 以上が必要です。".format(min_ver_str)
    line2 = "現在の Python: {}".format(current_ver_str)
    return line1 + "\n" + line2


def exit_if_unsupported_python(version_info=None, show_dialog=True):
    """
    Python バージョンが MIN_PYTHON 未満の場合、案内メッセージを出力して終了する。

    環境変数 RL_LOG_COMPARATOR_NO_DIALOG が空でなければダイアログを出さず標準エラー出力に出力。
    そうでなく show_dialog が True かつ sys.platform == "win32" なら MessageBoxW を表示。
    MessageBoxW が例外になった場合やそれ以外の環境では標準エラー出力に出力。
    """
    msg = ensure_supported_python(version_info)
    if msg is None:
        return

    no_dialog = bool(os.environ.get("RL_LOG_COMPARATOR_NO_DIALOG"))
    dialog_shown = False

    if not no_dialog and show_dialog and sys.platform == "win32":
        try:
            import ctypes
            # MessageBoxW(hWnd, lpText, lpCaption, uType)
            # uType: 0x10 = MB_ICONERROR
            ctypes.windll.user32.MessageBoxW(None, msg, "RL-Log-Comparator", 0x10)
            dialog_shown = True
        except Exception:
            dialog_shown = False

    if not dialog_shown:
        if sys.stderr is not None:
            try:
                sys.stderr.write(msg + "\n")
                sys.stderr.flush()
            except Exception:
                pass

    sys.exit(1)
