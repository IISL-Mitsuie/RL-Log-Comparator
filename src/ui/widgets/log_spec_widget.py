"""
ログデータ仕様ガイド表示＆仕様書 Markdown エクスポートウィジェット
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QFileDialog, QMessageBox
)

from src.core.paths import load_log_spec_markdown


class LogSpecWidget(QWidget):
    """ログデータ仕様ガイド表示＆仕様書 Markdown エクスポート画面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 上部アクションバー
        top_layout = QHBoxLayout()
        lbl_title = QLabel("RL-Log-Comparator ログデータ仕様・ガイド")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #2c3e50;")
        top_layout.addWidget(lbl_title)

        top_layout.addStretch()

        btn_export = QPushButton("📥 ログ仕様書 (DATA_FORMAT.md) をダウンロード")
        btn_export.setStyleSheet(
            "font-weight: bold; background-color: #27ae60; color: white; padding: 6px 12px; border-radius: 4px;"
        )
        btn_export.clicked.connect(self._export_markdown)
        top_layout.addWidget(btn_export)

        layout.addLayout(top_layout)

        # メインテキストビューア
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        layout.addWidget(self.text_browser, 1)

        self.reload_spec()

    def reload_spec(self) -> None:
        """外部の DATA_FORMAT.md を動的再読み込みして表示更新"""
        content = load_log_spec_markdown()
        self.text_browser.setMarkdown(content)

    def showEvent(self, event) -> None:
        """タブ表示時に最新の Markdown ファイルを自動再読み込み"""
        super().showEvent(event)
        self.reload_spec()

    def _export_markdown(self) -> None:
        default_filename = "DATA_FORMAT.md"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "ログフォーマット仕様書 (.md) を保存",
            default_filename,
            "Markdown Files (*.md);;All Files (*)"
        )
        if save_path:
            try:
                content = load_log_spec_markdown()
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(content)
                QMessageBox.information(self, "完了", f"ログ仕様書を保存しました:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"ファイルの保存に失敗しました:\n{e}")
