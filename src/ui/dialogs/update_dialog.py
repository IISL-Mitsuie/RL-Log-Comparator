"""
アップデート確認・ダウンロード・インストール適用ダイアログ (PySide6)
"""

import os
import sys
import threading
import webbrowser
import subprocess
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextBrowser, QProgressBar, QPushButton,
    QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QObject

from src.core.updater import UpdateInfo, download_installer, launch_installer_and_exit


class _DownloadWorker(QObject):
    """インストーラーダウンロード非同期ワーカー"""
    progress = Signal(int, str)      # (進捗率 %, メッセージ文字列)
    finished = Signal(str)           # (保存されたインストーラーパス)
    cancelled = Signal()
    failed = Signal(str)             # (エラーメッセージ)

    def __init__(self, download_url: str, filename: Optional[str] = None):
        super().__init__()
        self.download_url = download_url
        self.filename = filename
        self.cancel_event = threading.Event()

    def run(self):
        try:
            def _on_prog(dl: int, total: int):
                if total > 0:
                    pct = int((dl / total) * 100)
                    msg = f"ダウンロード中: {dl / (1024 * 1024):.1f} MB / {total / (1024 * 1024):.1f} MB ({pct}%)"
                    self.progress.emit(pct, msg)
                else:
                    msg = f"ダウンロード中: {dl / (1024 * 1024):.1f} MB"
                    self.progress.emit(0, msg)

            save_path = download_installer(
                self.download_url,
                target_filename=self.filename,
                progress_callback=_on_prog,
                cancel_event=self.cancel_event
            )
            self.finished.emit(save_path)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDialog(QDialog):
    """新バージョン案内・ダウンロード・更新適用ダイアログ"""

    def __init__(self, parent: Optional[QWidget], update_info: UpdateInfo, current_version: str):
        super().__init__(parent)
        self.update_info = update_info
        self.current_version = current_version
        self.worker: Optional[_DownloadWorker] = None
        self.download_thread: Optional[threading.Thread] = None
        self.downloaded_installer_path: Optional[str] = None

        self.setWindowTitle("アプリケーション アップデート")
        self.resize(700, 560)
        self.setMinimumSize(580, 440)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # 1. ヘッダー領域
        header_layout = QVBoxLayout()
        title_label = QLabel("🚀 新バージョンが利用可能です！")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title_label)

        size_text = ""
        if self.update_info.installer_size > 0:
            size_mb = self.update_info.installer_size / (1024 * 1024)
            size_text = f" ({size_mb:.1f} MB)"

        ver_text = (
            f"現在のバージョン: <b>v{self.current_version}</b>  ➔  "
            f"最新バージョン: <b style='color: #0969da;'>v{self.update_info.version}</b>{size_text}"
        )
        ver_label = QLabel(ver_text)
        ver_label.setStyleSheet("font-size: 13px;")
        header_layout.addWidget(ver_label)
        main_layout.addLayout(header_layout)

        # 境界線
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # 2. リリースノート表示
        notes_label = QLabel("<b>リリースノート:</b>")
        main_layout.addWidget(notes_label)

        self.notes_browser = QTextBrowser()
        self.notes_browser.setOpenExternalLinks(True)
        raw_notes = self.update_info.release_notes.strip() if self.update_info.release_notes else ""
        if raw_notes:
            self.notes_browser.setMarkdown(raw_notes)
        else:
            self.notes_browser.setPlainText("詳細なリリースノートはGitHubリリースページをご覧ください。")
        main_layout.addWidget(self.notes_browser, 1)

        # 3. ダウンロード進捗領域（初期は非表示）
        self.progress_container = QWidget()
        prog_layout = QVBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(4)

        self.progress_label = QLabel("ダウンロード準備中...")
        self.progress_label.setStyleSheet("color: #57606a; font-size: 12px;")
        prog_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        prog_layout.addWidget(self.progress_bar)

        self.progress_container.setVisible(False)
        main_layout.addWidget(self.progress_container)

        # 4. 下部ボタンバー
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_browser = QPushButton("GitHubで確認")
        self.btn_browser.clicked.connect(self._open_github)
        btn_layout.addWidget(self.btn_browser)

        btn_layout.addStretch()

        self.btn_close = QPushButton("閉じる")
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_close)

        if self.update_info.installer_download_url:
            self.btn_update = QPushButton("今すぐアップデート (自動インストール)")
            self.btn_update.setStyleSheet(
                "QPushButton {"
                "   background-color: #0969da; color: white; font-weight: bold; padding: 6px 16px;"
                "}"
                "QPushButton:hover {"
                "   background-color: #0858b9;"
                "}"
                "QPushButton:disabled {"
                "   background-color: #8c959f;"
                "}"
            )
            self.btn_update.clicked.connect(self._start_download)
            btn_layout.addWidget(self.btn_update)
        else:
            self.btn_update = None

        main_layout.addLayout(btn_layout)

    def _open_github(self):
        """ブラウザで GitHub リリースページを開く"""
        if self.update_info.release_url:
            webbrowser.open(self.update_info.release_url)

    def _start_download(self):
        """インストーラーの非同期ダウンロードを開始"""
        if not self.update_info.installer_download_url:
            return

        if self.btn_update:
            self.btn_update.setEnabled(False)
            self.btn_update.setText("ダウンロード中...")
        self.btn_close.setText("キャンセル")

        self.progress_container.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("接続中...")

        self.worker = _DownloadWorker(
            download_url=self.update_info.installer_download_url,
            filename=self.update_info.installer_name
        )
        self.worker.progress.connect(self._on_download_progress)
        self.worker.finished.connect(self._on_download_finished)
        self.worker.cancelled.connect(self._on_download_cancelled)
        self.worker.failed.connect(self._on_download_failed)

        self.download_thread = threading.Thread(target=self.worker.run, daemon=True)
        self.download_thread.start()

    def _on_download_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.progress_label.setText(msg)

    def _on_download_finished(self, save_path: str):
        self.downloaded_installer_path = save_path
        file_name = os.path.basename(save_path)

        self.progress_bar.setValue(100)
        self.progress_label.setText(f"✓ ダウンロード完了: {file_name}")

        self.btn_close.setText("後で (閉じる)")
        self.btn_browser.setText("保存先フォルダを開く")
        self.btn_browser.clicked.disconnect()
        self.btn_browser.clicked.connect(lambda: self._open_folder(save_path))

        if self.btn_update:
            self.btn_update.setEnabled(True)
            self.btn_update.setText("今すぐインストール")
            self.btn_update.clicked.disconnect()
            self.btn_update.clicked.connect(lambda: launch_installer_and_exit(save_path))

        reply = QMessageBox.question(
            self,
            "ダウンロード完了",
            f"インストーラー ({file_name}) のダウンロードが完了しました。\n\n"
            "今すぐアプリを終了してインストーラーを起動しますか？\n\n"
            "・「はい」: アプリを終了し、インストーラーを起動して更新\n"
            "・「いいえ」: 起動せず、後でダイアログから実行",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            launch_installer_and_exit(save_path)

    def _open_folder(self, file_path: str):
        """保存先フォルダを開き、ファイルをハイライト"""
        abs_path = os.path.abspath(file_path)
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{abs_path}"')
        else:
            webbrowser.open(os.path.dirname(abs_path))

    def _on_download_cancelled(self):
        self.progress_container.setVisible(False)
        if self.btn_update:
            self.btn_update.setEnabled(True)
            self.btn_update.setText("今すぐアップデート (自動インストール)")
        self.btn_close.setText("閉じる")
        QMessageBox.information(self, "キャンセル", "ダウンロードを中止しました。")

    def _on_download_failed(self, err_msg: str):
        self.progress_container.setVisible(False)
        if self.btn_update:
            self.btn_update.setEnabled(True)
            self.btn_update.setText("今すぐアップデート (自動インストール)")
        self.btn_close.setText("閉じる")
        QMessageBox.critical(self, "エラー", f"ダウンロードに失敗しました:\n{err_msg}")

    def closeEvent(self, event):
        if self.worker and self.download_thread and self.download_thread.is_alive():
            reply = QMessageBox.question(
                self,
                "ダウンロード中止",
                "インストーラーのダウンロードが進行中です。中止して閉じますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.cancel_event.set()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
