"""
論文用図表書き出しダイアログ
指定された寸法（cm / inch）、解像度 (DPI)、フォントサイズ、形式 (PNG / PDF / SVG) で
画面外 Figure を生成し、高品質な図表を書き出す。
"""

import logging
import os
from typing import Callable
import matplotlib as mpl
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QRadioButton, QButtonGroup
)

from src.ui.theme import LIGHT

logger = logging.getLogger(__name__)


# プリセット定義: (表示名, 幅cm, 高さcm)
PRESETS = [
    ("1 段組 (8.5 × 6 cm)", 8.5, 6.0),
    ("2 段組 (17 × 8 cm)", 17.0, 8.0),
    ("スライド 16:9 (25.4 × 14.3 cm)", 25.4, 14.3),
    ("カスタム", None, None),
]


def export_figure(
    filepath: str,
    render_func: Callable[[object], bool],
    chart_spec: object,
    width_inch: float,
    height_inch: float,
    dpi: int = 300,
    base_font_size: int = 9,
    show_legend: bool = True,
    show_grid: bool = True,
) -> bool:
    """
    画面外 Figure を構築し、LIGHT テーマおよび指定されたパラメータで図表を保存する。
    - bbox_inches='tight' は使用せず、指定された寸法・解像度を厳密に維持する。
    - pdf.fonttype / ps.fonttype = 42 (TrueType) で保存し、Type 3 フォントの混入を防ぐ。
    """
    import dataclasses

    fig = Figure(figsize=(width_inch, height_inch), dpi=dpi, facecolor=LIGHT.chart_bg)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111, facecolor=LIGHT.chart_bg)

    # 論文エクスポート用の ChartSpec を生成（常に LIGHT テーマを使用）
    export_spec = dataclasses.replace(
        chart_spec,
        font_label=base_font_size,
        font_ticks=max(5, base_font_size - 1),
        font_title=base_font_size + 1,
        font_legend=max(5, base_font_size - 1),
        theme=LIGHT,
        show_legend=show_legend,
        show_grid=show_grid,
    )

    with mpl.rc_context({
        "font.size": base_font_size,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "path",
    }):
        render_func(ax, export_spec)
        fig.tight_layout()
        fig.savefig(filepath, dpi=dpi)

    return True


class FigureExportDialog(QDialog):
    """論文用図表書き出し設定ダイアログ"""

    def __init__(self, parent=None, chart_spec=None, render_func=None):
        super().__init__(parent)
        self.setWindowTitle("📄 論文用に書き出し")
        self.resize(460, 420)
        self.chart_spec = chart_spec
        self.render_func = render_func
        self._updating_preset = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. プリセット選択
        group_preset = QGroupBox("プリセット")
        lay_preset = QHBoxLayout(group_preset)
        self.combo_preset = QComboBox()
        for name, _, _ in PRESETS:
            self.combo_preset.addItem(name)
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        lay_preset.addWidget(QLabel("サイズプリセット:"))
        lay_preset.addWidget(self.combo_preset, 1)
        layout.addWidget(group_preset)

        # 2. 寸法・単位設定
        group_size = QGroupBox("寸法設定")
        grid_size = QGridLayout(group_size)
        grid_size.setSpacing(8)

        self.btn_unit_cm = QRadioButton("cm (センチメートル)")
        self.btn_unit_inch = QRadioButton("inch (インチ)")
        self.btn_unit_cm.setChecked(True)
        self.unit_group = QButtonGroup(self)
        self.unit_group.addButton(self.btn_unit_cm)
        self.unit_group.addButton(self.btn_unit_inch)
        self.btn_unit_cm.toggled.connect(self._on_unit_toggled)

        lay_units = QHBoxLayout()
        lay_units.addWidget(self.btn_unit_cm)
        lay_units.addWidget(self.btn_unit_inch)
        lay_units.addStretch()
        grid_size.addLayout(lay_units, 0, 0, 1, 2)

        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(1.0, 100.0)
        self.spin_width.setDecimals(2)
        self.spin_width.setValue(8.5)
        self.spin_width.valueChanged.connect(self._on_custom_dimension_changed)

        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(1.0, 100.0)
        self.spin_height.setDecimals(2)
        self.spin_height.setValue(6.0)
        self.spin_height.valueChanged.connect(self._on_custom_dimension_changed)

        self.lbl_width = QLabel("幅 (cm):")
        self.lbl_height = QLabel("高さ (cm):")

        grid_size.addWidget(self.lbl_width, 1, 0)
        grid_size.addWidget(self.spin_width, 1, 1)
        grid_size.addWidget(self.lbl_height, 2, 0)
        grid_size.addWidget(self.spin_height, 2, 1)

        layout.addWidget(group_size)

        # 3. 出力オプション
        group_opt = QGroupBox("描画・解像度オプション")
        grid_opt = QGridLayout(group_opt)
        grid_opt.setSpacing(8)

        grid_opt.addWidget(QLabel("ファイル形式:"), 0, 0)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["PNG (*.png)", "PDF (*.pdf)", "SVG (*.svg)"])
        grid_opt.addWidget(self.combo_format, 0, 1)

        grid_opt.addWidget(QLabel("解像度 (DPI):"), 1, 0)
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 1200)
        self.spin_dpi.setValue(300)
        grid_opt.addWidget(self.spin_dpi, 1, 1)

        grid_opt.addWidget(QLabel("基本フォントサイズ (pt):"), 2, 0)
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(5, 36)
        self.spin_font_size.setValue(9)
        grid_opt.addWidget(self.spin_font_size, 2, 1)

        self.cb_legend = QCheckBox("凡例を含める")
        self.cb_legend.setChecked(True)
        grid_opt.addWidget(self.cb_legend, 3, 0)

        self.cb_grid = QCheckBox("グリッドを表示")
        self.cb_grid.setChecked(True)
        grid_opt.addWidget(self.cb_grid, 3, 1)

        layout.addWidget(group_opt)

        # ボタン
        lay_btns = QHBoxLayout()
        lay_btns.addStretch()
        self.btn_cancel = QPushButton("キャンセル")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_export = QPushButton("書き出し…")
        self.btn_export.setDefault(True)
        self.btn_export.clicked.connect(self._on_export_clicked)

        lay_btns.addWidget(self.btn_cancel)
        lay_btns.addWidget(self.btn_export)
        layout.addLayout(lay_btns)

    def _on_unit_toggled(self, is_cm: bool):
        """cm と inch の切り替えに伴う数値とラベルの更新"""
        self._updating_preset = True
        w = self.spin_width.value()
        h = self.spin_height.value()
        if is_cm:
            # inch -> cm
            self.lbl_width.setText("幅 (cm):")
            self.lbl_height.setText("高さ (cm):")
            self.spin_width.setValue(round(w * 2.54, 2))
            self.spin_height.setValue(round(h * 2.54, 2))
        else:
            # cm -> inch
            self.lbl_width.setText("幅 (inch):")
            self.lbl_height.setText("高さ (inch):")
            self.spin_width.setValue(round(w / 2.54, 2))
            self.spin_height.setValue(round(h / 2.54, 2))
        self._updating_preset = False

    def _on_preset_changed(self, idx: int):
        """プリセット選択時の寸法反映"""
        if self._updating_preset:
            return
        _, w_cm, h_cm = PRESETS[idx]
        if w_cm is None:
            return  # カスタム
        self._updating_preset = True
        is_cm = self.btn_unit_cm.isChecked()
        if is_cm:
            self.spin_width.setValue(w_cm)
            self.spin_height.setValue(h_cm)
        else:
            self.spin_width.setValue(round(w_cm / 2.54, 2))
            self.spin_height.setValue(round(h_cm / 2.54, 2))
        self._updating_preset = False

    def _on_custom_dimension_changed(self, _=0):
        """手動変更時にプリセットを「カスタム」に切り替え"""
        if self._updating_preset:
            return
        self._updating_preset = True
        self.combo_preset.setCurrentIndex(len(PRESETS) - 1)
        self._updating_preset = False

    def get_dimensions_inch(self) -> tuple[float, float]:
        """設定された寸法を inch 単位で返す"""
        w = self.spin_width.value()
        h = self.spin_height.value()
        if self.btn_unit_cm.isChecked():
            return w / 2.54, h / 2.54
        return w, h

    def _on_export_clicked(self):
        """ファイル保存ダイアログを開いてエクスポート実行"""
        fmt_idx = self.combo_format.currentIndex()
        if fmt_idx == 0:
            ext = ".png"
            filter_str = "PNG 画像 (*.png)"
        elif fmt_idx == 1:
            ext = ".pdf"
            filter_str = "PDF 文書 (*.pdf)"
        else:
            ext = ".svg"
            filter_str = "SVG 画像 (*.svg)"

        default_name = f"chart_export{ext}"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "論文用図表の保存", default_name, filter_str
        )
        if not filepath:
            return

        w_inch, h_inch = self.get_dimensions_inch()
        dpi = self.spin_dpi.value()
        font_size = self.spin_font_size.value()
        show_legend = self.cb_legend.isChecked()
        show_grid = self.cb_grid.isChecked()

        try:
            export_figure(
                filepath=filepath,
                render_func=self.render_func,
                chart_spec=self.chart_spec,
                width_inch=w_inch,
                height_inch=h_inch,
                dpi=dpi,
                base_font_size=font_size,
                show_legend=show_legend,
                show_grid=show_grid,
            )
            QMessageBox.information(self, "完了", f"図表を保存しました:\n{os.path.basename(filepath)}")
            self.accept()
        except Exception as e:
            logger.exception("図表の書き出しに失敗しました: %s", filepath)
            QMessageBox.critical(self, "エラー", f"図表の書き出しに失敗しました:\n{e}")
