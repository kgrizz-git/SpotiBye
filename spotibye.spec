# -*- mode: python ; coding: utf-8 -*-

import os
import re
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

# Project root directory
# PyInstaller may execute spec files without defining __file__.
PROJECT_ROOT = Path(__file__).parent.resolve() if '__file__' in globals() else Path.cwd().resolve()
SRC_DIR = PROJECT_ROOT / 'src'


def read_project_version(pyproject_path: Path) -> str:
    """Read project.version from pyproject.toml without extra dependencies."""
    content = pyproject_path.read_text(encoding='utf-8')
    in_project_section = False

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue

        if line.startswith('['):
            in_project_section = line == '[project]'
            continue

        if in_project_section:
            match = re.match(r'^version\s*=\s*["\']([^"\']+)["\']$', line)
            if match:
                return match.group(1)

    raise ValueError('Could not find [project].version in pyproject.toml')


def to_windows_version_tuple(version: str) -> tuple[int, int, int, int]:
    """Convert semantic version to a 4-part Windows version tuple."""
    parsed = []
    for part in version.split('.')[:4]:
        parsed.append(int(part) if part.isdigit() else 0)

    while len(parsed) < 4:
        parsed.append(0)

    return tuple(parsed[:4])


APP_VERSION = read_project_version(PROJECT_ROOT / 'pyproject.toml')
APP_VERSION_TUPLE = to_windows_version_tuple(APP_VERSION)

# Platform-specific settings
if sys.platform == 'win32':
    # Windows specific settings
    import PyInstaller.utils.win32.versioninfo as vs
    
    exe_name = 'SpotiBye.exe'
    icon = str(SRC_DIR / 'frontend' / 'assets' / 'icon.ico')
    
    # Version info for Windows executable
    version_info = vs.VSVersionInfo(
        ffi=vs.FixedFileInfo(
            filevers=APP_VERSION_TUPLE,
            prodvers=APP_VERSION_TUPLE,
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
                            vs.StringStruct('FileVersion', APP_VERSION),
                            vs.StringStruct('InternalName', 'SpotiBye'),
                            vs.StringStruct('LegalCopyright', '© 2025 Your Company. All rights reserved.'),
                            vs.StringStruct('OriginalFilename', 'SpotiBye.exe'),
                            vs.StringStruct('ProductName', 'SpotiBye'),
                            vs.StringStruct('ProductVersion', APP_VERSION)
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

# Default to unsigned local builds. For release signing/notarization,
# provide a valid certificate identity, for example:
#   export SPOTIBYE_CODESIGN_IDENTITY="Apple Development: Your Name (TEAMID)"
release_codesign_identity = os.environ.get('SPOTIBYE_CODESIGN_IDENTITY')

# Ensure the src/ directory is on sys.path
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

block_cipher = None

a = Analysis(
    ['run_frontend_backend.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(SRC_DIR / 'spotify_playlist_exporter_v2'), 'spotify_playlist_exporter_v2'),
        (str(SRC_DIR / 'frontend'), 'frontend'),
    ] + collect_data_files('certifi'),
    hiddenimports=[
        'kivy',
        'kivymd',
        'kivymd.icon_definitions',
        'certifi',
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
    codesign_identity=release_codesign_identity if sys.platform == 'darwin' else None,
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
            'CFBundleVersion': APP_VERSION,
            'CFBundleShortVersionString': APP_VERSION,
            'NSHighResolutionCapable': 'True',
            'NSRequiresAquaSystemAppearance': 'False',
            'NSAppTransportSecurity': {
                'NSAllowsArbitraryLoads': True
            },
        },
    )
