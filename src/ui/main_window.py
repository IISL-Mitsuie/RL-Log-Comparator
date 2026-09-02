"""
メインウィンドウモジュール (ExperimentCompareApp)
"""

import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QComboBox, QPushButton, QTabWidget,
    QFileDialog, QMessageBox
)
from PySide6.QtGui import QIcon

from src.config import CLEAR_HISTORY_TEXT
from src.core.paths import get_app_icon_path
from src.core.history import RecentFolderManager
from src.ui.widgets.yaml_diff_widget import YamlDiffWidget
from src.ui.widgets.image_compare_widget import ImageCompareWidget
from src.ui.widgets.csv_compare_widget import CsvCompareWidget
from src.ui.widgets.log_spec_widget import LogSpecWidget


class ExperimentCompareApp(QMainWindow):
    """RL-Log-Comparator メインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RL-Log-Comparator - 実験ログ対比・比較分析ツール (PySide6)")
        self.resize(1280, 850)

        # アプリアイコンの設定
        icon_path = get_app_icon_path()
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.history_mgr = RecentFolderManager()
        self._history = self.history_mgr.load_history()
        self._last_loaded_a = ""
        self._last_loaded_b = ""

        self._init_ui()
        self._update_history_combos()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 1. 上部: フォルダ選択バー
        folder_group = QGroupBox("比較対象実験ログフォルダ選択")
        folder_lay = QVBoxLayout(folder_group)

        # フォルダ A
        lay_a = QHBoxLayout()
        lay_a.addWidget(QLabel("フォルダ A (基準):"))
        self.combo_folder_a = QComboBox()
        self.combo_folder_a.setEditable(True)
        self.combo_folder_a.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        if self.combo_folder_a.lineEdit():
            self.combo_folder_a.lineEdit().setPlaceholderText("output_YYYYMMDD_HHMMSS フォルダへのパス (または履歴から選択)")
            self.combo_folder_a.lineEdit().textChanged.connect(self._check_auto_load)
        self.combo_folder_a.activated.connect(lambda idx: self._on_combo_activated(is_target_a=True, index=idx))
        lay_a.addWidget(self.combo_folder_a, 1)
        btn_browse_a = QPushButton("参照...")
        btn_browse_a.clicked.connect(lambda: self._browse_folder_smart(is_target_a=True))
        lay_a.addWidget(btn_browse_a)
        folder_lay.addLayout(lay_a)

        # フォルダ B
        lay_b = QHBoxLayout()
        lay_b.addWidget(QLabel("フォルダ B (比較):"))
        self.combo_folder_b = QComboBox()
        self.combo_folder_b.setEditable(True)
        self.combo_folder_b.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        if self.combo_folder_b.lineEdit():
            self.combo_folder_b.lineEdit().setPlaceholderText("output_YYYYMMDD_HHMMSS フォルダへのパス (または履歴から選択)")
            self.combo_folder_b.lineEdit().textChanged.connect(self._check_auto_load)
        self.combo_folder_b.activated.connect(lambda idx: self._on_combo_activated(is_target_a=False, index=idx))
        lay_b.addWidget(self.combo_folder_b, 1)
        btn_browse_b = QPushButton("参照...")
        btn_browse_b.clicked.connect(lambda: self._browse_folder_smart(is_target_a=False))
        lay_b.addWidget(btn_browse_b)
        folder_lay.addLayout(lay_b)

        main_layout.addWidget(folder_group)

        # 2. 中央: タブウィジェット
        self.tabs = QTabWidget()

        self.tab_yaml = YamlDiffWidget()
        self.tabs.addTab(self.tab_yaml, "1. ハイパーパラメータ差分 (YAML)")

        self.tab_images = ImageCompareWidget()
        self.tabs.addTab(self.tab_images, "2. 画像目視比較 (Side-by-Side)")

        self.tab_csv = CsvCompareWidget()
        self.tabs.addTab(self.tab_csv, "3. 数値ログ比較グラフ (CSV)")

        self.tab_spec = LogSpecWidget()
        self.tabs.addTab(self.tab_spec, "4. ログ仕様ガイド・エクスポート (Spec & Export)")

        main_layout.addWidget(self.tabs, 1)

    def _update_history_combos(self) -> None:
        """A/B 両方のコンボボックスのドロップダウン項目を最新の履歴で同期更新"""
        combos = [self.combo_folder_a, self.combo_folder_b]
        for combo in combos:
            current_text = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            for path in self._history:
                combo.addItem(path)
            if self._history:
                combo.insertSeparator(combo.count())
                combo.addItem(CLEAR_HISTORY_TEXT)
            combo.setCurrentIndex(-1)
            combo.setEditText(current_text)
            combo.blockSignals(False)

    def _on_combo_activated(self, is_target_a: bool, index: int) -> None:
        """コンボボックスのドロップダウン項目が選択された際のハンドラ"""
        combo = self.combo_folder_a if is_target_a else self.combo_folder_b
        item_text = combo.itemText(index)

        if item_text == CLEAR_HISTORY_TEXT:
            combo.setEditText("")
            self._clear_history()
            return

        if item_text and os.path.isdir(item_text):
            self._history = self.history_mgr.add_folder(item_text)
            self._update_history_combos()
            combo.setEditText(item_text)
            self._check_auto_load()

    def _clear_history(self) -> None:
        """確認ダイアログを表示の上、全履歴を消去"""
        reply = QMessageBox.question(
            self,
            "履歴のクリア",
            "実験ログフォルダの選択履歴をすべて消去しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_mgr.clear_history()
            self._history = []
            self._update_history_combos()

    def _browse_folder_smart(self, is_target_a: bool) -> None:
        """参照ボタン押下時: 前回の入力パス等を起点にフォルダ選択ダイアログを開き、履歴に追加"""
        target_combo = self.combo_folder_a if is_target_a else self.combo_folder_b
        other_combo = self.combo_folder_b if is_target_a else self.combo_folder_a

        target_path = target_combo.currentText().strip()
        other_path = other_combo.currentText().strip()

        if target_path and os.path.exists(target_path):
            initial_dir = os.path.dirname(os.path.abspath(target_path))
        elif other_path and os.path.exists(other_path):
            parent_1 = os.path.dirname(os.path.abspath(other_path))
            parent_2 = os.path.dirname(parent_1)
            initial_dir = parent_2 if os.path.exists(parent_2) else parent_1
        else:
            initial_dir = os.getcwd()

        folder = QFileDialog.getExistingDirectory(self, "実験出力ログフォルダを選択", initial_dir)
        if folder:
            norm_folder = os.path.abspath(folder)
            target_combo.setEditText(norm_folder)
            self._history = self.history_mgr.add_folder(norm_folder)
            self._update_history_combos()
            self._check_auto_load()

    def _check_auto_load(self) -> None:
        """両方の入力欄に有効なフォルダが存在する場合に自動読み込みを実行"""
        folder_a = self.combo_folder_a.currentText().strip()
        folder_b = self.combo_folder_b.currentText().strip()

        if folder_a and folder_b:
            if os.path.isdir(folder_a) and os.path.isdir(folder_b):
                if folder_a != self._last_loaded_a or folder_b != self._last_loaded_b:
                    self.load_all()

    def load_folders(self, path_a: str, path_b: str) -> None:
        """フォルダA/Bを指定して読み込み（CLI起動用。履歴には追加しない）"""
        self.combo_folder_a.blockSignals(True)
        self.combo_folder_b.blockSignals(True)
        self.combo_folder_a.setEditText(path_a)
        self.combo_folder_b.setEditText(path_b)
        self.combo_folder_a.blockSignals(False)
        self.combo_folder_b.blockSignals(False)
        self.load_all()

    def load_all(self) -> None:
        """フォルダA/Bのデータを各ビュー（YAML差分、画像比較、CSVグラフ）に読み込み"""
        folder_a = self.combo_folder_a.currentText().strip()
        folder_b = self.combo_folder_b.currentText().strip()

        if not folder_a or not folder_b:
            return

        if not os.path.exists(folder_a) or not os.path.exists(folder_b):
            return

        self._last_loaded_a = folder_a
        self._last_loaded_b = folder_b

        self.tab_yaml.load_yamls(folder_a, folder_b)
        self.tab_images.load_folders(folder_a, folder_b)
        self.tab_csv.load_csvs(folder_a, folder_b)
