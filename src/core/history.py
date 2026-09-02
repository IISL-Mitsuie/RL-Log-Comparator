"""
実験ログフォルダ選択履歴（Recent Folders）管理モジュール
"""

import os
from PySide6.QtCore import QSettings
from src.config import SETTINGS_ORG, SETTINGS_APP, SETTINGS_KEY_RECENT_FOLDERS, MAX_HISTORY_COUNT


class RecentFolderManager:
    """QSettings を用いたフォルダ選択履歴の永続化・MRU管理クラス"""

    def __init__(self, org: str = SETTINGS_ORG, app: str = SETTINGS_APP, max_count: int = MAX_HISTORY_COUNT):
        self.settings = QSettings(org, app)
        self.max_count = max_count

    def load_history(self) -> list[str]:
        """
        QSettings から履歴を読み込み、存在しないパスを除外して最大件数内に整形して返す。
        無効なパスが除外された場合は自動的に QSettings 側も更新する。
        """
        val = self.settings.value(SETTINGS_KEY_RECENT_FOLDERS, [])
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
        self.settings.setValue(SETTINGS_KEY_RECENT_FOLDERS, history_list[:self.max_count])

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
        self.settings.remove(SETTINGS_KEY_RECENT_FOLDERS)
