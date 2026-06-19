# -*- mode: python ; coding: utf-8 -*-
"""
CineSync AI Engine — PyInstaller Build Spec
Bundles the Python AI server into a standalone executable.
No Python installation required on target machine.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all hidden imports
hidden_imports = [
    # FastAPI / Uvicorn
    'fastapi',
    'fastapi.middleware.cors',
    'fastapi.responses',
    'uvicorn',
    'uvicorn.config',
    'uvicorn.main',
    'uvicorn.server',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'starlette',
    'starlette.routing',
    'starlette.middleware',
    'starlette.responses',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    
    # WebSockets
    'websockets',
    'websockets.legacy',
    'websockets.legacy.server',
    
    # Modal
    'modal',
    'modal.functions',
    
    # AI/ML
    'faster_whisper',
    'deep_translator',
    'edge_tts',
    'edge_tts.communicate',
    
    # Audio Processing
    'numpy',
    'scipy',
    'scipy.signal',
    'scipy.io',
    'scipy.io.wavfile',
    'pydub',
    'imageio_ffmpeg',
    
    # Utilities
    'pydantic',
    'pydantic.fields',
    'python_multipart',
    'multipart',
    'json',
    'asyncio',
    'logging',
    
    # Our modules
    'config',
    'core',
    'core.pipeline',
    'core.ws_manager',
    'core.media_processor',
    'services',
    'services.audio_debug',
    'services.character_mapper',
    'services.dubbing_pipeline',
    'services.emotion',
    'services.face_detection',
    'services.gpu_manager',
    'services.modal_client',
    'services.speaker_diarization',
    'services.stt_service',
    'services.translation_service',
    'services.tts_service',
]

# Collect data files from packages that need them
datas = []

# Try to collect edge-tts data
try:
    datas += collect_data_files('edge_tts')
except Exception:
    pass

# Try to collect certifi certificates (needed for HTTPS/Modal)
try:
    import certifi
    datas += [(certifi.where(), 'certifi')]
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas + [
        ('core', 'core'),
        ('services', 'services'),
        ('config.py', '.'),
        ('modal_app.py', '.'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',        # Not needed — Modal handles GPU inference
        'torchaudio',
        'torchvision',
        'matplotlib',
        'PIL',
        'tkinter',
        'pytest',
        'sphinx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='cinesync-ai-engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for logging (hidden by Electron)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='cinesync-ai-engine',
)
