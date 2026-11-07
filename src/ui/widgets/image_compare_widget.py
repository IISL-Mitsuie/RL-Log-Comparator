"""
同種画像並列目視比較ビューウィジェット
自動ペアリングモード（統合曲線と報酬推移のエイリアス対応）および左右自由選択モード（個別画像クロス対比）をサポート
表示モード: 並列 / オーバーレイ / スワイプ / 差分
"""

import os
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton, QGraphicsScene,
    QCheckBox, QComboBox, QLabel, QStackedWidget, QSlider
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from src.core.parsers.experiment import get_experiment_info
from src.core.parsers.image_pair import (
    detect_image_pairs, get_folder_image_list, ImagePairItem
)
from src.ui.widgets.sync_graphics_view import (
    SyncGraphicsView, ViewSyncController
)
from src.ui.widgets.image_overlay_view import ImageOverlayView


class ImageCompareWidget(QWidget):
    """同種画像並列・重ね合わせ目視比較ビュー"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder_a = ""
        self.folder_b = ""
        self._current_file_a: Optional[str] = None
        self._current_file_b: Optional[str] = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側: 画像種別一覧リスト & コントロール
        left_box = QGroupBox("画像比較コントロール")
        left_layout = QVBoxLayout(left_box)
        left_layout.setSpacing(8)

        # 表示モード切替コンボボックス
        left_layout.addWidget(QLabel("表示モード:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("並列", "parallel")
        self.combo_mode.addItem("オーバーレイ", "overlay")
        self.combo_mode.addItem("スワイプ", "swipe")
        self.combo_mode.addItem("差分", "diff")
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        left_layout.addWidget(self.combo_mode)

        # モード別コントロール群
        # --- オーバーレイ用コントロール ---
        self.widget_overlay_ctrl = QWidget()
        lay_overlay = QVBoxLayout(self.widget_overlay_ctrl)
        lay_overlay.setContentsMargins(0, 0, 0, 0)
        lay_overlay.setSpacing(4)
        self.lbl_opacity = QLabel("不透明度 (B): 50%")
        lay_overlay.addWidget(self.lbl_opacity)
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(50)
        self.slider_opacity.valueChanged.connect(self._on_opacity_slider_changed)
        lay_overlay.addWidget(self.slider_opacity)
        self.widget_overlay_ctrl.setVisible(False)
        left_layout.addWidget(self.widget_overlay_ctrl)

        # --- スワイプ用コントロール ---
        self.widget_swipe_ctrl = QWidget()
        lay_swipe = QVBoxLayout(self.widget_swipe_ctrl)
        lay_swipe.setContentsMargins(0, 0, 0, 0)
        lay_swipe.setSpacing(4)
        self.lbl_swipe = QLabel("スワイプ境界位置: 50%")
        lay_swipe.addWidget(self.lbl_swipe)
        self.slider_swipe = QSlider(Qt.Orientation.Horizontal)
        self.slider_swipe.setRange(0, 100)
        self.slider_swipe.setValue(50)
        self.slider_swipe.valueChanged.connect(self._on_swipe_slider_changed)
        lay_swipe.addWidget(self.slider_swipe)
        self.widget_swipe_ctrl.setVisible(False)
        left_layout.addWidget(self.widget_swipe_ctrl)

        # --- 差分用コントロール ---
        self.widget_diff_ctrl = QWidget()
        lay_diff = QVBoxLayout(self.widget_diff_ctrl)
        lay_diff.setContentsMargins(0, 0, 0, 0)
        lay_diff.setSpacing(4)
        lay_diff.addWidget(QLabel("差分増幅率:"))
        self.combo_diff_gain = QComboBox()
        self.combo_diff_gain.addItem("×1", 1.0)
        self.combo_diff_gain.addItem("×2", 2.0)
        self.combo_diff_gain.addItem("×3", 3.0)
        self.combo_diff_gain.addItem("×5", 5.0)
        self.combo_diff_gain.addItem("×10", 10.0)
        self.combo_diff_gain.currentIndexChanged.connect(self._on_diff_gain_changed)
        lay_diff.addWidget(self.combo_diff_gain)
        self.lbl_diff_ratio = QLabel("差分画素: 0.0%")
        lay_diff.addWidget(self.lbl_diff_ratio)
        self.widget_diff_ctrl.setVisible(False)
        left_layout.addWidget(self.widget_diff_ctrl)

        # --- リサイズ注記ラベル ---
        self.lbl_resize_notice = QLabel("")
        self.lbl_resize_notice.setWordWrap(True)
        self.lbl_resize_notice.setStyleSheet("color: #666666; font-size: 11px;")
        self.lbl_resize_notice.setVisible(False)
        left_layout.addWidget(self.lbl_resize_notice)

        # 左右自由選択モード切替チェックボックス
        self.cb_manual_mode = QCheckBox("左右自由選択モード (個別切替)")
        self.cb_manual_mode.setToolTip("左右で異なる種類の画像を自由に選択して比較します")
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

        # 右側: QStackedWidget による表示切替（0: 並列, 1: 重ね合わせ）
        self.right_stack = QStackedWidget()

        # ページ 0: 左右並列プレビュー
        self.right_splitter = QSplitter(Qt.Orientation.Horizontal)

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
        self.right_splitter.addWidget(self.box_a)

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
        self.right_splitter.addWidget(self.box_b)

        self.sync_controller = ViewSyncController(self)
        self.sync_controller.register(self.view_a, self.view_b)

        self.right_stack.addWidget(self.right_splitter)

        # ページ 1: 重ね合わせプレビュー (ImageOverlayView)
        self.overlay_view = ImageOverlayView()
        self.overlay_view.diff_ratio_changed.connect(self._on_diff_ratio_changed)
        self.overlay_view.resize_notice_changed.connect(self._on_resize_notice_changed)
        self.overlay_view.swipe_position_changed.connect(self._on_swipe_position_changed)
        self.right_stack.addWidget(self.overlay_view)

        self.main_splitter.addWidget(self.right_stack)
        self.main_splitter.setSizes([260, 980])

        main_layout.addWidget(self.main_splitter)

    def _has_both_images(self) -> bool:
        """A側とB側の両方に有効な画像が存在するかを判定"""
        return bool(
            self._current_file_a and os.path.exists(self._current_file_a) and
            self._current_file_b and os.path.exists(self._current_file_b)
        )

    def _update_mode_availability(self) -> None:
        """両画像が存在しない場合、重ねるモードを無効化し並列に戻す"""
        has_both = self._has_both_images()
        model = self.combo_mode.model()

        # index 1: overlay, 2: swipe, 3: diff
        for i in range(1, 4):
            item = model.item(i) if hasattr(model, "item") else None
            if item is not None:
                flags = item.flags()
                if has_both:
                    item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                else:
                    item.setFlags(flags & ~Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsSelectable)

        # 片側しかない状態で重ねるモードが選択されていたら並列に戻す
        if not has_both and self.combo_mode.currentIndex() != 0:
            self.combo_mode.setCurrentIndex(0)

    def _on_mode_changed(self) -> None:
        """表示モード切り替え処理"""
        mode_data = self.combo_mode.currentData()
        if not self._has_both_images() and mode_data != "parallel":
            self.combo_mode.setCurrentIndex(0)
            return

        is_parallel = (mode_data == "parallel")
        self.right_stack.setCurrentIndex(0 if is_parallel else 1)

        self.widget_overlay_ctrl.setVisible(mode_data == "overlay")
        self.widget_swipe_ctrl.setVisible(mode_data == "swipe")
        self.widget_diff_ctrl.setVisible(mode_data == "diff")

        if not is_parallel:
            self.overlay_view.set_mode(mode_data)
            self._update_overlay_params()
            self._update_resize_notice_display()
            self.overlay_view.fit_to_scene()
        else:
            self.lbl_resize_notice.setVisible(False)

    def _on_opacity_slider_changed(self, value: int) -> None:
        self.lbl_opacity.setText(f"不透明度 (B): {value}%")
        self.overlay_view.set_opacity(value / 100.0)

    def _on_swipe_slider_changed(self, value: int) -> None:
        self.lbl_swipe.setText(f"スワイプ境界位置: {value}%")
        self.overlay_view.set_swipe_position(value / 100.0)

    def _on_swipe_position_changed(self, ratio: float) -> None:
        val = int(round(ratio * 100))
        self.slider_swipe.blockSignals(True)
        self.slider_swipe.setValue(val)
        self.slider_swipe.blockSignals(False)
        self.lbl_swipe.setText(f"スワイプ境界位置: {val}%")

    def _on_diff_gain_changed(self) -> None:
        gain = self.combo_diff_gain.currentData()
        if gain is not None:
            self.overlay_view.set_diff_gain(float(gain))

    def _on_diff_ratio_changed(self, ratio: float) -> None:
        self.lbl_diff_ratio.setText(f"差分画素: {ratio * 100:.1f}%")

    def _on_resize_notice_changed(self, notice: str) -> None:
        self._update_resize_notice_display()

    def _update_resize_notice_display(self) -> None:
        notice = self.overlay_view.get_resize_notice()
        if notice and self.combo_mode.currentData() != "parallel":
            self.lbl_resize_notice.setText(f"※{notice}")
            self.lbl_resize_notice.setVisible(True)
        else:
            self.lbl_resize_notice.setText("")
            self.lbl_resize_notice.setVisible(False)

    def _update_overlay_params(self) -> None:
        self.overlay_view.set_opacity(self.slider_opacity.value() / 100.0)
        self.overlay_view.set_swipe_position(self.slider_swipe.value() / 100.0)
        gain = self.combo_diff_gain.currentData()
        if gain is not None:
            self.overlay_view.set_diff_gain(float(gain))

    def _on_manual_mode_toggled(self, checked: bool) -> None:
        """左右自由選択モードの切り替え"""
        self.combo_img_a.setVisible(checked)
        self.combo_img_b.setVisible(checked)
        self.list_images.setEnabled(not checked)

        if checked:
            self._update_current_images_from_combos()
        else:
            self._on_image_selected(self.list_images.currentRow())

    def apply_data(
        self,
        folder_a: str,
        folder_b: str,
        info_a: str,
        info_b: str,
        pairs: list[ImagePairItem],
        imgs_a: list[tuple[str, str, str]],
        imgs_b: list[tuple[str, str, str]],
    ) -> None:
        """解析済みの画像データを反映"""
        self.folder_a = folder_a
        self.folder_b = folder_b

        self.box_a.setTitle(f"実験 A: {info_a}")
        self.box_b.setTitle(f"実験 B: {info_b}")

        self._apply_detected_pairs(pairs)
        self._apply_individual_combos(imgs_a, imgs_b)

    def load_folders(self, folder_a: str, folder_b: str) -> None:
        """フォルダA/Bを設定し画像ペア一覧および個別画像リストを走査・更新（互換性のために維持）"""
        info_a = get_experiment_info(folder_a)
        info_b = get_experiment_info(folder_b)
        pairs = detect_image_pairs(folder_a, folder_b)
        imgs_a = get_folder_image_list(folder_a)
        imgs_b = get_folder_image_list(folder_b)
        self.apply_data(folder_a, folder_b, info_a, info_b, pairs, imgs_a, imgs_b)

    def _detect_images(self) -> None:
        """自動ペアリング一覧の構築（同期走査）"""
        pairs = detect_image_pairs(self.folder_a, self.folder_b)
        self._apply_detected_pairs(pairs)

    def _apply_detected_pairs(self, pairs: list[ImagePairItem]) -> None:
        """自動ペアリング一覧の構築（データ適用）"""
        self.list_images.blockSignals(True)
        self.list_images.clear()

        for pair in pairs:
            item = QListWidgetItem(pair.display_text)
            item.setData(Qt.ItemDataRole.UserRole, (pair.file_a, pair.file_b))
            self.list_images.addItem(item)

        self.list_images.blockSignals(False)

        if self.list_images.count() > 0:
            self.list_images.setCurrentRow(0)
            self._on_image_selected(0)
        else:
            self._current_file_a = None
            self._current_file_b = None
            self.scene_a.clear()
            self.scene_b.clear()
            self.overlay_view.set_images(None, None)
            self._update_mode_availability()

    def _update_individual_combos(self) -> None:
        """左右それぞれの個別画像コンボボックスを更新（同期走査）"""
        imgs_a = get_folder_image_list(self.folder_a)
        imgs_b = get_folder_image_list(self.folder_b)
        self._apply_individual_combos(imgs_a, imgs_b)

    def _apply_individual_combos(
        self, imgs_a: list[tuple[str, str, str]], imgs_b: list[tuple[str, str, str]]
    ) -> None:
        """左右それぞれの個別画像コンボボックスを更新（データ適用）"""
        # A側
        self.combo_img_a.blockSignals(True)
        self.combo_img_a.clear()
        for _, title, path in imgs_a:
            self.combo_img_a.addItem(title, path)
        self.combo_img_a.blockSignals(False)

        # B側
        self.combo_img_b.blockSignals(True)
        self.combo_img_b.clear()
        for _, title, path in imgs_b:
            self.combo_img_b.addItem(title, path)
        self.combo_img_b.blockSignals(False)

        if self.cb_manual_mode.isChecked():
            self._update_current_images_from_combos()

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
        self._current_file_a = file_a
        self._current_file_b = file_b

        self._apply_current_images()

    def _on_combo_a_changed(self) -> None:
        if self.cb_manual_mode.isChecked():
            self._update_current_images_from_combos()

    def _on_combo_b_changed(self) -> None:
        if self.cb_manual_mode.isChecked():
            self._update_current_images_from_combos()

    def _update_current_images_from_combos(self) -> None:
        self._current_file_a = self.combo_img_a.currentData()
        self._current_file_b = self.combo_img_b.currentData()
        self._apply_current_images()

    def _apply_current_images(self) -> None:
        """現在の画像ファイルを左右ビューおよび重ね合わせビューに反映"""
        file_a = self._current_file_a
        file_b = self._current_file_b

        self._show_image(self.scene_a, self.view_a, file_a)
        self._show_image(self.scene_b, self.view_b, file_b)

        has_both = self._has_both_images()
        if has_both and file_a and file_b:
            pix_a = QPixmap(file_a)
            pix_b = QPixmap(file_b)
            self.overlay_view.set_images(pix_a, pix_b)
        else:
            self.overlay_view.set_images(None, None)

        self._update_mode_availability()
        self._update_resize_notice_display()
        self._reset_views()

    def _show_image(self, scene: QGraphicsScene, view: SyncGraphicsView, file_path: str | None) -> None:
        scene.clear()
        if file_path and os.path.exists(file_path):
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                item = scene.addPixmap(pixmap)
                item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
                scene.setSceneRect(pixmap.rect().toRectF())

    def _reset_views(self) -> None:
        """ズーム・位置リセット"""
        if self.combo_mode.currentData() == "parallel":
            self.view_a.fit_to_scene()
            self.view_b.fit_to_scene()
        else:
            self.overlay_view.fit_to_scene()
