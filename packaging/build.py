"""
RL-Log-Comparator Full-Auto Clean Build Script
Creates a clean temporary virtual environment, installs minimal dependencies,
builds the PyInstaller binary, compiles the Inno Setup installer,
and cleans up all temporary build environments.
"""
import os
import sys
import shutil
import stat
import subprocess
import time
import tempfile
from pathlib import Path

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

def main():
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    print("=" * 60)
    print("  RL-Log-Comparator Full-Auto Clean Build Script")
    print("=" * 60)

    # Google Driveのファイルロックやクラウド同期遅延を回避するため、
    # 一時的なビルド用仮想環境および中間ビルドディレクトリはローカルTemp内に配置
    temp_base = Path(tempfile.gettempdir())
    venv_dir = temp_base / "rl_log_comparator_build_venv"
    build_dir = temp_base / "rl_log_comparator_build_work"
    legacy_venv = root_dir / ".venv_build"
    legacy_build = root_dir / "build"

    dist_dir = root_dir / "dist"
    installer_output_dir = root_dir / "dist_installer"
    requirements_file = root_dir / "requirements.txt"
    spec_file = root_dir / "packaging" / "RL-Log-Comparator.spec"
    iss_file = root_dir / "packaging" / "installer.iss"

    # 1. Clean previous build virtual environment and output directories
    print("[1/5] Cleaning previous build artifacts and creating clean virtual environment...")
    kill_existing_process()
    safe_rmtree(venv_dir)
    safe_rmtree(build_dir)
    safe_rmtree(legacy_venv)
    safe_rmtree(legacy_build)
    safe_rmtree(dist_dir)

    venv_created = False
    for attempt in range(3):
        try:
            subprocess.run([sys.executable, "-m", "venv", "--clear", str(venv_dir)], check=True)
            venv_created = True
            break
        except Exception as e:
            print(f"[WARNING] Virtualenv creation attempt {attempt + 1} failed: {e}. Retrying...")
            safe_rmtree(venv_dir)
            time.sleep(1)

    if not venv_created:
        print("[ERROR] Failed to create virtual environment.")
        return 1

    venv_python = venv_dir / "Scripts" / "python.exe"
    venv_pip = venv_dir / "Scripts" / "pip.exe"
    venv_pyinstaller = venv_dir / "Scripts" / "pyinstaller.exe"

    # 2. Install dependencies
    print("[2/5] Installing minimal dependencies from requirements.txt...")
    try:
        subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=False)
        subprocess.run([str(venv_pip), "install", "-r", str(requirements_file)], check=True)
    except Exception as e:
        print(f"[ERROR] Failed to install dependencies: {e}")
        safe_rmtree(venv_dir)
        return 1

    # 3. Build standalone binary with PyInstaller
    print("[3/5] Building standalone binary with PyInstaller...")
    try:
        subprocess.run(
            [
                str(venv_pyinstaller),
                "--noconfirm",
                "--workpath", str(build_dir),
                "--distpath", str(dist_dir),
                str(spec_file)
            ],
            check=True
        )
        print("[INFO] PyInstaller standalone binary created successfully.")
    except Exception as e:
        print(f"[ERROR] PyInstaller build failed: {e}")
        safe_rmtree(venv_dir)
        safe_rmtree(build_dir)
        return 1

    # 4. Search Inno Setup and compile installer
    print("[4/5] Compiling Windows Setup Installer with Inno Setup...")
    iscc_candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    iscc_path = None
    for cand in iscc_candidates:
        if cand.exists():
            iscc_path = cand
            break

    if iscc_path and iss_file.exists():
        print(f"[INFO] Running Inno Setup compiler: {iscc_path}")
        res = subprocess.run([str(iscc_path), str(iss_file)])
        if res.returncode == 0:
            print("[INFO] Inno Setup installer compiled successfully!")
        else:
            print("[ERROR] Inno Setup compilation failed.")
    else:
        if not iscc_path:
            print("[WARNING] Inno Setup compiler (ISCC.exe) not found.")
            print("[INFO] To create installer, install Inno Setup 6 from: https://jrsoftware.org/isdl.php")
        if not iss_file.exists():
            print(f"[ERROR] Inno Setup script not found: {iss_file}")

    # 5. Clean up temporary virtual environment and build cache
    print("[5/5] Cleaning up temporary build environment...")
    safe_rmtree(venv_dir)
    safe_rmtree(build_dir)

    print("=" * 60)
    print("  BUILD PROCESS FINISHED!")
    
    # installer.iss からバージョン番号を動的抽出
    app_version = "1.0.0"
    if iss_file.exists():
        try:
            with open(iss_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "MyAppVersion" in line and '"' in line:
                        app_version = line.split('"')[1]
                        break
        except Exception:
            pass

    setup_exe = installer_output_dir / f"RL_Log_Comparator_Setup_v{app_version}.exe"
    if setup_exe.exists():
        print(f"  [SUCCESS] Windows Installer: {setup_exe}")
    standalone_exe = dist_dir / "RL-Log-Comparator" / "RL-Log-Comparator.exe"
    if standalone_exe.exists():
        print(f"  [SUCCESS] Standalone Binary: {standalone_exe}")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())

