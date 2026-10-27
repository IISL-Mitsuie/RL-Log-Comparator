"""
バージョン管理の整合性検証テスト
Issue #19 (ISSUE-08: バージョンの一元管理とビルドの再現性)
"""
import importlib.util
import re
import tempfile
from pathlib import Path
import pytest

from src.config import APP_VERSION


ROOT_DIR = Path(__file__).resolve().parent.parent


def _import_build_module():
    """packaging/build.py を動的インポートする（サードパーティ packaging との衝突回避）"""
    build_script = ROOT_DIR / "packaging" / "build.py"
    spec = importlib.util.spec_from_file_location("build_script", build_script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_app_version_format():
    """src/config.py の APP_VERSION がセマンティックバージョニング形式（X.Y.Z）であること"""
    assert re.match(r"^\d+\.\d+\.\d+$", APP_VERSION), f"Invalid APP_VERSION: {APP_VERSION}"


def test_read_app_version():
    """packaging/build.py の read_app_version が正確にバージョンを読み取れること"""
    mod = _import_build_module()
    version = mod.read_app_version(ROOT_DIR)
    assert version == APP_VERSION
    assert re.match(r"^\d+\.\d+\.\d+$", version)


def test_read_app_version_invalid(tmp_path: Path):
    """不正な config.py の場合に read_app_version が ValueError を送出すること"""
    mod = _import_build_module()
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    bad_config = src_dir / "config.py"

    # バージョン定数なし
    bad_config.write_text('APP_NAME = "RL-Log-Comparator"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="could not be found"):
        mod.read_app_version(tmp_path)

    # 不正なバージョンフォーマット
    bad_config.write_text('APP_VERSION = "1.0"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid APP_VERSION format"):
        mod.read_app_version(tmp_path)

    bad_config.write_text('APP_VERSION = "alpha-1.0"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid APP_VERSION format"):
        mod.read_app_version(tmp_path)


def test_installer_iss_no_hardcoded_version():
    """
    packaging/installer.iss に固定のバージョン（例: #define MyAppVersion "1.3.2"）が直接定義されていないこと。
    #ifndef で囲まれた 0.0.0-dev の既定値のみ許容される。
    """
    iss_path = ROOT_DIR / "packaging" / "installer.iss"
    assert iss_path.exists(), f"installer.iss not found: {iss_path}"

    content = iss_path.read_text(encoding="utf-8")

    # 具体的な固定バージョン定義（0.0.0-dev を除く "数字.数字.数字" 等）が存在しないこと
    hardcoded_matches = re.findall(
        r'^\s*#define\s+MyAppVersion\s+["\'](?:\d+\.\d+(?:\.\d+)?|\d+)["\']',
        content,
        re.MULTILINE
    )
    assert not hardcoded_matches, f"Hardcoded MyAppVersion found in installer.iss: {hardcoded_matches}"

    # #ifndef MyAppVersion ～ #define MyAppVersion "0.0.0-dev" ～ #endif が存在すること
    expected_block = re.search(
        r'#ifndef\s+MyAppVersion\s*[\r\n]+\s*#define\s+MyAppVersion\s+"0\.0\.0-dev"\s*[\r\n]+\s*#endif',
        content
    )
    assert expected_block is not None, "installer.iss must contain #ifndef MyAppVersion block with default '0.0.0-dev'"


def test_version_info_template_placeholders():
    """packaging/version_info.template.txt に所定のプレースホルダーが含まれること"""
    template_path = ROOT_DIR / "packaging" / "version_info.template.txt"
    assert template_path.exists(), f"version_info.template.txt not found: {template_path}"

    content = template_path.read_text(encoding="utf-8")
    for placeholder in ["$MAJOR", "$MINOR", "$PATCH", "$VERSION"]:
        assert placeholder in content, f"Placeholder {placeholder} not found in version_info.template.txt"

    # 生成テスト
    mod = _import_build_module()
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = Path(tmp_dir) / "version_info.txt"
        mod.generate_version_info(ROOT_DIR, out_file, "9.8.7")
        assert out_file.exists()
        out_content = out_file.read_text(encoding="utf-8")
        assert "filevers=(9, 8, 7, 0)" in out_content
        assert "prodvers=(9, 8, 7, 0)" in out_content
        assert "'FileVersion', '9.8.7.0'" in out_content
        assert "'ProductVersion', '9.8.7.0'" in out_content


def test_readme_no_concrete_version_filename():
    """README.md に具体的なバージョンを含むファイル名（_v\\d+\\.\\d+\\.\\d+）が残っていないこと"""
    readme_path = ROOT_DIR / "README.md"
    assert readme_path.exists(), f"README.md not found: {readme_path}"

    content = readme_path.read_text(encoding="utf-8")
    matches = re.findall(r'_v\d+\.\d+\.\d+', content)
    assert not matches, f"Concrete version filename pattern found in README.md: {matches}"

