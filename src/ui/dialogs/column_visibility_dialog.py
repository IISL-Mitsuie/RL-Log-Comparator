"""
テーブル列の表示・非表示設定ダイアログ (ColumnVisibilityDialog)
"""

from typing import Iterable
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QFrame
)
from PySide6.QtCore import Qt


# 基本列の定義（タイムスタンプは基本列から除外され、フォルダ名がキーとなる）
DEFAULT_BASIC_COLUMNS = {"モード", "Shield", "フォルダ名"}


class ColumnVisibilityDialog(QDialog):
    """テーブル列の表示・非表示をチェックボックス付きリストで編集するダイアログ"""

    def __init__(
        self,
        all_columns: list[str],
        hidden_columns: Iterable[str] = (),
        parent=None
    ):
        super().__init__(parent)
        self.all_columns = all_columns
        self.hidden_set = set(hidden_columns)

        self.setWindowTitle("テーブル列の表示・非表示設定")
        self.resize(420, 520)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 説明文
        lbl_info = QLabel("表示したいカラムにチェックを入れてください:")
        lbl_info.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_info)

        # 検索フィルタ欄
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("列名を検索...")
        self.edit_search.textChanged.connect(self._filter_items)
        layout.addWidget(self.edit_search)

        # クイック操作ボタン行
        btn_quick_lay = QHBoxLayout()
        btn_all = QPushButton("すべて表示")
        btn_all.clicked.connect(self._select_all)
        btn_quick_lay.addWidget(btn_all)

        btn_basic = QPushButton("基本列のみ")
        btn_basic.setToolTip("モード、Shield、フォルダ名のみ表示")
        btn_basic.clicked.connect(self._select_basic_only)
        btn_quick_lay.addWidget(btn_basic)

        btn_none = QPushButton("すべて非表示")
        btn_none.clicked.connect(self._select_none)
        btn_quick_lay.addWidget(btn_none)
        layout.addLayout(btn_quick_lay)

        # カラムリストウィジェット
        self.list_widget = QListWidget()
        for col_name in self.all_columns:
            item = QListWidgetItem(col_name, self.list_widget)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            is_visible = col_name not in self.hidden_set
            item.setCheckState(Qt.CheckState.Checked if is_visible else Qt.CheckState.Unchecked)
        layout.addWidget(self.list_widget, 1)

        # セパレータ
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # 下部ボタン行
        bottom_lay = QHBoxLayout()
        bottom_lay.addStretch()

        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        bottom_lay.addWidget(btn_cancel)

        btn_ok = QPushButton("適用")
        btn_ok.setStyleSheet("font-weight: bold; padding: 4px 16px;")
        btn_ok.clicked.connect(self.accept)
        bottom_lay.addWidget(btn_ok)

        layout.addLayout(bottom_lay)

    def _filter_items(self, text: str):
        query = text.strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(query not in item.text().lower())

    def _select_all(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(Qt.CheckState.Checked)

    def _select_none(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)

    def _select_basic_only(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.text() in DEFAULT_BASIC_COLUMNS:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

    def get_hidden_columns(self) -> set[str]:
        """非表示に設定された列名の集合を返す"""
        hidden = set()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Unchecked:
                hidden.add(item.text())
        return hidden
