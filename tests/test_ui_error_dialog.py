"""
未捕捉例外の通知ダイアログ (ErrorDialogNotifier) の単体テスト
"""

import threading
from unittest.mock import patch

from src.ui.error_dialog import ErrorDialogNotifier
from tests.helpers import get_qapp


def test_notify_from_main_thread_shows_dialog_with_log_path():
    get_qapp()
    notifier = ErrorDialogNotifier("C:/logs/app.log")
    with patch("src.ui.error_dialog.QMessageBox.critical") as mock_critical:
        notifier.notify("ValueError: x")
    mock_critical.assert_called_once()
    message = mock_critical.call_args.args[2]
    assert "ValueError: x" in message
    assert "C:/logs/app.log" in message


def test_notify_from_worker_thread_is_shown_on_main_thread():
    app = get_qapp()
    notifier = ErrorDialogNotifier(None)
    shown_threads = []
    with patch("src.ui.error_dialog.QMessageBox.critical",
               side_effect=lambda *args: shown_threads.append(threading.current_thread())) as mock_critical:
        worker = threading.Thread(target=notifier.notify, args=("RuntimeError: y",))
        worker.start()
        worker.join()
        # キュー経由で届くので、イベントを処理するまでは表示されない
        assert mock_critical.call_count == 0
        app.processEvents()
    assert shown_threads == [threading.main_thread()]
    assert "ログファイルを作成できなかった" in mock_critical.call_args.args[2]


def test_notify_is_queued_while_event_loop_runs():
    app = get_qapp()
    notifier = ErrorDialogNotifier(None)
    app.processEvents()  # イベントループが動き始めた状態にする
    with patch("src.ui.error_dialog.QMessageBox.critical") as mock_critical:
        notifier.notify("ValueError: in paint")
        assert mock_critical.call_count == 0
        app.processEvents()
    assert mock_critical.call_count == 1


def test_same_error_is_shown_only_once():
    get_qapp()
    notifier = ErrorDialogNotifier(None)
    with patch("src.ui.error_dialog.QMessageBox.critical") as mock_critical:
        notifier.notify("ValueError: repeated")
        notifier.notify("ValueError: repeated")
        notifier.notify("ValueError: other")
    assert [c.args[2].split("\n\n")[1] for c in mock_critical.call_args_list] == [
        "ValueError: repeated", "ValueError: other"
    ]
