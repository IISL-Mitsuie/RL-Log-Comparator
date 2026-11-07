"""
アップデータコアモジュール (src/core/updater.py) の単体テスト
"""

import hashlib
import json
import os
import threading
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from src.core.updater import (
    UpdateVerificationError,
    compare_versions,
    download_installer,
    fetch_latest_release_info,
    is_newer_version,
    launch_installer,
    launch_installer_and_exit,
    parse_version_tuple,
)


class TestUpdater(unittest.TestCase):
    """Updater コアロジックのテスト"""

    def test_parse_version_tuple(self):
        self.assertEqual(parse_version_tuple("1.0.0"), (1, 0, 0))
        self.assertEqual(parse_version_tuple("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version_tuple("V2.10.4-rc1"), (2, 10, 4))
        self.assertEqual(parse_version_tuple(""), (0,))
        self.assertEqual(parse_version_tuple(None), (0,))

    def test_compare_versions(self):
        # 等しい
        self.assertEqual(compare_versions("1.0.0", "1.0.0"), 0)
        self.assertEqual(compare_versions("v1.0.0", "1.0"), 0)
        self.assertEqual(compare_versions("1.2.0", "v1.2"), 0)

        # v1 > v2
        self.assertEqual(compare_versions("1.1.0", "1.0.9"), 1)
        self.assertEqual(compare_versions("2.0.0", "1.99.99"), 1)
        self.assertEqual(compare_versions("1.0.1", "1.0.0"), 1)

        # v1 < v2
        self.assertEqual(compare_versions("1.0.0", "1.0.1"), -1)
        self.assertEqual(compare_versions("1.0.0", "2.0.0"), -1)
        self.assertEqual(compare_versions("0.9.9", "1.0.0"), -1)

    def test_is_newer_version(self):
        self.assertTrue(is_newer_version(current_version="1.0.0", latest_version="1.0.1"))
        self.assertTrue(is_newer_version(current_version="1.0.0", latest_version="1.1.0"))
        self.assertTrue(is_newer_version(current_version="1.0.0", latest_version="2.0.0"))

        self.assertFalse(is_newer_version(current_version="1.0.0", latest_version="1.0.0"))
        self.assertFalse(is_newer_version(current_version="1.1.0", latest_version="1.0.0"))

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_info_with_digest(self, mock_urlopen):
        dummy_hash = "a" * 64
        mock_response_data = {
            "tag_name": "v1.1.0",
            "name": "RL-Log-Comparator v1.1.0",
            "body": "## 新機能\n- 自動更新機能の追加",
            "html_url": "https://github.com/IISL-Mitsuie/RL-Log-Comparator/releases/tag/v1.1.0",
            "published_at": "2026-09-02T16:00:00Z",
            "assets": [
                {
                    "name": "RL_Log_Comparator_Setup_v1.1.0.exe",
                    "browser_download_url": "https://github.com/IISL-Mitsuie/RL-Log-Comparator/releases/download/v1.1.0/RL_Log_Comparator_Setup_v1.1.0.exe",
                    "size": 62000000,
                    "digest": f"sha256:{dummy_hash}"
                }
            ]
        }

        mock_cm = MagicMock()
        mock_cm.status = 200
        mock_cm.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        info = fetch_latest_release_info(
            repo_owner="IISL-Mitsuie",
            repo_name="RL-Log-Comparator",
            current_version="1.0.0"
        )

        self.assertIsNotNone(info)
        self.assertEqual(info.version, "1.1.0")
        self.assertEqual(info.tag_name, "v1.1.0")
        self.assertEqual(info.title, "RL-Log-Comparator v1.1.0")
        self.assertTrue(info.is_update_available)
        self.assertEqual(info.installer_name, "RL_Log_Comparator_Setup_v1.1.0.exe")
        self.assertEqual(info.installer_size, 62000000)
        self.assertEqual(info.installer_sha256, dummy_hash)

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_info_with_sha256_asset(self, mock_urlopen):
        dummy_hash = "b" * 64
        release_json = {
            "tag_name": "v1.1.0",
            "name": "RL-Log-Comparator v1.1.0",
            "body": "body",
            "html_url": "https://github.com/example",
            "published_at": "2026-09-02T16:00:00Z",
            "assets": [
                {
                    "name": "RL_Log_Comparator_Setup_v1.1.0.exe",
                    "browser_download_url": "https://example.com/Setup.exe",
                    "size": 5000
                },
                {
                    "name": "RL_Log_Comparator_Setup_v1.1.0.exe.sha256",
                    "browser_download_url": "https://example.com/Setup.exe.sha256",
                    "size": 100
                }
            ]
        }

        # 1回目の urlopen は release_json、2回目は .sha256 の取得
        mock_cm1 = MagicMock()
        mock_cm1.status = 200
        mock_cm1.read.return_value = json.dumps(release_json).encode("utf-8")
        mock_cm1.__enter__.return_value = mock_cm1

        mock_cm2 = MagicMock()
        mock_cm2.status = 200
        mock_cm2.read.return_value = f"{dummy_hash} *RL_Log_Comparator_Setup_v1.1.0.exe\n".encode("utf-8")
        mock_cm2.__enter__.return_value = mock_cm2

        mock_urlopen.side_effect = [mock_cm1, mock_cm2]

        info = fetch_latest_release_info(
            repo_owner="IISL-Mitsuie",
            repo_name="RL-Log-Comparator",
            current_version="1.0.0"
        )

        self.assertIsNotNone(info)
        self.assertEqual(info.installer_sha256, dummy_hash)

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_info_no_hash(self, mock_urlopen):
        # digest も .sha256 もない場合
        release_json = {
            "tag_name": "v1.1.0",
            "name": "RL-Log-Comparator v1.1.0",
            "body": "body",
            "html_url": "https://github.com/example",
            "published_at": "2026-09-02T16:00:00Z",
            "assets": [
                {
                    "name": "RL_Log_Comparator_Setup_v1.1.0.exe",
                    "browser_download_url": "https://example.com/Setup.exe",
                    "size": 5000
                }
            ]
        }
        mock_cm = MagicMock()
        mock_cm.status = 200
        mock_cm.read.return_value = json.dumps(release_json).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        info = fetch_latest_release_info(
            repo_owner="IISL-Mitsuie",
            repo_name="RL-Log-Comparator",
            current_version="1.0.0"
        )
        self.assertIsNotNone(info)
        self.assertIsNone(info.installer_sha256)

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_info_invalid_installer_name(self, mock_urlopen):
        # 命名規則 RL_Log_Comparator_Setup_vX.Y.Z.exe に合致しないファイルは無視される
        release_json = {
            "tag_name": "v1.1.0",
            "name": "RL-Log-Comparator v1.1.0",
            "body": "body",
            "html_url": "https://github.com/example",
            "published_at": "2026-09-02T16:00:00Z",
            "assets": [
                {
                    "name": "Setup.exe",
                    "browser_download_url": "https://example.com/Setup.exe",
                    "size": 5000
                }
            ]
        }
        mock_cm = MagicMock()
        mock_cm.status = 200
        mock_cm.read.return_value = json.dumps(release_json).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        info = fetch_latest_release_info(
            repo_owner="IISL-Mitsuie",
            repo_name="RL-Log-Comparator",
            current_version="1.0.0"
        )
        self.assertIsNotNone(info)
        self.assertIsNone(info.installer_download_url)
        self.assertIsNone(info.installer_name)

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_info_no_update(self, mock_urlopen):
        mock_response_data = {
            "tag_name": "v1.0.0",
            "name": "RL-Log-Comparator v1.0.0",
            "body": "Initial Release",
            "html_url": "https://github.com/IISL-Mitsuie/RL-Log-Comparator/releases/tag/v1.0.0",
            "published_at": "2026-08-24T08:33:34Z",
            "assets": []
        }

        mock_cm = MagicMock()
        mock_cm.status = 200
        mock_cm.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        info = fetch_latest_release_info(
            repo_owner="IISL-Mitsuie",
            repo_name="RL-Log-Comparator",
            current_version="1.0.0"
        )

        self.assertIsNotNone(info)
        self.assertFalse(info.is_update_available)

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_info_offline(self, mock_urlopen):
        # ネットワークエラー時に例外を外に出さず None を返すことを確認
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

        info = fetch_latest_release_info(
            repo_owner="IISL-Mitsuie",
            repo_name="RL-Log-Comparator",
            current_version="1.0.0"
        )
        self.assertIsNone(info)

    @patch("urllib.request.urlopen")
    def test_fetch_latest_release_info_http_error(self, mock_urlopen):
        # 404/500 等のエラー時
        mock_cm = MagicMock()
        mock_cm.status = 404
        mock_urlopen.return_value = mock_cm

        info = fetch_latest_release_info(
            repo_owner="IISL-Mitsuie",
            repo_name="RL-Log-Comparator",
            current_version="1.0.0"
        )
        self.assertIsNone(info)

    @patch("urllib.request.urlopen")
    def test_download_installer(self, mock_urlopen):
        content = b"Hello World!"
        expected_hash = hashlib.sha256(content).hexdigest()
        expected_size = len(content)

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(expected_size)}
        mock_resp.read.side_effect = [b"Hello ", b"World!", b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        progress_records = []
        def _prog(dl, total):
            progress_records.append((dl, total))

        save_path = download_installer(
            download_url="https://example.com/test_setup.exe",
            expected_sha256=expected_hash,
            expected_size=expected_size,
            target_filename="test_setup.exe",
            progress_callback=_prog
        )

        try:
            self.assertTrue(os.path.exists(save_path))
            with open(save_path, "rb") as f:
                self.assertEqual(f.read(), content)
            self.assertTrue(len(progress_records) > 0)
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)
            temp_parent = os.path.dirname(save_path)
            if os.path.exists(temp_parent) and "rllc_update_" in temp_parent:
                os.rmdir(temp_parent)

    @patch("urllib.request.urlopen")
    def test_download_installer_hash_mismatch(self, mock_urlopen):
        content = b"Corrupted Data!"
        actual_hash = hashlib.sha256(content).hexdigest()
        different_hash = "f" * 64
        self.assertNotEqual(actual_hash, different_hash)

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(len(content))}
        mock_resp.read.side_effect = [content, b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with self.assertRaises(UpdateVerificationError) as ctx:
            download_installer(
                download_url="https://example.com/test_setup.exe",
                expected_sha256=different_hash,
                expected_size=len(content),
                target_filename="test_bad_hash.exe"
            )
        self.assertIn("SHA-256", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_download_installer_size_mismatch(self, mock_urlopen):
        content = b"Incomplete Data"
        expected_hash = hashlib.sha256(content).hexdigest()

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "1000"}  # ヘッダーは1000バイト
        mock_resp.read.side_effect = [content, b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with self.assertRaises(UpdateVerificationError) as ctx:
            download_installer(
                download_url="https://example.com/test_setup.exe",
                expected_sha256=expected_hash,
                expected_size=1000,  # 期待値は1000だが実際はlen(content)
                target_filename="test_bad_size.exe"
            )
        self.assertIn("ファイルサイズ", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_download_installer_cancelled(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "100"}
        mock_resp.read.return_value = b"X" * 10
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        cancel_event = threading.Event()
        cancel_event.set()  # すでにキャンセル状態

        with self.assertRaises(InterruptedError):
            download_installer(
                download_url="https://example.com/test_cancel.exe",
                expected_sha256="a" * 64,
                expected_size=100,
                target_filename="test_cancel.exe",
                cancel_event=cancel_event
            )

    def test_launch_installer_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            launch_installer("C:\\nonexistent_installer_file_12345.exe")
        with self.assertRaises(FileNotFoundError):
            launch_installer_and_exit("C:\\nonexistent_installer_file_12345.exe")


if __name__ == "__main__":
    unittest.main()



if __name__ == "__main__":
    unittest.main()
