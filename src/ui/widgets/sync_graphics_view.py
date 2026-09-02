"""
同期パン＆ズーム機能を備えた QGraphicsView
"""

from PySide6.QtWidgets import QGraphicsView
from PySide6.QtGui import QWheelEvent
from PySide6.QtCore import Signal, QPointF


class SyncGraphicsView(QGraphicsView):
    """パートナービューとパン（スクロール）およびズームを同期する QGraphicsView"""

    zoomed = Signal(float, QPointF)
    scrolled = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(self.renderHints())
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.partner_view = None
        self._is_syncing = False

        self.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_partner(self, partner: 'SyncGraphicsView') -> None:
        """同期対象のパートナービューを設定"""
        self.partner_view = partner

    def wheelEvent(self, event: QWheelEvent) -> None:
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)

        if self.partner_view and not self._is_syncing:
            self._is_syncing = True
            self.partner_view._sync_zoom(zoom_factor)
            self._is_syncing = False

        event.accept()

    def _sync_zoom(self, zoom_factor: float) -> None:
        self.scale(zoom_factor, zoom_factor)

    def _on_scroll(self) -> None:
        if self.partner_view and not self._is_syncing:
            self._is_syncing = True
            h_val = self.horizontalScrollBar().value()
            v_val = self.verticalScrollBar().value()
            self.partner_view._sync_scroll(h_val, v_val)
            self._is_syncing = False

    def _sync_scroll(self, h_val: int, v_val: int) -> None:
        self.horizontalScrollBar().setValue(h_val)
        self.verticalScrollBar().setValue(v_val)
