"""
RL-Log-Comparator 自動更新コアモジュール (src/core/updater.py)
GitHub Releases API を利用した新バージョン確認・インストーラーダウンロード・適用
依存ライブラリ: Python 標準ライブラリのみ
"""

import os
import sys
import json
import urllib.request
import urllib.error
import subprocess
import tempfile
import threading
from typing import Optional, Callable, Dict, Any, Tuple
from dataclasses import dataclass

GITHUB_API_LATEST_RELEASE_URL = "https://api.github.com/repos/{owner}/{repo}/releases/latest"


@dataclass
class UpdateInfo:
    """更新情報データクラス"""
    version: str                                  # 例: "1.1.0"
    tag_name: str                                 # 例: "v1.1.0"
    title: str                                   # リリースタイトル
    release_notes: str                           # リリースノート本文 (Markdown)
    release_url: str                             # GitHub リリースページ URL
    published_at: str                            # 公開日時 (ISO8601)
    installer_download_url: Optional[str] = None # .exe などのインストーラー直接DL URL
    installer_name: Optional[str] = None         # インストーラーファイル名
    installer_size: int = 0                      # ファイルサイズ (バイト)
    is_update_available: bool = False            # 新バージョンが存在するかどうか


def parse_version_tuple(v_str: Optional[str]) -> Tuple[int, ...]:
    """
    セマンティックバージョニング文字列（例: 'v1.2.3', '1.0.0-rc1'）を整数のタプルに変換
    """
    if not v_str:
        return (0,)
    clean_str = v_str.strip().lstrip("vV").split("-")[0]
    parts = []
    for p in clean_str.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def compare_versions(v1: str, v2: str) -> int:
    """
    2つのバージョン文字列を比較
    戻り値:
        v1 > v2  ->  1
        v1 == v2 ->  0
        v1 < v2  -> -1
    """
    t1 = parse_version_tuple(v1)
    t2 = parse_version_tuple(v2)
    max_len = max(len(t1), len(t2))
    t1_padded = t1 + (0,) * (max_len - len(t1))
    t2_padded = t2 + (0,) * (max_len - len(t2))

    if t1_padded > t2_padded:
        return 1
    elif t1_padded < t2_padded:
        return -1
    return 0


def is_newer_version(current_version: str, latest_version: str) -> bool:
    """latest_version が current_version より新しいかを判定"""
    return compare_versions(latest_version, current_version) > 0


def fetch_latest_release_info(
    repo_owner: str,
    repo_name: str,
    current_version: str,
    timeout_sec: float = 5.0
) -> Optional[UpdateInfo]:
    """
    GitHub Releases API から最新バージョン情報を取得（同期処理）
    ※ ネットワークエラーやオフライン時は例外を出さず None を返します。
    """
    url = GITHUB_API_LATEST_RELEASE_URL.format(owner=repo_owner, repo=repo_name)
    headers = {
        "User-Agent": f"{repo_name}-AppUpdater/{current_version}",
        "Accept": "application/vnd.github.v3+json",
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            if response.status != 200:
                return None
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    tag_name = data.get("tag_name", "")
    version_str = tag_name.lstrip("vV")
    title = data.get("name") or tag_name
    release_notes = data.get("body", "")
    release_url = data.get("html_url", "")
    published_at = data.get("published_at", "")

    # Windows インストーラー (.exe) アセットを探索
    installer_url = None
    installer_name = None
    installer_size = 0

    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            installer_url = asset.get("browser_download_url")
            installer_name = name
            installer_size = asset.get("size", 0)
            break

    update_available = is_newer_version(current_version, version_str)

    return UpdateInfo(
        version=version_str,
        tag_name=tag_name,
        title=title,
        release_notes=release_notes,
        release_url=release_url,
        published_at=published_at,
        installer_download_url=installer_url,
        installer_name=installer_name,
        installer_size=installer_size,
        is_update_available=update_available
    )


def check_for_updates_async(
    repo_owner: str,
    repo_name: str,
    current_version: str,
    on_complete: Callable[[Optional[UpdateInfo]], None],
    timeout_sec: float = 5.0
) -> threading.Thread:
    """
    最新バージョンをバックグラウンドスレッドで非同期確認
    """
    def _worker():
        info = fetch_latest_release_info(repo_owner, repo_name, current_version, timeout_sec)
        on_complete(info)

    thread = threading.Thread(target=_worker, daemon=True, name="UpdateCheckWorker")
    thread.start()
    return thread


def download_installer(
    download_url: str,
    target_filename: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    chunk_size: int = 65536
) -> str:
    """
    インストーラーを %TEMP% 配下にストリーミングダウンロード
    戻り値: 保存されたインストーラーの絶対パス
    """
    temp_dir = tempfile.gettempdir()
    if not target_filename:
        target_filename = os.path.basename(download_url.split("?")[0]) or "Setup_Update.exe"
    save_path = os.path.join(temp_dir, target_filename)

    req = urllib.request.Request(download_url, headers={"User-Agent": "AppUpdater/1.0"})
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0

        with open(save_path, "wb") as f:
            while True:
                if cancel_event and cancel_event.is_set():
                    f.close()
                    if os.path.exists(save_path):
                        try:
                            os.remove(save_path)
                        except OSError:
                            pass
                    raise InterruptedError("Download was cancelled by user.")

                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                if progress_callback:
                    progress_callback(downloaded, total_size)

    return save_path


def launch_installer_and_exit(installer_path: str) -> None:
    """
    インストーラーを独立プロセスで起動し、現在のアプリケーション自身を正常終了する
    """
    abs_path = os.path.abspath(installer_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Installer file not found: {abs_path}")

    if sys.platform == "win32":
        # 新しい独立したプロセスグループで起動（親プロセス終了に巻き込まれない）
        subprocess.Popen(
            [abs_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True
        )
    else:
        subprocess.Popen([abs_path], close_fds=True)

    sys.exit(0)
