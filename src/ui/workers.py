import inspect
import logging
import threading
from typing import Any, Callable
from PySide6.QtCore import QObject, QRunnable, Signal

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """
    ワーカーの実行結果・エラー・進捗を通知するシグナル集。
    Qt のシグナル・スロット機構により、ワーカースレッドからメイン UI スレッドへ安全に渡される。
    """
    finished = Signal(int, object)    # (generation, result)
    failed = Signal(int, str)         # (generation, error_message)
    progress = Signal(int, int, str)  # (generation, count, message)


class FunctionWorker(QRunnable):
    """
    任意の関数を QThreadPool 上で非同期実行するための汎用ワーカークラス。
    世代番号（generation）とキャンセル用 Event をサポートする。
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        generation: int = 0,
        **kwargs: Any
    ):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.generation = generation
        self.signals = WorkerSignals()
        self.cancel_event = threading.Event()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        """ワーカーにキャンセル要求を発行"""
        self.cancel_event.set()

    def run(self) -> None:
        try:
            kwargs = dict(self.kwargs)
            try:
                sig = inspect.signature(self.fn)
                if "cancel_event" in sig.parameters and "cancel_event" not in kwargs:
                    kwargs["cancel_event"] = self.cancel_event
                if "progress_callback" in sig.parameters and "progress_callback" not in kwargs:
                    kwargs["progress_callback"] = (
                        lambda count, msg: self.signals.progress.emit(self.generation, count, msg)
                    )
            except (ValueError, TypeError):
                pass

            result = self.fn(*self.args, **kwargs)
            self.signals.finished.emit(self.generation, result)
        except Exception as exc:
            logger.exception("Worker failed")
            self.signals.failed.emit(self.generation, str(exc))
