"""
実験ログ一覧・探索ビューウィジェット (ExperimentExplorerWidget)
親フォルダ配下の実験ログとconfigパラメータを表形式で一覧表示し、
行クリックによるグラフプレビュー（タブ状態維持）およびダブルクリックによるフォルダA/Bセット連携を提供
"""

import os
from typing import Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QFileDialog,
    QMenu, QMessageBox, QAbstractItemView, QFrame, QComboBox
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices, QAction, QFont, QColor

from src.config import SETTINGS_KEY_RECENT_ROOT_DIRS, CLEAR_HISTORY_TEXT
from src.core.history import RecentFolderManager
from src.core.parsers.experiment_scanner import (
    scan_experiments_directory, ExperimentLogRecord
)
from src.ui.dialogs.experiment_action_dialog import (
    ExperimentActionDialog, ExperimentAction
)
from src.ui.dialogs.column_visibility_dialog import ColumnVisibilityDialog
from src.ui.dialogs.column_filter_dialog import ColumnFilterDialog



class SortableTableWidgetItem(QTableWidgetItem):
    """数値や日付などの適切な順序比較に対応したテーブルアイテム"""

    def __init__(self, text: str, sort_value: Any = None):
        super().__init__(text)
        self.sort_value = sort_value if sort_value is not None else text

    def __lt__(self, other):
        if isinstance(other, SortableTableWidgetItem):
            try:
                # どちらかが None や空文字の場合は末尾へ
                if self.sort_value is None or self.sort_value == "":
                    return False
                if other.sort_value is None or other.sort_value == "":
                    return True
                return self.sort_value < other.sort_value
            except TypeError:
                return str(self.sort_value) < str(other.sort_value)
        return super().__lt__(other)

class ShiftScrollTableWidget(QTableWidget):
    """Shift + ホイールスクロールで横スクロールに対応したテーブルウィジェット"""

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            delta = event.angleDelta().y()
            if delta != 0:
                h_bar = self.horizontalScrollBar()
                if h_bar:
                    h_bar.setValue(h_bar.value() - delta)
                    event.accept()
                    return
        super().wheelEvent(event)


class ImagePreviewLabel(QLabel):
    """ウィンドウサイズ変更時にアスペクト比を維持して画像をスケール表示するラベル"""

    def __init__(self, placeholder_text: str = "画像がありません", parent=None):
        super().__init__(parent)
        self.placeholder_text = placeholder_text
        self._pixmap: Optional[QPixmap] = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 150)
        self.setStyleSheet("background-color: #1e1e1e; color: #888; border-radius: 4px;")
        self.show_placeholder()

    def set_image(self, file_path: Optional[str]):
        if file_path and os.path.exists(file_path):
            self._pixmap = QPixmap(file_path)
            self._update_scaled()
        else:
            self._pixmap = None
            self.show_placeholder()

    def show_placeholder(self, text: Optional[str] = None):
        self._pixmap = None
        self.setText(text or self.placeholder_text)

    def _update_scaled(self):
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            super().setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled()


class ExperimentExplorerWidget(QWidget):
    """実験ログ一覧・探索（Log Explorer）ウィジェット"""

    request_set_folder_a = Signal(str)
    request_set_folder_b = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_mgr = RecentFolderManager(settings_key=SETTINGS_KEY_RECENT_ROOT_DIRS)
        self._history = self.history_mgr.load_history()
        self._records: list[ExperimentLogRecord] = []
        self._config_keys: list[str] = []
        self._current_selected_record: Optional[ExperimentLogRecord] = None
        self._last_sidebar_width: int = 480
        self._hidden_column_names: set[str] = {"タイムスタンプ"}
        self._raw_column_names: list[str] = []
        self._column_filters: dict[str, set[str]] = {}

        self._init_ui()
        self._update_history_combo()

    @property
    def edit_root_dir(self):
        """QLineEdit 互換アクセサ（外部コード・既存テストとの後方互換性用）"""
        return self.combo_root_dir.lineEdit()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 1. 上部コントロールバー
        ctrl_group = QGroupBox("探索設定")
        ctrl_layout = QVBoxLayout(ctrl_group)
        ctrl_layout.setSpacing(6)

        # 1-1. 親フォルダ選択行
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("探索ルートフォルダ:"))
        self.combo_root_dir = QComboBox()
        self.combo_root_dir.setEditable(True)
        self.combo_root_dir.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        if self.combo_root_dir.lineEdit():
            self.combo_root_dir.lineEdit().setPlaceholderText("実験ログ群が格納されているフォルダへのパス (例: output_robotino_rl_control) または履歴から選択")
            self.combo_root_dir.lineEdit().returnPressed.connect(self.scan_directory)
        self.combo_root_dir.activated.connect(self._on_root_combo_activated)
        folder_row.addWidget(self.combo_root_dir, 1)

        btn_browse = QPushButton("参照...")
        btn_browse.clicked.connect(self._browse_directory)
        folder_row.addWidget(btn_browse)

        self.cb_recursive = QCheckBox("サブフォルダも含めて検索")
        self.cb_recursive.setChecked(True)
        self.cb_recursive.toggled.connect(self.scan_directory)
        folder_row.addWidget(self.cb_recursive)

        btn_reload = QPushButton("🔄 再読み込み")
        btn_reload.clicked.connect(self.scan_directory)
        folder_row.addWidget(btn_reload)
        ctrl_layout.addLayout(folder_row)

        # 1-2. フィルタ & カラム設定行
        action_row = QHBoxLayout()
        action_row.addWidget(QLabel("クイックフィルタ:"))
        self.edit_filter = QLineEdit()
        self.edit_filter.setPlaceholderText("モード、日時、パラメータ等で絞り込み...")
        self.edit_filter.textChanged.connect(self._apply_filter)
        action_row.addWidget(self.edit_filter, 1)

        btn_clear_filter = QPushButton("✕")
        btn_clear_filter.setMaximumWidth(28)
        btn_clear_filter.setToolTip("クイックフィルタをクリア")
        btn_clear_filter.clicked.connect(lambda: self.edit_filter.setText(""))
        action_row.addWidget(btn_clear_filter)

        self.btn_reset_all_filters = QPushButton("✕ フィルター全解除")
        self.btn_reset_all_filters.setToolTip("クイックフィルタおよび各列のフィルターをすべて解除します")
        self.btn_reset_all_filters.setEnabled(False)
        self.btn_reset_all_filters.clicked.connect(self.clear_all_filters)
        action_row.addWidget(self.btn_reset_all_filters)

        action_row.addSpacing(16)
        self.btn_column_filter = QPushButton("🔍 列フィルター...")
        self.btn_column_filter.setToolTip("列を選択してフィルター設定ダイアログを開きます")
        self.btn_column_filter.clicked.connect(self._open_column_filter_picker)
        action_row.addWidget(self.btn_column_filter)

        self.btn_column_settings = QPushButton("⚙️ カラム表示設定...")
        self.btn_column_settings.setToolTip("テーブル列の表示・非表示を設定します")
        self.btn_column_settings.clicked.connect(self._open_column_settings)
        action_row.addWidget(self.btn_column_settings)

        ctrl_layout.addLayout(action_row)

        main_layout.addWidget(ctrl_group)

        # 2. 中央・右部: スプリッター（左右分割: 左=テーブル, 右=プレビューサイドバー）
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # 2-1. テーブル領域（左側）
        table_container = QWidget()
        table_lay = QVBoxLayout(table_container)
        table_lay.setContentsMargins(0, 0, 0, 0)
        table_lay.setSpacing(4)

        table_top_lay = QHBoxLayout()
        self.lbl_table_status = QLabel("探索フォルダを指定して「再読み込み」を押してください。")
        self.lbl_table_status.setStyleSheet("color: #666; font-size: 11px;")
        table_top_lay.addWidget(self.lbl_table_status, 1)

        self.btn_toggle_sidebar = QPushButton("🖼️ プレビュー非表示 ❯")
        self.btn_toggle_sidebar.setToolTip("画像プレビューサイドバーを非表示にしてテーブルを全幅に拡張します")
        self.btn_toggle_sidebar.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        table_top_lay.addWidget(self.btn_toggle_sidebar)

        table_lay.addLayout(table_top_lay)

        self.table = ShiftScrollTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        # 選択行の視認性向上: 明るいパステルブルー背景と明瞭な黒文字
        self.table.setStyleSheet("""
            QTableWidget {
                selection-background-color: #d8ebfc;
                selection-color: #111827;
                alternate-background-color: #f8fafc;
                background-color: #ffffff;
                gridline-color: #e2e8f0;
            }
            QTableWidget::item:selected {
                background-color: #d8ebfc;
                color: #111827;
            }
            QTableWidget::item:selected:!active {
                background-color: #e5edf6;
                color: #1f2937;
            }
            QTableWidget::item:hover:!selected {
                background-color: #f1f5f9;
            }
        """)

        # 列ヘッダーのコンテキストメニュー & ダブルクリック（列フィルター機能）
        header = self.table.horizontalHeader()
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_context_menu)
        header.sectionDoubleClicked.connect(self.open_column_filter)
        header.setToolTip("クリックでソート、ダブルクリックまたは右クリックで列フィルターを設定")

        table_lay.addWidget(self.table)

        self.splitter.addWidget(table_container)

        # 2-2. プレビュー領域（右サイドバー）
        self.preview_container = QWidget()
        preview_lay = QVBoxLayout(self.preview_container)
        preview_lay.setContentsMargins(4, 0, 0, 0)
        preview_lay.setSpacing(6)

        # 選択中レコードの情報表示バー + 閉じるボタン
        preview_top_lay = QHBoxLayout()
        self.lbl_preview_header = QLabel("ログ行を選択するとグラフがプレビュー表示されます。")
        self.lbl_preview_header.setStyleSheet("font-weight: bold; padding: 4px 6px; background: #eef2f7; border-radius: 3px; font-size: 11px;")
        self.lbl_preview_header.setWordWrap(True)
        preview_top_lay.addWidget(self.lbl_preview_header, 1)

        self.btn_close_sidebar = QPushButton("✕")
        self.btn_close_sidebar.setToolTip("プレビューサイドバーを閉じる")
        self.btn_close_sidebar.setFixedSize(22, 22)
        self.btn_close_sidebar.setStyleSheet("font-weight: bold; padding: 0px;")
        self.btn_close_sidebar.clicked.connect(lambda: self.set_sidebar_visible(False))
        preview_top_lay.addWidget(self.btn_close_sidebar)

        preview_lay.addLayout(preview_top_lay)

        # グラフプレビュー用タブウィジェット（同時に1枚表示、タブインデックス維持）
        self.preview_tabs = QTabWidget()

        self.preview_rewards = ImagePreviewLabel("報酬推移グラフ\n(learning_rewards_*.png)\nがありません")
        self.preview_tabs.addTab(self.preview_rewards, "📈 報酬推移")

        self.preview_steps = ImagePreviewLabel("ステップ推移グラフ\n(learning_steps_*.png)\nがありません")
        self.preview_tabs.addTab(self.preview_steps, "📉 ステップ推移")

        self.preview_trajectory = ImagePreviewLabel("移動軌跡\n(trajectory_*.png)\nがありません")
        self.preview_tabs.addTab(self.preview_trajectory, "🗺️ 移動軌跡")

        preview_lay.addWidget(self.preview_tabs, 1)
        self.splitter.addWidget(self.preview_container)

        # 初期スプリッター比率 (左テーブル 60% : 右サイドバー 40%)
        self.splitter.setSizes([740, 480])
        main_layout.addWidget(self.splitter, 1)

    def toggle_sidebar(self):
        """サイドバーの表示/非表示を切り替える"""
        self.set_sidebar_visible(self.preview_container.isHidden())

    def set_sidebar_visible(self, visible: bool):
        """サイドバーの表示/非表示を設定する"""
        is_currently_visible = not self.preview_container.isHidden()
        if visible == is_currently_visible:
            return

        if visible:
            self.preview_container.setVisible(True)
            total_width = self.splitter.width()
            target_sidebar_w = self._last_sidebar_width if self._last_sidebar_width > 100 else 480
            if total_width > target_sidebar_w + 150:
                left_w = total_width - target_sidebar_w
                self.splitter.setSizes([left_w, target_sidebar_w])
            else:
                self.splitter.setSizes([740, 480])
            self.btn_toggle_sidebar.setText("🖼️ プレビュー非表示 ❯")
            self.btn_toggle_sidebar.setToolTip("画像プレビューサイドバーを非表示にしてテーブルを全幅に拡張します")
        else:
            sizes = self.splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > 50:
                self._last_sidebar_width = sizes[1]
            self.preview_container.setVisible(False)
            self.btn_toggle_sidebar.setText("🖼️ プレビュー表示 ❮")
            self.btn_toggle_sidebar.setToolTip("画像プレビューサイドバーを表示します")




    def get_root_directory(self) -> str:
        """現在入力されている探索ルートフォルダパスを取得"""
        return self.combo_root_dir.currentText().strip()

    def set_root_directory(self, path: str):
        """外部からルートフォルダを設定して走査を開始"""
        norm_path = os.path.abspath(path.strip()) if path and os.path.exists(path.strip()) else path.strip()
        self.combo_root_dir.setEditText(norm_path)
        self.scan_directory()

    def _update_history_combo(self) -> None:
        """コンボボックスのドロップダウン項目を最新のルートフォルダ履歴で更新"""
        current_text = self.combo_root_dir.currentText()
        self.combo_root_dir.blockSignals(True)
        self.combo_root_dir.clear()
        for p in self._history:
            self.combo_root_dir.addItem(p)
        if self._history:
            self.combo_root_dir.insertSeparator(self.combo_root_dir.count())
            self.combo_root_dir.addItem(CLEAR_HISTORY_TEXT)
        self.combo_root_dir.setCurrentIndex(-1)
        self.combo_root_dir.setEditText(current_text)
        self.combo_root_dir.blockSignals(False)

    def _on_root_combo_activated(self, index: int) -> None:
        """ルートフォルダ履歴コンボボックスが選択された際のハンドラ"""
        item_text = self.combo_root_dir.itemText(index)
        if item_text == CLEAR_HISTORY_TEXT:
            self.combo_root_dir.setEditText("")
            self._clear_history()
            return

        if item_text and os.path.isdir(item_text):
            self.combo_root_dir.setEditText(item_text)
            self.scan_directory()

    def _clear_history(self) -> None:
        """確認ダイアログを表示の上、探索ルートフォルダ履歴をすべて消去"""
        reply = QMessageBox.question(
            self,
            "履歴のクリア",
            "探索ルートフォルダの選択履歴をすべて消去しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_mgr.clear_history()
            self._history = []
            self._update_history_combo()

    def _browse_directory(self):
        """フォルダ選択ダイアログ"""
        current = self.combo_root_dir.currentText().strip()
        initial = current if current and os.path.exists(current) else os.getcwd()
        folder = QFileDialog.getExistingDirectory(self, "実験ログ探索ルートフォルダを選択", initial)
        if folder:
            norm_folder = os.path.abspath(folder)
            self.combo_root_dir.setEditText(norm_folder)
            self.scan_directory()

    def scan_directory(self):
        """指定されたルートフォルダ配下を走査してテーブルを構築"""
        root_dir = self.combo_root_dir.currentText().strip()
        if not root_dir or not os.path.isdir(root_dir):
            self.lbl_table_status.setText("⚠️ 有効なディレクトリを指定してください。")
            return

        norm_dir = os.path.abspath(root_dir)
        self._history = self.history_mgr.add_folder(norm_dir)
        self._update_history_combo()
        self.combo_root_dir.setEditText(norm_dir)

        recursive = self.cb_recursive.isChecked()
        self.lbl_table_status.setText(f"フォルダを探索中: {norm_dir} (再帰: {recursive})...")

        records, config_keys = scan_experiments_directory(norm_dir, recursive=recursive)
        self._records = records
        self._config_keys = config_keys

        self._populate_table()
        self.lbl_table_status.setText(
            f"探索完了: {len(records)} 件の実験ログを検出しました（Configパラメータ数: {len(config_keys)} 列）。"
        )

    def _populate_table(self):
        """テーブルの行・列を構築"""
        self.table.setSortingEnabled(False)
        self.table.clear()

        # ヘッダー列定義:
        # Col 0: モード (最左列)
        # Col 1: Shield (可否)
        # Col 2: フォルダ名 (基本列・キー)
        # Col 3: タイムスタンプ (デフォルト非表示)
        # Col 4以降: config_keys
        headers = ["モード", "Shield", "フォルダ名", "タイムスタンプ"] + self._config_keys
        self._raw_column_names = headers[:]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self._records))

        for row_idx, record in enumerate(self._records):
            # Col 0: モード
            item_mode = SortableTableWidgetItem(record.mode, record.mode)
            item_mode.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item_mode.font()
            font.setBold(True)
            item_mode.setFont(font)
            item_mode.setData(Qt.ItemDataRole.UserRole, record)
            self.table.setItem(row_idx, 0, item_mode)

            # Col 1: Shield (可否)
            sort_shield = 1 if record.use_shield is True else (0 if record.use_shield is False else -1)
            item_shield = SortableTableWidgetItem(record.display_shield, sort_shield)
            item_shield.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if record.use_shield is True:
                item_shield.setForeground(QColor("#2e7d32"))  # 緑
                font_s = item_shield.font()
                font_s.setBold(True)
                item_shield.setFont(font_s)
            elif record.use_shield is False:
                item_shield.setForeground(QColor("#757575"))  # グレー
            self.table.setItem(row_idx, 1, item_shield)

            # Col 2: フォルダ名 (キー)
            item_folder = SortableTableWidgetItem(record.folder_name, record.folder_name)
            self.table.setItem(row_idx, 2, item_folder)

            # Col 3: タイムスタンプ (デフォルト非表示)
            item_time = SortableTableWidgetItem(record.display_timestamp, record.timestamp_key)
            item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 3, item_time)

            # Col 4以降: 各Configパラメータ
            for col_offset, key in enumerate(self._config_keys):
                val = record.config_flat.get(key, "")
                val_str = str(val) if val is not None else ""
                item_val = SortableTableWidgetItem(val_str, val)
                if isinstance(val, (int, float)):
                    item_val.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, 4 + col_offset, item_val)

        self.table.setSortingEnabled(True)

        # 列幅の自動調整（主要列）
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        # 1行目を選択
        if self._records:
            self.table.selectRow(0)
        else:
            self._clear_preview()

        self._update_header_labels()
        self._apply_column_visibility()
        self._apply_filter()


    def _get_col_base_name(self, col_idx: int) -> str:
        """列インデックスからフィルター記号等を含まないベース列名を取得"""
        if 0 <= col_idx < len(self._raw_column_names):
            return self._raw_column_names[col_idx]
        item = self.table.horizontalHeaderItem(col_idx)
        if item:
            return item.text().replace(" 🔍", "").strip()
        return ""

    def _update_header_labels(self):
        """各列ヘッダーの表示（フィルター中アイコン 🔍 やツールチップ）を更新"""
        for col_idx in range(self.table.columnCount()):
            base_name = self._get_col_base_name(col_idx)
            if not base_name:
                continue
            item = self.table.horizontalHeaderItem(col_idx)
            if not item:
                item = QTableWidgetItem()
                self.table.setHorizontalHeaderItem(col_idx, item)

            if base_name in self._column_filters:
                item.setText(f"{base_name} 🔍")
                allowed = self._column_filters[base_name]
                item.setToolTip(f"列フィルター適用中: {len(allowed)} 件選択\n(右クリックで編集または解除)")
            else:
                item.setText(base_name)
                item.setToolTip("クリックでソート、右クリックで列フィルターを設定")

    def _on_header_context_menu(self, pos):
        """テーブルヘッダーの右クリックメニュー"""
        header = self.table.horizontalHeader()
        col_idx = header.logicalIndexAt(pos)
        if col_idx < 0:
            return

        col_name = self._get_col_base_name(col_idx)
        if not col_name:
            return

        menu = QMenu(self)
        act_filter = menu.addAction(f"🔍 「{col_name}」をフィルター...")

        act_clear_col = None
        if col_name in self._column_filters:
            act_clear_col = menu.addAction(f"✕ 「{col_name}」のフィルターを解除")

        menu.addSeparator()
        act_hide_col = menu.addAction(f"🚫 この列（{col_name}）を非表示")
        act_col_settings = menu.addAction("⚙️ カラム表示設定...")

        has_any_filter = bool(self._column_filters) or bool(self.edit_filter.text().strip())
        act_clear_all = None
        if has_any_filter:
            menu.addSeparator()
            act_clear_all = menu.addAction("✕ すべてのフィルターを解除")

        action = menu.exec(header.mapToGlobal(pos))
        if action == act_filter:
            self.open_column_filter(col_idx)
        elif action == act_clear_col:
            self.clear_column_filter(col_name)
        elif action == act_hide_col:
            self.hide_column(col_name)
        elif action == act_col_settings:
            self._open_column_settings()
        elif action == act_clear_all:
            self.clear_all_filters()

    def hide_column(self, col_name: str):
        """指定した列を非表示にする"""
        self._hidden_column_names.add(col_name)
        self._apply_column_visibility()

    def open_column_filter(self, col_idx: int):
        """指定列のフィルター設定ダイアログを開く"""
        col_name = self._get_col_base_name(col_idx)
        if not col_name:
            return

        # テーブル内から該当列のユニーク値を収集
        row_count = self.table.rowCount()
        unique_set = set()
        for row in range(row_count):
            item = self.table.item(row, col_idx)
            val_str = item.text() if item else ""
            unique_set.add(val_str)

        unique_values = sorted(list(unique_set))
        current_selected = self._column_filters.get(col_name)

        dlg = ColumnFilterDialog(
            column_name=col_name,
            unique_values=unique_values,
            current_selected_values=current_selected,
            parent=self
        )
        if dlg.exec():
            is_filtered, selected_values = dlg.get_filter_result()
            if is_filtered:
                self._column_filters[col_name] = selected_values
            else:
                self._column_filters.pop(col_name, None)
            self._update_header_labels()
            self._apply_filter()

    def clear_column_filter(self, col_name: str):
        """指定列のフィルターを解除"""
        if col_name in self._column_filters:
            self._column_filters.pop(col_name, None)
            self._update_header_labels()
            self._apply_filter()

    def clear_all_filters(self):
        """すべての列フィルターおよびクイックフィルタを解除"""
        self._column_filters.clear()
        self.edit_filter.setText("")
        self._update_header_labels()
        self._apply_filter()

    def _open_column_filter_picker(self):
        """列フィルターを開く対象の列を選択するメニューを表示"""
        col_count = self.table.columnCount()
        if col_count == 0:
            QMessageBox.information(self, "案内", "実験ログを探索・読み込みした後に列フィルターを開いてください。")
            return

        menu = QMenu(self)
        for col_idx in range(col_count):
            if self.table.isColumnHidden(col_idx):
                continue
            base_name = self._get_col_base_name(col_idx)
            is_filtered = base_name in self._column_filters
            mark = " 🔍" if is_filtered else ""
            action = menu.addAction(f"{base_name}{mark}")
            action.triggered.connect(lambda checked=False, idx=col_idx: self.open_column_filter(idx))

        menu.exec(self.btn_column_filter.mapToGlobal(self.btn_column_filter.rect().bottomLeft()))

    def _apply_filter(self):
        """クイックフィルタおよび各列フィルターによる行の絞り込み"""
        query = self.edit_filter.text().strip().lower()
        row_count = self.table.rowCount()
        col_count = self.table.columnCount()

        has_filters = bool(query) or bool(self._column_filters)
        self.btn_reset_all_filters.setEnabled(has_filters)

        visible_count = 0
        for row in range(row_count):
            # 1. 各列フィルターの判定（AND条件）
            col_match = True
            for col_idx in range(col_count):
                base_name = self._get_col_base_name(col_idx)
                if base_name in self._column_filters:
                    allowed_vals = self._column_filters[base_name]
                    item = self.table.item(row, col_idx)
                    val_str = item.text() if item else ""
                    if val_str not in allowed_vals:
                        col_match = False
                        break

            if not col_match:
                self.table.setRowHidden(row, True)
                continue

            # 2. クイックフィルタ（全列フリーワード検索）の判定
            if not query:
                self.table.setRowHidden(row, False)
                visible_count += 1
                continue

            text_match = False
            for col_idx in range(col_count):
                item = self.table.item(row, col_idx)
                if item and query in item.text().lower():
                    text_match = True
                    break

            self.table.setRowHidden(row, not text_match)
            if text_match:
                visible_count += 1

        # ステータス表示の更新
        if has_filters:
            conds = []
            if query:
                conds.append(f"キーワード: '{query}'")
            for col_name in self._column_filters:
                conds.append(f"{col_name} 列")
            desc = ", ".join(conds)
            self.lbl_table_status.setText(f"フィルター適用中 ({desc}): {visible_count} / {row_count} 件を表示")
        else:
            if self._records:
                self.lbl_table_status.setText(
                    f"探索完了: {len(self._records)} 件の実験ログを検出しました（Configパラメータ数: {len(self._config_keys)} 列）。"
                )

    def _get_selected_record(self) -> Optional[ExperimentLogRecord]:
        """現在選択されている行の ExperimentLogRecord を取得"""
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return None
        row = selected_ranges[0].topRow()
        item = self.table.item(row, 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_row_selected(self):
        """テーブルの行選択変更時: プレビュー画像を更新（タブインデックスは維持）"""
        record = self._get_selected_record()
        self._current_selected_record = record

        if not record:
            self._clear_preview()
            return

        # プレビューヘッダー更新
        shield_info = f" (Shield: {record.display_shield})" if record.display_shield != "-" else ""
        self.lbl_preview_header.setText(
            f"選択中: [{record.mode}]{shield_info} {record.folder_name}  ({record.display_timestamp})"
        )


        # タブの現在インデックスを保持したまま画像のみ更新
        self.preview_rewards.set_image(record.images.get("rewards"))
        self.preview_steps.set_image(record.images.get("steps"))
        self.preview_trajectory.set_image(record.images.get("trajectory"))

    def _clear_preview(self):
        """プレビュー表示をクリア"""
        self.lbl_preview_header.setText("ログ行を選択するとグラフがプレビュー表示されます。")
        self.preview_rewards.show_placeholder()
        self.preview_steps.show_placeholder()
        self.preview_trajectory.show_placeholder()

    def _on_cell_double_clicked(self, row: int, column: int):
        """行ダブルクリック時: アクション選択ダイアログを表示"""
        item = self.table.item(row, 0)
        if not item:
            return
        record: Optional[ExperimentLogRecord] = item.data(Qt.ItemDataRole.UserRole)
        if not record:
            return

        dlg = ExperimentActionDialog(record, self)
        dlg.exec()

        if dlg.selected_action == ExperimentAction.SET_A:
            self.request_set_folder_a.emit(record.folder_path)
        elif dlg.selected_action == ExperimentAction.SET_B:
            self.request_set_folder_b.emit(record.folder_path)

    def _on_table_context_menu(self, pos):
        """テーブルの右クリックコンテキストメニュー"""
        record = self._get_selected_record()
        if not record:
            return

        menu = QMenu(self)
        act_set_a = menu.addAction("🅰️ フォルダ A (基準) に設定")
        act_set_b = menu.addAction("🅱️ フォルダ B (比較) に設定")
        menu.addSeparator()
        act_explorer = menu.addAction("📁 フォルダをエクスプローラーで開く")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_set_a:
            self.request_set_folder_a.emit(record.folder_path)
        elif action == act_set_b:
            self.request_set_folder_b.emit(record.folder_path)
        elif action == act_explorer:
            QDesktopServices.openUrl(QUrl.fromLocalFile(record.folder_path))

    def _set_selected_as_a(self):
        record = self._get_selected_record()
        if record:
            self.request_set_folder_a.emit(record.folder_path)
        else:
            QMessageBox.information(self, "案内", "テーブルから実験ログを選択してください。")

    def _set_selected_as_b(self):
        record = self._get_selected_record()
        if record:
            self.request_set_folder_b.emit(record.folder_path)
        else:
            QMessageBox.information(self, "案内", "テーブルから実験ログを選択してください。")

    def _open_column_settings(self):
        """カラム表示設定ダイアログを開く"""
        col_count = self.table.columnCount()
        if col_count == 0:
            QMessageBox.information(self, "案内", "実験ログを探索・読み込みした後にカラム設定を開いてください。")
            return

        all_cols = self._raw_column_names if self._raw_column_names else [
            self._get_col_base_name(i) for i in range(col_count)
        ]
        dlg = ColumnVisibilityDialog(all_cols, self._hidden_column_names, self)
        if dlg.exec():
            self._hidden_column_names = dlg.get_hidden_columns()
            self._apply_column_visibility()

    def _apply_column_visibility(self):
        """テーブルの各列に対して非表示設定を適用"""
        col_count = self.table.columnCount()
        for col_idx in range(col_count):
            base_name = self._get_col_base_name(col_idx)
            is_hidden = base_name in self._hidden_column_names
            self.table.setColumnHidden(col_idx, is_hidden)

