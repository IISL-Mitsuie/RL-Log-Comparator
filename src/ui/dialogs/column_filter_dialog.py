"""
テーブル列ごとのフィルター設定ダイアログ (ColumnFilterDialog)
Excel風のハイブリッド方式: 検索テキスト入力 + ユニーク値チェックボックス選択
"""

from typing import Optional, Iterable
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QFrame
)
from PySide6.QtCore import Qt


class ColumnFilterDialog(QDialog):
    """テーブル列のユニーク値一覧から絞り込みを行うダイアログ"""

    def __init__(
        self,
        column_name: str,
        unique_values: list[str],
        current_selected_values: Optional[Iterable[str]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.column_name = column_name
        self.unique_values = unique_values
        self.selected_set: set[str] = (
            set(current_selected_values) if current_selected_values is not None
            else set(unique_values)
        )
        self._is_filter_cleared: bool = False

        self.setWindowTitle(f"列フィルター: {column_name}")
        self.resize(380, 480)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 列名ヘッダー
        lbl_info = QLabel(f"列「{self.column_name}」の絞り込み:")
        lbl_info.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_info)

        # 検索入力欄（テキスト絞り込み）
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("値を検索して絞り込み...")
        self.edit_search.textChanged.connect(self._filter_items)
        layout.addWidget(self.edit_search)

        # クイック操作ボタン行
        btn_lay = QHBoxLayout()
        btn_all = QPushButton("すべて選択")
        btn_all.clicked.connect(self._select_all)
        btn_lay.addWidget(btn_all)

        btn_none = QPushButton("すべて解除")
        btn_none.clicked.connect(self._select_none)
        btn_lay.addWidget(btn_none)
        layout.addLayout(btn_lay)

        # ユニーク値チェックリスト
        self.list_widget = QListWidget()
        for val in self.unique_values:
            display_text = val if val != "" else "(空白)"
            item = QListWidgetItem(display_text, self.list_widget)
            item.setData(Qt.ItemDataRole.UserRole, val)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            is_checked = val in self.selected_set
            item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
        layout.addWidget(self.list_widget, 1)

        # セパレータ
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # 下部ボタン行
        bottom_lay = QHBoxLayout()

        btn_clear = QPushButton("この列のフィルターを解除")
        btn_clear.setToolTip("この列の絞り込みを解除して全件表示にします")
        btn_clear.clicked.connect(self._on_clear_clicked)
        bottom_lay.addWidget(btn_clear)

        bottom_lay.addStretch()

        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        bottom_lay.addWidget(btn_cancel)

        btn_apply = QPushButton("適用")
        btn_apply.setStyleSheet("font-weight: bold; padding: 4px 16px;")
        btn_apply.clicked.connect(self.accept)
        bottom_lay.addWidget(btn_apply)

        layout.addLayout(bottom_lay)

    def _filter_items(self, text: str):
        query = text.strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            raw_val = item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(query not in raw_val.lower())

    def _select_all(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            # 検索で表示されている項目のみ選択するか、全体か（全体を選択）
            item.setCheckState(Qt.CheckState.Checked)

    def _select_none(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)

    def _on_clear_clicked(self):
        self._is_filter_cleared = True
        self.accept()

    def get_filter_result(self) -> tuple[bool, set[str]]:
        """
        フィルター結果を返す: (is_filtered, selected_values)
        - is_filtered: フィルターが有効（絞り込み中）なら True、全件表示なら False
        - selected_values: 表示対象となる値の集合
        """
        if self._is_filter_cleared:
            return False, set(self.unique_values)

        selected = set()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.add(item.data(Qt.ItemDataRole.UserRole))

        # 全て選択されている場合はフィルターなしと等価
        if len(selected) == len(self.unique_values):
            return False, selected

        return True, selected
