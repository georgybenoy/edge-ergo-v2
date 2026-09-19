"""
EdgeErgo — Standalone Agent Build Script (PRD §107 Phase 16).

Automates building EdgeErgoAgent.exe using PyInstaller and the EdgeErgoAgent.spec.
Validates presence of MediaPipe task model assets before starting the build.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = PROJECT_ROOT / "installer" / "EdgeErgoAgent.spec"
DIST_DIR = PROJECT_ROOT / "installer" / "dist"
BUILD_DIR = PROJECT_ROOT / "installer" / "build"
POSE_MODEL = PROJECT_ROOT / "edge_agent" / "models" / "pose_landmarker_lite.task"
FACE_MODEL = PROJECT_ROOT / "edge_agent" / "models" / "face_landmarker.task"


def check_prerequisites() -> None:
    """Verify that required model files exist before bundling."""
    print("=" * 70)
    print("EdgeErgo Agent Build — Preflight Checks")
    print("=" * 70)

    if not POSE_MODEL.exists():
        raise FileNotFoundError(
            f"Required MediaPipe Pose model missing at: {POSE_MODEL}.\n"
            "Please ensure pose_landmarker_lite.task is present in edge_agent/models/."
        )
    print(f"  [OK] Found MediaPipe Pose model ({POSE_MODEL.stat().st_size / 1024 / 1024:.2f} MB)")

    if not FACE_MODEL.exists():
        raise FileNotFoundError(
            f"Required MediaPipe Face model missing at: {FACE_MODEL}.\n"
            "Please ensure face_landmarker.task is present in edge_agent/models/."
        )
    print(f"  [OK] Found MediaPipe Face model ({FACE_MODEL.stat().st_size / 1024 / 1024:.2f} MB)")

    if not SPEC_FILE.exists():
        raise FileNotFoundError(f"PyInstaller spec file not found at: {SPEC_FILE}")
    print(f"  [OK] Found PyInstaller spec: {SPEC_FILE.name}")


def run_pyinstaller() -> Path:
    """Execute PyInstaller with EdgeErgoAgent.spec."""
    print("\nStarting PyInstaller build...")
    start_time = time.time()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        str(SPEC_FILE),
    ]

    print(f"Command: {' '.join(cmd)}\n")
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"PyInstaller failed with return code {proc.returncode}")

    target_exe = DIST_DIR / "EdgeErgoAgent.exe"
    if not target_exe.exists():
        # Check if without .exe extension (non-windows)
        alt = DIST_DIR / "EdgeErgoAgent"
        if alt.exists():
            target_exe = alt
        else:
            raise FileNotFoundError(f"Target executable not found at: {target_exe}")

    duration = time.time() - start_time
    exe_size_mb = target_exe.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 70)
    print("BUILD SUCCESSFUL!")
    print("=" * 70)
    print(f"  Output Executable: {target_exe}")
    print(f"  File Size:         {exe_size_mb:.2f} MB")
    print(f"  Build Duration:    {duration:.1f} seconds")
    print("=" * 70)
    return target_exe


if __name__ == "__main__":
    try:
        check_prerequisites()
        exe_path = run_pyinstaller()
    except Exception as e:
        print(f"\n[BUILD ERROR] {e}", file=sys.stderr)
        sys.exit(1)
