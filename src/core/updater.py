"""
RL-Log-Comparator 自動更新コアモジュール (src/core/updater.py)
GitHub Releases API を利用した新バージョン確認・インストーラーダウンロード・適用
依存ライブラリ: Python 標準ライブラリのみ
"""

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)

GITHUB_API_LATEST_RELEASE_URL = "https://api.github.com/repos/{owner}/{repo}/releases/latest"
INSTALLER_NAME_PATTERN = re.compile(r"^RL_Log_Comparator_Setup_v\d+\.\d+\.\d+\.exe$")


class UpdateVerificationError(Exception):
    """ダウンロードしたインストーラーの検証（ハッシュまたはサイズ）に失敗したときの例外"""
    pass


@dataclass
class UpdateInfo:
    """更新情報データクラス"""
    version: str                                  # 例: "1.2.0"
    tag_name: str                                 # 例: "v1.2.0"
    title: str                                   # リリースタイトル
    release_notes: str                           # リリースノート本文 (Markdown)
    release_url: str                             # GitHub リリースページ URL
    published_at: str                            # 公開日時 (ISO8601)
    installer_download_url: Optional[str] = None # .exe などのインストーラー直接DL URL
    installer_name: Optional[str] = None         # インストーラーファイル名
    installer_size: int = 0                      # ファイルサイズ (バイト)
    installer_sha256: Optional[str] = None       # 期待される SHA-256 ハッシュ (64桁16進小文字)
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
        logger.debug("最新リリース情報を取得できませんでした: %s", url, exc_info=True)
        return None

    tag_name = data.get("tag_name", "")
    version_str = tag_name.lstrip("vV")
    title = data.get("name") or tag_name
    release_notes = data.get("body", "")
    release_url = data.get("html_url", "")
    published_at = data.get("published_at", "")

    # Windows インストーラー (.exe) アセットを探索（正規表現に一致するものに限定）
    installer_url = None
    installer_name = None
    installer_size = 0
    installer_sha256 = None

    assets = data.get("assets", [])
    target_asset = None
    for asset in assets:
        name = asset.get("name", "")
        if INSTALLER_NAME_PATTERN.match(name):
            target_asset = asset
            installer_url = asset.get("browser_download_url")
            installer_name = name
            installer_size = asset.get("size", 0)
            break

    if target_asset and installer_name:
        # 1. asset の digest フィールドを確認 ("sha256:<hex>")
        digest = target_asset.get("digest")
        if isinstance(digest, str) and digest.lower().startswith("sha256:"):
            hex_part = digest.split(":", 1)[1].strip().lower()
            if len(hex_part) == 64 and re.match(r"^[0-9a-f]{64}$", hex_part):
                installer_sha256 = hex_part

        # 2. digest がなければ、同リリースの <インストーラー名>.sha256 アセットを探す
        if not installer_sha256:
            sha256_asset_name = f"{installer_name}.sha256"
            sha256_url = None
            for asset in assets:
                if asset.get("name") == sha256_asset_name:
                    sha256_url = asset.get("browser_download_url")
                    break

            if sha256_url:
                try:
                    sha_req = urllib.request.Request(sha256_url, headers=headers)
                    with urllib.request.urlopen(sha_req, timeout=timeout_sec) as sha_resp:
                        if sha_resp.status == 200:
                            content = sha_resp.read().decode("utf-8", errors="ignore").strip()
                            match = re.match(r"^([0-9a-fA-F]{64})", content)
                            if match:
                                installer_sha256 = match.group(1).lower()
                except Exception:
                    logger.debug("SHA-256 アセットの取得に失敗しました: %s", sha256_url, exc_info=True)

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
        installer_sha256=installer_sha256,
        is_update_available=update_available
    )


def download_installer(
    download_url: str,
    expected_sha256: str,
    expected_size: int,
    target_filename: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    chunk_size: int = 65536
) -> str:
    """
    インストーラーを一時フォルダ配下にストリーミングダウンロードし、完全性を検証する。

    保存先は tempfile.mkdtemp(prefix="rllc_update_") 内の <名前>.part とし、
    チャンクごとに hashlib.sha256() を更新する。
    完了後、バイト数が expected_size と一致し、かつ SHA-256 が expected_sha256 と一致する場合のみ
    正式名に os.replace する。不一致なら .part を削除して UpdateVerificationError を送出する。

    戻り値:
        検証済みのインストーラー実行ファイルの絶対パス
    例外:
        UpdateVerificationError: サイズまたはSHA-256ハッシュが期待値と不一致の場合
        InterruptedError: ユーザーによりダウンロードがキャンセルされた場合
    """
    temp_dir = tempfile.mkdtemp(prefix="rllc_update_")
    if not target_filename:
        target_filename = os.path.basename(download_url.split("?")[0]) or "RL_Log_Comparator_Setup.exe"

    final_path = os.path.join(temp_dir, target_filename)
    part_path = os.path.join(temp_dir, f"{target_filename}.part")

    req = urllib.request.Request(download_url, headers={"User-Agent": "AppUpdater/1.0"})
    hasher = hashlib.sha256()
    downloaded = 0

    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            content_len_header = resp.headers.get("Content-Length")
            total_size = int(content_len_header) if content_len_header and content_len_header.isdigit() else expected_size

            with open(part_path, "wb") as f:
                while True:
                    if cancel_event and cancel_event.is_set():
                        f.close()
                        if os.path.exists(part_path):
                            try:
                                os.remove(part_path)
                            except OSError:
                                logger.debug("中断したダウンロードファイルを削除できませんでした: %s", part_path, exc_info=True)
                        raise InterruptedError("Download was cancelled by user.")

                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)

                    if progress_callback:
                        progress_callback(downloaded, total_size or expected_size)

        # 完全性検証
        clean_expected_hash = expected_sha256.strip().lower()
        actual_hash = hasher.hexdigest().lower()

        if downloaded != expected_size:
            raise UpdateVerificationError(
                f"ファイルサイズの検証に失敗しました (期待値: {expected_size} bytes, 実際: {downloaded} bytes)"
            )

        if actual_hash != clean_expected_hash:
            raise UpdateVerificationError(
                f"SHA-256 ハッシュの検証に失敗しました (期待値: {clean_expected_hash}, 実際: {actual_hash})"
            )

        # 検証成功：正式ファイル名へ移動
        os.replace(part_path, final_path)
        return final_path

    except Exception:
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                pass
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
        raise


def launch_installer(installer_path: str) -> None:
    """
    インストーラーを独立プロセスで起動する（アプリ自体の終了は呼び出し元で行う）
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


def launch_installer_and_exit(installer_path: str) -> None:
    """後方互換用エイリアス: インストーラーを起動し、sys.exit(0) を呼ぶ"""
    launch_installer(installer_path)
    sys.exit(0)

