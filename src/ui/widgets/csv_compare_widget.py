"""
数値ログ (CSV) 重ね合わせ比較グラフビューウィジェット
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QSlider, QLabel, QCheckBox
)
from PySide6.QtCore import Qt

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from src.core.parsers.experiment import get_experiment_info
from src.core.parsers.csv_metric import read_log_csv, compute_metric_series, METRIC_DEFINITIONS


class CsvCompareWidget(QWidget):
    """数値ログ (learning_log_*.csv) 重ね合わせ比較ビュー"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.df_a = None
        self.df_b = None
        self.info_a = "フォルダ A"
        self.info_b = "フォルダ B"
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側: 指標選択・移動平均設定
        left_box = QGroupBox("表示指標一覧 (常時表示)")
        left_lay = QVBoxLayout(left_box)

        self.list_metrics = QListWidget()
        for name, idx, _, _ in METRIC_DEFINITIONS:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.list_metrics.addItem(item)

        self.list_metrics.currentRowChanged.connect(self.update_chart)
        left_lay.addWidget(self.list_metrics)

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

        self.cb_raw_data = QCheckBox("生データを背景表示")
        self.cb_raw_data.setChecked(True)
        self.cb_raw_data.toggled.connect(self.update_chart)
        left_lay.addWidget(self.cb_raw_data)

        self.main_splitter.addWidget(left_box)

        # 右側: Matplotlib グラフ描画領域
        right_widget = QWidget()
        right_lay = QVBoxLayout(right_widget)

        self.figure = Figure(figsize=(8, 5), dpi=100, facecolor='#ffffff')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        right_lay.addWidget(self.toolbar)
        right_lay.addWidget(self.canvas, 1)

        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setSizes([240, 1000])

        main_layout.addWidget(self.main_splitter)

        self.list_metrics.setCurrentRow(0)

    def _on_ma_changed(self, val: int) -> None:
        self.lbl_ma_val.setText(f"{val} ep")
        self.update_chart()

    def load_csvs(self, folder_a: str, folder_b: str) -> None:
        """フォルダA/Bの CSV ログを読み込んでチャートを更新"""
        self.info_a = get_experiment_info(folder_a)
        self.info_b = get_experiment_info(folder_b)

        self.df_a = read_log_csv(folder_a)
        self.df_b = read_log_csv(folder_b)

        self.update_chart()

    def update_chart(self) -> None:
        """選択指標・設定に基づきグラフを描画更新"""
        self.figure.clear()
        self.figure.patch.set_facecolor('#ffffff')
        ax = self.figure.add_subplot(111, facecolor='#ffffff')

        row = self.list_metrics.currentRow()
        if row < 0:
            row = 0
        item = self.list_metrics.item(row)
        metric_idx = item.data(Qt.ItemDataRole.UserRole) if item else 0

        window = self.slider_ma.value()
        show_raw = self.cb_raw_data.isChecked()

        data_a = compute_metric_series(self.df_a, metric_idx, window, f"A: {self.info_a}")
        data_b = compute_metric_series(self.df_b, metric_idx, window, f"B: {self.info_b}")

        has_plot = False
        y_label = data_a.y_label or data_b.y_label or "Value"

        # A系列のプロット (青系統)
        if data_a.has_data and data_a.x is not None:
            if show_raw and data_a.y_raw is not None:
                ax.plot(data_a.x, data_a.y_raw, color="#4a90e2", alpha=0.3, linewidth=1.0)
            if data_a.y_ma is not None:
                ax.plot(data_a.x, data_a.y_ma, label=data_a.legend_label_ma, color="#0055ff", linewidth=2.0)
                has_plot = True

        # B系列のプロット (赤系統)
        if data_b.has_data and data_b.x is not None:
            if show_raw and data_b.y_raw is not None:
                ax.plot(data_b.x, data_b.y_raw, color="#e74c3c", alpha=0.3, linewidth=1.0)
            if data_b.y_ma is not None:
                ax.plot(data_b.x, data_b.y_ma, label=data_b.legend_label_ma, color="#cc0000", linewidth=2.0)
                has_plot = True

        ax.set_xlabel("Episode", fontsize=11, color='#222222', labelpad=6)
        ax.set_ylabel(y_label, fontsize=11, color='#222222', labelpad=6)
        ax.set_title(f"学習推移比較: {y_label}", fontsize=12, fontweight='bold', color='#222222', pad=10)
        ax.grid(True, linestyle="--", alpha=0.6, color='#cccccc')
        ax.tick_params(colors='#333333', labelsize=10)
        for spine in ax.spines.values():
            spine.set_color('#888888')

        if has_plot:
            legend = ax.legend(loc="best", framealpha=0.9, facecolor='#ffffff', edgecolor='#cccccc', fontsize=10)
            for text in legend.get_texts():
                text.set_color('#222222')
        else:
            ax.text(0.5, 0.5, "比較対象の CSV データが存在しません",
                    horizontalalignment='center', verticalalignment='center',
                    transform=ax.transAxes, fontsize=14, color='#666666')

        try:
            self.figure.tight_layout(pad=1.2)
        except Exception:
            pass

        self.canvas.draw()
