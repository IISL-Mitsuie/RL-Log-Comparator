"""
同種画像並列目視比較ビューウィジェット
自動ペアリングモード（統合曲線と報酬推移のエイリアス対応）および左右自由選択モード（個別画像クロス対比）をサポート
"""

import os
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton, QGraphicsScene,
    QCheckBox, QComboBox, QLabel
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from src.core.parsers.experiment import get_experiment_info
from src.core.parsers.image_pair import (
    detect_image_pairs, ImagePairItem, get_folder_image_list
)
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

        # 左側: 画像種別一覧リスト & コントロール
        left_box = QGroupBox("画像比較コントロール")
        left_layout = QVBoxLayout(left_box)
        left_layout.setSpacing(8)

        # 左右自由選択モード切替チェックボックス
        self.cb_manual_mode = QCheckBox("左右自由選択モード (個別切替)")
        self.cb_manual_mode.setToolTip("左右で異なる種類の画像を自由に選択して並列比較します")
        self.cb_manual_mode.toggled.connect(self._on_manual_mode_toggled)
        left_layout.addWidget(self.cb_manual_mode)

        # ペアリング画像リスト（自動モード用）
        left_layout.addWidget(QLabel("画像ペア一覧:"))
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

        # 実験 A ボックス
        self.box_a = QGroupBox("実験 A")
        lay_a = QVBoxLayout(self.box_a)
        lay_a.setSpacing(6)

        # A側画像選択コンボ（自由選択モード用）
        self.combo_img_a = QComboBox()
        self.combo_img_a.setToolTip("実験 A の画像を選択")
        self.combo_img_a.currentIndexChanged.connect(self._on_combo_a_changed)
        self.combo_img_a.setVisible(False)
        lay_a.addWidget(self.combo_img_a)

        self.scene_a = QGraphicsScene()
        self.view_a = SyncGraphicsView(self.scene_a)
        lay_a.addWidget(self.view_a)
        right_splitter.addWidget(self.box_a)

        # 実験 B ボックス
        self.box_b = QGroupBox("実験 B")
        lay_b = QVBoxLayout(self.box_b)
        lay_b.setSpacing(6)

        # B側画像選択コンボ（自由選択モード用）
        self.combo_img_b = QComboBox()
        self.combo_img_b.setToolTip("実験 B の画像を選択")
        self.combo_img_b.currentIndexChanged.connect(self._on_combo_b_changed)
        self.combo_img_b.setVisible(False)
        lay_b.addWidget(self.combo_img_b)

        self.scene_b = QGraphicsScene()
        self.view_b = SyncGraphicsView(self.scene_b)
        lay_b.addWidget(self.view_b)
        right_splitter.addWidget(self.box_b)

        self.view_a.set_partner(self.view_b)
        self.view_b.set_partner(self.view_a)

        self.main_splitter.addWidget(right_splitter)
        self.main_splitter.setSizes([260, 980])

        main_layout.addWidget(self.main_splitter)

    def _on_manual_mode_toggled(self, checked: bool) -> None:
        """左右自由選択モードの切り替え"""
        self.combo_img_a.setVisible(checked)
        self.combo_img_b.setVisible(checked)
        self.list_images.setEnabled(not checked)

        if checked:
            # 自由選択モードON時: 各コンボの選択画像を即時表示
            self._on_combo_a_changed()
            self._on_combo_b_changed()
        else:
            # 自動ペアモード復帰時: リストの選択画像を即時表示
            self._on_image_selected(self.list_images.currentRow())

    def load_folders(self, folder_a: str, folder_b: str) -> None:
        """フォルダA/Bを設定し画像ペア一覧および個別画像リストを走査・更新"""
        self.folder_a = folder_a
        self.folder_b = folder_b

        info_a = get_experiment_info(folder_a)
        info_b = get_experiment_info(folder_b)
        self.box_a.setTitle(f"実験 A: {info_a}")
        self.box_b.setTitle(f"実験 B: {info_b}")

        self._detect_images()
        self._update_individual_combos()

    def _detect_images(self) -> None:
        """自動ペアリング一覧の構築"""
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

    def _update_individual_combos(self) -> None:
        """左右それぞれの個別画像コンボボックスを更新"""
        # A側
        self.combo_img_a.blockSignals(True)
        self.combo_img_a.clear()
        imgs_a = get_folder_image_list(self.folder_a)
        for _, title, path in imgs_a:
            self.combo_img_a.addItem(title, path)
        self.combo_img_a.blockSignals(False)

        # B側
        self.combo_img_b.blockSignals(True)
        self.combo_img_b.clear()
        imgs_b = get_folder_image_list(self.folder_b)
        for _, title, path in imgs_b:
            self.combo_img_b.addItem(title, path)
        self.combo_img_b.blockSignals(False)

        if self.cb_manual_mode.isChecked():
            self._on_combo_a_changed()
            self._on_combo_b_changed()

    def _on_image_selected(self, row: int) -> None:
        """自動ペアリストからの選択時"""
        if row < 0 or self.cb_manual_mode.isChecked():
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

    def _on_combo_a_changed(self) -> None:
        """A側個別コンボ選択時"""
        file_a = self.combo_img_a.currentData()
        self._show_image(self.scene_a, self.view_a, file_a)
        self._reset_views()

    def _on_combo_b_changed(self) -> None:
        """B側個別コンボ選択時"""
        file_b = self.combo_img_b.currentData()
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
