"""
キーボードショートカット一覧ダイアログ (ShortcutsDialog)
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


# カテゴリ別ショートカット・マウス操作の定義
SHORTCUT_DATA: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "📁 ファイル操作",
        [
            ("フォルダ A を開く…", "Ctrl+O"),
            ("フォルダ B を開く…", "Ctrl+Shift+O"),
            ("A と B を入れ替え", "Ctrl+Shift+X"),
            ("アプリケーション終了", "Ctrl+Q"),
        ],
    ),
    (
        "📑 タブ・画面切り替え",
        [
            ("1. 実験ログ一覧・探索", "Ctrl+1"),
            ("2. ハイパーパラメータ差分", "Ctrl+2"),
            ("3. 画像目視比較", "Ctrl+3"),
            ("4. 数値ログ比較グラフ", "Ctrl+4"),
            ("5. ログ仕様ガイド・エクスポート", "Ctrl+5"),
        ],
    ),
    (
        "❓ ヘルプ・ガイド",
        [
            ("ログ仕様ガイドを表示", "F1"),
            ("キーボードショートカット一覧を表示", "F2"),
        ],
    ),
    (
        "🖱️ マウス・ビュー操作（早見）",
        [
            ("テーブル横スクロール (Log Explorer)", "Shift + マウスホイール"),
            ("ズームイン / ズームアウト (画像比較)", "マウスホイール"),
            ("パン移動 (画像比較)", "ドラッグ"),
        ],
    ),
]


class ShortcutsDialog(QDialog):
    """キーボードショートカットおよび操作一覧を表示するダイアログ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("キーボードショートカット一覧")
        self.resize(540, 460)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 1. 案内ラベル
        lbl_info = QLabel("本アプリケーションで利用可能なキーボードショートカットおよびマウス操作一覧です:")
        lbl_info.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_info)

        # 2. 検索フィルタボックス
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("操作やキーを検索...")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._filter_items)
        layout.addWidget(self.edit_search)

        # 3. ショートカット一覧ツリー
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["操作・機能", "キーボードショートカット / 操作"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)

        header_font = self.tree.header().font()
        header_font.setBold(True)
        self.tree.header().setFont(header_font)

        self._populate_tree()
        layout.addWidget(self.tree, 1)

        # 4. 下部ボタン行
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()

        self.btn_close = QPushButton("閉じる")
        self.btn_close.setDefault(True)
        self.btn_close.clicked.connect(self.accept)
        btn_lay.addWidget(self.btn_close)

        layout.addLayout(btn_lay)

    def _populate_tree(self):
        """ツリーにカテゴリと各ショートカット項目を追加"""
        self.tree.clear()
        category_font = QFont()
        category_font.setBold(True)

        key_font = QFont("Consolas, 'Courier New', monospace")
        key_font.setBold(True)

        for category_title, items in SHORTCUT_DATA:
            cat_item = QTreeWidgetItem(self.tree, [category_title, ""])
            cat_item.setFont(0, category_font)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

            for action_text, shortcut_text in items:
                child = QTreeWidgetItem(cat_item, [action_text, shortcut_text])
                child.setFont(1, key_font)
                child.setTextAlignment(1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.tree.expandAll()

    def _filter_items(self, text: str):
        """検索文字列による項目の動的フィルタリング"""
        query = text.strip().lower()

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat_item = root.child(i)
            cat_text = cat_item.text(0).lower()
            cat_matches = query in cat_text

            matched_children_count = 0
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                action_text = child.text(0).lower()
                shortcut_text = child.text(1).lower()

                if not query or cat_matches or query in action_text or query in shortcut_text:
                    child.setHidden(False)
                    matched_children_count += 1
                else:
                    child.setHidden(True)

            if not query or cat_matches or matched_children_count > 0:
                cat_item.setHidden(False)
                cat_item.setExpanded(True)
            else:
                cat_item.setHidden(True)
