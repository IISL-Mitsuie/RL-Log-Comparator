"""
RL-Log-Comparator テーマ管理モジュール
ライト／ダークテーマのトークン定義、スタイルシート生成、およびテーマ切り替え管理
"""

from dataclasses import dataclass
import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from src.config import SETTINGS_KEY_THEME
from src.core.settings import create_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Theme:
    name: str                      # 'light' | 'dark'
    # --- UI（意味ごと）---
    text_muted: str                # 補足の文字（ステータス表示など）
    accent: str                    # 強調ボタンの背景（更新可能の通知など）
    accent_hover: str
    accent_text: str
    success: str                   # Shield 有効などの文字
    info: str                      # 継続学習の文字など
    heading: str                   # 見出しの文字（仕様ガイドなど）
    panel_bg: str                  # 見出しラベルの背景（Explorer のプレビュー見出し）
    panel_text: str
    selection_bg: str              # 表の選択行
    selection_text: str
    diff_only_a_bg: str            # YAML 差分: A のみ存在
    diff_only_b_bg: str            # YAML 差分: B のみ存在
    diff_changed_bg: str           # YAML 差分: 差分あり
    diff_text: str                 # 差分の行の文字色
    # --- グラフ（Matplotlib）---
    chart_bg: str
    chart_text: str
    chart_grid: str
    chart_spine: str
    chart_legend_bg: str
    chart_legend_edge: str
    series_a_line: str
    series_a_raw: str
    series_a_marker: str
    series_b_line: str
    series_b_raw: str
    series_b_marker: str
    boundary_line: str
    boundary_text: str
    # --- 補助トークン ---
    error: str = "#c0392b"
    warning: str = "#aa5500"


LIGHT: Theme = Theme(
    name="light",
    text_muted="#666666",
    accent="#0969da",
    accent_hover="#0858b9",
    accent_text="#ffffff",
    success="#2e7d32",
    info="#1565c0",
    heading="#2c3e50",
    panel_bg="#eef2f7",
    panel_text="#111827",
    selection_bg="#d8ebfc",
    selection_text="#111827",
    diff_only_a_bg="#e6ffe6",
    diff_only_b_bg="#ffe6e6",
    diff_changed_bg="#fff5c8",
    diff_text="#111827",
    chart_bg="#ffffff",
    chart_text="#222222",
    chart_grid="#cccccc",
    chart_spine="#888888",
    chart_legend_bg="#ffffff",
    chart_legend_edge="#cccccc",
    series_a_line="#0055ff",
    series_a_raw="#4a90e2",
    series_a_marker="#002299",
    series_b_line="#cc0000",
    series_b_raw="#e74c3c",
    series_b_marker="#990000",
    boundary_line="#888888",
    boundary_text="#555555",
    error="#c0392b",
    warning="#aa5500",
)

DARK: Theme = Theme(
    name="dark",
    text_muted="#a0a0a0",
    accent="#1f6feb",
    accent_hover="#388bfd",
    accent_text="#ffffff",
    success="#66bb6a",
    info="#64b5f6",
    heading="#e6edf3",
    panel_bg="#2b3340",
    panel_text="#e6edf3",
    selection_bg="#264f78",
    selection_text="#ffffff",
    diff_only_a_bg="#244a2c",
    diff_only_b_bg="#5a2a2a",
    diff_changed_bg="#5a4b1a",
    diff_text="#f0f0f0",
    chart_bg="#1e1e1e",
    chart_text="#e6e6e6",
    chart_grid="#444444",
    chart_spine="#888888",
    chart_legend_bg="#2a2a2a",
    chart_legend_edge="#555555",
    series_a_line="#56b4e9",
    series_a_raw="#56b4e9",
    series_a_marker="#9bd4f5",
    series_b_line="#e69f00",
    series_b_raw="#e69f00",
    series_b_marker="#f5c765",
    boundary_line="#aaaaaa",
    boundary_text="#cccccc",
    error="#ff6b6b",
    warning="#e69f00",
)


def current_theme() -> Theme:
    """現在の配色（システムの配色の解決結果）に応じた Theme を返す"""
    pref = ThemeManager._active_preference
    if pref in ("light", "dark"):
        return DARK if pref == "dark" else LIGHT

    app = QGuiApplication.instance()
    if app is not None:
        hints = QGuiApplication.styleHints()
        if hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark:
            return DARK
    return LIGHT


def build_app_stylesheet(theme: Theme) -> str:
    """アプリ共通のスタイルシートを返す（role プロパティや基本ウィジェットに対応）"""
    return f"""
    /* 意味付けラベル */
    QLabel[role="muted"] {{
        color: {theme.text_muted};
    }}
    QLabel[role="heading"] {{
        color: {theme.heading};
    }}
    QLabel[role="info"] {{
        color: {theme.info};
    }}
    QLabel[role="success"] {{
        color: {theme.success};
    }}
    QLabel[role="panel-header"] {{
        background-color: {theme.panel_bg};
        color: {theme.panel_text};
    }}
    QLabel[role="status"] {{
        color: {theme.info};
    }}
    QLabel[role="status-error"] {{
        color: {theme.error};
    }}
    QLabel[role="image-preview"] {{
        background-color: {theme.chart_bg};
        color: {theme.text_muted};
    }}
    QLabel[role="separator"] {{
        color: {theme.chart_grid};
    }}

    /* 強調・アクションボタン */
    QPushButton[role="accent"] {{
        background-color: {theme.accent};
        color: {theme.accent_text};
        font-weight: bold;
    }}
    QPushButton[role="accent"]:hover {{
        background-color: {theme.accent_hover};
    }}
    QPushButton[role="accent"]:disabled {{
        background-color: {theme.panel_bg};
        color: {theme.text_muted};
    }}

    /* 表の選択色 (背景・交互行・枠線等は標準パレットに任せる) */
    QTableWidget {{
        selection-background-color: {theme.selection_bg};
        selection-color: {theme.selection_text};
    }}
    QTableWidget::item:selected {{
        background-color: {theme.selection_bg};
        color: {theme.selection_text};
    }}
    """


class ThemeManager(QObject):
    """
    アプリケーションのテーマ（システムに従う／ライト／ダーク）を一元管理するクラス
    """
    theme_changed = Signal(object)  # 発行時に current_theme() (Theme) を渡す

    _instance: Optional['ThemeManager'] = None
    _active_preference: str = "system"

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        if ThemeManager._instance is None:
            ThemeManager._instance = self

        try:
            saved_pref = create_settings().value(SETTINGS_KEY_THEME, "system", type=str)
        except Exception:
            saved_pref = "system"

        if saved_pref:
            saved_pref = saved_pref.lower().strip()
        if saved_pref not in ("system", "light", "dark"):
            saved_pref = "system"

        self._preference: str = saved_pref
        ThemeManager._active_preference = saved_pref
        self._original_style_name: Optional[str] = None

        hints = QGuiApplication.styleHints()
        if hints is not None:
            try:
                hints.colorSchemeChanged.connect(self._on_color_scheme_changed)
            except Exception:
                logger.debug("styleHints.colorSchemeChanged への接続に失敗しました", exc_info=True)

    @classmethod
    def instance(cls) -> 'ThemeManager':
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def get_preference(self) -> str:
        """現在のテーマ設定値 ('system' | 'light' | 'dark') を返す"""
        return self._preference

    def load_preference(self) -> None:
        """保存されたテーマ設定を読み込んで適用する（再保存は行わない）"""
        try:
            saved_pref = create_settings().value(SETTINGS_KEY_THEME, "system", type=str)
        except Exception:
            saved_pref = "system"
        self.set_preference(saved_pref, save=False)

    def set_preference(self, pref: str, *, save: bool = True) -> None:
        """
        テーマ設定を変更し、即座に適用してシグナルを発行する。
        pref: 'system' | 'light' | 'dark'
        save: True の場合、QSettings に設定を保存する
        """
        pref = pref.lower().strip() if pref else "system"
        if pref not in ("system", "light", "dark"):
            pref = "system"
        self._preference = pref
        ThemeManager._active_preference = pref

        if save:
            try:
                create_settings().setValue(SETTINGS_KEY_THEME, self._preference)
            except Exception:
                logger.debug("テーマ設定の保存に失敗しました", exc_info=True)

        hints = QGuiApplication.styleHints()
        if hints is not None:
            if pref == "dark":
                hints.setColorScheme(Qt.ColorScheme.Dark)
            elif pref == "light":
                hints.setColorScheme(Qt.ColorScheme.Light)
            else:
                hints.setColorScheme(Qt.ColorScheme.Unknown)

        self._apply_current_theme()

    def _apply_current_theme(self) -> None:
        """現在のテーマ状態を QApplication および登録コンポーネントに反映"""
        resolved = current_theme()
        app = QApplication.instance()
        if app is not None:
            # Windows 10 等で windowsvista スタイルが使われている環境への配慮
            current_style = app.style().objectName().lower()
            if resolved.name == "dark":
                if current_style == "windowsvista":
                    if self._original_style_name is None:
                        self._original_style_name = app.style().objectName()
                    app.setStyle("Fusion")
            else:
                if self._original_style_name is not None:
                    app.setStyle(self._original_style_name)
                    self._original_style_name = None

            app.setStyleSheet(build_app_stylesheet(resolved))

        self.theme_changed.emit(resolved)

    def _on_color_scheme_changed(self) -> None:
        """OS のシステム配色変更を検知した際のハンドラ"""
        if self._preference == "system":
            self._apply_current_theme()


def get_theme_manager() -> ThemeManager:
    """ThemeManager シングルトンインスタンスを取得する"""
    return ThemeManager.instance()
