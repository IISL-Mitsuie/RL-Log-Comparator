"""
アップデータコアモジュール (src/core/updater.py) の単体テスト
"""

import os
import json
import unittest
import urllib.error
import threading
from unittest.mock import patch, MagicMock

from src.core.updater import (
    parse_version_tuple,
    compare_versions,
    is_newer_version,
    fetch_latest_release_info,
    check_for_updates_async,
    download_installer,
    launch_installer_and_exit,
    UpdateInfo
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
    def test_fetch_latest_release_info_success(self, mock_urlopen):
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
                    "size": 62000000
                },
                {
                    "name": "source.zip",
                    "browser_download_url": "https://example.com/source.zip",
                    "size": 1000
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

    def test_check_for_updates_async(self):
        done_event = threading.Event()
        received_info = []

        with patch("src.core.updater.fetch_latest_release_info") as mock_fetch:
            dummy_info = UpdateInfo(
                version="1.1.0",
                tag_name="v1.1.0",
                title="v1.1.0",
                release_notes="notes",
                release_url="https://example.com",
                published_at="2026-09-02",
                is_update_available=True
            )
            mock_fetch.return_value = dummy_info

            def on_complete(info):
                received_info.append(info)
                done_event.set()

            thread = check_for_updates_async(
                repo_owner="IISL-Mitsuie",
                repo_name="RL-Log-Comparator",
                current_version="1.0.0",
                on_complete=on_complete
            )

            done_event.wait(timeout=2.0)
            self.assertEqual(len(received_info), 1)
            self.assertEqual(received_info[0], dummy_info)

    @patch("urllib.request.urlopen")
    def test_download_installer(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "12"}
        mock_resp.read.side_effect = [b"Hello ", b"World!", b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        progress_records = []
        def _prog(dl, total):
            progress_records.append((dl, total))

        save_path = download_installer(
            download_url="https://example.com/test_setup.exe",
            target_filename="test_setup.exe",
            progress_callback=_prog
        )

        try:
            self.assertTrue(os.path.exists(save_path))
            with open(save_path, "rb") as f:
                self.assertEqual(f.read(), b"Hello World!")
            self.assertTrue(len(progress_records) > 0)
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)

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
                target_filename="test_cancel.exe",
                cancel_event=cancel_event
            )

    def test_launch_installer_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            launch_installer_and_exit("C:\\nonexistent_installer_file_12345.exe")


if __name__ == "__main__":
    unittest.main()
