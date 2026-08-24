"""
RL-Log-Comparator (PySide6 GUI)
強化学習実験ログ対比・比較分析ツール

2つの実験出力フォルダ (output_YYYYMMDD_HHMMSS) を選択し、
1. ハイパーパラメータ (config_used_*.yaml) の差分比較（初期状態は差分項目のみ表示）
2. 同種画像 (learning_rewards, learning_steps, trajectory 等) の同期パン＆ズーム対応並列目視比較
3. 数値ログ (learning_log_*.csv) の移動平均付き重ね合わせ比較グラフ描画
4. ログデータの最低仕様・推奨仕様ガイド表示および仕様書 Markdown エクスポート
を行うスタンドアロン GUI ツールです。

Usage:
    python main.py [folder_A] [folder_B]
"""

import sys
import os
import glob
import re
import ctypes
import tempfile

# Windows タスクバーでのグループ化およびアプリアイコン分離
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("IISL.RL_Log_Comparator.1_0")
except Exception:
    pass

# Matplotlib のキャッシュディレクトリ設定（import matplotlib 前に設定して他環境の破損キャッシュ競合を回避）
local_appdata = os.environ.get('LOCALAPPDATA', tempfile.gettempdir())
mpl_cache_dir = os.path.join(local_appdata, 'RL-Log-Comparator', '.matplotlib')

try:
    os.makedirs(mpl_cache_dir, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = mpl_cache_dir
except Exception:
    pass


def get_bundled_font_path():
    """アプリに同梱された日本語フォント (ipaexg.ttf) の絶対パスを取得"""
    if getattr(sys, 'frozen', False):
        base_dirs = [
            getattr(sys, '_MEIPASS', ''),
            os.path.dirname(sys.executable),
        ]
    else:
        base_dirs = [
            os.path.dirname(os.path.abspath(__file__)),
        ]

    for b in base_dirs:
        if not b:
            continue
        candidates = [
            os.path.join(b, "fonts", "ipaexg.ttf"),
            os.path.join(b, "packaging", "fonts", "ipaexg.ttf"),
            os.path.join(b, "ipaexg.ttf"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return os.path.abspath(c)
    return ""


import yaml
import numpy as np
import pandas as pd

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QCheckBox, QComboBox, QSlider,
    QLabel, QPushButton, QTabWidget, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QGroupBox, QLineEdit, QMessageBox, QFrame, QHeaderView,
    QListWidget, QListWidgetItem, QTextBrowser
)
from PySide6.QtGui import QPixmap, QTransform, QColor, QBrush, QFont, QWheelEvent, QIcon
from PySide6.QtCore import Qt, Signal, Slot, QPointF

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure


def setup_matplotlib_japanese_font():
    """
    Matplotlib の日本語および英数字フォント設定を確実に行う
    1. 同梱されたオープンソース日本語フォント (ipaexg.ttf) を最優先で登録
    2. Windows 標準のフォント (MS Gothic, Yu Gothic, Meiryo, BIZ UDGothic) をフォールバック登録
    3. rcParams のフォントファミリー、文字色、負符号を確実に設定
    """
    registered_families = []

    def register_font_file(font_path):
        if not font_path or not os.path.exists(font_path):
            return
        try:
            fm.fontManager.addfont(font_path)
            prop = fm.FontProperties(fname=font_path)
            name = prop.get_name()
            if name and name not in registered_families:
                registered_families.append(name)
        except Exception:
            pass

    # 1. 同梱フォント (IPAexゴシック) の登録（最優先）
    bundled_font = get_bundled_font_path()
    register_font_file(bundled_font)

    # 2. Windows 標準フォントの登録（フォールバック）
    windir = os.environ.get('WINDIR', r'C:\Windows')
    fonts_dir = os.path.join(windir, 'Fonts')
    win_font_files = ['msgothic.ttc', 'YuGothM.ttc', 'meiryo.ttc', 'BIZ-UDGothicR.ttc']

    for font_file in win_font_files:
        register_font_file(os.path.join(fonts_dir, font_file))

    # 3. フォールバックリストの構成（確実に存在する名前のみ + DejaVu Sans）
    final_font_list = registered_families if registered_families else ['DejaVu Sans']
    if 'DejaVu Sans' not in final_font_list:
        final_font_list.append('DejaVu Sans')

    plt.rcParams['font.family'] = final_font_list
    plt.rcParams['font.sans-serif'] = final_font_list
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['text.color'] = '#222222'
    plt.rcParams['axes.labelcolor'] = '#222222'
    plt.rcParams['xtick.color'] = '#222222'
    plt.rcParams['ytick.color'] = '#222222'
    plt.rcParams['axes.edgecolor'] = '#888888'


# フォント設定を初期実行
setup_matplotlib_japanese_font()


def get_app_icon_path():
    """アプリアイコン (.ico) のパスを取得"""
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(base_dir, "packaging", "app_icon.ico"),
        os.path.join(base_dir, "app_icon.ico"),
        os.path.join(base_dir, "reference", "image_icon.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def get_log_spec_path():
    """DATA_FORMAT.md (または reference/RL-Log-Comparator_Log_Format_Spec.md) の絶対パスを取得"""
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(base_dir, "DATA_FORMAT.md"),
        os.path.join(base_dir, "reference", "RL-Log-Comparator_Log_Format_Spec.md"),
        os.path.join(base_dir, "doc", "RL-Log-Comparator_Log_Format_Spec.md"),
        os.path.join(base_dir, "RL-Log-Comparator_Log_Format_Spec.md"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def load_log_spec_markdown():
    """DATA_FORMAT.md を読み込んで内容を返す（未存在時はエラー文）"""
    spec_path = get_log_spec_path()
    if os.path.exists(spec_path):
        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"# エラー\n\n仕様書ファイルの読み込みに失敗しました:\n`{e}`"
    return f"# エラー\n\n仕様書ファイルが見つかりません:\n`{spec_path}`"


def get_experiment_info(folder_path):
    """
    フォルダパスから学習モード（RL, S-SAP, Q-SAP等）とタイムスタンプを抽出して整形文字列を返す
    例: '[S-SAP] 20260801_235449'
    """
    if not folder_path or not os.path.exists(folder_path):
        return "未選択 / 存在しないフォルダ"

    abs_path = os.path.abspath(folder_path)
    folder_name = os.path.basename(abs_path)
    parent_name = os.path.basename(os.path.dirname(abs_path))

    timestamp = folder_name
    match = re.search(r'(\d{8}_\d{6})', folder_name)
    if match:
        timestamp = match.group(1)

    mode = parent_name
    yaml_files = glob.glob(os.path.join(abs_path, "config_used_*.yaml"))
    if yaml_files:
        try:
            with open(yaml_files[0], 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                if 'mode' in data:
                    mode = str(data['mode'])
                elif 'algorithm' in data:
                    mode = str(data['algorithm'])
        except Exception:
            pass

    return f"[{mode}] {timestamp}"


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
        btn_export.setStyleSheet("font-weight: bold; background-color: #27ae60; color: white; padding: 6px 12px; border-radius: 4px;")
        btn_export.clicked.connect(self._export_markdown)
        top_layout.addWidget(btn_export)

        layout.addLayout(top_layout)

        # メインテキストビューア
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        layout.addWidget(self.text_browser, 1)

        self.reload_spec()

    def reload_spec(self):
        """外部の DATA_FORMAT.md を動的再読み込みして表示更新"""
        content = load_log_spec_markdown()
        self.text_browser.setMarkdown(content)

    def showEvent(self, event):
        """タブ表示時に最新の Markdown ファイルを自動再読み込み"""
        super().showEvent(event)
        self.reload_spec()

    def _export_markdown(self):
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


class SyncGraphicsView(QGraphicsView):
    """同期パン＆ズーム機能を備えた QGraphicsView"""

    zoomed = Signal(float, QPointF)
    scrolled = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(self.renderHints())
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.partner_view = None
        self._is_syncing = False

        self.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_partner(self, partner):
        self.partner_view = partner

    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor

        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)

        if self.partner_view and not self._is_syncing:
            self._is_syncing = True
            self.partner_view._sync_zoom(zoom_factor)
            self._is_syncing = False

        event.accept()

    def _sync_zoom(self, zoom_factor):
        self.scale(zoom_factor, zoom_factor)

    def _on_scroll(self):
        if self.partner_view and not self._is_syncing:
            self._is_syncing = True
            h_val = self.horizontalScrollBar().value()
            v_val = self.verticalScrollBar().value()
            self.partner_view._sync_scroll(h_val, v_val)
            self._is_syncing = False

    def _sync_scroll(self, h_val, v_val):
        self.horizontalScrollBar().setValue(h_val)
        self.verticalScrollBar().setValue(v_val)


class YamlDiffWidget(QWidget):
    """ハイパーパラメータ (YAML) 差分比較ビュー"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.info_a = "フォルダ A"
        self.info_b = "フォルダ B"
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

        self.yaml_a = {}
        self.yaml_b = {}

    def load_yamls(self, path_a, path_b):
        self.info_a = get_experiment_info(path_a)
        self.info_b = get_experiment_info(path_b)
        self.tree.setHeaderLabels(["パラメータキー", f"A: {self.info_a}", f"B: {self.info_b}", "状態"])

        self.yaml_a = self._read_yaml(path_a)
        self.yaml_b = self._read_yaml(path_b)
        self.refresh_tree()

    def _read_yaml(self, folder_path):
        if not folder_path or not os.path.isdir(folder_path):
            return {}
        yaml_files = glob.glob(os.path.join(folder_path, "config_used_*.yaml"))
        if not yaml_files:
            yaml_files = glob.glob(os.path.join(folder_path, "*.yaml"))
        if not yaml_files:
            return {}
        try:
            with open(yaml_files[0], "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[ERROR] Failed to read YAML ({yaml_files[0]}): {e}")
            return {}

    def refresh_tree(self):
        self.tree.clear()
        diff_only = self.cb_diff_only.isChecked()

        all_keys = sorted(list(set(self.yaml_a.keys()) | set(self.yaml_b.keys())))

        for key in all_keys:
            val_a = self.yaml_a.get(key)
            val_b = self.yaml_b.get(key)
            self._build_tree_nodes(self.tree.invisibleRootItem(), key, val_a, val_b, diff_only)

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

    def _build_tree_nodes(self, parent_item, key, val_a, val_b, diff_only):
        has_a = val_a is not None
        has_b = val_b is not None

        if isinstance(val_a, dict) or isinstance(val_b, dict):
            dict_a = val_a if isinstance(val_a, dict) else {}
            dict_b = val_b if isinstance(val_b, dict) else {}
            sub_keys = sorted(list(set(dict_a.keys()) | set(dict_b.keys())))

            item = QTreeWidgetItem(parent_item, [str(key), "", "", "階層"])
            has_diff_in_children = False

            for skey in sub_keys:
                s_a = dict_a.get(skey)
                s_b = dict_b.get(skey)
                child_has_diff = self._build_tree_nodes(item, skey, s_a, s_b, diff_only)
                if child_has_diff:
                    has_diff_in_children = True

            if diff_only and not has_diff_in_children:
                index = parent_item.indexOfChild(item)
                if index >= 0:
                    parent_item.takeChild(index)
                return False
            return True

        is_different = False
        state_str = "一致"
        bg_color = None

        if not has_a and has_b:
            is_different = True
            state_str = "Bのみ存在"
            bg_color = QColor(255, 230, 230)
        elif has_a and not has_b:
            is_different = True
            state_str = "Aのみ存在"
            bg_color = QColor(230, 255, 230)
        elif val_a != val_b:
            is_different = True
            state_str = "差分あり"
            bg_color = QColor(255, 245, 200)

        if diff_only and not is_different:
            return False

        str_a = str(val_a) if has_a else "(なし)"
        str_b = str(val_b) if has_b else "(なし)"

        item = QTreeWidgetItem(parent_item, [str(key), str_a, str_b, state_str])

        if bg_color:
            for col in range(4):
                item.setBackground(col, QBrush(bg_color))
            item.setFont(0, QFont("", -1, QFont.Weight.Bold))

        return is_different


class ImageCompareWidget(QWidget):
    """同種画像並列目視比較ビュー"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder_a = ""
        self.folder_b = ""
        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_box = QGroupBox("画像種別一覧 (常時表示)")
        left_layout = QVBoxLayout(left_box)

        self.list_images = QListWidget()
        self.list_images.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_images.currentRowChanged.connect(self._on_image_selected)
        left_layout.addWidget(self.list_images)

        btn_reset_zoom = QPushButton("ズーム・位置リセット")
        btn_reset_zoom.clicked.connect(self._reset_views)
        left_layout.addWidget(btn_reset_zoom)

        self.main_splitter.addWidget(left_box)

        right_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.box_a = QGroupBox("実験 A")
        lay_a = QVBoxLayout(self.box_a)
        self.scene_a = QGraphicsScene()
        self.view_a = SyncGraphicsView(self.scene_a)
        lay_a.addWidget(self.view_a)
        right_splitter.addWidget(self.box_a)

        self.box_b = QGroupBox("実験 B")
        lay_b = QVBoxLayout(self.box_b)
        self.scene_b = QGraphicsScene()
        self.view_b = SyncGraphicsView(self.scene_b)
        lay_b.addWidget(self.view_b)
        right_splitter.addWidget(self.box_b)

        self.view_a.set_partner(self.view_b)
        self.view_b.set_partner(self.view_a)

        self.main_splitter.addWidget(right_splitter)
        self.main_splitter.setSizes([240, 1000])

        main_layout.addWidget(self.main_splitter)

    def load_folders(self, folder_a, folder_b):
        self.folder_a = folder_a
        self.folder_b = folder_b

        info_a = get_experiment_info(folder_a)
        info_b = get_experiment_info(folder_b)
        self.box_a.setTitle(f"実験 A: {info_a}")
        self.box_b.setTitle(f"実験 B: {info_b}")

        self._detect_images()

    def _detect_images(self):
        self.list_images.blockSignals(True)
        self.list_images.clear()

        imgs_a = glob.glob(os.path.join(self.folder_a, "*.png")) if self.folder_a else []
        imgs_b = glob.glob(os.path.join(self.folder_b, "*.png")) if self.folder_b else []

        def extract_prefix(filepath):
            filename = os.path.basename(filepath)
            name_no_ext = os.path.splitext(filename)[0]
            parts = name_no_ext.split('_')
            if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
                return "_".join(parts[:-2])
            elif len(parts) >= 2 and parts[-1].isdigit():
                return "_".join(parts[:-1])
            return name_no_ext

        prefixes_a = {extract_prefix(p): p for p in imgs_a}
        prefixes_b = {extract_prefix(p): p for p in imgs_b}

        all_prefixes = sorted(list(set(prefixes_a.keys()) | set(prefixes_b.keys())))

        for prefix in all_prefixes:
            has_in_a = prefix in prefixes_a
            has_in_b = prefix in prefixes_b
            tag = ""
            if has_in_a and has_in_b:
                tag = " (両方)"
            elif has_in_a:
                tag = " (Aのみ)"
            else:
                tag = " (Bのみ)"

            item = QListWidgetItem(f"{prefix}{tag}")
            item.setData(Qt.ItemDataRole.UserRole, (prefixes_a.get(prefix), prefixes_b.get(prefix)))
            self.list_images.addItem(item)

        self.list_images.blockSignals(False)

        if self.list_images.count() > 0:
            self.list_images.setCurrentRow(0)
        else:
            self.scene_a.clear()
            self.scene_b.clear()

    def _on_image_selected(self, row):
        if row < 0:
            return
        item = self.list_images.item(row)
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        file_a, file_b = data

        self._show_image(self.scene_a, self.view_a, file_a)
        self._show_image(self.scene_b, self.view_b, file_b)
        self._reset_views()

    def _show_image(self, scene, view, file_path):
        scene.clear()
        if file_path and os.path.exists(file_path):
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scene.addPixmap(pixmap)
                scene.setSceneRect(pixmap.rect().toRectF())

    def _reset_views(self):
        self.view_a.resetTransform()
        self.view_b.resetTransform()
        if not self.scene_a.itemsBoundingRect().isEmpty():
            self.view_a.fitInView(self.scene_a.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        if not self.scene_b.itemsBoundingRect().isEmpty():
            self.view_b.fitInView(self.scene_b.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)


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

        left_box = QGroupBox("表示指標一覧 (常時表示)")
        left_lay = QVBoxLayout(left_box)

        self.list_metrics = QListWidget()
        metrics = [
            ("TotalReward (累計報酬)", 0),
            ("Steps (エピソードステップ数)", 1),
            ("UnsafeActions (安全違反回数)", 2),
            ("GoalSuccessRate (成功率 %)", 3)
        ]
        for name, idx in metrics:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.list_metrics.addItem(item)

        self.list_metrics.currentRowChanged.connect(self.update_chart)
        left_lay.addWidget(self.list_metrics)

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

        self.cb_raw_data = QCheckBox("生データを背景表示")
        self.cb_raw_data.setChecked(True)
        self.cb_raw_data.toggled.connect(self.update_chart)
        left_lay.addWidget(self.cb_raw_data)

        self.main_splitter.addWidget(left_box)

        right_widget = QWidget()
        right_lay = QVBoxLayout(right_widget)

        self.figure = Figure(figsize=(8, 5), dpi=100, facecolor='#ffffff')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        right_lay.addWidget(self.toolbar)
        right_lay.addWidget(self.canvas, 1)

        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setSizes([240, 1000])

        main_layout.addWidget(self.main_splitter)

        self.list_metrics.setCurrentRow(0)

    def _on_ma_changed(self, val):
        self.lbl_ma_val.setText(f"{val} ep")
        self.update_chart()

    def load_csvs(self, folder_a, folder_b):
        self.info_a = get_experiment_info(folder_a)
        self.info_b = get_experiment_info(folder_b)

        self.df_a = self._read_log_csv(folder_a)
        self.df_b = self._read_log_csv(folder_b)

        self.update_chart()

    def _read_log_csv(self, folder_path):
        if not folder_path or not os.path.isdir(folder_path):
            return None
        csv_files = glob.glob(os.path.join(folder_path, "learning_log_*.csv"))
        if not csv_files:
            csv_files = glob.glob(os.path.join(folder_path, "*.csv"))
        if not csv_files:
            return None
        try:
            df = pd.read_csv(csv_files[0])
            if 'Episode' not in df.columns:
                df['Episode'] = np.arange(1, len(df) + 1)
            return df
        except Exception as e:
            print(f"[ERROR] Failed to read CSV ({csv_files[0]}): {e}")
            return None

    def update_chart(self):
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

        col_name = "TotalReward"
        y_label = "Total Reward"
        if metric_idx == 1:
            col_name = "Steps"
            y_label = "Steps per Episode"
        elif metric_idx == 2:
            col_name = "UnsafeActions"
            y_label = "Unsafe Actions Count"
        elif metric_idx == 3:
            col_name = "GoalSuccessRate"
            y_label = f"Goal Success Rate (% [{window} ep MA])"

        has_plot = False

        def plot_dataset(df, label_name, color_raw, color_ma):
            nonlocal has_plot
            if df is None or len(df) == 0:
                return

            x = df['Episode'].values

            if col_name == "GoalSuccessRate":
                if 'Result' in df.columns:
                    is_goal = (df['Result'] == 'Goal').astype(float) * 100.0
                    ma_vals = is_goal.rolling(window=window, min_periods=1).mean()
                    ax.plot(x, ma_vals, label=f"{label_name} (成功率)", color=color_ma, linewidth=2.0)
                    has_plot = True
            elif col_name in df.columns:
                y = df[col_name].values
                if show_raw:
                    ax.plot(x, y, color=color_raw, alpha=0.3, linewidth=1.0)

                ma_vals = pd.Series(y).rolling(window=window, min_periods=1).mean()
                ax.plot(x, ma_vals, label=f"{label_name} (移動平均: {window}ep)", color=color_ma, linewidth=2.0)
                has_plot = True

        plot_dataset(self.df_a, f"A: {self.info_a}", "#4a90e2", "#0055ff")
        plot_dataset(self.df_b, f"B: {self.info_b}", "#e74c3c", "#cc0000")

        ax.set_xlabel("Episode", fontsize=11, color='#222222', labelpad=6)
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


class ExperimentCompareApp(QMainWindow):
    """メインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RL-Log-Comparator - 実験ログ対比・比較分析ツール (PySide6)")
        self.resize(1280, 850)

        # アプリアイコンの設定
        icon_path = get_app_icon_path()
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._last_loaded_a = ""
        self._last_loaded_b = ""
        self._init_ui()

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
        self.edit_folder_a = QLineEdit()
        self.edit_folder_a.setPlaceholderText("output_YYYYMMDD_HHMMSS フォルダへのパス")
        self.edit_folder_a.textChanged.connect(self._check_auto_load)
        lay_a.addWidget(self.edit_folder_a, 1)
        btn_browse_a = QPushButton("参照...")
        btn_browse_a.clicked.connect(lambda: self._browse_folder_smart(is_target_a=True))
        lay_a.addWidget(btn_browse_a)
        folder_lay.addLayout(lay_a)

        # フォルダ B
        lay_b = QHBoxLayout()
        lay_b.addWidget(QLabel("フォルダ B (比較):"))
        self.edit_folder_b = QLineEdit()
        self.edit_folder_b.setPlaceholderText("output_YYYYMMDD_HHMMSS フォルダへのパス")
        self.edit_folder_b.textChanged.connect(self._check_auto_load)
        lay_b.addWidget(self.edit_folder_b, 1)
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

    def _browse_folder_smart(self, is_target_a: bool):
        target_edit = self.edit_folder_a if is_target_a else self.edit_folder_b
        other_edit = self.edit_folder_b if is_target_a else self.edit_folder_a

        target_path = target_edit.text().strip()
        other_path = other_edit.text().strip()

        initial_dir = ""

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
            target_edit.setText(folder)
            self._check_auto_load()

    def _check_auto_load(self):
        folder_a = self.edit_folder_a.text().strip()
        folder_b = self.edit_folder_b.text().strip()

        if folder_a and folder_b:
            if os.path.isdir(folder_a) and os.path.isdir(folder_b):
                if folder_a != self._last_loaded_a or folder_b != self._last_loaded_b:
                    self.load_all()

    def load_folders(self, path_a, path_b):
        self.edit_folder_a.blockSignals(True)
        self.edit_folder_b.blockSignals(True)
        self.edit_folder_a.setText(path_a)
        self.edit_folder_b.setText(path_b)
        self.edit_folder_a.blockSignals(False)
        self.edit_folder_b.blockSignals(False)
        self.load_all()

    def load_all(self):
        folder_a = self.edit_folder_a.text().strip()
        folder_b = self.edit_folder_b.text().strip()

        if not folder_a or not folder_b:
            return

        if not os.path.exists(folder_a) or not os.path.exists(folder_b):
            return

        self._last_loaded_a = folder_a
        self._last_loaded_b = folder_b

        self.tab_yaml.load_yamls(folder_a, folder_b)
        self.tab_images.load_folders(folder_a, folder_b)
        self.tab_csv.load_csvs(folder_a, folder_b)


def main():
    app = QApplication(sys.argv)

    icon_path = get_app_icon_path()
    if icon_path and os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = ExperimentCompareApp()

    if len(sys.argv) >= 3:
        path_a = sys.argv[1]
        path_b = sys.argv[2]
        window.load_folders(path_a, path_b)
    elif len(sys.argv) == 2:
        path_a = sys.argv[1]
        window.edit_folder_a.setText(path_a)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
