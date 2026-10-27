"""
重ね合わせ画像表示ビュー (オーバーレイ・スワイプ・差分)
"""

from typing import Optional
import numpy as np
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QGraphicsLineItem, QGraphicsItem
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QWheelEvent,
    QMouseEvent
)
from PySide6.QtCore import Qt, QRectF, Signal, QPointF

from src.core.image_diff import compute_abs_diff, diff_ratio


def qpixmap_to_rgba_array(pixmap: QPixmap) -> np.ndarray:
    """QPixmap を RGBA uint8 の numpy 配列 (H, W, 4) に変換"""
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = image.width(), image.height()
    bpl = image.bytesPerLine()
    ptr = image.bits()
    raw = np.frombuffer(ptr, dtype=np.uint8).copy().reshape((h, bpl))
    return np.ascontiguousarray(raw[:, :w * 4].reshape((h, w, 4)))


def rgba_array_to_qpixmap(arr: np.ndarray) -> QPixmap:
    """RGBA uint8 の numpy 配列 (H, W, 4) を QPixmap に変換"""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w, _ = arr.shape
    image = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(image.copy())


class ImageOverlayView(QGraphicsView):
    """重ね合わせ表示ビュー（オーバーレイ、スワイプ、差分）"""

    MIN_ZOOM: float = 0.1
    MAX_ZOOM: float = 40.0

    # シグナル
    diff_ratio_changed = Signal(float)
    resize_notice_changed = Signal(str)
    swipe_position_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # レンダリング設定 & ドラッグ設定
        self.setRenderHints(
            QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)

        self.fit_scale: float = 1.0

        # 状態パラメータ
        self._mode: str = "overlay"  # "overlay", "swipe", "diff"
        self._opacity: float = 0.5   # 0.0 〜 1.0
        self._swipe_ratio: float = 0.5  # 0.0 〜 1.0
        self._diff_gain: float = 1.0  # 1.0 〜 10.0

        self._pix_a_orig: Optional[QPixmap] = None
        self._pix_b_orig: Optional[QPixmap] = None
        self._pix_b_scaled: Optional[QPixmap] = None

        self._arr_a: Optional[np.ndarray] = None
        self._arr_b: Optional[np.ndarray] = None

        self._resize_notice: str = ""
        self._diff_ratio: float = 0.0

        self._base_width: int = 0
        self._base_height: int = 0

        self._is_dragging_swipe: bool = False

        # シーンアイテムの初期化
        # A: 背景画像
        self.item_a = QGraphicsPixmapItem()
        self.item_a.setZValue(1)
        self.item_a.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self.item_a)

        # B: 前景画像（クリッピング親アイテムを持つ）
        self.clip_item = QGraphicsRectItem()
        self.clip_item.setZValue(2)
        self.clip_item.setPen(Qt.PenStyle.NoPen)
        self.clip_item.setBrush(Qt.BrushStyle.NoBrush)
        self.clip_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        self._scene.addItem(self.clip_item)

        self.item_b = QGraphicsPixmapItem(self.clip_item)
        self.item_b.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

        # 差分表示用アイテム
        self.item_diff = QGraphicsPixmapItem()
        self.item_diff.setZValue(3)
        self.item_diff.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.item_diff.setVisible(False)
        self._scene.addItem(self.item_diff)

        # スワイプ境界線アイテム
        self.swipe_line = QGraphicsLineItem()
        self.swipe_line.setZValue(10)
        line_pen = QPen(QColor(255, 255, 255, 240), 2)
        self.swipe_line.setPen(line_pen)
        self.swipe_line.setVisible(False)
        self._scene.addItem(self.swipe_line)

    def set_images(self, pix_a: Optional[QPixmap], pix_b: Optional[QPixmap]) -> None:
        """比較する 2 枚の画像を設定"""
        self._pix_a_orig = pix_a
        self._pix_b_orig = pix_b

        if pix_a is None or pix_a.isNull() or pix_b is None or pix_b.isNull():
            self._clear_view()
            return

        w_a = pix_a.width()
        h_a = pix_a.height()
        w_b = pix_b.width()
        h_b = pix_b.height()

        self._base_width = w_a
        self._base_height = h_a
        self._scene.setSceneRect(0, 0, w_a, h_a)

        # サイズ調整（B を A の大きさに合わせる）
        if w_a == w_b and h_a == h_b:
            self._pix_b_scaled = pix_b
            self._resize_notice = ""
        else:
            scaled_b = pix_b.scaled(
                w_a, h_a,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            bw = scaled_b.width()
            bh = scaled_b.height()

            canvas = QPixmap(w_a, h_a)
            canvas.fill(Qt.GlobalColor.transparent)
            painter = QPainter(canvas)
            ox = (w_a - bw) // 2
            oy = (h_a - bh) // 2
            painter.drawPixmap(ox, oy, scaled_b)
            painter.end()

            self._pix_b_scaled = canvas
            action = "縮小" if (bw < w_b or bh < h_b) else "拡大"
            self._resize_notice = f"B を {w_b}×{h_b} → {bw}×{bh} に{action}して重ねています"

        self.resize_notice_changed.emit(self._resize_notice)

        # Pixmap アイテムにセット
        self.item_a.setPixmap(pix_a)
        self.item_b.setPixmap(self._pix_b_scaled)

        # 差分用 numpy 配列の作成
        self._arr_a = qpixmap_to_rgba_array(pix_a)
        self._arr_b = qpixmap_to_rgba_array(self._pix_b_scaled)
        try:
            self._diff_ratio = diff_ratio(self._arr_a, self._arr_b, threshold=16)
        except Exception:
            self._diff_ratio = 0.0
        self.diff_ratio_changed.emit(self._diff_ratio)

        self._update_display()
        self.fit_to_scene()

    def _clear_view(self) -> None:
        self.item_a.setPixmap(QPixmap())
        self.item_b.setPixmap(QPixmap())
        self.item_diff.setPixmap(QPixmap())
        self._pix_b_scaled = None
        self._arr_a = None
        self._arr_b = None
        self._resize_notice = ""
        self._diff_ratio = 0.0
        self._base_width = 0
        self._base_height = 0
        self.resize_notice_changed.emit("")
        self.diff_ratio_changed.emit(0.0)
        self._scene.setSceneRect(QRectF())

    def set_mode(self, mode: str) -> None:
        """表示モードを設定 ('overlay', 'swipe', 'diff')"""
        if mode not in ("overlay", "swipe", "diff"):
            return
        self._mode = mode
        self._update_display()

    def set_opacity(self, value: float) -> None:
        """オーバーレイ時の B の不透明度を設定 (0.0〜1.0 または 0〜100)"""
        if value > 1.0:
            value = value / 100.0
        self._opacity = max(0.0, min(1.0, float(value)))
        if self._mode == "overlay":
            self.item_b.setOpacity(self._opacity)

    def set_swipe_position(self, ratio: float) -> None:
        """スワイプ境界線の位置を設定 (0.0〜1.0)"""
        self._swipe_ratio = max(0.0, min(1.0, float(ratio)))
        if self._mode == "swipe":
            self._apply_swipe_layout()

    def set_diff_gain(self, gain: float) -> None:
        """差分表示の増幅率を設定 (>= 1.0)"""
        self._diff_gain = max(1.0, float(gain))
        if self._mode == "diff":
            self._update_diff_pixmap()

    def get_diff_ratio(self) -> float:
        """計算済みの差分画素割合を取得"""
        return self._diff_ratio

    def get_resize_notice(self) -> str:
        """画像リサイズの注記を取得"""
        return self._resize_notice

    def _update_display(self) -> None:
        """現在のモードに応じて表示を切り替え"""
        if self._pix_a_orig is None or self._pix_b_scaled is None:
            return

        w = self._base_width
        h = self._base_height

        if self._mode == "overlay":
            self.item_a.setVisible(True)
            self.clip_item.setVisible(True)
            self.clip_item.setRect(0, 0, w, h)
            self.item_b.setOpacity(self._opacity)
            self.swipe_line.setVisible(False)
            self.item_diff.setVisible(False)

        elif self._mode == "swipe":
            self.item_a.setVisible(True)
            self.clip_item.setVisible(True)
            self.item_b.setOpacity(1.0)
            self._apply_swipe_layout()
            self.swipe_line.setVisible(True)
            self.item_diff.setVisible(False)

        elif self._mode == "diff":
            self.item_a.setVisible(False)
            self.clip_item.setVisible(False)
            self.swipe_line.setVisible(False)
            self._update_diff_pixmap()
            self.item_diff.setVisible(True)

    def _apply_swipe_layout(self) -> None:
        """スワイプ境界線とクリップ領域の更新"""
        w = self._base_width
        h = self._base_height
        x = self._swipe_ratio * w

        # 左側に A、右側に B を表示するため、B は [x, w] にクリップ
        self.clip_item.setRect(x, 0, max(0.0, w - x), h)
        self.swipe_line.setLine(x, 0, x, h)

    def _update_diff_pixmap(self) -> None:
        """差分画像を再生成して item_diff にセット"""
        if self._arr_a is None or self._arr_b is None:
            return
        try:
            diff_arr = compute_abs_diff(self._arr_a, self._arr_b, gain=self._diff_gain)
            pix = rgba_array_to_qpixmap(diff_arr)
            self.item_diff.setPixmap(pix)
        except Exception:
            self.item_diff.setPixmap(QPixmap())

    def fit_to_scene(self) -> None:
        """シーン全体がビューに収まるようにスケールと位置をリセット"""
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

    def wheelEvent(self, event: QWheelEvent) -> None:
        """SyncGraphicsView と同等のズーム処理"""
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
            self.scale(actual_factor, actual_factor)

        event.accept()

    def _is_near_swipe_line(self, pos) -> bool:
        """ビュー座標 pos がスワイプ境界線の近傍にあるかを判定"""
        if self._mode != "swipe" or self._base_width <= 0:
            return False
        scene_x = self._swipe_ratio * self._base_width
        view_point = self.mapFromScene(QPointF(scene_x, 0))
        return abs(pos.x() - view_point.x()) <= 8

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_near_swipe_line(event.pos()):
            self._is_dragging_swipe = True
            self.setCursor(Qt.CursorShape.SplitHCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging_swipe:
            if self._base_width > 0:
                scene_pos = self.mapToScene(event.pos())
                ratio = max(0.0, min(1.0, scene_pos.x() / self._base_width))
                self.set_swipe_position(ratio)
                self.swipe_position_changed.emit(ratio)
            event.accept()
            return

        if self._mode == "swipe" and self._is_near_swipe_line(event.pos()):
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging_swipe:
            self._is_dragging_swipe = False
            if self._is_near_swipe_line(event.pos()):
                self.setCursor(Qt.CursorShape.SplitHCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
