"""
テーマ管理モジュールおよびダークモード対応の単体テスト
- WCAG コントラスト比テスト
- src/ui 配下からの固定色（カラーコード直書き）排除テスト
- ThemeManager によるテーマ切り替え・永続化テスト
- Windowsvista スタイル環境での Fusion フォールバックテスト
- YAML 差分ノードの kind 属性割り当てテスト
"""

import re
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from src.config import SETTINGS_KEY_THEME
from src.core.parsers.yaml_diff import build_diff_tree
from src.core.settings import create_settings
from src.ui.theme import LIGHT, DARK, Theme, ThemeManager, current_theme, get_theme_manager


def _srgb_to_luminance(hex_str: str) -> float:
    """16進数カラーコードから WCAG 2.1 相対輝度 (0.0 - 1.0) を計算"""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join(c * 2 for c in hex_str)
    r, g, b = [int(hex_str[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    r_lin = r / 12.92 if r <= 0.04045 else ((r + 0.055) / 1.055) ** 2.4
    g_lin = g / 12.92 if g <= 0.04045 else ((g + 0.055) / 1.055) ** 2.4
    b_lin = b / 12.92 if b <= 0.04045 else ((b + 0.055) / 1.055) ** 2.4
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _contrast_ratio(c1: str, c2: str) -> float:
    """2色間のコントラスト比 (1.0 - 21.0) を計算"""
    l1 = _srgb_to_luminance(c1)
    l2 = _srgb_to_luminance(c2)
    l_max, l_min = max(l1, l2), min(l1, l2)
    return (l_max + 0.05) / (l_min + 0.05)


@pytest.mark.parametrize("theme,std_bg", [
    (LIGHT, "#ffffff"),
    (DARK, "#1e1e1e"),
])
def test_wcag_contrast_ratios(theme: Theme, std_bg: str):
    """LIGHT / DARK の全トークンの組み合わせで WCAG コントラスト比基準を満たすこと"""
    # 1. 4.5:1 以上の組み合わせ（通常の文字・UI要素）
    pairs_4_5 = [
        ("panel_text x panel_bg", theme.panel_text, theme.panel_bg),
        ("selection_text x selection_bg", theme.selection_text, theme.selection_bg),
        ("diff_text x diff_only_a_bg", theme.diff_text, theme.diff_only_a_bg),
        ("diff_text x diff_only_b_bg", theme.diff_text, theme.diff_only_b_bg),
        ("diff_text x diff_changed_bg", theme.diff_text, theme.diff_changed_bg),
        ("accent_text x accent", theme.accent_text, theme.accent),
        ("chart_text x chart_bg", theme.chart_text, theme.chart_bg),
        ("chart_text x chart_legend_bg", theme.chart_text, theme.chart_legend_bg),
        ("text_muted x std_bg", theme.text_muted, std_bg),
        ("success x std_bg", theme.success, std_bg),
        ("info x std_bg", theme.info, std_bg),
        ("heading x std_bg", theme.heading, std_bg),
    ]

    for label, c1, c2 in pairs_4_5:
        cr = _contrast_ratio(c1, c2)
        assert cr >= 4.5, f"[{theme.name}] {label}: コントラスト比 {cr:.2f} が 4.5 未満です ({c1} vs {c2})"

    # 2. 3:1 以上の組み合わせ（グラフ系列の線色）
    pairs_3_0 = [
        ("series_a_line x chart_bg", theme.series_a_line, theme.chart_bg),
        ("series_b_line x chart_bg", theme.series_b_line, theme.chart_bg),
    ]

    for label, c1, c2 in pairs_3_0:
        cr = _contrast_ratio(c1, c2)
        assert cr >= 3.0, f"[{theme.name}] {label}: コントラスト比 {cr:.2f} が 3.0 未満です ({c1} vs {c2})"


def test_no_hardcoded_hex_colors_in_ui():
    """src/ui 配下（theme.py を除く）の .py ファイルに #[0-9a-fA-F]{6} が存在しないこと"""
    repo_root = Path(__file__).resolve().parent.parent
    ui_dir = repo_root / "src" / "ui"
    assert ui_dir.is_dir()

    pattern = re.compile(r'#[0-9a-fA-F]{6}\b')
    violations = []

    for py_file in ui_dir.rglob("*.py"):
        if py_file.name == "theme.py":
            continue
        content = py_file.read_text(encoding="utf-8")
        matches = pattern.findall(content)
        if matches:
            rel_path = py_file.relative_to(repo_root)
            violations.append(f"{rel_path}: {matches}")

    assert not violations, "src/ui にカラーコードの直書きが見つかりました:\n" + "\n".join(violations)


def test_theme_manager_switching(qapp):
    """ThemeManager による light / dark 切り替えとシグナル発行"""
    manager = get_theme_manager()
    emitted = []

    def on_changed(t):
        emitted.append(t)

    manager.theme_changed.connect(on_changed)
    try:
        manager.set_preference("dark")
        assert manager.get_preference() == "dark"
        assert current_theme().name == "dark"
        assert len(emitted) >= 1
        assert emitted[-1].name == "dark"

        manager.set_preference("light")
        assert manager.get_preference() == "light"
        assert current_theme().name == "light"
        assert emitted[-1].name == "light"

        manager.set_preference("system")
        assert manager.get_preference() == "system"
    finally:
        manager.theme_changed.disconnect(on_changed)
        manager.set_preference("system")


def test_theme_preference_persistence(tmp_path, monkeypatch, qapp):
    """テーマ設定が QSettings に保存され、復元できること"""
    settings = create_settings()
    settings.setValue(SETTINGS_KEY_THEME, "dark")

    loaded_pref = settings.value(SETTINGS_KEY_THEME, "system", type=str)
    assert loaded_pref == "dark"

    manager = ThemeManager()
    try:
        manager.set_preference(loaded_pref)
        assert manager.get_preference() == "dark"
        assert current_theme().name == "dark"
    finally:
        manager.set_preference("system")


def test_windowsvista_style_fallback(monkeypatch, qapp):
    """windowsvista スタイル環境下でダーク時に Fusion へ切り替わり、ライトで元に戻ること"""
    app = QApplication.instance()

    class MockVistaStyle:
        def objectName(self):
            return "windowsvista"

    applied_styles = []

    def fake_set_style(style_arg):
        applied_styles.append(style_arg)

    monkeypatch.setattr(app, "style", lambda: MockVistaStyle())
    monkeypatch.setattr(app, "setStyle", fake_set_style)

    manager = ThemeManager()
    try:
        manager.set_preference("dark")
        assert "Fusion" in applied_styles

        manager.set_preference("light")
        assert "windowsvista" in applied_styles
    finally:
        manager.set_preference("system")


def test_diff_node_kind_assignment():
    """YAML 差分ノードの kind が状態ごとに正しく付与されること"""
    yaml_a = {
        "lr": 0.001,
        "batch_size": 32,
        "only_in_a": "value_a",
        "nested": {
            "sub_same": 100,
            "sub_changed": "old",
        },
        "only_branch_a": {
            "x": 1
        }
    }
    yaml_b = {
        "lr": 0.002,           # changed
        "batch_size": 32,      # same
        "only_in_b": "value_b", # only_b
        "nested": {            # group
            "sub_same": 100,   # same
            "sub_changed": "new", # changed
        },
        "only_branch_b": {     # only_b
            "y": 2
        }
    }

    nodes = build_diff_tree(yaml_a, yaml_b, diff_only=False)
    node_map = {n.key: n for n in nodes}

    assert node_map["batch_size"].kind == "same"
    assert node_map["batch_size"].state_str == "一致"

    assert node_map["lr"].kind == "changed"
    assert node_map["lr"].state_str == "差分あり"

    assert node_map["only_in_a"].kind == "only_a"
    assert node_map["only_in_a"].state_str == "Aのみ存在"

    assert node_map["only_in_b"].kind == "only_b"
    assert node_map["only_in_b"].state_str == "Bのみ存在"

    assert node_map["only_branch_a"].kind == "only_a"
    assert node_map["only_branch_b"].kind == "only_b"

    nested_node = node_map["nested"]
    assert nested_node.kind == "group"
    assert nested_node.state_str == "階層"

    sub_map = {c.key: c for c in nested_node.children}
    assert sub_map["sub_same"].kind == "same"
    assert sub_map["sub_changed"].kind == "changed"
