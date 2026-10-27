"""
FunctionWorker および WorkerSignals の単体テスト
"""

import threading
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import QThreadPool
from src.ui.workers import FunctionWorker
from tests.helpers import get_qapp


def sample_task(x: int, y: int) -> int:
    return x + y


def sample_task_with_cancel(cancel_event: threading.Event) -> str:
    while not cancel_event.is_set():
        time.sleep(0.01)
    return "cancelled"


def sample_failing_task() -> None:
    raise ValueError("intentional error")


class TestWorkers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def test_worker_success(self):
        pool = QThreadPool()
        results = []

        worker = FunctionWorker(sample_task, 10, 20, generation=42)
        worker.signals.finished.connect(lambda gen, res: results.append((gen, res)))

        pool.start(worker)
        pool.waitForDone(2000)
        self.app.processEvents()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], (42, 30))

    def test_worker_failure_logs_exception(self):
        pool = QThreadPool()
        failures = []

        worker = FunctionWorker(sample_failing_task, generation=7)
        worker.signals.failed.connect(lambda gen, msg: failures.append((gen, msg)))

        with patch("src.ui.workers.logger.exception") as mock_log:
            pool.start(worker)
            pool.waitForDone(2000)
            self.app.processEvents()
            mock_log.assert_called_once_with("Worker failed")

        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0][0], 7)
        self.assertIn("intentional error", failures[0][1])

    def test_worker_cancellation(self):
        pool = QThreadPool()
        results = []

        worker = FunctionWorker(sample_task_with_cancel, generation=1)
        worker.signals.finished.connect(lambda gen, res: results.append((gen, res)))

        pool.start(worker)
        time.sleep(0.05)
        worker.cancel()
        pool.waitForDone(2000)
        self.app.processEvents()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], (1, "cancelled"))


if __name__ == "__main__":
    unittest.main()
