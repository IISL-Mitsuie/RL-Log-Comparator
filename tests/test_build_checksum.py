"""
ビルド時の SHA-256 生成および AppMutex の単体テスト (tests/test_build_checksum.py)
"""

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from main import init_app_mutex

# packaging/build.py を動的ロード（サードパーティ製 packaging モジュールとの名前衝突を回避）
_build_script_path = Path(__file__).resolve().parent.parent / "packaging" / "build.py"
_spec = importlib.util.spec_from_file_location("build_script", _build_script_path)
assert _spec is not None and _spec.loader is not None
_build_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build_mod)
generate_sha256_file = _build_mod.generate_sha256_file


class TestBuildChecksumAndMutex(unittest.TestCase):
    """build.py の SHA-256 生成処理および main.py の AppMutex のテスト"""

    def test_generate_sha256_file_format_and_content(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_file = tmp_path / "RL_Log_Comparator_Setup_v1.0.0.exe"
            content = b"Binary installer payload test 123456789"
            test_file.write_bytes(content)

            sha_path = generate_sha256_file(test_file)

            # ファイル名が <exe名>.sha256 であること
            self.assertEqual(sha_path.name, "RL_Log_Comparator_Setup_v1.0.0.exe.sha256")
            self.assertTrue(sha_path.exists())

            # sha256sum 互換フォーマット: "<64桁16進> *<ファイル名>\n"
            sha_text = sha_path.read_text(encoding="utf-8")
            expected_hex = hashlib.sha256(content).hexdigest().lower()
            expected_line = f"{expected_hex} *{test_file.name}\n"
            self.assertEqual(sha_text, expected_line)

    def test_init_app_mutex(self):
        init_app_mutex()
        if sys.platform == "win32":
            import main
            self.assertIsNotNone(main._APP_MUTEX_HANDLE)


if __name__ == "__main__":
    unittest.main()
