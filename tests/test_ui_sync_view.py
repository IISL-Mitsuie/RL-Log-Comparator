"""
同期パン＆ズームビュー (SyncGraphicsView) の単体テスト
"""

import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QWheelEvent, QPainter
from PySide6.QtCore import QPointF, QPoint, Qt
from src.ui.widgets.sync_graphics_view import SyncGraphicsView, ViewSyncController
from tests.helpers import get_qapp


def _create_wheel_event(delta_y: int, pos: QPoint = QPoint(100, 100)) -> QWheelEvent:
    """テスト用の QWheelEvent を生成するヘルパー"""
    return QWheelEvent(
        QPointF(pos),
        QPointF(pos),
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


class TestUiSyncView(unittest.TestCase):
    """SyncGraphicsView の同期機能テスト"""

    @classmethod
    def setUpClass(cls):
        cls.app = get_qapp()

    def test_sync_scroll(self):
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

    def test_render_hints(self):
        """縮小表示時のスムージング等のレンダーヒントが有効化されていることを検証"""
        v = SyncGraphicsView()
        hints = v.renderHints()
        self.assertTrue(bool(hints & QPainter.RenderHint.SmoothPixmapTransform))
        self.assertTrue(bool(hints & QPainter.RenderHint.Antialiasing))

    def test_different_resolutions_sync(self):
        """異なる解像度の画像間で正規化状態 (cx, cy, zoom) が同期されることを検証"""
        scene_a = QGraphicsScene(0, 0, 800, 600)
        scene_b = QGraphicsScene(0, 0, 1600, 1200)

        v_a = SyncGraphicsView(scene_a)
        v_b = SyncGraphicsView(scene_b)
        v_a.resize(400, 300)
        v_b.resize(400, 300)
        v_a.show()
        v_b.show()

        controller = ViewSyncController()
        controller.register(v_a, v_b)

        v_a.fit_to_scene()
        v_b.fit_to_scene()

        # 初期状態: zoom は 1.0、中心はほぼ (0.5, 0.5)
        state_a = v_a.normalized_state()
        state_b = v_b.normalized_state()
        self.assertIsNotNone(state_a)
        self.assertIsNotNone(state_b)
        self.assertAlmostEqual(state_a[2], 1.0, places=2)
        self.assertAlmostEqual(state_b[2], 1.0, places=2)

        # v_a をズームおよびパン操作
        v_a.scale(2.0, 2.0)
        v_a.centerOn(600, 150)  # 右上 1/4 (cx=0.75, cy=0.25)
        v_a.changed.emit()

        state_a_after = v_a.normalized_state()
        state_b_after = v_b.normalized_state()

        # 左右で正規化状態が一致することを検証
        self.assertAlmostEqual(state_a_after[0], state_b_after[0], places=2)
        self.assertAlmostEqual(state_a_after[1], state_b_after[1], places=2)
        self.assertAlmostEqual(state_a_after[2], state_b_after[2], places=2)

        v_a.close()
        v_b.close()

    def test_single_apply_and_no_loop(self):
        """1回のホイール操作で相手側への適用が1回のみ行われ、往復ループしないことを検証"""
        scene_a = QGraphicsScene(0, 0, 800, 600)
        scene_b = QGraphicsScene(0, 0, 800, 600)

        v_a = SyncGraphicsView(scene_a)
        v_b = SyncGraphicsView(scene_b)
        v_a.resize(400, 300)
        v_b.resize(400, 300)
        v_a.show()
        v_b.show()

        controller = ViewSyncController()
        controller.register(v_a, v_b)
        v_a.fit_to_scene()
        v_b.fit_to_scene()

        v_b.apply_normalized_state = MagicMock(side_effect=v_b.apply_normalized_state)
        v_a.apply_normalized_state = MagicMock(side_effect=v_a.apply_normalized_state)

        # v_a にホイールイベント（拡大）を発行
        event = _create_wheel_event(120)
        v_a.wheelEvent(event)

        # 相手側への適用がちょうど 1 回
        self.assertEqual(v_b.apply_normalized_state.call_count, 1)
        # 逆方向（v_b -> v_a）への往復適用は 0 回
        self.assertEqual(v_a.apply_normalized_state.call_count, 0)

        v_a.close()
        v_b.close()

    def test_zoom_limits(self):
        """ズーム倍率が 0.1〜40.0 の範囲に収まることを検証"""
        scene = QGraphicsScene(0, 0, 800, 600)
        v = SyncGraphicsView(scene)
        v.resize(400, 300)
        v.show()
        v.fit_to_scene()

        # 極端に縮小ホイール操作を繰り返す
        event_out = _create_wheel_event(-120)
        for _ in range(50):
            v.wheelEvent(event_out)

        zoom_min = v.transform().m11() / v.fit_scale
        self.assertGreaterEqual(zoom_min, 0.1 - 1e-4)

        # 極端に拡大ホイール操作を繰り返す
        event_in = _create_wheel_event(120)
        for _ in range(100):
            v.wheelEvent(event_in)

        zoom_max = v.transform().m11() / v.fit_scale
        self.assertLessEqual(zoom_max, 40.0 + 1e-4)

        v.close()

    def test_fit_to_scene_resets_view(self):
        """fit_to_scene で全体表示に戻り zoom が 1.0 にリセットされることを検証"""
        scene = QGraphicsScene(0, 0, 800, 600)
        v = SyncGraphicsView(scene)
        v.resize(400, 300)
        v.show()
        v.fit_to_scene()

        # ズーム・移動
        v.scale(3.0, 3.0)
        v.centerOn(100, 100)
        state_zoomed = v.normalized_state()
        self.assertGreater(state_zoomed[2], 2.0)

        # リセット
        v.fit_to_scene()
        state_reset = v.normalized_state()
        self.assertAlmostEqual(state_reset[2], 1.0, places=2)
        self.assertAlmostEqual(state_reset[0], 0.5, places=1)
        self.assertAlmostEqual(state_reset[1], 0.5, places=1)

        v.close()

    def test_empty_scene_handling(self):
        """シーンが空の場合でもエラーなく安全にスキップされることを検証"""
        v_empty_a = SyncGraphicsView()
        v_empty_b = SyncGraphicsView()
        controller = ViewSyncController()
        controller.register(v_empty_a, v_empty_b)

        # 状態取得が None
        self.assertIsNone(v_empty_a.normalized_state())

        # 例外が出ないことを検証
        event = _create_wheel_event(120)
        v_empty_a.wheelEvent(event)
        v_empty_a.changed.emit()


if __name__ == "__main__":
    unittest.main()
