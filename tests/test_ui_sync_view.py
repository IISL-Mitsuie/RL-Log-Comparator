"""
同期パン＆ズームビュー (SyncGraphicsView) の単体テスト
"""

import unittest
from PySide6.QtGui import QWheelEvent
from PySide6.QtCore import QPoint, Qt
from src.ui.widgets.sync_graphics_view import SyncGraphicsView
from tests.helpers import get_qapp


class TestUiSyncView(unittest.TestCase):
    """SyncGraphicsView の同期機能テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def test_sync_scroll(self):
        from PySide6.QtWidgets import QGraphicsScene
        scene1 = QGraphicsScene(0, 0, 1000, 1000)
        scene2 = QGraphicsScene(0, 0, 1000, 1000)

        v1 = SyncGraphicsView(scene1)
        v2 = SyncGraphicsView(scene2)
        v1.resize(200, 200)
        v2.resize(200, 200)
        v1.show()
        v2.show()

        v1.set_partner(v2)
        v2.set_partner(v1)

        # _sync_scroll のテスト
        v1._sync_scroll(50, 80)
        self.assertEqual(v1.horizontalScrollBar().value(), 50)
        self.assertEqual(v1.verticalScrollBar().value(), 80)

        v1.close()
        v2.close()

    def test_sync_zoom(self):
        v1 = SyncGraphicsView()
        v2 = SyncGraphicsView()
        v1.set_partner(v2)
        v2.set_partner(v1)

        transform_before_1 = v1.transform()
        transform_before_2 = v2.transform()

        # _sync_zoom が自身のスケールを変更することを検証
        v1._sync_zoom(1.15)
        self.assertNotEqual(v1.transform(), transform_before_1)

        v2._sync_zoom(1.15)
        self.assertNotEqual(v2.transform(), transform_before_2)


if __name__ == "__main__":
    unittest.main()
