# Build Instructions for Presidio PDF GUI

## Prerequisites

### 1. Flutter SDK
Install Flutter 3.0.0 or higher:
- Download from https://flutter.dev/docs/get-started/install
- Add Flutter to your PATH
- Run `flutter doctor` to verify installation

### 2. Desktop Development Setup

#### Windows
```bash
# Enable Windows desktop development
flutter config --enable-windows-desktop
```

#### macOS
```bash
# Enable macOS desktop development
flutter config --enable-macos-desktop
# Install Xcode from App Store
```

#### Linux
```bash
# Enable Linux desktop development
flutter config --enable-linux-desktop

# Install required packages (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install clang cmake ninja-build pkg-config libgtk-3-dev liblzma-dev
```

### 3. Python Backend
Ensure the Python backend is properly installed:
```bash
# Navigate to project root
cd ../

# Install using uv (recommended)
uv sync

# Install Japanese spaCy model
uv pip install https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.7.0/ja_core_news_sm-3.7.0-py3-none-any.whl
```

## Build Steps

### 1. Setup Flutter Dependencies
```bash
# Navigate to Flutter app directory
cd flutter_app

# Install dependencies
flutter pub get

# Generate code for JSON serialization
flutter packages pub run build_runner build
```

### 2. Development Build
```bash
# Run in debug mode
flutter run -d windows  # Windows
flutter run -d macos    # macOS
flutter run -d linux    # Linux

# Or run with hot reload
flutter run --hot
```

### 3. Production Build
```bash
# Build release version
flutter build windows --release  # Windows
flutter build macos --release    # macOS
flutter build linux --release    # Linux
```

## Build Outputs

### Windows
- Executable: `build/windows/runner/Release/presidio_pdf_gui.exe`
- All files in `build/windows/runner/Release/` are needed for distribution

### macOS
- App bundle: `build/macos/Build/Products/Release/presidio_pdf_gui.app`
- Can be distributed as a .dmg or .pkg

### Linux
- Executable: `build/linux/x64/release/bundle/presidio_pdf_gui`
- All files in `build/linux/x64/release/bundle/` are needed for distribution

## Troubleshooting

### Common Build Issues

1. **Flutter Doctor Issues**
   ```bash
   flutter doctor
   # Follow the recommendations to fix any issues
   ```

2. **Missing Desktop Platform**
   ```bash
   flutter config --enable-windows-desktop
   flutter config --enable-macos-desktop  
   flutter config --enable-linux-desktop
   ```

3. **Dependency Issues**
   ```bash
   flutter clean
   flutter pub get
   flutter packages pub run build_runner clean
   flutter packages pub run build_runner build --delete-conflicting-outputs
   ```

4. **Code Generation Errors**
   ```bash
   # Clean and regenerate
   flutter packages pub run build_runner clean
   flutter packages pub run build_runner build --delete-conflicting-outputs
   ```

### Platform-Specific Issues

#### Windows
- Ensure Visual Studio or Visual Studio Build Tools are installed
- Windows 10 SDK required

#### macOS  
- Xcode must be installed from App Store
- Command Line Tools: `xcode-select --install`

#### Linux
- Install development libraries: `sudo apt-get install clang cmake ninja-build pkg-config libgtk-3-dev liblzma-dev`

## Testing

### Unit Tests
```bash
flutter test
```

### Integration Tests
```bash
flutter test integration_test/
```

## Packaging for Distribution

### Windows
1. Build release version
2. Create installer using tools like:
   - NSIS (Nullsoft Scriptable Install System)
   - Inno Setup
   - WiX Toolset

### macOS
1. Build release version
2. Create .dmg or .pkg using:
   - create-dmg
   - pkgbuild
   - Xcode's Archive feature

### Linux
1. Build release version  
2. Create package using:
   - AppImage
   - Flatpak
   - Snap
   - DEB/RPM packages

## Development Tips

### Hot Reload
Use `r` in the console to hot reload during development.

### Debug Mode
```bash
flutter run --debug
```

### Profile Mode (for performance testing)
```bash
flutter run --profile
```

### Analyzing Code
```bash
flutter analyze
```

### Format Code
```bash
flutter format .
```

## Environment Variables

Set these environment variables if needed:

- `FLUTTER_ROOT`: Path to Flutter SDK
- `PATH`: Include Flutter bin directory
- `ANDROID_HOME`: Android SDK path (for mobile development)

## IDE Setup

### VS Code
Install extensions:
- Flutter
- Dart

### Android Studio/IntelliJ
Install plugins:
- Flutter
- Dart

### Recommended VS Code Settings
```json
{
  "dart.flutterSdkPath": "/path/to/flutter",
  "dart.openDevTools": "flutter",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll": true
  }
}
```