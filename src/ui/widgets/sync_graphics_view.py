"""
同期パン＆ズーム機能を備えた QGraphicsView
"""

from typing import Optional, Tuple
from PySide6.QtWidgets import QGraphicsView
from PySide6.QtGui import QWheelEvent, QPainter
from PySide6.QtCore import Signal, QPointF, Qt, QObject


class ViewSyncController(QObject):
    """2つの SyncGraphicsView 間で正規化された表示状態（中心相対位置・倍率）を同期するコントローラ"""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._syncing: bool = False
        self.view_a: Optional['SyncGraphicsView'] = None
        self.view_b: Optional['SyncGraphicsView'] = None

    def register(self, view_a: 'SyncGraphicsView', view_b: 'SyncGraphicsView') -> None:
        """2つのビューを同期対象として登録"""
        self._disconnect_views()

        self.view_a = view_a
        self.view_b = view_b

        if self.view_a is not None:
            self.view_a._controller = self
            self.view_a.partner_view = self.view_b
            self.view_a.changed.connect(self._on_view_a_changed)

        if self.view_b is not None:
            self.view_b._controller = self
            self.view_b.partner_view = self.view_a
            self.view_b.changed.connect(self._on_view_b_changed)

    def _disconnect_views(self) -> None:
        if self.view_a is not None:
            try:
                self.view_a.changed.disconnect(self._on_view_a_changed)
            except (RuntimeError, TypeError):
                pass
            self.view_a = None
        if self.view_b is not None:
            try:
                self.view_b.changed.disconnect(self._on_view_b_changed)
            except (RuntimeError, TypeError):
                pass
            self.view_b = None

    def _on_view_a_changed(self) -> None:
        if self.view_a is not None:
            self.on_view_changed(self.view_a)

    def _on_view_b_changed(self) -> None:
        if self.view_b is not None:
            self.on_view_changed(self.view_b)

    def on_view_changed(self, source: 'SyncGraphicsView') -> None:
        """source ビューの変更を検知し、相手ビューへ正規化状態を同期"""
        if self._syncing:
            return

        target = self.view_b if source is self.view_a else self.view_a
        if target is None:
            return

        state = source.normalized_state()
        if state is None:
            return

        target_scene = target.scene()
        if target_scene is None:
            return
        sr = target_scene.sceneRect()
        if sr.isEmpty() or sr.width() <= 0 or sr.height() <= 0:
            return

        self._syncing = True
        try:
            target.apply_normalized_state(*state)
        finally:
            self._syncing = False


class SyncGraphicsView(QGraphicsView):
    """パートナービューとパン（スクロール）およびズームを同期する QGraphicsView"""

    MIN_ZOOM: float = 0.1
    MAX_ZOOM: float = 40.0

    changed = Signal()
    zoomed = Signal(float, QPointF)
    scrolled = Signal(int, int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHints(
            QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.fit_scale: float = 1.0
        self.partner_view: Optional['SyncGraphicsView'] = None
        self._controller: Optional[ViewSyncController] = None
        self._is_syncing: bool = False
        self._in_wheel: bool = False
        self._is_fitting: bool = False
        self._is_applying: bool = False

        self.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_partner(self, partner: Optional['SyncGraphicsView']) -> None:
        """同期対象のパートナービューを設定（ViewSyncController を自動共有）"""
        self.partner_view = partner
        if partner is None:
            self._controller = None
            return

        if partner._controller is not None:
            self._controller = partner._controller
            if self._controller.view_a is not self and self._controller.view_b is not self:
                self._controller.register(partner, self)
        elif self._controller is not None:
            if self._controller.view_a is not partner and self._controller.view_b is not partner:
                self._controller.register(self, partner)
            partner._controller = self._controller
        else:
            controller = ViewSyncController(self)
            controller.register(self, partner)
            self._controller = controller
            partner._controller = controller

    def fit_to_scene(self) -> None:
        """シーン全体がビューに収まるようにスケールと位置をリセットし、fit_scaleを記録"""
        self._is_fitting = True
        try:
            self.resetTransform()
            scene = self.scene()
            if scene is not None:
                rect = scene.sceneRect()
                if not rect.isEmpty() and rect.width() > 0 and rect.height() > 0:
                    self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
                    scale = self.transform().m11()
                    self.fit_scale = scale if scale > 0 else 1.0
                    return
            self.fit_scale = 1.0
        finally:
            self._is_fitting = False

    def normalized_state(self) -> Optional[Tuple[float, float, float]]:
        """現在の表示状態を中心相対座標 (cx, cy) と相対倍率 zoom として返す"""
        scene = self.scene()
        if scene is None:
            return None
        rect = scene.sceneRect()
        if rect.isEmpty() or rect.width() <= 0 or rect.height() <= 0 or self.fit_scale <= 0:
            return None

        center = self.mapToScene(self.viewport().rect().center())
        cx = (center.x() - rect.left()) / rect.width()
        cy = (center.y() - rect.top()) / rect.height()
        zoom = self.transform().m11() / self.fit_scale
        return (cx, cy, zoom)

    def apply_normalized_state(self, cx: float, cy: float, zoom: float) -> None:
        """正規化された中心相対座標 (cx, cy) と相対倍率 zoom を適用"""
        scene = self.scene()
        if scene is None:
            return
        rect = scene.sceneRect()
        if rect.isEmpty() or rect.width() <= 0 or rect.height() <= 0 or self.fit_scale <= 0:
            return

        self._is_applying = True
        try:
            target_scale = self.fit_scale * zoom
            self.resetTransform()
            self.scale(target_scale, target_scale)
            target_x = rect.left() + cx * rect.width()
            target_y = rect.top() + cy * rect.height()
            self.centerOn(target_x, target_y)
        finally:
            self._is_applying = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return

        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        factor = zoom_in_factor if delta > 0 else zoom_out_factor

        current_zoom = self.transform().m11() / self.fit_scale if self.fit_scale > 0 else 1.0
        target_zoom = current_zoom * factor
        clamped_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, target_zoom))
        actual_factor = clamped_zoom / current_zoom if current_zoom > 0 else 1.0

        if abs(actual_factor - 1.0) > 1e-5:
            self._in_wheel = True
            try:
                self.scale(actual_factor, actual_factor)
                self.changed.emit()
            finally:
                self._in_wheel = False

        event.accept()

    def _sync_zoom(self, zoom_factor: float) -> None:
        """互換性のための内部メソッド"""
        self.scale(zoom_factor, zoom_factor)

    def _on_scroll(self) -> None:
        if self._in_wheel or self._is_fitting or self._is_applying:
            return
        self.changed.emit()

    def _sync_scroll(self, h_val: int, v_val: int) -> None:
        """互換性のための内部メソッド"""
        self.horizontalScrollBar().setValue(h_val)
        self.verticalScrollBar().setValue(v_val)
