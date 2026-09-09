"""
実験ログ選択時アクションダイアログ (ExperimentActionDialog)
ダブルクリック時に「フォルダAに設定」「フォルダBに設定」「フォルダをエクスプローラーで開く」を選択
"""

from enum import Enum, auto
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGroupBox
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from src.core.parsers.experiment_scanner import ExperimentLogRecord


class ExperimentAction(Enum):
    """ダイアログで選択されたアクション"""
    CANCEL = auto()
    SET_A = auto()
    SET_B = auto()
    OPEN_EXPLORER = auto()


class ExperimentActionDialog(QDialog):
    """実験ログ選択時のアクション確認・実行ダイアログ"""

    def __init__(self, record: ExperimentLogRecord, parent=None):
        super().__init__(parent)
        self.record = record
        self.selected_action = ExperimentAction.CANCEL

        self.setWindowTitle("実験ログのアクション選択")
        self.setFixedWidth(520)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. 実験概要情報表示
        info_group = QGroupBox("選択された実験ログ")
        info_lay = QVBoxLayout(info_group)
        info_lay.setSpacing(6)

        shield_str = f" <span style='font-size: 12px; color: #555;'>(Shield: {self.record.display_shield})</span>" if self.record.display_shield != "-" else ""
        lbl_title = QLabel(f"<b>[{self.record.mode}]</b>{shield_str} {self.record.display_timestamp}")

        lbl_title.setStyleSheet("font-size: 14px;")
        info_lay.addWidget(lbl_title)

        lbl_folder = QLabel(f"フォルダ: {self.record.folder_name}")
        info_lay.addWidget(lbl_folder)

        lbl_path = QLabel(f"<span style='color: #666; font-size: 11px;'>{self.record.folder_path}</span>")
        lbl_path.setWordWrap(True)
        info_lay.addWidget(lbl_path)

        layout.addWidget(info_group)

        # 2. ガイダンス
        lbl_prompt = QLabel("この実験ログに対して実行するアクションを選択してください:")
        layout.addWidget(lbl_prompt)

        # 3. アクションボタン群
        btn_lay = QVBoxLayout()
        btn_lay.setSpacing(8)

        self.btn_set_a = QPushButton("🅰️ フォルダ A (基準) に設定")
        self.btn_set_a.setStyleSheet("padding: 8px 14px; font-weight: bold; text-align: left;")
        self.btn_set_a.clicked.connect(self._on_set_a)
        btn_lay.addWidget(self.btn_set_a)

        self.btn_set_b = QPushButton("🅱️ フォルダ B (比較) に設定")
        self.btn_set_b.setStyleSheet("padding: 8px 14px; font-weight: bold; text-align: left;")
        self.btn_set_b.clicked.connect(self._on_set_b)
        btn_lay.addWidget(self.btn_set_b)

        self.btn_explorer = QPushButton("📁 フォルダをエクスプローラーで開く")
        self.btn_explorer.setStyleSheet("padding: 8px 14px; text-align: left;")
        self.btn_explorer.clicked.connect(self._on_open_explorer)
        btn_lay.addWidget(self.btn_explorer)

        layout.addLayout(btn_lay)

        # セパレータ
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # 4. 下部: キャンセルボタン
        bottom_lay = QHBoxLayout()
        bottom_lay.addStretch()
        btn_cancel = QPushButton("キャンセル")
        btn_cancel.clicked.connect(self.reject)
        bottom_lay.addWidget(btn_cancel)

        layout.addLayout(bottom_lay)

    def _on_set_a(self):
        self.selected_action = ExperimentAction.SET_A
        self.accept()

    def _on_set_b(self):
        self.selected_action = ExperimentAction.SET_B
        self.accept()

    def _on_open_explorer(self):
        self.selected_action = ExperimentAction.OPEN_EXPLORER
        # OS標準のエクスプローラーで開く
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.record.folder_path))
        self.accept()
