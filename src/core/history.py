"""
実験ログフォルダ選択履歴（Recent Folders）およびセッション状態管理モジュール
"""

import os
from typing import Optional
from PySide6.QtCore import QSettings
from src.config import (
    SETTINGS_ORG, SETTINGS_APP,
    SETTINGS_KEY_RECENT_FOLDERS,
    SETTINGS_KEY_RECENT_ROOT_DIRS,
    SETTINGS_KEY_LAST_ROOT_DIR,
    SETTINGS_KEY_LAST_FOLDER_A,
    SETTINGS_KEY_LAST_FOLDER_B,
    MAX_HISTORY_COUNT
)


class RecentFolderManager:
    """QSettings を用いたフォルダ選択履歴の永続化・MRU管理クラス"""

    def __init__(
        self,
        org: str = SETTINGS_ORG,
        app: str = SETTINGS_APP,
        max_count: int = MAX_HISTORY_COUNT,
        settings_key: str = SETTINGS_KEY_RECENT_FOLDERS,
    ):
        self.settings = QSettings(org, app)
        self.max_count = max_count
        self.settings_key = settings_key

    def load_history(self) -> list[str]:
        """
        QSettings から履歴を読み込み、存在しないパスを除外して最大件数内に整形して返す。
        無効なパスが除外された場合は自動的に QSettings 側も更新する。
        """
        val = self.settings.value(self.settings_key, [])
        if isinstance(val, str):
            val = [val] if val else []
        elif not isinstance(val, list):
            val = []

        valid_history: list[str] = []
        for p in val:
            if isinstance(p, str) and p.strip() and os.path.isdir(p.strip()):
                norm_p = os.path.abspath(p.strip())
                if norm_p not in valid_history:
                    valid_history.append(norm_p)

        valid_history = valid_history[:self.max_count]
        if valid_history != val:
            self.save_history(valid_history)
        return valid_history

    def save_history(self, history_list: list[str]) -> None:
        """QSettings に履歴リストを保存"""
        self.settings.setValue(self.settings_key, history_list[:self.max_count])

    def add_folder(self, folder_path: str) -> list[str]:
        """
        フォルダパスを履歴の先頭に追加（MRU順・上限件数内）して最新の履歴リストを返す
        """
        if not folder_path or not os.path.isdir(folder_path):
            return self.load_history()

        abs_path = os.path.abspath(folder_path)
        history = self.load_history()
        if abs_path in history:
            history.remove(abs_path)
        history.insert(0, abs_path)
        history = history[:self.max_count]
        self.save_history(history)
        return history

    def clear_history(self) -> None:
        """全履歴を消去"""
        self.settings.remove(self.settings_key)


class SessionStateManager:
    """アプリ終了時のパス保存および次回起動時の復元を行うセッション管理クラス"""

    def __init__(self, org: str = SETTINGS_ORG, app: str = SETTINGS_APP):
        self.settings = QSettings(org, app)

    def save_last_paths(
        self,
        root_dir: Optional[str] = None,
        folder_a: Optional[str] = None,
        folder_b: Optional[str] = None,
    ) -> None:
        """アプリ終了時のパスを QSettings に保存"""
        if root_dir is not None:
            self.settings.setValue(SETTINGS_KEY_LAST_ROOT_DIR, root_dir.strip())
        if folder_a is not None:
            self.settings.setValue(SETTINGS_KEY_LAST_FOLDER_A, folder_a.strip())
        if folder_b is not None:
            self.settings.setValue(SETTINGS_KEY_LAST_FOLDER_B, folder_b.strip())

    def load_last_paths(self) -> dict[str, str]:
        """
        保存されたパスを取得。
        実在する有効なディレクトリのみを辞書形式で返す。
        """
        result = {}
        root = self.settings.value(SETTINGS_KEY_LAST_ROOT_DIR, "")
        if isinstance(root, str) and root.strip() and os.path.isdir(root.strip()):
            result["root_dir"] = os.path.abspath(root.strip())

        a = self.settings.value(SETTINGS_KEY_LAST_FOLDER_A, "")
        if isinstance(a, str) and a.strip() and os.path.isdir(a.strip()):
            result["folder_a"] = os.path.abspath(a.strip())

        b = self.settings.value(SETTINGS_KEY_LAST_FOLDER_B, "")
        if isinstance(b, str) and b.strip() and os.path.isdir(b.strip()):
            result["folder_b"] = os.path.abspath(b.strip())

        return result

    def clear_last_paths(self) -> None:
        """保存されたセッションパスをクリア"""
        self.settings.remove(SETTINGS_KEY_LAST_ROOT_DIR)
        self.settings.remove(SETTINGS_KEY_LAST_FOLDER_A)
        self.settings.remove(SETTINGS_KEY_LAST_FOLDER_B)
