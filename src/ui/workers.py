import inspect
import logging
import threading
from typing import Any, Callable, Optional
from PySide6.QtCore import QObject, QRunnable, Signal, Qt, QCoreApplication

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """
    ワーカーの実行結果・エラー・進捗を通知するシグナル集。
    Qt のシグナル・スロット機構により、ワーカースレッドからメイン UI スレッドへ安全に渡される。
    """
    finished = Signal(int, object)    # (generation, result)
    failed = Signal(int, str)         # (generation, error_message)
    progress = Signal(int, int, str)  # (generation, count, message)


class WorkerLifecycleManager(QObject):
    """
    FunctionWorker の強参照を保持し、メインスレッド上のシグナル配送完了後に安全に破棄するマネージャー。
    """
    release_requested = Signal(object)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._active_workers: set["FunctionWorker"] = set()
        self.release_requested.connect(
            self._on_release_worker,
            Qt.ConnectionType.QueuedConnection
        )

    def retain(self, worker: "FunctionWorker") -> None:
        self._active_workers.add(worker)

    def _on_release_worker(self, worker: Any) -> None:
        self._active_workers.discard(worker)


_lifecycle_manager: Optional[WorkerLifecycleManager] = None


def get_worker_lifecycle_manager() -> Optional[WorkerLifecycleManager]:
    """メインスレッド所属の WorkerLifecycleManager シングルトンを取得（QCoreApplication 存在時）"""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        app = QCoreApplication.instance()
        if app is not None:
            _lifecycle_manager = WorkerLifecycleManager(parent=app)
    return _lifecycle_manager


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
        self.setAutoDelete(False)

        mgr = get_worker_lifecycle_manager()
        if mgr is not None:
            mgr.retain(self)

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
        finally:
            mgr = get_worker_lifecycle_manager()
            if mgr is not None:
                mgr.release_requested.emit(self)

