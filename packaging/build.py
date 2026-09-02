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
    requirements_file = root_dir / "requirements.txt"
    spec_file = root_dir / "packaging" / "RL-Log-Comparator.spec"
    iss_file = root_dir / "packaging" / "installer.iss"

    # 1. Clean previous build artifacts in project workspace
    print("[1/5] Cleaning previous build artifacts and setting up workspace...")
    kill_existing_process()
    safe_rmtree(legacy_build)
    safe_rmtree(dist_dir)
    installer_output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Check build tool environment
    print("[2/5] Preparing PyInstaller build environment...")
    pyi_cmd = [sys.executable, "-m", "PyInstaller"]

    # 3. Build standalone binary with PyInstaller
    print("[3/5] Building standalone binary with PyInstaller...")
    try:
        subprocess.run(
            pyi_cmd + [
                "--noconfirm",
                "--workpath", str(build_dir),
                "--distpath", str(temp_dist_dir),
                str(spec_file)
            ],
            check=True
        )
        print("[INFO] PyInstaller standalone binary created successfully.")

    except Exception as e:
        print(f"[ERROR] PyInstaller build failed: {e}")
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
        compiled_source = temp_dist_dir / "RL-Log-Comparator"
        res = subprocess.run([
            str(iscc_path),
            f"/DSourceDir={compiled_source}",
            f"/O{temp_installer_dir}",
            str(iss_file)
        ])
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

    # Copy installer exe
    if temp_installer_dir.exists():
        for f in temp_installer_dir.glob("*.exe"):
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
                    print(f"[INFO] Successfully copied installer to {dest} ({dest.stat().st_size} bytes)")
                    break
                except Exception as e:
                    time.sleep(1.0)
                    if attempt == 4:
                        print(f"[WARNING] Could not copy installer to dist_installer: {e}")

    safe_rmtree(temp_root)

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

