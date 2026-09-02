"""
ファイルパス解決および静的リソース読み込みモジュール
"""

import sys
import os


def get_project_root() -> str:
    """プロジェクトのルートディレクトリ（またはfrozen時の実行ディレクトリ）を取得"""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    # src/core/paths.py から 2 階層上がプロジェクトルート
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get_bundled_font_path() -> str:
    """アプリに同梱された日本語フォント (ipaexg.ttf) の絶対パスを取得"""
    if getattr(sys, 'frozen', False):
        base_dirs = [
            getattr(sys, '_MEIPASS', ''),
            os.path.dirname(sys.executable),
        ]
    else:
        root = get_project_root()
        base_dirs = [
            root,
            os.path.join(root, "packaging"),
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


def get_app_icon_path() -> str:
    """アプリアイコン (.ico) のパスを取得"""
    if getattr(sys, 'frozen', False):
        base_dirs = [
            getattr(sys, '_MEIPASS', ''),
            os.path.dirname(sys.executable),
        ]
    else:
        root = get_project_root()
        base_dirs = [
            root,
            os.path.join(root, "packaging"),
        ]

    for b in base_dirs:
        if not b:
            continue
        candidates = [
            os.path.join(b, "packaging", "app_icon.ico"),
            os.path.join(b, "app_icon.ico"),
            os.path.join(b, "reference", "image_icon.png"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return os.path.abspath(p)
    return ""


def get_log_spec_path() -> str:
    """DATA_FORMAT.md の絶対パスを取得"""
    root = get_project_root()
    candidates = [
        os.path.join(root, "DATA_FORMAT.md"),
        os.path.join(root, "reference", "RL-Log-Comparator_Log_Format_Spec.md"),
        os.path.join(root, "doc", "RL-Log-Comparator_Log_Format_Spec.md"),
        os.path.join(root, "RL-Log-Comparator_Log_Format_Spec.md"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return os.path.abspath(p)
    return candidates[0]


def load_log_spec_markdown() -> str:
    """DATA_FORMAT.md を読み込んで内容を返す（未存在時はエラー文）"""
    spec_path = get_log_spec_path()
    if os.path.exists(spec_path):
        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"# エラー\n\n仕様書ファイルの読み込みに失敗しました:\n`{e}`"
    return f"# エラー\n\n仕様書ファイルが見つかりません:\n`{spec_path}`"
