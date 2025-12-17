# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()
SRC_DIR = PROJECT_ROOT / 'src'

# Platform-specific settings
if sys.platform == 'win32':
    # Windows specific settings
    import PyInstaller.utils.win32.versioninfo as vs
    
    exe_name = 'SpotiBye.exe'
    icon = str(SRC_DIR / 'frontend' / 'assets' / 'icon.ico')
    
    # Version info for Windows executable
    version_info = vs.VSVersionInfo(
        ffi=vs.FixedFileInfo(
            filevers=(1, 0, 0, 0),
            prodvers=(1, 0, 0, 0),
            mask=0x3f,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0)
        ),
        kids=[
            vs.StringFileInfo(
                [
                    vs.StringTable(
                        '040904B0',
                        [
                            vs.StringStruct('CompanyName', 'Your Company'),
                            vs.StringStruct('FileDescription', 'SpotiBye - Spotify Playlist Exporter'),
                            vs.StringStruct('FileVersion', '1.0.0'),
                            vs.StringStruct('InternalName', 'SpotiBye'),
                            vs.StringStruct('LegalCopyright', '© 2025 Your Company. All rights reserved.'),
                            vs.StringStruct('OriginalFilename', 'SpotiBye.exe'),
                            vs.StringStruct('ProductName', 'SpotiBye'),
                            vs.StringStruct('ProductVersion', '1.0.0')
                        ]
                    )
                ]
            ),
            vs.VarFileInfo([vs.VarStruct('Translation', [0, 1200])])
        ]
    )
else:
    # macOS specific settings
    exe_name = 'SpotiBye'
    icon = str(SRC_DIR / 'frontend' / 'assets' / 'icon.icns')
    version_info = None

# Ensure the src/ directory is on sys.path
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(SRC_DIR / 'spotify_playlist_exporter_v2'), 'spotify_playlist_exporter_v2'),
        (str(SRC_DIR / 'frontend'), 'frontend'),
    ],
    hiddenimports=[
        'kivy',
        'kivymd',
        'requests',
        'spotipy',
        'openpyxl',
        'pandas',
        'PIL',
        'pkg_resources.py2_warn',
        'pkg_resources.markers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'pydoc',
        'pdb',
        'distutils',
        'setuptools',
        'numpy',  # If not used directly
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging, False for production
    disable_windowed_traceback=False,
    argv_emulation=sys.platform == 'darwin',  # Enable for macOS
    target_arch=None,
    codesign_identity=None if sys.platform != 'darwin' else 'Apple Development',
    entitlements_file=None,
    version=version_info,
    icon=icon if os.path.exists(icon) else None,
)

# macOS specific: Create .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='SpotiBye.app',
        icon=icon if os.path.exists(icon) else None,
        bundle_identifier='com.yourcompany.spotibye',
        info_plist={
            'CFBundleName': 'SpotiBye',
            'CFBundleDisplayName': 'SpotiBye',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': 'True',
            'NSRequiresAquaSystemAppearance': 'False',
            'NSAppTransportSecurity': {
                'NSAllowsArbitraryLoads': True
            },
        },
    )
