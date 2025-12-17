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
- PyInstaller (included in requirements.txt)
- Deployed backend URL
- Spotify Developer App credentials
- Icons for your application:
  - Windows: `src/frontend/assets/icon.ico` (recommended size: 256x256px)
  - macOS: `src/frontend/assets/icon.icns` (recommended size: 1024x1024px @1x, 2048x2048px @2x)
  - Linux: `src/frontend/assets/icon.png` (recommended size: 512x512px)

## ✅ Step 1: Prepare Frontend Configuration

The backend configuration is already set up with environment variable support. The configuration can be found at `src/frontend/config/backend_config.py` and supports both development and production environments.

## Step 2: Install Dependencies

PyInstaller and all other required dependencies are included in `requirements.txt`. Install them with:

```bash
pip install -r requirements.txt
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

## Step 5: Automated Builds with GitHub Actions

To automate the build process for all platforms, we've set up GitHub Actions workflows that will build and package the application on push to the main branch or when a new tag is created.

### Prerequisites
- A GitHub repository for your project
- Push the code to the repository if you haven't already:
  ```bash
  git remote add origin https://github.com/yourusername/SpotiBye.git
  git branch -M main
  git push -u origin main
  ```

### Enabling GitHub Actions

1. **Initial Setup**:
   - GitHub Actions is enabled by default for all public repositories
   - For private repositories, ensure you have admin access

2. **Verify Actions are Enabled**:
   1. Go to your repository on GitHub
   2. Click on the "Actions" tab
   3. If you see a button saying "I understand my workflows, go ahead and enable them", click it
   4. If you see workflow runs or setup options, Actions is already enabled

3. **For Organization Repositories**:
   - Organization owners need to enable Actions in organization settings:
     1. Go to your organization's settings
     2. Select "Actions" in the left sidebar
     3. Under "Actions permissions", select "Allow all actions" or configure as needed
     4. Click "Save"

4. **First Run**:
   - The workflow will automatically run when you push the code to the repository
   - You can also manually trigger it from the Actions tab

### How It Works

1. **Workflow Triggers**:
   - **Scheduled**: Nightly builds (optional)
   - **On Push**: To main branch (for testing)
   - **On Tag**: Creates a release with assets when a new version tag is pushed (e.g., `v1.0.0`)
   - **Manual**: Trigger builds for specific platforms through the GitHub UI

2. **Build Process**:
   - Sets up Python environment
   - Installs system dependencies
   - Installs Python dependencies
   - Builds platform-specific executables
   - Packages them for distribution
   - Uploads artifacts

3. **Automatic Releases**:
   - When you push a tag starting with 'v' (e.g., `v1.0.0`):
     - Creates a GitHub release
     - Attaches all built executables
     - Generates release notes automatically

### Using the Workflow

1. **Manual Build**:
   - Go to Actions tab in your GitHub repository
   - Select "Build Executables"
   - Click "Run workflow"
   - Choose platform (or leave as 'all' for all platforms)
   - Click "Run workflow"

2. **Create a New Release**:
   ```bash
   # Create and push a new tag
   git tag -a v1.0.0 -m "Initial release"
   git push origin v1.0.0
   ```

### Artifacts

- **Windows**: `SpotiBye-Windows.zip` (Portable executable)
- **macOS**: `SpotiBye-macOS.dmg` (Disk image with app bundle)
- **Linux**: `SpotiBye-Linux.tar.gz` (Tarball with AppImage and desktop file)

## Step 6: Distribution Options

### Option A: Direct File Distribution
- Upload the executable file to file hosting service
- Provide download link to users
- Simple but requires manual updates

### Option B: Installer Package
- Create installer for Windows/macOS
  - Windows: Use Inno Setup or NSIS
  - macOS: Create DMG with create-dmg
- Handles dependencies and updates
- Better user experience

### Option C: App Store Distribution
- **Windows**: Package for Microsoft Store (requires signing)
- **macOS**: Notarize and distribute via Mac App Store or Developer ID
- Requires signing and review process
- Most professional approach

## Platform-Specific Notes

### Windows
- Executable will be created as `dist/SpotiBye/SpotiBye.exe`
- For best results, sign the executable with a valid code signing certificate
- Consider using Inno Setup to create an installer

### macOS
- Application bundle will be created as `dist/SpotiBye.app`
- To distribute outside the App Store:
  1. Sign the app with Developer ID
  2. Notarize with Apple
  3. Package in a DMG with create-dmg

### Linux
- Binary will be created as `dist/SpotiBye/SpotiBye`
- Dependencies:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install -y python3-dev python3-pip python3-venv \
      build-essential libssl-dev libffi-dev \
      libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
      libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev \
      zlib1g-dev

  # Fedora
  sudo dnf install -y python3-devel python3-pip \
      @development-tools openssl-devel \
      SDL2-devel SDL2_image-devel SDL2_mixer-devel SDL2_ttf-devel \
      portmidi-devel zlib-devel
  ```
- Distribution options:
  1. **AppImage** (recommended for most users):
     ```bash
     # Install appimagetool
     wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
     chmod +x appimagetool-x86_64.AppImage
     
     # Create AppDir structure
     mkdir -p AppDir/usr/bin AppDir/usr/share/applications
     cp -r dist/SpotiBye/* AppDir/usr/bin/
     
     # Create .desktop file
     cat > AppDir/spotibye.desktop <<EOL
     [Desktop Entry]
     Name=SpotiBye
     Comment=Spotify Playlist Exporter
     Exec=SpotiBye
     Icon=spotibye
     Type=Application
     Categories=Audio;Music;
     EOL
     
     # Create AppImage
     ./appimagetool-x86_64.AppImage AppDir/ SpotiBye-x86_64.AppImage
     ```

  2. **DEB/RPM packages**:
     - Use `fpm` to create distribution-specific packages
     - Example for DEB:
       ```bash
       gem install fpm
       fpm -s dir -t deb -n spotibye -v 1.0.0 --prefix=/usr -C dist/SpotiBye .
       ```

  3. **Flatpak** (for distribution through Flathub):
     - Create a manifest file and build with `flatpak-builder`
     - Provides sandboxing and dependency management

### iOS (Limited Support)
Direct iOS builds are not supported due to platform restrictions. Consider these alternatives:

1. **Web Version**:
   - Create a responsive web interface
   - Host it alongside your backend
   - Users can add to home screen

2. **Kivy-iOS** (Experimental):
   ```bash
   # Install kivy-ios
   pip3 install kivy-ios
   
   # Build for iOS
   toolchain build python3 kivy
   toolchain build spotify_playlist_exporter_v2
   
   # Open in Xcode
   open spotify_playlist_exporter_v2-ios/YourApp.xcodeproj
   ```
   Note: This requires Xcode and a Mac with macOS.

3. **Native App**:
   - Develop a native iOS app in Swift/SwiftUI
   - Connect to your existing backend API
   - Publish on the App Store

## Step 7: Versioning and Update Management

### Versioning Strategy
- Use [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH)
- Update version in `src/spotify_playlist_exporter_v2/__init__.py`
- Tag releases with `v` prefix (e.g., `v1.0.0`)

### Update Channels
1. **Stable**: Official releases (tags)
2. **Nightly**: Automated builds from main branch (optional)
3. **Beta**: Pre-release versions (GitHub pre-releases)

### Update Notifications
- Include a version check in the application
- Notify users of new versions on startup
- Provide changelog with each release

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
- On Linux, you might need additional system packages for certain Python modules

**Linux-Specific Issues**
- **Missing Dependencies**:
  ```bash
  # If you see GLIBC or other library errors, install:
  sudo apt-get install -y libx11-dev libxext-dev libxss-dev libxrandr-dev \
      libxinerama-dev libxcursor-dev libxi-dev libgl1-mesa-dev libdbus-1-dev \
      libgles2-mesa-dev libegl1-mesa-dev
  ```

- **Font Rendering Issues**:
  - Install Microsoft Core Fonts or other common fonts:
    ```bash
    sudo apt-get install -y ttf-mscorefonts-installer
    ```
  - Set the `QT_QPA_PLATFORM` environment variable if needed:
    ```bash
    export QT_QPA_PLATFORM=xcb
    ```

- **Wayland Issues**:
  - If using Wayland, try running with XWayland:
    ```bash
    GDK_BACKEND=x11 ./SpotiBye
    ```
  - Or switch to X11 if possible
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
