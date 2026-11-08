"""
数値ログ (CSV) 重ね合わせ比較グラフビューウィジェット
単一学習および継続学習（全タスク統合 / タスク別ズーム、タスク境界線、収束スターマーカー）に対応
フォルダA/B間での個別タスク選択および凡例の任意編集（カスタム凡例）をサポート
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QSlider, QLabel, QCheckBox, QComboBox,
    QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
import pandas as pd

import numpy as np
import matplotlib as mpl
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

# グラフ保存時の高精細解像度 (300 DPI) 設定
mpl.rcParams['savefig.dpi'] = 300


from src.config import (
    SETTINGS_KEY_CHART_FONT_LABEL, SETTINGS_KEY_CHART_FONT_TICKS,
    SETTINGS_KEY_CHART_FONT_TITLE, SETTINGS_KEY_CHART_FONT_LEGEND,
    SETTINGS_KEY_CHART_SMOOTHING, SETTINGS_KEY_CHART_MA_WINDOW,
    SETTINGS_KEY_CHART_EMA_WEIGHT, SETTINGS_KEY_CHART_LOG_SCALE,
    DEFAULT_CHART_FONT_LABEL, DEFAULT_CHART_FONT_TICKS,
    DEFAULT_CHART_FONT_TITLE, DEFAULT_CHART_FONT_LEGEND
)
from src.core.settings import create_settings
from src.core.parsers.experiment import get_experiment_info
from src.core.parsers.csv_metric import (
    read_log_csv, compute_metric_series, get_available_metrics, TaskOption,
    scan_task_options, load_task_dataframe, EPISODE_X_LABEL, CsvLoadError,
    MetricSeriesData
)
from src.ui.dialogs.figure_export_dialog import FigureExportDialog
from src.ui.theme import Theme, current_theme, get_theme_manager

logger = logging.getLogger(__name__)


@dataclass
class ChartSpec:
    """グラフ描画仕様・パラメータ"""
    data_a: MetricSeriesData
    data_b: MetricSeriesData
    chart_title: str
    x_label: str
    y_label: str
    legend_label_a: str
    legend_label_b: str
    show_raw: bool
    show_boundaries: bool
    show_convergence: bool
    is_log_scale: bool
    font_label: int
    font_ticks: int
    font_title: int
    font_legend: int
    theme: Theme
    show_legend: bool = True
    show_grid: bool = True
    x_axis_mismatch: bool = False
    load_error_msgs: dict[str, str] = field(default_factory=dict)
    has_df_a: bool = False
    has_df_b: bool = False


def _drop_nan(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """値が記録されていない (NaN) 点を除外する（記録された点同士を線で結ぶため）"""
    x = np.asarray(x)
    y = np.asarray(y, dtype=float)
    mask = ~np.isnan(y)
    return x[mask], y[mask]


def _render_chart(ax, spec: ChartSpec) -> bool:
    """
    与えられた Axes に spec の指定に従ってグラフを描画する。
    画面描画 (FigureCanvasQTAgg) と論文用エクスポート (FigureCanvasAgg) の共通描画関数。
    戻り値: 何かプロットされたか (has_plot)
    """
    has_plot = False

    # A系列のプロット
    if spec.data_a.has_data and spec.data_a.x is not None:
        if spec.show_raw and spec.data_a.y_raw is not None:
            ax.plot(*_drop_nan(spec.data_a.x, spec.data_a.y_raw), color=spec.theme.series_a_raw, alpha=0.25, linewidth=1.0)
        if spec.data_a.y_ma is not None:
            ax.plot(*_drop_nan(spec.data_a.x, spec.data_a.y_ma), label=spec.legend_label_a, color=spec.theme.series_a_line, linewidth=2.0)
            has_plot = True

        # Aの収束ポイント描画 (★マーカー)
        if spec.show_convergence and spec.data_a.converged_episodes:
            label_star_a = f"{spec.legend_label_a} 収束点 (★)" if spec.legend_label_a else "A 収束点 (★)"
            ax.scatter(
                spec.data_a.converged_episodes, spec.data_a.converged_y_values,
                marker='*', s=140, color=spec.theme.series_a_marker, edgecolors=spec.theme.chart_bg, linewidths=1.0,
                zorder=5, label=label_star_a
            )

    # B系列のプロット
    if spec.data_b.has_data and spec.data_b.x is not None:
        if spec.show_raw and spec.data_b.y_raw is not None:
            ax.plot(*_drop_nan(spec.data_b.x, spec.data_b.y_raw), color=spec.theme.series_b_raw, alpha=0.25, linewidth=1.0)
        if spec.data_b.y_ma is not None:
            ax.plot(*_drop_nan(spec.data_b.x, spec.data_b.y_ma), label=spec.legend_label_b, color=spec.theme.series_b_line, linewidth=2.0)
            has_plot = True

        # Bの収束ポイント描画 (★マーカー)
        if spec.show_convergence and spec.data_b.converged_episodes:
            label_star_b = f"{spec.legend_label_b} 収束点 (★)" if spec.legend_label_b else "B 収束点 (★)"
            ax.scatter(
                spec.data_b.converged_episodes, spec.data_b.converged_y_values,
                marker='*', s=140, color=spec.theme.series_b_marker, edgecolors=spec.theme.chart_bg, linewidths=1.0,
                zorder=5, label=label_star_b
            )

    # 片側のみデータが存在する場合の凡例
    if spec.data_a.has_data and not spec.data_b.has_data:
        ax.plot([], [], ' ', label=spec.load_error_msgs.get("B", "B: [該当列なし]"))
    elif not spec.data_a.has_data and spec.data_b.has_data:
        ax.plot([], [], ' ', label=spec.load_error_msgs.get("A", "A: [該当列なし]"))

    # タスク境界線の描画 (縦破線)
    if spec.show_boundaries:
        boundaries = spec.data_a.task_boundaries if spec.data_a.task_boundaries else spec.data_b.task_boundaries
        for ep_b, label_b in boundaries:
            ax.axvline(x=ep_b, color=spec.theme.boundary_line, linestyle="--", alpha=0.7, linewidth=1.2)
            ax.text(
                ep_b + 1, 0.98, f" {label_b}",
                transform=ax.get_xaxis_transform(),
                color=spec.theme.boundary_text, fontsize=max(6, spec.font_ticks - 1), fontweight='bold',
                verticalalignment='top', alpha=0.9
            )

    # Y 軸対数表示の処理
    y_label_str = spec.y_label
    if spec.is_log_scale and has_plot:
        all_y_vals = []
        for d in (spec.data_a, spec.data_b):
            if d.has_data:
                if d.y_ma is not None:
                    valid = d.y_ma[~np.isnan(d.y_ma)]
                    if len(valid) > 0:
                        all_y_vals.append(valid)
                if spec.show_raw and d.y_raw is not None:
                    valid = d.y_raw[~np.isnan(d.y_raw)]
                    if len(valid) > 0:
                        all_y_vals.append(valid)
        if all_y_vals:
            merged_y = np.concatenate(all_y_vals)
            has_non_pos = np.any(merged_y <= 0)
            pos_vals = merged_y[merged_y > 0]
            if has_non_pos:
                linthresh = float(np.min(pos_vals)) if len(pos_vals) > 0 else 1.0
                ax.set_yscale('symlog', linthresh=linthresh)
                if not y_label_str.endswith("(symlog)"):
                    y_label_str = f"{y_label_str} (symlog)" if y_label_str else "(symlog)"
            else:
                ax.set_yscale('log')
        else:
            ax.set_yscale('log')

    ax.set_xlabel(spec.x_label, fontsize=spec.font_label, color=spec.theme.chart_text, labelpad=6)
    ax.set_ylabel(y_label_str, fontsize=spec.font_label, color=spec.theme.chart_text, labelpad=6)
    ax.set_title(spec.chart_title, fontsize=spec.font_title, fontweight='bold', color=spec.theme.chart_text, pad=10)
    if spec.show_grid:
        ax.grid(True, linestyle="--", alpha=0.6, color=spec.theme.chart_grid)
    else:
        ax.grid(False)
    ax.tick_params(colors=spec.theme.chart_text, labelsize=spec.font_ticks)
    for spine in ax.spines.values():
        spine.set_color(spec.theme.chart_spine)

    if has_plot and spec.show_legend:
        legend = ax.legend(loc="best", framealpha=0.9, facecolor=spec.theme.chart_legend_bg, edgecolor=spec.theme.chart_legend_edge, fontsize=spec.font_legend)
        if legend:
            for text in legend.get_texts():
                text.set_color(spec.theme.chart_text)
        if spec.x_axis_mismatch:
            ax.text(0.99, 0.01, "※ X 軸の単位が A/B で異なります",
                    horizontalalignment='right', verticalalignment='bottom',
                    transform=ax.transAxes, fontsize=max(6, spec.font_legend - 1), color=spec.theme.warning)

    # 描画できる系列がない場合
    if not has_plot and spec.load_error_msgs:
        center_lines = [spec.load_error_msgs[side] for side in sorted(spec.load_error_msgs)]
        for side, has_df in (("A", spec.has_df_a), ("B", spec.has_df_b)):
            if side not in spec.load_error_msgs and has_df:
                center_lines.append(f"{side}: [該当列なし]")
        ax.text(0.5, 0.5, "\n".join(center_lines),
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=max(10, spec.font_title), color=spec.theme.error)
    elif not has_plot:
        ax.text(0.5, 0.5, "比較対象の CSV データが存在しません",
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=max(10, spec.font_title), color=spec.theme.text_muted)

    return has_plot


class CsvCompareWidget(QWidget):
    """数値ログ (learning_log_*.csv) 重ね合わせ比較ビュー"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder_a = ""
        self.folder_b = ""
        self.df_a = None
        self.df_b = None
        # 「CSV がない」と「読み込みに失敗した」を区別するため、失敗したファイル名を保持する ("A"/"B" → ファイル名)
        self._csv_load_errors: dict[str, str] = {}
        self.info_a = "フォルダ A"
        self.info_b = "フォルダ B"
        self.task_options_a: list[TaskOption] = []
        self.task_options_b: list[TaskOption] = []
        self._task_df_cache: dict[tuple[str, int, Optional[str]], Optional[pd.DataFrame]] = {}
        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(100)
        self._redraw_timer.timeout.connect(self.update_chart)
        self._need_reset_texts = True
        self._init_ui()
        get_theme_manager().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _theme=None) -> None:
        """テーマ変更時にグラフを再描画（入力済みテキストは保持）"""
        self.update_chart()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側: 対象タスク選択・指標選択・移動平均設定・凡例設定
        left_box = QGroupBox("比較コントロール")
        left_lay = QVBoxLayout(left_box)
        left_lay.setSpacing(8)

        # 1. 対象タスク選択
        # (A) 個別タスク選択モード切替チェックボックス
        self.cb_independent_tasks = QCheckBox("A/B 個別タスク選択モード (異なるタスクを比較)")
        self.cb_independent_tasks.setToolTip("フォルダAとフォルダBで異なるタスクやCSVを個別に選択して比較します")
        self.cb_independent_tasks.toggled.connect(self._on_independent_tasks_toggled)
        left_lay.addWidget(self.cb_independent_tasks)

        # (B) 通常モード用（連動タスク選択コンボ）
        self.lbl_task_common = QLabel("表示対象タスク:")
        self.combo_task = QComboBox()
        self.combo_task.addItem("全タスク統合 (通算エピソード)", 0)
        self.combo_task.currentIndexChanged.connect(self._on_task_changed)
        left_lay.addWidget(self.lbl_task_common)
        left_lay.addWidget(self.combo_task)

        # (C) 個別タスク選択モード用（A側 / B側 個別タスク選択コンボ）
        self.lbl_task_a = QLabel("タスク A (フォルダA):")
        self.combo_task_a = QComboBox()
        self.combo_task_a.currentIndexChanged.connect(self._on_individual_task_changed)
        left_lay.addWidget(self.lbl_task_a)
        left_lay.addWidget(self.combo_task_a)

        self.lbl_task_b = QLabel("タスク B (フォルダB):")
        self.combo_task_b = QComboBox()
        self.combo_task_b.currentIndexChanged.connect(self._on_individual_task_changed)
        left_lay.addWidget(self.lbl_task_b)
        left_lay.addWidget(self.combo_task_b)

        # 個別選択UIは初期状態では非表示
        self.lbl_task_a.setVisible(False)
        self.combo_task_a.setVisible(False)
        self.lbl_task_b.setVisible(False)
        self.combo_task_b.setVisible(False)

        # 2. 表示指標一覧 (動的生成)
        left_lay.addWidget(QLabel("表示指標一覧:"))
        self.list_metrics = QListWidget()
        self._update_metrics_list()

        self.list_metrics.currentRowChanged.connect(self._on_metric_changed)
        left_lay.addWidget(self.list_metrics)

        # 3. 平滑化設定
        smooth_box = QGroupBox("平滑化設定")
        smooth_lay = QVBoxLayout(smooth_box)
        smooth_lay.setSpacing(6)

        lay_sm_type = QHBoxLayout()
        lay_sm_type.addWidget(QLabel("平滑化方式:"))
        self.combo_smoothing = QComboBox()
        self.combo_smoothing.addItem("移動平均", "ma")
        self.combo_smoothing.addItem("EMA (TensorBoard方式)", "ema")
        self.combo_smoothing.addItem("なし", "none")
        self.combo_smoothing.currentIndexChanged.connect(self._on_smoothing_type_changed)
        lay_sm_type.addWidget(self.combo_smoothing, 1)
        smooth_lay.addLayout(lay_sm_type)

        # 移動平均用UI (スライダー + QSpinBox 連動)
        self.container_ma = QWidget()
        lay_ma_container = QVBoxLayout(self.container_ma)
        lay_ma_container.setContentsMargins(0, 0, 0, 0)
        lay_ma_container.setSpacing(4)

        lay_ma_row = QHBoxLayout()
        lbl_ma = QLabel("窓幅:")
        lbl_ma.setFixedWidth(40)
        lay_ma_row.addWidget(lbl_ma)

        self.slider_ma = QSlider(Qt.Orientation.Horizontal)
        self.slider_ma.setRange(1, 50)
        self.slider_ma.setValue(10)
        self.slider_ma.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_ma.setTickInterval(5)
        lay_ma_row.addWidget(self.slider_ma, 1)

        self.spin_ma = QSpinBox()
        self.spin_ma.setRange(1, 50)
        self.spin_ma.setValue(10)
        self.spin_ma.setSuffix(" ep")
        self.spin_ma.setFixedWidth(75)
        lay_ma_row.addWidget(self.spin_ma)
        lay_ma_container.addLayout(lay_ma_row)

        self.lbl_ma_val = QLabel("10 ep")
        self.lbl_ma_val.setVisible(False)

        self.slider_ma.valueChanged.connect(self._on_slider_ma_changed)
        self.spin_ma.valueChanged.connect(self._on_spin_ma_changed)

        smooth_lay.addWidget(self.container_ma)

        # EMA用UI (スライダー + QDoubleSpinBox 連動)
        self.container_ema = QWidget()
        lay_ema_container = QVBoxLayout(self.container_ema)
        lay_ema_container.setContentsMargins(0, 0, 0, 0)
        lay_ema_container.setSpacing(4)

        lay_ema_row = QHBoxLayout()
        lbl_ema = QLabel("係数:")
        lbl_ema.setFixedWidth(40)
        lay_ema_row.addWidget(lbl_ema)

        self.slider_ema = QSlider(Qt.Orientation.Horizontal)
        self.slider_ema.setRange(0, 999)
        self.slider_ema.setValue(600)
        self.slider_ema.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_ema.setTickInterval(100)
        lay_ema_row.addWidget(self.slider_ema, 1)

        self.spin_ema = QDoubleSpinBox()
        self.spin_ema.setRange(0.000, 0.999)
        self.spin_ema.setSingleStep(0.05)
        self.spin_ema.setDecimals(3)
        self.spin_ema.setValue(0.600)
        self.spin_ema.setFixedWidth(75)
        lay_ema_row.addWidget(self.spin_ema)
        lay_ema_container.addLayout(lay_ema_row)

        self.slider_ema.valueChanged.connect(self._on_slider_ema_changed)
        self.spin_ema.valueChanged.connect(self._on_spin_ema_changed)

        smooth_lay.addWidget(self.container_ema)
        self.container_ema.setVisible(False)

        left_lay.addWidget(smooth_box)

        # 4. グラフテキスト・フォント設定 (タイトル・軸・凡例・文字サイズ)
        text_box = QGroupBox("グラフテキスト・フォント設定")
        text_lay = QVBoxLayout(text_box)
        text_lay.setSpacing(5)

        lay_title = QHBoxLayout()
        lbl_title = QLabel("タイトル:")
        lbl_title.setFixedWidth(52)
        lay_title.addWidget(lbl_title)
        self.txt_title = QLineEdit()
        self.txt_title.setToolTip("グラフ上部のタイトル (空欄にすると非表示)")
        self.txt_title.textChanged.connect(self._on_custom_text_changed)
        lay_title.addWidget(self.txt_title)
        text_lay.addLayout(lay_title)

        lay_xlabel = QHBoxLayout()
        lbl_xlabel = QLabel("X軸:")
        lbl_xlabel.setFixedWidth(52)
        lay_xlabel.addWidget(lbl_xlabel)
        self.txt_xlabel = QLineEdit()
        self.txt_xlabel.setToolTip("横軸 (X軸) のラベル (空欄にすると非表示)")
        self.txt_xlabel.textChanged.connect(self._on_custom_text_changed)
        lay_xlabel.addWidget(self.txt_xlabel)
        text_lay.addLayout(lay_xlabel)

        lay_ylabel = QHBoxLayout()
        lbl_ylabel = QLabel("Y軸:")
        lbl_ylabel.setFixedWidth(52)
        lay_ylabel.addWidget(lbl_ylabel)
        self.txt_ylabel = QLineEdit()
        self.txt_ylabel.setToolTip("縦軸 (Y軸) のラベル (空欄にすると非表示)")
        self.txt_ylabel.textChanged.connect(self._on_custom_text_changed)
        lay_ylabel.addWidget(self.txt_ylabel)
        text_lay.addLayout(lay_ylabel)

        lay_leg_a = QHBoxLayout()
        lbl_leg_a = QLabel("凡例 A:")
        lbl_leg_a.setFixedWidth(52)
        lay_leg_a.addWidget(lbl_leg_a)
        self.txt_legend_a = QLineEdit()
        self.txt_legend_a.setPlaceholderText("A系列の凡例 (空欄でデフォルト)")
        self.txt_legend_a.textChanged.connect(self._on_custom_text_changed)
        lay_leg_a.addWidget(self.txt_legend_a)
        text_lay.addLayout(lay_leg_a)

        lay_leg_b = QHBoxLayout()
        lbl_leg_b = QLabel("凡例 B:")
        lbl_leg_b.setFixedWidth(52)
        lay_leg_b.addWidget(lbl_leg_b)
        self.txt_legend_b = QLineEdit()
        self.txt_legend_b.setPlaceholderText("B系列の凡例 (空欄でデフォルト)")
        self.txt_legend_b.textChanged.connect(self._on_custom_text_changed)
        lay_leg_b.addWidget(self.txt_legend_b)
        text_lay.addLayout(lay_leg_b)

        # フォントサイズ設定 (pt)
        lbl_font_header = QLabel("フォントサイズ (pt):")
        text_lay.addWidget(lbl_font_header)

        lay_font_row1 = QHBoxLayout()
        lbl_font_label = QLabel("軸ラベル:")
        lbl_font_label.setFixedWidth(52)
        lay_font_row1.addWidget(lbl_font_label)
        self.spin_font_label = QSpinBox()
        self.spin_font_label.setRange(6, 28)
        self.spin_font_label.setValue(DEFAULT_CHART_FONT_LABEL)
        self.spin_font_label.setToolTip("X軸・Y軸ラベルのフォントサイズ (pt)")
        self.spin_font_label.valueChanged.connect(self._on_font_size_changed)
        lay_font_row1.addWidget(self.spin_font_label)

        lbl_font_ticks = QLabel("軸数値:")
        lbl_font_ticks.setFixedWidth(44)
        lay_font_row1.addWidget(lbl_font_ticks)
        self.spin_font_ticks = QSpinBox()
        self.spin_font_ticks.setRange(6, 28)
        self.spin_font_ticks.setValue(DEFAULT_CHART_FONT_TICKS)
        self.spin_font_ticks.setToolTip("軸目盛り数値のフォントサイズ (pt)")
        self.spin_font_ticks.valueChanged.connect(self._on_font_size_changed)
        lay_font_row1.addWidget(self.spin_font_ticks)
        text_lay.addLayout(lay_font_row1)

        lay_font_row2 = QHBoxLayout()
        lbl_font_title = QLabel("タイトル:")
        lbl_font_title.setFixedWidth(52)
        lay_font_row2.addWidget(lbl_font_title)
        self.spin_font_title = QSpinBox()
        self.spin_font_title.setRange(6, 28)
        self.spin_font_title.setValue(DEFAULT_CHART_FONT_TITLE)
        self.spin_font_title.setToolTip("グラフタイトルのフォントサイズ (pt)")
        self.spin_font_title.valueChanged.connect(self._on_font_size_changed)
        lay_font_row2.addWidget(self.spin_font_title)

        lbl_font_legend = QLabel("凡例:")
        lbl_font_legend.setFixedWidth(44)
        lay_font_row2.addWidget(lbl_font_legend)
        self.spin_font_legend = QSpinBox()
        self.spin_font_legend.setRange(6, 28)
        self.spin_font_legend.setValue(DEFAULT_CHART_FONT_LEGEND)
        self.spin_font_legend.setToolTip("凡例のフォントサイズ (pt)")
        self.spin_font_legend.valueChanged.connect(self._on_font_size_changed)
        lay_font_row2.addWidget(self.spin_font_legend)
        text_lay.addLayout(lay_font_row2)

        self.btn_reset_texts = QPushButton("🔄 すべてデフォルトに戻す")
        self.btn_reset_texts.setToolTip("タイトル・軸ラベル・凡例およびフォントサイズをデフォルト設定に戻します")
        self.btn_reset_texts.clicked.connect(self._reset_all_custom_texts)
        text_lay.addWidget(self.btn_reset_texts)

        # 既存テストおよび旧コードとの後方互換性エイリアス
        self.btn_reset_legend = self.btn_reset_texts

        left_lay.addWidget(text_box)

        # 5. オプション（生データ、境界線、収束マーカー、対数軸）
        self.cb_raw_data = QCheckBox("生データを背景表示")
        self.cb_raw_data.setChecked(True)
        self.cb_raw_data.toggled.connect(self.update_chart)
        left_lay.addWidget(self.cb_raw_data)

        self.cb_task_boundaries = QCheckBox("タスク境界線 (縦破線) を表示")
        self.cb_task_boundaries.setChecked(True)
        self.cb_task_boundaries.toggled.connect(self.update_chart)
        left_lay.addWidget(self.cb_task_boundaries)

        self.cb_converged_points = QCheckBox("収束ポイント (★) を表示")
        self.cb_converged_points.setChecked(True)
        self.cb_converged_points.toggled.connect(self.update_chart)
        left_lay.addWidget(self.cb_converged_points)

        self.cb_log_scale = QCheckBox("Y 軸を対数表示")
        self.cb_log_scale.setToolTip("Y 軸を対数スケールで表示します（0以下の値を含む場合は symlog スケール）")
        self.cb_log_scale.toggled.connect(self._on_log_scale_toggled)
        left_lay.addWidget(self.cb_log_scale)

        self.main_splitter.addWidget(left_box)

        # 右側: Matplotlib グラフ描画領域
        right_widget = QWidget()
        right_lay = QVBoxLayout(right_widget)

        top_bar_lay = QHBoxLayout()
        self.figure = Figure(figsize=(8, 5), dpi=100, facecolor=current_theme().chart_bg)
        self.canvas = FigureCanvasQTAgg(self.figure)
        orig_draw_idle = self.canvas._draw_idle
        def _safe_draw_idle():
            try:
                orig_draw_idle()
            except RuntimeError:
                pass
        self.canvas._draw_idle = _safe_draw_idle
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        top_bar_lay.addWidget(self.toolbar)
        top_bar_lay.addStretch()

        self.btn_export_csv = QPushButton("📋 表示データを CSV に保存…")
        self.btn_export_csv.setToolTip("現在プロットされているデータ（生データおよび平滑化データ）を CSV ファイルに書き出します")
        self.btn_export_csv.clicked.connect(self._export_chart_data_csv)
        top_bar_lay.addWidget(self.btn_export_csv)

        self.btn_export_paper = QPushButton("📄 論文用に書き出し…")
        self.btn_export_paper.setToolTip("論文の段組みやスライドに応じたサイズ・解像度・形式で図を保存します")
        self.btn_export_paper.clicked.connect(self._open_figure_export_dialog)
        top_bar_lay.addWidget(self.btn_export_paper)

        right_lay.addLayout(top_bar_lay)
        right_lay.addWidget(self.canvas, 1)

        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setSizes([260, 980])

        main_layout.addWidget(self.main_splitter)

        self.list_metrics.setCurrentRow(0)
        self._load_chart_settings()

    def _schedule_redraw(self) -> None:
        """タイマーによるデバウンス再描画をスケジュール（100ms 後に update_chart を実行）"""
        self._redraw_timer.start(100)

    def _on_slider_ma_changed(self, val: int) -> None:
        if self.spin_ma.value() != val:
            self.spin_ma.blockSignals(True)
            self.spin_ma.setValue(val)
            self.spin_ma.blockSignals(False)
        self.lbl_ma_val.setText(f"{val} ep")
        self._save_smoothing_settings()
        self._schedule_redraw()

    def _on_spin_ma_changed(self, val: int) -> None:
        if self.slider_ma.value() != val:
            self.slider_ma.blockSignals(True)
            self.slider_ma.setValue(val)
            self.slider_ma.blockSignals(False)
        self.lbl_ma_val.setText(f"{val} ep")
        self._save_smoothing_settings()
        self._schedule_redraw()

    def _on_slider_ema_changed(self, val: int) -> None:
        val_float = val / 1000.0
        if abs(self.spin_ema.value() - val_float) > 1e-4:
            self.spin_ema.blockSignals(True)
            self.spin_ema.setValue(val_float)
            self.spin_ema.blockSignals(False)
        self._save_smoothing_settings()
        self._schedule_redraw()

    def _on_spin_ema_changed(self, val: float) -> None:
        val_int = int(round(val * 1000.0))
        if self.slider_ema.value() != val_int:
            self.slider_ema.blockSignals(True)
            self.slider_ema.setValue(val_int)
            self.slider_ema.blockSignals(False)
        self._save_smoothing_settings()
        self._schedule_redraw()

    def _on_smoothing_type_changed(self, idx: int) -> None:
        mode = self.combo_smoothing.currentData() or "ma"
        self.container_ma.setVisible(mode == "ma")
        self.container_ema.setVisible(mode == "ema")
        self._save_smoothing_settings()
        self.update_chart()

    def _on_log_scale_toggled(self, checked: bool) -> None:
        settings = create_settings()
        settings.setValue(SETTINGS_KEY_CHART_LOG_SCALE, checked)
        self.update_chart()

    def _on_ma_changed(self, val: int) -> None:
        """後方互換用"""
        self._on_slider_ma_changed(val)

    def _on_custom_text_changed(self, text: str) -> None:
        """テキスト入力変更時のリアルタイム再描画"""
        self._schedule_redraw()

    def _on_custom_legend_changed(self, text: str) -> None:
        """後方互換: 凡例テキスト変更時のリアルタイム再描画"""
        self._on_custom_text_changed(text)

    def _on_font_size_changed(self, val: int = 0) -> None:
        """フォントサイズ変更時のリアルタイム再描画および設定保存"""
        self._save_chart_font_settings()
        self.update_chart()

    def _load_chart_settings(self) -> None:
        """QSettings から平滑化・対数軸・フォントサイズ設定を一括読み込み"""
        self._load_chart_font_settings()
        settings = create_settings()

        smoothing = str(settings.value(SETTINGS_KEY_CHART_SMOOTHING, "ma"))
        idx = self.combo_smoothing.findData(smoothing)
        if idx >= 0:
            self.combo_smoothing.blockSignals(True)
            self.combo_smoothing.setCurrentIndex(idx)
            self.combo_smoothing.blockSignals(False)

        try:
            ma_window = int(settings.value(SETTINGS_KEY_CHART_MA_WINDOW, 10))
        except (ValueError, TypeError):
            ma_window = 10
        upper = min(5000, max(self.slider_ma.maximum(), ma_window))
        self.slider_ma.setMaximum(upper)
        self.spin_ma.setMaximum(upper)
        self.slider_ma.blockSignals(True)
        self.slider_ma.setValue(ma_window)
        self.slider_ma.blockSignals(False)
        self.spin_ma.blockSignals(True)
        self.spin_ma.setValue(ma_window)
        self.spin_ma.blockSignals(False)
        self.lbl_ma_val.setText(f"{ma_window} ep")

        try:
            ema_weight = float(settings.value(SETTINGS_KEY_CHART_EMA_WEIGHT, 0.6))
        except (ValueError, TypeError):
            ema_weight = 0.6
        self.spin_ema.blockSignals(True)
        self.spin_ema.setValue(ema_weight)
        self.spin_ema.blockSignals(False)
        self.slider_ema.blockSignals(True)
        self.slider_ema.setValue(int(round(ema_weight * 1000.0)))
        self.slider_ema.blockSignals(False)

        mode = self.combo_smoothing.currentData() or "ma"
        self.container_ma.setVisible(mode == "ma")
        self.container_ema.setVisible(mode == "ema")

        log_scale = settings.value(SETTINGS_KEY_CHART_LOG_SCALE, False, type=bool)
        self.cb_log_scale.blockSignals(True)
        self.cb_log_scale.setChecked(bool(log_scale))
        self.cb_log_scale.blockSignals(False)

    def _save_smoothing_settings(self) -> None:
        """平滑化設定を QSettings に保存"""
        settings = create_settings()
        settings.setValue(SETTINGS_KEY_CHART_SMOOTHING, self.combo_smoothing.currentData())
        settings.setValue(SETTINGS_KEY_CHART_MA_WINDOW, self.spin_ma.value())
        settings.setValue(SETTINGS_KEY_CHART_EMA_WEIGHT, self.spin_ema.value())

    def _update_ma_window_range(self) -> None:
        """データ長に応じて移動平均窓幅の最大値を更新 (範囲 1〜max(50, データ長の半分)、上限 5000)"""
        max_len = 0
        if self.df_a is not None and len(self.df_a) > 0:
            max_len = max(max_len, len(self.df_a))
        if self.df_b is not None and len(self.df_b) > 0:
            max_len = max(max_len, len(self.df_b))
        upper = min(5000, max(50, max_len // 2))
        self.slider_ma.setMaximum(upper)
        self.spin_ma.setMaximum(upper)

    def _load_chart_font_settings(self) -> None:
        """QSettings からフォントサイズ設定を読み込み"""
        settings = create_settings()
        try:
            font_label = int(settings.value(SETTINGS_KEY_CHART_FONT_LABEL, DEFAULT_CHART_FONT_LABEL))
        except (ValueError, TypeError):
            font_label = DEFAULT_CHART_FONT_LABEL
        try:
            font_ticks = int(settings.value(SETTINGS_KEY_CHART_FONT_TICKS, DEFAULT_CHART_FONT_TICKS))
        except (ValueError, TypeError):
            font_ticks = DEFAULT_CHART_FONT_TICKS
        try:
            font_title = int(settings.value(SETTINGS_KEY_CHART_FONT_TITLE, DEFAULT_CHART_FONT_TITLE))
        except (ValueError, TypeError):
            font_title = DEFAULT_CHART_FONT_TITLE
        try:
            font_legend = int(settings.value(SETTINGS_KEY_CHART_FONT_LEGEND, DEFAULT_CHART_FONT_LEGEND))
        except (ValueError, TypeError):
            font_legend = DEFAULT_CHART_FONT_LEGEND

        if hasattr(self, 'spin_font_label'):
            self.spin_font_label.blockSignals(True)
            self.spin_font_label.setValue(font_label)
            self.spin_font_label.blockSignals(False)
        if hasattr(self, 'spin_font_ticks'):
            self.spin_font_ticks.blockSignals(True)
            self.spin_font_ticks.setValue(font_ticks)
            self.spin_font_ticks.blockSignals(False)
        if hasattr(self, 'spin_font_title'):
            self.spin_font_title.blockSignals(True)
            self.spin_font_title.setValue(font_title)
            self.spin_font_title.blockSignals(False)
        if hasattr(self, 'spin_font_legend'):
            self.spin_font_legend.blockSignals(True)
            self.spin_font_legend.setValue(font_legend)
            self.spin_font_legend.blockSignals(False)

    def _save_chart_font_settings(self) -> None:
        """フォントサイズ設定を QSettings に保存"""
        settings = create_settings()
        if hasattr(self, 'spin_font_label'):
            settings.setValue(SETTINGS_KEY_CHART_FONT_LABEL, self.spin_font_label.value())
        if hasattr(self, 'spin_font_ticks'):
            settings.setValue(SETTINGS_KEY_CHART_FONT_TICKS, self.spin_font_ticks.value())
        if hasattr(self, 'spin_font_title'):
            settings.setValue(SETTINGS_KEY_CHART_FONT_TITLE, self.spin_font_title.value())
        if hasattr(self, 'spin_font_legend'):
            settings.setValue(SETTINGS_KEY_CHART_FONT_LEGEND, self.spin_font_legend.value())

    def _reset_all_custom_texts(self) -> None:
        """すべてのテキスト入力（タイトル・軸・凡例）およびフォントサイズをデフォルトに戻す"""
        self._need_reset_texts = True
        if hasattr(self, 'spin_font_label'):
            self.spin_font_label.blockSignals(True)
            self.spin_font_label.setValue(DEFAULT_CHART_FONT_LABEL)
            self.spin_font_label.blockSignals(False)
        if hasattr(self, 'spin_font_ticks'):
            self.spin_font_ticks.blockSignals(True)
            self.spin_font_ticks.setValue(DEFAULT_CHART_FONT_TICKS)
            self.spin_font_ticks.blockSignals(False)
        if hasattr(self, 'spin_font_title'):
            self.spin_font_title.blockSignals(True)
            self.spin_font_title.setValue(DEFAULT_CHART_FONT_TITLE)
            self.spin_font_title.blockSignals(False)
        if hasattr(self, 'spin_font_legend'):
            self.spin_font_legend.blockSignals(True)
            self.spin_font_legend.setValue(DEFAULT_CHART_FONT_LEGEND)
            self.spin_font_legend.blockSignals(False)
        self._save_chart_font_settings()
        self.update_chart()

    def _reset_custom_legends(self) -> None:
        """後方互換用: デフォルトに戻す"""
        self._reset_all_custom_texts()


    def _on_metric_changed(self, row: int) -> None:
        """指標変更時（質問2: 案B - すべてデフォルトに自動リセット）"""
        self._need_reset_texts = True
        self.update_chart()

    def _on_independent_tasks_toggled(self, checked: bool) -> None:
        """A/B 個別タスク選択モードの切り替え"""
        self.lbl_task_common.setVisible(not checked)
        self.combo_task.setVisible(not checked)
        self.lbl_task_a.setVisible(checked)
        self.combo_task_a.setVisible(checked)
        self.lbl_task_b.setVisible(checked)
        self.combo_task_b.setVisible(checked)

        if checked:
            # 個別タスク選択モード時はタスク境界線は無効、収束ポイントは有効
            self.cb_task_boundaries.setEnabled(False)
            self.cb_converged_points.setEnabled(True)
        else:
            task_id = self.combo_task.currentData()
            has_multiple_tasks = self.combo_task.count() > 1
            is_all_tasks = (task_id == 0 or task_id is None)
            self.cb_task_boundaries.setEnabled(has_multiple_tasks and is_all_tasks)
            self.cb_converged_points.setEnabled(has_multiple_tasks and is_all_tasks)

        self._need_reset_texts = True
        self.update_chart()

    def _on_task_changed(self, index: int) -> None:
        """通常モードでのタスク選択変更時のUI制御"""
        task_id = self.combo_task.currentData()
        has_multiple_tasks = self.combo_task.count() > 1
        is_all_tasks = (task_id == 0 or task_id is None)
        self.cb_task_boundaries.setEnabled(has_multiple_tasks and is_all_tasks)
        self.cb_converged_points.setEnabled(has_multiple_tasks and is_all_tasks)
        self._need_reset_texts = True
        self.update_chart()

    def _on_individual_task_changed(self, index: int) -> None:
        """個別タスク選択変更時の再描画（質問2: 案B - すべてデフォルトに自動リセット）"""
        self._need_reset_texts = True
        self.update_chart()

    def _get_task_dataframe(self, side: str, opt: TaskOption) -> Optional[pd.DataFrame]:
        """タスク別 DataFrame をキャッシュから取得、または読み込んでキャッシュに保持"""
        folder = self.folder_a if side == "A" else self.folder_b
        base_df = self.df_a if side == "A" else self.df_b
        cache_key = (folder, opt.task_id, opt.csv_path)
        if cache_key in self._task_df_cache:
            return self._task_df_cache[cache_key]
        df = load_task_dataframe(base_df, folder, opt)
        self._task_df_cache[cache_key] = df
        return df

    def apply_data(
        self,
        folder_a: str,
        folder_b: str,
        info_a: str,
        info_b: str,
        df_a: Optional[pd.DataFrame],
        df_failed_a: Optional[str],
        df_b: Optional[pd.DataFrame],
        df_failed_b: Optional[str],
        task_options_a: list[TaskOption],
        task_options_b: list[TaskOption],
    ) -> None:
        """解析済みのCSVデータを反映"""
        self._task_df_cache.clear()
        self._csv_load_errors = {}
        if df_failed_a:
            self._csv_load_errors["A"] = df_failed_a
        if df_failed_b:
            self._csv_load_errors["B"] = df_failed_b

        self.folder_a = folder_a
        self.folder_b = folder_b
        self.info_a = info_a
        self.info_b = info_b

        # フォルダ再読み込み時はテキスト設定をデフォルトにリセット
        self._need_reset_texts = True

        self.df_a = df_a
        self.df_b = df_b
        self.task_options_a = task_options_a
        self.task_options_b = task_options_b

        # 指標一覧およびタスク一覧の統合更新
        self._update_metrics_list()
        self._populate_task_combos()
        self._update_ma_window_range()
        self.update_chart()

    def load_csvs(self, folder_a: str, folder_b: str) -> None:
        """フォルダA/Bの CSV ログを同期的に読み込んでタスクリスト、指標リストおよびチャートを更新（互換性のために維持）"""
        self._csv_load_errors = {}
        info_a = get_experiment_info(folder_a)
        info_b = get_experiment_info(folder_b)
        df_a = self._read_csv_or_record_error(folder_a, "A")
        df_b = self._read_csv_or_record_error(folder_b, "B")
        opts_a = scan_task_options(folder_a, df_a)
        opts_b = scan_task_options(folder_b, df_b)
        self.apply_data(
            folder_a,
            folder_b,
            info_a,
            info_b,
            df_a,
            self._csv_load_errors.get("A"),
            df_b,
            self._csv_load_errors.get("B"),
            opts_a,
            opts_b,
        )

    def _read_csv_or_record_error(self, folder: str, side: str):
        """CSV を読み込む。失敗した場合はファイル名を記録して None を返す"""
        try:
            return read_log_csv(folder, raise_on_error=True)
        except CsvLoadError as e:
            self._csv_load_errors[side] = os.path.basename(e.path)
            return None

    def _update_metrics_list(self) -> None:
        """AおよびBの DataFrame から利用可能な指標一覧を取得し、リストを動的再構築（案A: グループ化）"""
        current_item = self.list_metrics.currentItem()
        prev_key = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None

        self.list_metrics.blockSignals(True)
        self.list_metrics.clear()

        metrics = get_available_metrics(self.df_a, self.df_b)

        last_category = None
        target_row = 0

        for m in metrics:
            # カテゴリの変わり目にセパレータ（区切り見出し）を挿入
            if m.category == "domain" and last_category == "primary":
                sep_item = QListWidgetItem("── 独自ドメイン指標 ──")
                sep_item.setFlags(Qt.ItemFlag.NoItemFlags)  # 選択不可
                sep_item.setForeground(Qt.GlobalColor.darkGray)
                self.list_metrics.addItem(sep_item)
            elif m.category == "generic" and last_category != "generic":
                sep_item = QListWidgetItem("── CSVその他の数値系列 ──")
                sep_item.setFlags(Qt.ItemFlag.NoItemFlags)  # 選択不可
                sep_item.setForeground(Qt.GlobalColor.darkGray)
                self.list_metrics.addItem(sep_item)

            last_category = m.category

            item = QListWidgetItem(m.display_name)
            item.setData(Qt.ItemDataRole.UserRole, m.key)
            self.list_metrics.addItem(item)

            if prev_key and m.key == prev_key:
                target_row = self.list_metrics.count() - 1

        self.list_metrics.blockSignals(False)
        if self.list_metrics.count() > 0:
            self.list_metrics.setCurrentRow(target_row)

    def _update_task_combos(self) -> None:
        """フォルダAおよびBからタスク一覧を取得し、通常コンボおよびA/B個別コンボを更新"""
        self.task_options_a = scan_task_options(self.folder_a, self.df_a)
        self.task_options_b = scan_task_options(self.folder_b, self.df_b)
        self._populate_task_combos()

    def _populate_task_combos(self) -> None:
        """タスクオプションに基づいてコンボボックス群を更新"""
        # 2. 通常コンボ (self.combo_task) の更新 (全タスク統合 + マージされたタスク)
        self.combo_task.blockSignals(True)
        self.combo_task.clear()

        merged_tasks: dict[int, str] = {0: "全タスク統合 (通算エピソード)"}
        for opt in self.task_options_a:
            if opt.task_id > 0:
                merged_tasks[opt.task_id] = opt.display_name
        for opt in self.task_options_b:
            if opt.task_id > 0:
                if opt.task_id not in merged_tasks or ("(" not in merged_tasks[opt.task_id] and "(" in opt.display_name):
                    merged_tasks[opt.task_id] = opt.display_name

        for t_id in sorted(merged_tasks.keys()):
            self.combo_task.addItem(merged_tasks[t_id], t_id)

        has_multiple_tasks = len(merged_tasks) > 1
        self.combo_task.setEnabled(has_multiple_tasks)
        if not has_multiple_tasks and self.combo_task.count() > 0:
            self.combo_task.setItemText(0, "単一タスク / 汎用ログ (全エピソード)")
        self.combo_task.blockSignals(False)

        # 3. 個別コンボ A (self.combo_task_a) の更新
        self.combo_task_a.blockSignals(True)
        self.combo_task_a.clear()
        for opt in self.task_options_a:
            self.combo_task_a.addItem(opt.display_name, opt)
        self.combo_task_a.setEnabled(len(self.task_options_a) > 0)
        self.combo_task_a.blockSignals(False)

        # 4. 個別コンボ B (self.combo_task_b) の更新
        self.combo_task_b.blockSignals(True)
        self.combo_task_b.clear()
        for opt in self.task_options_b:
            self.combo_task_b.addItem(opt.display_name, opt)
        self.combo_task_b.setEnabled(len(self.task_options_b) > 0)

        # 同一フォルダ比較等の利便性のため、B側は可能なら2番目のタスクをデフォルト選択
        if self.folder_a and self.folder_a == self.folder_b and self.combo_task_b.count() > 1:
            self.combo_task_b.setCurrentIndex(1)
        elif self.combo_task_b.count() > 0:
            self.combo_task_b.setCurrentIndex(0)
        self.combo_task_b.blockSignals(False)

        # 個別モード切替チェックボックスの有効化判定
        can_individual = len(self.task_options_a) > 0 or len(self.task_options_b) > 0
        self.cb_independent_tasks.setEnabled(can_individual)

        # 初期表示制御
        if not self.cb_independent_tasks.isChecked():
            self._on_task_changed(self.combo_task.currentIndex())

    def update_chart(self) -> None:
        """選択指標・タスク・凡例設定に基づきグラフを描画更新"""
        self._redraw_timer.stop()
        theme = current_theme()
        self.figure.clear()
        self.figure.patch.set_facecolor(theme.chart_bg)
        ax = self.figure.add_subplot(111, facecolor=theme.chart_bg)

        row = self.list_metrics.currentRow()
        if row < 0:
            row = 0
        item = self.list_metrics.item(row)
        metric_key = item.data(Qt.ItemDataRole.UserRole) if item else 0

        # セパレータ等の無効アイテムが選択された場合は何もしない
        if metric_key is None:
            return

        smoothing = self.combo_smoothing.currentData() or "ma"
        window = self.spin_ma.value()
        ema_weight = self.spin_ema.value()
        show_raw = self.cb_raw_data.isChecked()
        is_independent = self.cb_independent_tasks.isChecked()
        title_metric_name = item.text() if item else ""
        x_axis_mismatch = False

        if is_independent:
            # --- A/B 個別タスク選択モード ---
            opt_a: Optional[TaskOption] = self.combo_task_a.currentData()
            opt_b: Optional[TaskOption] = self.combo_task_b.currentData()

            task_df_a = self._get_task_dataframe("A", opt_a) if opt_a else None
            task_df_b = self._get_task_dataframe("B", opt_b) if opt_b else None

            task_name_a = opt_a.short_name if opt_a else "タスク A"
            task_name_b = opt_b.short_name if opt_b else "タスク B"

            if self.folder_a and self.folder_a == self.folder_b:
                label_a = f"A: {task_name_a}"
                label_b = f"B: {task_name_b}"
            else:
                label_a = f"A: {self.info_a} ({task_name_a})"
                label_b = f"B: {self.info_b} ({task_name_b})"

            task_filter_id_a = opt_a.task_id if opt_a and opt_a.task_id > 0 else 0
            task_filter_id_b = opt_b.task_id if opt_b and opt_b.task_id > 0 else 0

            data_a = compute_metric_series(
                task_df_a, metric_key, window, label_a, task_filter_id=task_filter_id_a,
                smoothing=smoothing, ema_weight=ema_weight
            )
            data_b = compute_metric_series(
                task_df_b, metric_key, window, label_b, task_filter_id=task_filter_id_b,
                smoothing=smoothing, ema_weight=ema_weight
            )

            show_boundaries = False  # 個別タスク比較では全体境界線は描画しない
            show_convergence = self.cb_converged_points.isChecked()

            # タスク絞り込み時（opt.task_id >= 0 かつ全タスク統合でない場合）は従来どおり Task_Episode 基準のラベルとし、
            # 汎用 CSV 等で step 列などが使われた場合は実際の列名を反映する
            is_task_filter_a = opt_a is not None and opt_a.task_id > 0
            is_task_filter_b = opt_b is not None and opt_b.task_id > 0
            has_task_filter = (
                (is_task_filter_a and (data_a.has_data or not data_b.has_data))
                or (is_task_filter_b and (data_b.has_data or not data_a.has_data))
            )
            if has_task_filter:
                default_x_label = "Task Episode (エピソード [1..N])"
            else:
                if data_a.has_data or not data_b.has_data:
                    default_x_label = data_a.x_label or data_b.x_label or EPISODE_X_LABEL
                else:
                    default_x_label = data_b.x_label or EPISODE_X_LABEL
            default_chart_title = f"学習推移比較: {title_metric_name} (A: {task_name_a} vs B: {task_name_b})"

        else:
            # --- 通常モード（連動） ---
            task_id = self.combo_task.currentData() or 0
            show_boundaries = self.cb_task_boundaries.isChecked() and (task_id == 0)
            show_convergence = self.cb_converged_points.isChecked() and (task_id == 0)

            data_a = compute_metric_series(
                self.df_a, metric_key, window, f"A: {self.info_a}", task_filter_id=task_id,
                smoothing=smoothing, ema_weight=ema_weight
            )
            data_b = compute_metric_series(
                self.df_b, metric_key, window, f"B: {self.info_b}", task_filter_id=task_id,
                smoothing=smoothing, ema_weight=ema_weight
            )

            if task_id > 0:
                default_x_label = f"Task Episode (Task {task_id} 内エピソード [1..N])"
            else:
                # データがある側の X 軸ラベルを優先する
                if data_a.has_data or not data_b.has_data:
                    default_x_label = data_a.x_label or data_b.x_label or EPISODE_X_LABEL
                else:
                    default_x_label = data_b.x_label or EPISODE_X_LABEL
            default_chart_title = f"学習推移比較: {title_metric_name}"

        # A と B で X 軸の種類（エピソード / ステップ等）が異なる場合は両方を示す（通常モード・個別モード共通）
        x_axis_mismatch = bool(
            data_a.has_data and data_b.has_data
            and data_a.x_kind and data_b.x_kind and data_a.x_kind != data_b.x_kind
        )
        if x_axis_mismatch:
            default_x_label = f"A: {data_a.x_label} / B: {data_b.x_label}"

        default_y_label = data_a.y_label or data_b.y_label or "Value"

        # リセットフラグが立っている場合（指標・タスク変更、フォルダロード、リセットボタン押下時）
        if getattr(self, '_need_reset_texts', False):
            if hasattr(self, 'txt_title'):
                self.txt_title.blockSignals(True)
                self.txt_title.setText(default_chart_title)
                self.txt_title.blockSignals(False)
            if hasattr(self, 'txt_xlabel'):
                self.txt_xlabel.blockSignals(True)
                self.txt_xlabel.setText(default_x_label)
                self.txt_xlabel.blockSignals(False)
            if hasattr(self, 'txt_ylabel'):
                self.txt_ylabel.blockSignals(True)
                self.txt_ylabel.setText(default_y_label)
                self.txt_ylabel.blockSignals(False)
            if hasattr(self, 'txt_legend_a'):
                self.txt_legend_a.blockSignals(True)
                self.txt_legend_a.clear()
                self.txt_legend_a.blockSignals(False)
            if hasattr(self, 'txt_legend_b'):
                self.txt_legend_b.blockSignals(True)
                self.txt_legend_b.clear()
                self.txt_legend_b.blockSignals(False)
            self._need_reset_texts = False

        # プレースホルダーの更新
        if hasattr(self, 'txt_title'):
            self.txt_title.setPlaceholderText(default_chart_title)
        if hasattr(self, 'txt_xlabel'):
            self.txt_xlabel.setPlaceholderText(default_x_label)
        if hasattr(self, 'txt_ylabel'):
            if self.txt_ylabel.text() == self.txt_ylabel.placeholderText():
                self.txt_ylabel.blockSignals(True)
                self.txt_ylabel.setText(default_y_label)
                self.txt_ylabel.blockSignals(False)
            self.txt_ylabel.setPlaceholderText(default_y_label)
        if hasattr(self, 'txt_legend_a') and hasattr(self, 'txt_legend_b'):
            self.txt_legend_a.setPlaceholderText(data_a.legend_label_ma or "A系列のデフォルト凡例")
            self.txt_legend_b.setPlaceholderText(data_b.legend_label_ma or "B系列のデフォルト凡例")

        # 描画用テキストの取得（空欄を含む任意変更に対応）
        chart_title = self.txt_title.text() if hasattr(self, 'txt_title') else default_chart_title
        x_label = self.txt_xlabel.text() if hasattr(self, 'txt_xlabel') else default_x_label
        y_label = self.txt_ylabel.text() if hasattr(self, 'txt_ylabel') else default_y_label

        # カスタム凡例の取得と適用 (案A: 入力文字列そのままを完全上書き)
        custom_a = self.txt_legend_a.text().strip() if hasattr(self, 'txt_legend_a') else ""
        custom_b = self.txt_legend_b.text().strip() if hasattr(self, 'txt_legend_b') else ""

        legend_label_a = custom_a if custom_a else data_a.legend_label_ma
        legend_label_b = custom_b if custom_b else data_b.legend_label_ma

        # CSV の読み込みに失敗した場合は「データなし」と区別して表示する
        load_error_msgs = {
            side: f"フォルダ {side} の CSV の読み込みに失敗しました: {name}（詳細はログを参照）"
            for side, name in self._csv_load_errors.items()
        }

        # フォントサイズ設定の取得
        font_label = self.spin_font_label.value() if hasattr(self, 'spin_font_label') else DEFAULT_CHART_FONT_LABEL
        font_ticks = self.spin_font_ticks.value() if hasattr(self, 'spin_font_ticks') else DEFAULT_CHART_FONT_TICKS
        font_title = self.spin_font_title.value() if hasattr(self, 'spin_font_title') else DEFAULT_CHART_FONT_TITLE
        font_legend = self.spin_font_legend.value() if hasattr(self, 'spin_font_legend') else DEFAULT_CHART_FONT_LEGEND

        spec = ChartSpec(
            data_a=data_a,
            data_b=data_b,
            chart_title=chart_title,
            x_label=x_label,
            y_label=y_label,
            legend_label_a=legend_label_a,
            legend_label_b=legend_label_b,
            show_raw=show_raw,
            show_boundaries=show_boundaries,
            show_convergence=show_convergence,
            is_log_scale=self.cb_log_scale.isChecked(),
            font_label=font_label,
            font_ticks=font_ticks,
            font_title=font_title,
            font_legend=font_legend,
            theme=theme,
            show_legend=True,
            show_grid=True,
            x_axis_mismatch=x_axis_mismatch,
            load_error_msgs=load_error_msgs,
            has_df_a=self.df_a is not None,
            has_df_b=self.df_b is not None,
        )
        self._current_spec = spec

        _render_chart(ax, spec)

        try:
            self.figure.tight_layout(pad=1.2)
        except Exception:
            logger.debug("グラフのレイアウト調整に失敗しました", exc_info=True)

        self.canvas.draw_idle()

    def _export_chart_data_csv(self) -> None:
        """表示中のデータを CSV に保存"""
        if not hasattr(self, '_current_spec') or self._current_spec is None:
            QMessageBox.warning(self, "警告", "保存対象のグラフデータがありません。")
            return

        spec = self._current_spec
        if not (spec.data_a.has_data or spec.data_b.has_data):
            QMessageBox.warning(self, "警告", "保存対象のデータがありません。")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "表示データを CSV に保存", "chart_data.csv", "CSV ファイル (*.csv)"
        )
        if not filepath:
            return

        try:
            self._write_chart_data_to_csv(filepath, spec)
            QMessageBox.information(self, "完了", f"データを CSV に保存しました:\n{os.path.basename(filepath)}")
        except Exception as e:
            logger.exception("CSV 保存に失敗しました: %s", filepath)
            QMessageBox.critical(self, "エラー", f"CSV 保存に失敗しました:\n{e}")

    def _write_chart_data_to_csv(self, filepath: str, spec: ChartSpec) -> None:
        """
        ChartSpec のデータを縦持ち CSV (utf-8-sig) で保存する。
        列: series, x, y_raw, y_smoothed
        先頭にメタデータコメント行: # metric=..., smoothing=..., window=..., ema_weight=...
        """
        row = self.list_metrics.currentRow()
        item = self.list_metrics.item(row) if row >= 0 else None
        metric_key = item.data(Qt.ItemDataRole.UserRole) if item else "unknown"
        smoothing = self.combo_smoothing.currentData() or "ma"
        window = self.spin_ma.value()
        ema_weight = self.spin_ema.value()

        comment_line = f"# metric={metric_key}, smoothing={smoothing}, window={window}, ema_weight={ema_weight:.3f}\n"

        rows = []
        for side, data, legend in [("A", spec.data_a, spec.legend_label_a), ("B", spec.data_b, spec.legend_label_b)]:
            if not data.has_data or data.x is None:
                continue
            series_name = legend if legend else f"Series {side}"
            x_arr = data.x
            y_raw_arr = data.y_raw if data.y_raw is not None else [np.nan] * len(x_arr)
            y_smooth_arr = data.y_ma if data.y_ma is not None else [np.nan] * len(x_arr)

            for x_val, y_r, y_s in zip(x_arr, y_raw_arr, y_smooth_arr):
                rows.append({
                    "series": series_name,
                    "x": x_val,
                    "y_raw": y_r,
                    "y_smoothed": y_s,
                })

        df_out = pd.DataFrame(rows, columns=["series", "x", "y_raw", "y_smoothed"])
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            f.write(comment_line)
            df_out.to_csv(f, index=False)

    def _open_figure_export_dialog(self) -> None:
        """論文用書き出しダイアログを開く"""
        if not hasattr(self, '_current_spec') or self._current_spec is None:
            QMessageBox.warning(self, "警告", "保存対象のグラフデータがありません。")
            return

        spec = self._current_spec
        if not (spec.data_a.has_data or spec.data_b.has_data):
            QMessageBox.warning(self, "警告", "保存対象のデータがありません。")
            return

        dialog = FigureExportDialog(
            parent=self,
            chart_spec=spec,
            render_func=_render_chart
        )
        dialog.exec()
