"""
数値ログ (CSV) 重ね合わせ比較グラフビューウィジェット
単一学習および継続学習（全タスク統合 / タスク別ズーム、タスク境界線、収束スターマーカー）に対応
フォルダA/B間での個別タスク選択および凡例の任意編集（カスタム凡例）をサポート
"""

import logging
import os
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QSlider, QLabel, QCheckBox, QComboBox,
    QLineEdit, QPushButton, QSpinBox
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
    DEFAULT_CHART_FONT_LABEL, DEFAULT_CHART_FONT_TICKS,
    DEFAULT_CHART_FONT_TITLE, DEFAULT_CHART_FONT_LEGEND
)
from src.core.settings import create_settings
from src.core.parsers.experiment import get_experiment_info
from src.core.parsers.csv_metric import (
    read_log_csv, compute_metric_series, get_available_metrics, TaskOption,
    scan_task_options, load_task_dataframe, EPISODE_X_LABEL, CsvLoadError
)

logger = logging.getLogger(__name__)


def _drop_nan(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """値が記録されていない (NaN) 点を除外する（記録された点同士を線で結ぶため）"""
    x = np.asarray(x)
    y = np.asarray(y, dtype=float)
    mask = ~np.isnan(y)
    return x[mask], y[mask]


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

        # 3. 移動平均設定
        left_lay.addWidget(QLabel("移動平均ウィンドウ:"))
        self.slider_ma = QSlider(Qt.Orientation.Horizontal)
        self.slider_ma.setRange(1, 50)
        self.slider_ma.setValue(10)
        self.slider_ma.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_ma.setTickInterval(5)
        self.slider_ma.valueChanged.connect(self._on_ma_changed)
        left_lay.addWidget(self.slider_ma)

        self.lbl_ma_val = QLabel("10 ep")
        left_lay.addWidget(self.lbl_ma_val)

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

        # 5. オプション（生データ、境界線、収束マーカー）
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

        self.main_splitter.addWidget(left_box)

        # 右側: Matplotlib グラフ描画領域
        right_widget = QWidget()
        right_lay = QVBoxLayout(right_widget)

        self.figure = Figure(figsize=(8, 5), dpi=100, facecolor='#ffffff')
        self.canvas = FigureCanvasQTAgg(self.figure)
        orig_draw_idle = self.canvas._draw_idle
        def _safe_draw_idle():
            try:
                orig_draw_idle()
            except RuntimeError:
                pass
        self.canvas._draw_idle = _safe_draw_idle
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        right_lay.addWidget(self.toolbar)
        right_lay.addWidget(self.canvas, 1)

        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setSizes([260, 980])

        main_layout.addWidget(self.main_splitter)

        self.list_metrics.setCurrentRow(0)
        self._load_chart_font_settings()

    def _schedule_redraw(self) -> None:
        """タイマーによるデバウンス再描画をスケジュール（100ms 後に update_chart を実行）"""
        self._redraw_timer.start(100)

    def _on_ma_changed(self, val: int) -> None:
        self.lbl_ma_val.setText(f"{val} ep")
        self._schedule_redraw()

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

    def load_csvs(self, folder_a: str, folder_b: str) -> None:
        """フォルダA/Bの CSV ログを読み込んでタスクリスト、指標リストおよびチャートを更新"""
        self._task_df_cache.clear()
        self._csv_load_errors = {}
        self.folder_a = folder_a
        self.folder_b = folder_b
        self.info_a = get_experiment_info(folder_a)
        self.info_b = get_experiment_info(folder_b)

        # フォルダ再読み込み時はテキスト設定をデフォルトにリセット
        self._need_reset_texts = True

        self.df_a = self._read_csv_or_record_error(folder_a, "A")
        self.df_b = self._read_csv_or_record_error(folder_b, "B")

        # 指標一覧およびタスク一覧の統合更新
        self._update_metrics_list()
        self._update_task_combos()
        self.update_chart()

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
        # 1. フォルダA/Bから TaskOption をスキャン
        self.task_options_a = scan_task_options(self.folder_a, self.df_a)
        self.task_options_b = scan_task_options(self.folder_b, self.df_b)

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
        self.figure.clear()
        self.figure.patch.set_facecolor('#ffffff')
        ax = self.figure.add_subplot(111, facecolor='#ffffff')

        row = self.list_metrics.currentRow()
        if row < 0:
            row = 0
        item = self.list_metrics.item(row)
        metric_key = item.data(Qt.ItemDataRole.UserRole) if item else 0

        # セパレータ等の無効アイテムが選択された場合は何もしない
        if metric_key is None:
            return

        window = self.slider_ma.value()
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

            data_a = compute_metric_series(task_df_a, metric_key, window, label_a, task_filter_id=task_filter_id_a)
            data_b = compute_metric_series(task_df_b, metric_key, window, label_b, task_filter_id=task_filter_id_b)

            show_boundaries = False  # 個別タスク比較では全体境界線は描画しない
            show_convergence = self.cb_converged_points.isChecked()
            default_x_label = "Task Episode (エピソード [1..N])"
            default_chart_title = f"学習推移比較: {title_metric_name} (A: {task_name_a} vs B: {task_name_b})"

        else:
            # --- 通常モード（連動） ---
            task_id = self.combo_task.currentData() or 0
            show_boundaries = self.cb_task_boundaries.isChecked() and (task_id == 0)
            show_convergence = self.cb_converged_points.isChecked() and (task_id == 0)

            data_a = compute_metric_series(self.df_a, metric_key, window, f"A: {self.info_a}", task_filter_id=task_id)
            data_b = compute_metric_series(self.df_b, metric_key, window, f"B: {self.info_b}", task_filter_id=task_id)

            if task_id > 0:
                default_x_label = f"Task Episode (Task {task_id} 内エピソード [1..N])"
            else:
                # データがある側の X 軸ラベルを優先する
                if data_a.has_data or not data_b.has_data:
                    default_x_label = data_a.x_label or data_b.x_label or EPISODE_X_LABEL
                else:
                    default_x_label = data_b.x_label or EPISODE_X_LABEL
                # A と B で X 軸の種類（エピソード / ステップ等）が異なる場合は両方を示す
                x_axis_mismatch = bool(
                    data_a.has_data and data_b.has_data
                    and data_a.x_kind and data_b.x_kind and data_a.x_kind != data_b.x_kind
                )
                if x_axis_mismatch:
                    default_x_label = f"A: {data_a.x_label} / B: {data_b.x_label}"
            default_chart_title = f"学習推移比較: {title_metric_name}"

        default_y_label = data_a.y_label or data_b.y_label or "Value"

        # リセットフラグが立っている場合（指標・タスク変更、フォルダロード、リセットボタン押下時）
        # 質問1: 案A（入力欄にデフォルト値が常時表示され、消すと空欄化）
        # 質問2: 案B（指標やタスクを変更したときは、すべてデフォルトに自動リセット）
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

        has_plot = False

        # A系列のプロット (青系統)
        if data_a.has_data and data_a.x is not None:
            if show_raw and data_a.y_raw is not None:
                ax.plot(*_drop_nan(data_a.x, data_a.y_raw), color="#4a90e2", alpha=0.25, linewidth=1.0)
            if data_a.y_ma is not None:
                ax.plot(*_drop_nan(data_a.x, data_a.y_ma), label=legend_label_a, color="#0055ff", linewidth=2.0)
                has_plot = True

            # Aの収束ポイント描画 (★マーカー)
            if show_convergence and data_a.converged_episodes:
                label_star_a = f"{custom_a} 収束点 (★)" if custom_a else "A 収束点 (★)"
                ax.scatter(
                    data_a.converged_episodes, data_a.converged_y_values,
                    marker='*', s=140, color="#002299", edgecolors="#ffffff", linewidths=1.0,
                    zorder=5, label=label_star_a
                )

        # B系列のプロット (赤系統)
        if data_b.has_data and data_b.x is not None:
            if show_raw and data_b.y_raw is not None:
                ax.plot(*_drop_nan(data_b.x, data_b.y_raw), color="#e74c3c", alpha=0.25, linewidth=1.0)
            if data_b.y_ma is not None:
                ax.plot(*_drop_nan(data_b.x, data_b.y_ma), label=legend_label_b, color="#cc0000", linewidth=2.0)
                has_plot = True

            # Bの収束ポイント描画 (★マーカー)
            if show_convergence and data_b.converged_episodes:
                label_star_b = f"{custom_b} 収束点 (★)" if custom_b else "B 収束点 (★)"
                ax.scatter(
                    data_b.converged_episodes, data_b.converged_y_values,
                    marker='*', s=140, color="#990000", edgecolors="#ffffff", linewidths=1.0,
                    zorder=5, label=label_star_b
                )

        # CSV の読み込みに失敗した場合は「データなし」と区別して表示する
        load_error_msgs = {
            side: f"フォルダ {side} の CSV の読み込みに失敗しました: {name}（詳細はログを参照）"
            for side, name in self._csv_load_errors.items()
        }

        # 片側のみデータが存在する場合の案内（読み込みに失敗した側は、その旨を凡例に示す）
        if data_a.has_data and not data_b.has_data:
            ax.plot([], [], ' ', label=load_error_msgs.get("B", "B: [該当列なし]"))
        elif not data_a.has_data and data_b.has_data:
            ax.plot([], [], ' ', label=load_error_msgs.get("A", "A: [該当列なし]"))

        # フォントサイズ設定の取得
        font_label = self.spin_font_label.value() if hasattr(self, 'spin_font_label') else DEFAULT_CHART_FONT_LABEL
        font_ticks = self.spin_font_ticks.value() if hasattr(self, 'spin_font_ticks') else DEFAULT_CHART_FONT_TICKS
        font_title = self.spin_font_title.value() if hasattr(self, 'spin_font_title') else DEFAULT_CHART_FONT_TITLE
        font_legend = self.spin_font_legend.value() if hasattr(self, 'spin_font_legend') else DEFAULT_CHART_FONT_LEGEND

        # タスク境界線の描画 (縦破線: 通常モードの全タスク統合時のみ)
        if show_boundaries:
            boundaries = data_a.task_boundaries if data_a.task_boundaries else data_b.task_boundaries
            for ep_b, label_b in boundaries:
                ax.axvline(x=ep_b, color="#888888", linestyle="--", alpha=0.7, linewidth=1.2)
                ax.text(
                    ep_b + 1, 0.98, f" {label_b}",
                    transform=ax.get_xaxis_transform(),
                    color="#555555", fontsize=max(6, font_ticks - 1), fontweight='bold',
                    verticalalignment='top', alpha=0.9
                )

        ax.set_xlabel(x_label, fontsize=font_label, color='#222222', labelpad=6)
        ax.set_ylabel(y_label, fontsize=font_label, color='#222222', labelpad=6)
        ax.set_title(chart_title, fontsize=font_title, fontweight='bold', color='#222222', pad=10)
        ax.grid(True, linestyle="--", alpha=0.6, color='#cccccc')
        ax.tick_params(colors='#333333', labelsize=font_ticks)
        for spine in ax.spines.values():
            spine.set_color('#888888')

        if has_plot:
            legend = ax.legend(loc="best", framealpha=0.9, facecolor='#ffffff', edgecolor='#cccccc', fontsize=font_legend)
            for text in legend.get_texts():
                text.set_color('#222222')
            if x_axis_mismatch:
                ax.text(0.99, 0.01, "※ X 軸の単位が A/B で異なります",
                        horizontalalignment='right', verticalalignment='bottom',
                        transform=ax.transAxes, fontsize=max(6, font_legend - 1), color='#aa5500')

        # 描画できる系列がない場合は、読み込みの失敗を中央に表示する（片側だけの失敗は凡例に示す）
        if not has_plot and load_error_msgs:
            center_lines = [load_error_msgs[side] for side in sorted(load_error_msgs)]
            # 読み込めた側に、選択した指標のデータがないことも併せて示す
            for side, df in (("A", self.df_a), ("B", self.df_b)):
                if side not in load_error_msgs and df is not None:
                    center_lines.append(f"{side}: [該当列なし]")
            ax.text(0.5, 0.5, "\n".join(center_lines),
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes, fontsize=max(10, font_title), color='#c0392b')
        elif not has_plot:
            ax.text(0.5, 0.5, "比較対象の CSV データが存在しません",
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes, fontsize=max(10, font_title), color='#666666')


        try:
            self.figure.tight_layout(pad=1.2)
        except Exception:
            logger.debug("グラフのレイアウト調整に失敗しました", exc_info=True)

        self.canvas.draw_idle()
