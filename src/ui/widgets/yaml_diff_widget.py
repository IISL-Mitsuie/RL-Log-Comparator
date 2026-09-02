"""
ハイパーパラメータ (YAML) 差分比較ビューウィジェット
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QCheckBox, QPushButton, QLabel, QHeaderView
)
from PySide6.QtGui import QColor, QBrush, QFont

from src.core.parsers.experiment import get_experiment_info
from src.core.parsers.yaml_diff import read_yaml_file, build_diff_tree, DiffNode


class YamlDiffWidget(QWidget):
    """ハイパーパラメータ (YAML) 差分比較ビュー"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.info_a = "フォルダ A"
        self.info_b = "フォルダ B"
        self.yaml_a = {}
        self.yaml_b = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        ctrl_layout = QHBoxLayout()
        self.cb_diff_only = QCheckBox("差分があるパラメータのみ表示")
        self.cb_diff_only.setChecked(True)
        self.cb_diff_only.toggled.connect(self.refresh_tree)
        ctrl_layout.addWidget(self.cb_diff_only)

        btn_expand = QPushButton("すべて展開")
        btn_expand.clicked.connect(lambda: self.tree.expandAll())
        ctrl_layout.addWidget(btn_expand)

        btn_collapse = QPushButton("すべて折りたたむ")
        btn_collapse.clicked.connect(lambda: self.tree.collapseAll())
        ctrl_layout.addWidget(btn_collapse)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #0055cc; padding: 4px;")
        layout.addWidget(self.lbl_status)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["パラメータキー", "A", "B", "状態"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(0, 250)
        self.tree.setAlternatingRowColors(True)

        layout.addWidget(self.tree)

    def load_yamls(self, path_a: str, path_b: str) -> None:
        """フォルダA/Bの YAML を読み込んでツリーを更新"""
        self.info_a = get_experiment_info(path_a)
        self.info_b = get_experiment_info(path_b)
        self.tree.setHeaderLabels(["パラメータキー", f"A: {self.info_a}", f"B: {self.info_b}", "状態"])

        self.yaml_a = read_yaml_file(path_a)
        self.yaml_b = read_yaml_file(path_b)
        self.refresh_tree()

    def refresh_tree(self) -> None:
        """現在の差分表示設定に基づいてツリーを再構築"""
        self.tree.clear()
        diff_only = self.cb_diff_only.isChecked()

        nodes = build_diff_tree(self.yaml_a, self.yaml_b, diff_only=diff_only)

        for node in nodes:
            self._render_node(self.tree.invisibleRootItem(), node)

        self.tree.expandAll()

        root_count = self.tree.topLevelItemCount()
        if root_count == 0:
            if diff_only and (self.yaml_a or self.yaml_b):
                self.lbl_status.setText("※ 差分のあるパラメータはありません（すべての設定値が完全一致しています）")
            else:
                self.lbl_status.setText("※ 表示できるハイパーパラメータが存在しません")
        else:
            if diff_only:
                self.lbl_status.setText(f"※ 差分のあるパラメータを表示中 ({root_count} 項目)")
            else:
                self.lbl_status.setText(f"※ 全パラメータを表示中 ({root_count} 項目)")

    def _render_node(self, parent_item: QTreeWidgetItem, node: DiffNode) -> None:
        """DiffNode 構造体を QTreeWidgetItem に描画"""
        item = QTreeWidgetItem(parent_item, [node.key, node.val_a_str, node.val_b_str, node.state_str])

        if node.bg_color_hex:
            bg_color = QColor(node.bg_color_hex)
            for col in range(4):
                item.setBackground(col, QBrush(bg_color))
            item.setFont(0, QFont("", -1, QFont.Weight.Bold))

        for child in node.children:
            self._render_node(item, child)
