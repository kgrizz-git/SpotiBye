# Frontend Distribution Guide

## Overview

This guide explains how to package and distribute the SpotiBye frontend application to end users while connecting to the deployed Cloudflare Workers backend.

## Architecture

**Frontend Package**: User-facing desktop application
- Contains UI components and business logic
- Connects to remote backend API
- No backend code included

**Backend Service**: Cloudflare Workers deployment
- Handles Spotify API integration
- Manages authentication and data processing
- Deployed separately and maintained by you

## Prerequisites

- Python 3.8+ (for building)
- PyInstaller for packaging
- Deployed backend URL
- Spotify Developer App credentials

## Step 1: Prepare Frontend Configuration

Update the backend configuration to point to your production backend:

```python
# src/frontend/config/backend_config.py
BACKEND_URL: Final[str] = "https://your-production-backend.workers.dev"
```

## Step 2: Install PyInstaller

```bash
pip install pyinstaller
```

## Step 3: Create PyInstaller Spec File

Create a spec file to exclude backend files and optimize the package:

```python
# spotibye.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/spotify_playlist_exporter_v2', 'spotify_playlist_exporter_v2'),
        ('src/frontend', 'frontend'),
    ],
    hiddenimports=[
        'kivy',
        'kivymd',
        'requests',
        'spotipy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'src/backend',
        'docs',
        'tests',
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
    name='SpotiBye',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

## Step 4: Build the Package

```bash
pyinstaller spotibye.spec
```

This creates a standalone executable in the `dist` directory.

## Step 5: Test the Package

```bash
# Test the executable
./dist/SpotiBye
```

Verify:
- Application launches correctly
- Backend connection works
- Authentication flow functions
- All features operate as expected

## Step 6: Distribution Options

### Option A: Direct File Distribution
- Upload the executable file to file hosting service
- Provide download link to users
- Simple but requires manual updates

### Option B: Installer Package
- Create installer for Windows/macOS/Linux
- Handles dependencies and updates
- Better user experience

### Option C: App Store Distribution
- Package for Microsoft Store, Mac App Store
- Requires signing and review process
- Most professional approach

## Step 7: Update Management

### Version Updates
1. Update backend URL in configuration
2. Rebuild package with PyInstaller
3. Distribute new version
4. Notify users of update

### Backend Updates
- Frontend automatically uses updated backend
- No frontend changes needed for backend improvements
- Maintain backward compatibility

## Troubleshooting

### Common Issues

**Module Not Found Errors**
- Ensure all dependencies are listed in `hiddenimports`
- Check that data files are correctly specified

**Application Won't Start**
- Test in development environment first
- Check console output for error messages
- Verify backend URL is accessible

**Large Package Size**
- Use UPX compression (enabled by default)
- Exclude unnecessary modules in spec file
- Consider one-folder mode instead of one-file

### Platform-Specific Notes

**Windows**
- May need Visual C++ Redistributable
- Test on different Windows versions

**macOS**
- May need code signing for distribution
- Test on Intel and Apple Silicon

**Linux**
- Include system dependencies
- Test on different distributions

## Security Considerations

- Use HTTPS for backend communication
- Validate backend SSL certificates
- Don't embed sensitive data in executable
- Keep backend credentials secure

## Conclusion

This distribution approach provides:
- Clean separation of frontend and backend
- Easy updates and maintenance
- Professional user experience
- Secure architecture

Users get a lightweight desktop application that connects to your managed backend service, ensuring consistent performance and security while simplifying distribution.
