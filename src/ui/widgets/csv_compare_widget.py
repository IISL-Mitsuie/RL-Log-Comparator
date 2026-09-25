"""
数値ログ (CSV) 重ね合わせ比較グラフビューウィジェット
単一学習および継続学習（全タスク統合 / タスク別ズーム、タスク境界線、収束スターマーカー）に対応
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QGroupBox,
    QListWidget, QListWidgetItem, QSlider, QLabel, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from src.core.parsers.experiment import get_experiment_info
from src.core.parsers.csv_metric import (
    read_log_csv, compute_metric_series, get_available_tasks, METRIC_DEFINITIONS
)


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

        # 左側: 対象タスク選択・指標選択・移動平均設定
        left_box = QGroupBox("比較コントロール")
        left_lay = QVBoxLayout(left_box)
        left_lay.setSpacing(8)

        # 1. 対象タスク選択（案A）
        left_lay.addWidget(QLabel("表示対象タスク:"))
        self.combo_task = QComboBox()
        self.combo_task.addItem("全タスク統合 (通算エピソード)", 0)
        self.combo_task.currentIndexChanged.connect(self._on_task_changed)
        left_lay.addWidget(self.combo_task)

        # 2. 表示指標一覧
        left_lay.addWidget(QLabel("表示指標一覧:"))
        self.list_metrics = QListWidget()
        for name, idx, _, _ in METRIC_DEFINITIONS:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.list_metrics.addItem(item)

        self.list_metrics.currentRowChanged.connect(self.update_chart)
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

        # 4. オプション（生データ、境界線、収束マーカー）
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
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        right_lay.addWidget(self.toolbar)
        right_lay.addWidget(self.canvas, 1)

        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setSizes([260, 980])

        main_layout.addWidget(self.main_splitter)

        self.list_metrics.setCurrentRow(0)

    def _on_ma_changed(self, val: int) -> None:
        self.lbl_ma_val.setText(f"{val} ep")
        self.update_chart()

    def _on_task_changed(self, index: int) -> None:
        """タスク選択変更時のUI制御"""
        task_id = self.combo_task.currentData()
        # 特定タスク選択時はタスク境界線・収束マーカーオプションを無効化
        is_all_tasks = (task_id == 0 or task_id is None)
        self.cb_task_boundaries.setEnabled(is_all_tasks)
        self.cb_converged_points.setEnabled(is_all_tasks)
        self.update_chart()

    def load_csvs(self, folder_a: str, folder_b: str) -> None:
        """フォルダA/Bの CSV ログを読み込んでタスクリストおよびチャートを更新"""
        self.info_a = get_experiment_info(folder_a)
        self.info_b = get_experiment_info(folder_b)

        self.df_a = read_log_csv(folder_a)
        self.df_b = read_log_csv(folder_b)

        # 利用可能タスク一覧の統合更新
        self._update_task_combo()
        self.update_chart()

    def _update_task_combo(self) -> None:
        """AおよびBの DataFrame からタスク一覧を統合してコンボボックスを更新"""
        self.combo_task.blockSignals(True)
        self.combo_task.clear()

        tasks_a = get_available_tasks(self.df_a)
        tasks_b = get_available_tasks(self.df_b)

        # task_id をキーとしてマージ
        merged_tasks: dict[int, str] = {}
        for t_id, desc in tasks_a:
            merged_tasks[t_id] = desc
        for t_id, desc in tasks_b:
            if t_id not in merged_tasks:
                merged_tasks[t_id] = desc
            elif t_id > 0 and "(" not in merged_tasks[t_id] and "(" in desc:
                merged_tasks[t_id] = desc  # ゴール座標がある方を優先

        # task_id 昇順で追加
        for t_id in sorted(merged_tasks.keys()):
            self.combo_task.addItem(merged_tasks[t_id], t_id)

        self.combo_task.blockSignals(False)
        self._on_task_changed(self.combo_task.currentIndex())

    def update_chart(self) -> None:
        """選択指標・タスク・設定に基づきグラフを描画更新"""
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
        task_id = self.combo_task.currentData() or 0
        show_boundaries = self.cb_task_boundaries.isChecked() and (task_id == 0)
        show_convergence = self.cb_converged_points.isChecked() and (task_id == 0)

        data_a = compute_metric_series(self.df_a, metric_idx, window, f"A: {self.info_a}", task_filter_id=task_id)
        data_b = compute_metric_series(self.df_b, metric_idx, window, f"B: {self.info_b}", task_filter_id=task_id)

        has_plot = False
        y_label = data_a.y_label or data_b.y_label or "Value"

        # A系列のプロット (青系統)
        if data_a.has_data and data_a.x is not None:
            if show_raw and data_a.y_raw is not None:
                ax.plot(data_a.x, data_a.y_raw, color="#4a90e2", alpha=0.25, linewidth=1.0)
            if data_a.y_ma is not None:
                ax.plot(data_a.x, data_a.y_ma, label=data_a.legend_label_ma, color="#0055ff", linewidth=2.0)
                has_plot = True

            # Aの収束ポイント描画 (★マーカー)
            if show_convergence and data_a.converged_episodes:
                ax.scatter(
                    data_a.converged_episodes, data_a.converged_y_values,
                    marker='*', s=140, color="#002299", edgecolors="#ffffff", linewidths=1.0,
                    zorder=5, label="A 収束点 (★)"
                )

        # B系列のプロット (赤系統)
        if data_b.has_data and data_b.x is not None:
            if show_raw and data_b.y_raw is not None:
                ax.plot(data_b.x, data_b.y_raw, color="#e74c3c", alpha=0.25, linewidth=1.0)
            if data_b.y_ma is not None:
                ax.plot(data_b.x, data_b.y_ma, label=data_b.legend_label_ma, color="#cc0000", linewidth=2.0)
                has_plot = True

            # Bの収束ポイント描画 (★マーカー)
            if show_convergence and data_b.converged_episodes:
                ax.scatter(
                    data_b.converged_episodes, data_b.converged_y_values,
                    marker='*', s=140, color="#990000", edgecolors="#ffffff", linewidths=1.0,
                    zorder=5, label="B 収束点 (★)"
                )

        # タスク境界線の描画 (縦破線)
        if show_boundaries:
            # AまたはBのタスク境界線を描画（主にAを基準、AがなければB）
            boundaries = data_a.task_boundaries if data_a.task_boundaries else data_b.task_boundaries
            for ep_b, label_b in boundaries:
                ax.axvline(x=ep_b, color="#888888", linestyle="--", alpha=0.7, linewidth=1.2)
                # グラフ上部にタスクラベルを注記
                ax.text(
                    ep_b + 1, 0.98, f" {label_b}",
                    transform=ax.get_xaxis_transform(),
                    color="#555555", fontsize=9, fontweight='bold',
                    verticalalignment='top', alpha=0.9
                )

        # X軸ラベル
        if task_id > 0:
            x_label = f"Task Episode (Task {task_id} 内エピソード [1..N])"
        else:
            x_label = "Total Episode (通算エピソード)"

        ax.set_xlabel(x_label, fontsize=11, color='#222222', labelpad=6)
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
