# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Build Specification for EdgeErgoAgent.exe
Packages edge_agent into a standalone single-file Windows executable (PRD §12.1, §13, §107 Phase 16).
Bundles required MediaPipe vision task models and PySide6 Qt GUI dependencies.
"""

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Workspace root directory
project_dir = os.path.abspath(os.path.join(SPECPATH, ".."))

# Collect MediaPipe runtime data files
datas = collect_data_files('mediapipe')

# Explicitly bundle required MediaPipe task models
model_files = [
    (os.path.join(project_dir, 'edge_agent', 'models', 'pose_landmarker_lite.task'), os.path.join('edge_agent', 'models')),
    (os.path.join(project_dir, 'edge_agent', 'models', 'face_landmarker.task'), os.path.join('edge_agent', 'models')),
    (os.path.join(project_dir, 'edge_agent', 'models', 'pose_landmarker_lite.task'), 'models'),
    (os.path.join(project_dir, 'edge_agent', 'models', 'face_landmarker.task'), 'models'),
]

for src, dst in model_files:
    if os.path.exists(src):
        datas.append((src, dst))

hiddenimports = [
    'mediapipe',
    'cv2',
    'numpy',
    'httpx',
    'sqlite3',
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'edge_agent',
    'edge_agent.main',
    'edge_agent.camera.camera',
    'edge_agent.config.config_manager',
    'edge_agent.ergonomics.scoring',
    'edge_agent.ergonomics.rula',
    'edge_agent.ergonomics.reba',
    'edge_agent.expression.classifier',
    'edge_agent.feedback.alert_engine',
    'edge_agent.feedback.recommendations',
    'edge_agent.feedback.scheduler',
    'edge_agent.geometry.angle_calculator',
    'edge_agent.health.heartbeat',
    'edge_agent.overlay.overlay',
    'edge_agent.storage.local_db',
    'edge_agent.sync.server_sync',
    'edge_agent.temporal.analyzer',
    'edge_agent.setup',
    'edge_agent.setup.interactive',
    'edge_agent.vision.pose_engine',
    'edge_agent.vision.face_engine',
]

a = Analysis(
    [os.path.join(project_dir, 'edge_agent', 'main.py')],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    excludes=['tkinter', 'torch', 'torchvision', 'pandas'],
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EdgeErgoAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
