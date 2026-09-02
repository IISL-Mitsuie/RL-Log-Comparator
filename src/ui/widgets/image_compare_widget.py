"""
同種画像並列目視比較ビューウィジェット
"""

import os
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton, QGraphicsScene
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from src.core.parsers.experiment import get_experiment_info
from src.core.parsers.image_pair import detect_image_pairs, ImagePairItem
from src.ui.widgets.sync_graphics_view import SyncGraphicsView


class ImageCompareWidget(QWidget):
    """同種画像並列目視比較ビュー"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder_a = ""
        self.folder_b = ""
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側: 画像種別一覧リスト
        left_box = QGroupBox("画像種別一覧 (常時表示)")
        left_layout = QVBoxLayout(left_box)

        self.list_images = QListWidget()
        self.list_images.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_images.currentRowChanged.connect(self._on_image_selected)
        left_layout.addWidget(self.list_images)

        btn_reset_zoom = QPushButton("ズーム・位置リセット")
        btn_reset_zoom.clicked.connect(self._reset_views)
        left_layout.addWidget(btn_reset_zoom)

        self.main_splitter.addWidget(left_box)

        # 右側: 左右並列画像プレビュー
        right_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.box_a = QGroupBox("実験 A")
        lay_a = QVBoxLayout(self.box_a)
        self.scene_a = QGraphicsScene()
        self.view_a = SyncGraphicsView(self.scene_a)
        lay_a.addWidget(self.view_a)
        right_splitter.addWidget(self.box_a)

        self.box_b = QGroupBox("実験 B")
        lay_b = QVBoxLayout(self.box_b)
        self.scene_b = QGraphicsScene()
        self.view_b = SyncGraphicsView(self.scene_b)
        lay_b.addWidget(self.view_b)
        right_splitter.addWidget(self.box_b)

        self.view_a.set_partner(self.view_b)
        self.view_b.set_partner(self.view_a)

        self.main_splitter.addWidget(right_splitter)
        self.main_splitter.setSizes([240, 1000])

        main_layout.addWidget(self.main_splitter)

    def load_folders(self, folder_a: str, folder_b: str) -> None:
        """フォルダA/Bを設定し画像ペア一覧を走査・表示"""
        self.folder_a = folder_a
        self.folder_b = folder_b

        info_a = get_experiment_info(folder_a)
        info_b = get_experiment_info(folder_b)
        self.box_a.setTitle(f"実験 A: {info_a}")
        self.box_b.setTitle(f"実験 B: {info_b}")

        self._detect_images()

    def _detect_images(self) -> None:
        self.list_images.blockSignals(True)
        self.list_images.clear()

        pairs = detect_image_pairs(self.folder_a, self.folder_b)

        for pair in pairs:
            item = QListWidgetItem(pair.display_text)
            item.setData(Qt.ItemDataRole.UserRole, (pair.file_a, pair.file_b))
            self.list_images.addItem(item)

        self.list_images.blockSignals(False)

        if self.list_images.count() > 0:
            self.list_images.setCurrentRow(0)
        else:
            self.scene_a.clear()
            self.scene_b.clear()

    def _on_image_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self.list_images.item(row)
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        file_a, file_b = data

        self._show_image(self.scene_a, self.view_a, file_a)
        self._show_image(self.scene_b, self.view_b, file_b)
        self._reset_views()

    def _show_image(self, scene: QGraphicsScene, view: SyncGraphicsView, file_path: str | None) -> None:
        scene.clear()
        if file_path and os.path.exists(file_path):
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scene.addPixmap(pixmap)
                scene.setSceneRect(pixmap.rect().toRectF())

    def _reset_views(self) -> None:
        self.view_a.resetTransform()
        self.view_b.resetTransform()
        if not self.scene_a.itemsBoundingRect().isEmpty():
            self.view_a.fitInView(self.scene_a.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        if not self.scene_b.itemsBoundingRect().isEmpty():
            self.view_b.fitInView(self.scene_b.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
