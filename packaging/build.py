"""
RL-Log-Comparator Full-Auto Clean Build Script
Creates a clean temporary virtual environment, installs minimal dependencies,
builds the PyInstaller binary, compiles the Inno Setup installer,
and cleans up all temporary build environments.
"""
import argparse
import os
import re
import shutil
import stat
import string
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def read_app_version(root: Path) -> str:
    """src/config.py から APP_VERSION を正規表現で取得する（import は行わない）"""
    config_path = root / "src" / "config.py"
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    pattern = re.compile(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
    content = config_path.read_text(encoding="utf-8")
    match = pattern.search(content)
    if not match:
        raise ValueError("APP_VERSION could not be found in src/config.py")

    version = match.group(1).strip()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise ValueError(
            f"Invalid APP_VERSION format: '{version}'. Must match '^\\d+\\.\\d+\\.\\d+$'"
        )
    return version


def generate_version_info(root: Path, output_path: Path, app_version: str) -> Path:
    """packaging/version_info.template.txt から一時 version_info.txt を生成する"""
    template_path = root / "packaging" / "version_info.template.txt"
    if not template_path.exists():
        raise FileNotFoundError(f"Version info template not found: {template_path}")

    major, minor, patch = map(int, app_version.split("."))
    template_content = template_path.read_text(encoding="utf-8")
    tmpl = string.Template(template_content)
    filled_content = tmpl.substitute(
        MAJOR=major,
        MINOR=minor,
        PATCH=patch,
        VERSION=app_version,
    )
    output_path.write_text(filled_content, encoding="utf-8")
    return output_path


def remove_readonly(func, path, excinfo):
    """Windowsの読み取り専用属性を強制解除して削除を再試行するハンドラ"""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def safe_rmtree(path, retries=5, delay=0.5):
    """
    Windows環境のファイルロックや読み取り専用属性に対応した堅牢なディレクトリ削除
    """
    p = Path(path)
    if not p.exists():
        return

    for attempt in range(retries):
        try:
            if sys.version_info >= (3, 12):
                def _onexc(func, filepath, err):
                    try:
                        os.chmod(filepath, stat.S_IWRITE)
                        func(filepath)
                    except Exception:
                        pass
                shutil.rmtree(p, onexc=_onexc)
            else:
                shutil.rmtree(p, onerror=remove_readonly)

            if not p.exists():
                return
        except Exception:
            pass
        time.sleep(delay)

    if p.exists():
        try:
            shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass


def kill_existing_process():
    """実行中の RL-Log-Comparator.exe プロセスがあれば安全に終了"""
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "RL-Log-Comparator.exe", "/T"],
            capture_output=True,
            check=False
        )
    except Exception:
        pass


def run_prebuild_tests(python_exe: str, skip_tests: bool = False) -> bool:
    """ビルド前に pytest を実行する"""
    if skip_tests:
        print("[INFO] Skipping pre-build tests (--skip-tests specified).")
        return True

    print("[INFO] Running pre-build tests (pytest -q)...")
    try:
        check_res = subprocess.run([python_exe, "-c", "import pytest"], capture_output=True)
        if check_res.returncode != 0:
            print("[WARNING] pytest is not installed in the current environment. Skipping pre-build tests.")
            return True
        res = subprocess.run([python_exe, "-m", "pytest", "-q"])
        if res.returncode != 0:
            print(f"[ERROR] Pre-build tests failed with exit code {res.returncode}.")
            return False
        print("[INFO] Pre-build tests passed successfully.")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to run pre-build tests: {e}")
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="RL-Log-Comparator Build Script")
    parser.add_argument(
        "--use-current-env",
        action="store_true",
        help="Use current Python environment instead of creating a clean temporary venv."
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running pre-build pytest suite."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    print("=" * 60)
    print("  RL-Log-Comparator Full-Auto Clean Build Script")
    print("=" * 60)

    try:
        app_version = read_app_version(root_dir)
        print(f"[INFO] Building RL-Log-Comparator v{app_version}")
    except Exception as e:
        print(f"[ERROR] Failed to read application version: {e}")
        return 1

    # Pre-build tests
    if not run_prebuild_tests(sys.executable, skip_tests=args.skip_tests):
        return 1

    # Google Driveのファイルロックやクラウド同期遅延を回避するため、
    # 実行ごとに完全に独立したユニークなローカル一時ディレクトリを作成してビルド
    temp_root = Path(tempfile.mkdtemp(prefix="rl_build_"))
    build_dir = temp_root / "work"
    temp_dist_dir = temp_root / "dist"
    temp_installer_dir = temp_root / "installer_out"

    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "RL-Log-Comparator").mkdir(parents=True, exist_ok=True)
    temp_dist_dir.mkdir(parents=True, exist_ok=True)
    temp_installer_dir.mkdir(parents=True, exist_ok=True)

    legacy_build = root_dir / "build"
    dist_dir = root_dir / "dist"
    installer_output_dir = root_dir / "dist_installer"
    spec_file = root_dir / "packaging" / "RL-Log-Comparator.spec"
    iss_file = root_dir / "packaging" / "installer.iss"

    # 1. Clean previous build artifacts in project workspace
    print("[1/5] Cleaning previous build artifacts and setting up workspace...")
    kill_existing_process()
    safe_rmtree(legacy_build)
    safe_rmtree(dist_dir)
    installer_output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Check and prepare build tool environment
    if args.use_current_env:
        print("[2/5] Using current Python environment (--use-current-env)...")
        build_python = sys.executable
    else:
        print("[2/5] Creating clean temporary virtual environment in %TEMP%...")
        venv_dir = temp_root / "venv"
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            venv_python = venv_dir / "Scripts" / "python.exe"
            subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)

            req_build = root_dir / "requirements-build.txt"
            constraints = root_dir / "constraints.txt"
            install_cmd = [str(venv_python), "-m", "pip", "install", "-r", str(req_build)]
            if constraints.exists():
                install_cmd.extend(["-c", str(constraints)])
            subprocess.run(install_cmd, check=True)
            build_python = str(venv_python)
            print("[INFO] Clean virtual environment prepared successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to setup virtual environment: {e}")
            safe_rmtree(temp_root)
            return 1

    # 3. Build standalone binary with PyInstaller
    print("[3/5] Building standalone binary with PyInstaller...")
    version_info_path = temp_root / "version_info.txt"
    try:
        generate_version_info(root_dir, version_info_path, app_version)
    except Exception as e:
        print(f"[ERROR] Failed to generate version_info.txt: {e}")
        safe_rmtree(temp_root)
        return 1

    build_env = os.environ.copy()
    build_env["RLLC_VERSION_INFO"] = str(version_info_path)

    pyi_cmd = [build_python, "-m", "PyInstaller"]
    try:
        subprocess.run(
            pyi_cmd + [
                "--noconfirm",
                "--workpath", str(build_dir),
                "--distpath", str(temp_dist_dir),
                str(spec_file)
            ],
            env=build_env,
            check=True
        )
        print("[INFO] PyInstaller standalone binary created successfully.")
    except Exception as e:
        print(f"[ERROR] PyInstaller build failed: {e}")
        safe_rmtree(temp_root)
        return 1

    # ポータブル版 ZIP の生成
    compiled_source = temp_dist_dir / "RL-Log-Comparator"
    if compiled_source.exists():
        print(f"[INFO] Creating portable ZIP archive for v{app_version}...")
        portable_zip_base = temp_installer_dir / f"RL_Log_Comparator_v{app_version}_portable"
        try:
            shutil.make_archive(
                str(portable_zip_base),
                "zip",
                root_dir=temp_dist_dir,
                base_dir="RL-Log-Comparator"
            )
            print(f"[INFO] Portable ZIP created: {portable_zip_base}.zip")
        except Exception as e:
            print(f"[ERROR] Failed to create portable ZIP archive: {e}")
            safe_rmtree(temp_root)
            return 1

    # 4. Search Inno Setup and compile installer
    print("[4/5] Compiling Windows Setup Installer with Inno Setup...")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    iscc_candidates = [
        Path(local_app_data) / "Programs" / "Inno Setup 6" / "ISCC.exe" if local_app_data else None,
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    iscc_path = None
    which_iscc = shutil.which("ISCC.exe") or shutil.which("iscc")
    if which_iscc:
        iscc_path = Path(which_iscc)
    else:
        for cand in iscc_candidates:
            if cand and cand.exists():
                iscc_path = cand
                break

    if iscc_path and iss_file.exists():
        print(f"[INFO] Running Inno Setup compiler: {iscc_path}")
        res = subprocess.run([
            str(iscc_path),
            f"/DSourceDir={compiled_source}",
            f"/DMyAppVersion={app_version}",
            f"/O{temp_installer_dir}",
            str(iss_file)
        ])
        if res.returncode == 0:
            print("[INFO] Inno Setup installer compiled successfully!")
        else:
            print(f"[ERROR] Inno Setup compilation failed with code {res.returncode}.")
            safe_rmtree(temp_root)
            return 1
    else:
        if not iscc_path:
            print("[WARNING] Inno Setup compiler (ISCC.exe) not found.")
            print("[INFO] To create installer, install Inno Setup 6 from: https://jrsoftware.org/isdl.php")
        if not iss_file.exists():
            print(f"[ERROR] Inno Setup script not found: {iss_file}")
            safe_rmtree(temp_root)
            return 1

    # 5. Copy outputs to project root and clean up temporary build environment
    print("[5/5] Deploying build artifacts and cleaning up...")

    # Copy standalone dist
    temp_binary_dir = temp_dist_dir / "RL-Log-Comparator"
    if temp_binary_dir.exists():
        dist_dir.mkdir(parents=True, exist_ok=True)
        target_binary_dir = dist_dir / "RL-Log-Comparator"
        safe_rmtree(target_binary_dir)
        for attempt in range(5):
            try:
                shutil.copytree(temp_binary_dir, target_binary_dir, dirs_exist_ok=True)
                break
            except Exception as e:
                time.sleep(1.0)
                if attempt == 4:
                    print(f"[WARNING] Could not copy dist to project: {e}")

    # Copy installer exe and portable zip
    if temp_installer_dir.exists():
        for f in list(temp_installer_dir.glob("*.exe")) + list(temp_installer_dir.glob("*.zip")):
            dest = installer_output_dir / f.name
            for attempt in range(5):
                try:
                    if dest.exists():
                        try:
                            dest.unlink()
                        except Exception:
                            pass
                    with open(f, "rb") as src_f, open(dest, "wb") as dst_f:
                        while chunk := src_f.read(1024 * 1024):
                            dst_f.write(chunk)
                        dst_f.flush()
                        os.fsync(dst_f.fileno())
                    print(f"[INFO] Successfully copied {f.name} to {dest} ({dest.stat().st_size} bytes)")
                    break
                except Exception as e:
                    time.sleep(1.0)
                    if attempt == 4:
                        print(f"[WARNING] Could not copy {f.name} to dist_installer: {e}")

    safe_rmtree(temp_root)

    print("=" * 60)
    print("  BUILD PROCESS FINISHED!")
    setup_exe = installer_output_dir / f"RL_Log_Comparator_Setup_v{app_version}.exe"
    if setup_exe.exists():
        print(f"  [SUCCESS] Windows Installer: {setup_exe}")
    portable_zip = installer_output_dir / f"RL_Log_Comparator_v{app_version}_portable.zip"
    if portable_zip.exists():
        print(f"  [SUCCESS] Portable ZIP:      {portable_zip}")
    standalone_exe = dist_dir / "RL-Log-Comparator" / "RL-Log-Comparator.exe"
    if standalone_exe.exists():
        print(f"  [SUCCESS] Standalone Binary: {standalone_exe}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

