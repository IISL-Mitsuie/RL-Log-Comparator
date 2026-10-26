"""
未捕捉例外の通知ダイアログ
install_exception_hooks() から呼ばれ、どのスレッドから呼ばれてもメインスレッドでダイアログを表示する。
"""

import threading
from typing import Optional
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QObject, Qt, QTimer, Signal


class ErrorDialogNotifier(QObject):
    """未捕捉例外をエラーダイアログで通知する（メインスレッドで生成すること）"""

    # キュー経由でメインスレッドのスロットへ届ける
    _queued = Signal(str)

    def __init__(self, log_path: Optional[str], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._log_path = log_path
        self._showing = False
        self._shown_summaries: set[str] = set()
        self._loop_running = False
        self._queued.connect(self._show, Qt.ConnectionType.QueuedConnection)
        # イベントループが始まったら、以降の表示はキュー経由にする
        QTimer.singleShot(0, self._mark_loop_running)

    def _mark_loop_running(self) -> None:
        self._loop_running = True

    def notify(self, summary: str) -> None:
        """エラーダイアログの表示を要求する（スレッドセーフ）"""
        if self._loop_running or threading.current_thread() is not threading.main_thread():
            # 描画処理などの途中でモーダルダイアログを開かないよう、イベントループに戻ってから表示する
            self._queued.emit(summary)
        else:
            # イベントループの開始前（起動中）の例外は、その場で表示する
            self._show(summary)

    def build_message(self, summary: str) -> str:
        """ダイアログの本文を作る"""
        if self._log_path:
            log_hint = f"詳細はログファイルを参照してください:\n{self._log_path}"
        else:
            log_hint = "ログファイルを作成できなかったため、詳細は記録されていません。"
        return f"予期しないエラーが発生しました。\n\n{summary}\n\n{log_hint}"

    def _show(self, summary: str) -> None:
        # 例外が続けて起きても、表示中や同じ内容のダイアログは重ねて出さない（ログには毎回記録される）
        if self._showing or summary in self._shown_summaries:
            return
        self._showing = True
        self._shown_summaries.add(summary)
        try:
            QMessageBox.critical(None, "RL-Log-Comparator - エラー", self.build_message(summary))
        finally:
            self._showing = False
