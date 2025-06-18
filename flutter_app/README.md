# Presidio PDF GUI

A Flutter desktop application for PDF personal information detection and masking using Microsoft Presidio.

## Features

- **PDF Viewer**: View PDF documents with zoom, pan, and page navigation
- **Personal Information Detection**: Automatic detection of Japanese personal information using Presidio
- **Interactive Editing**: Create, edit, and delete annotations manually
- **Configurable Settings**: Extensive configuration options for detection and masking
- **Export Reports**: Export detection results in JSON or CSV format
- **Cross-Platform**: Supports Windows, macOS, and Linux

## Installation

### Prerequisites

1. **Flutter SDK**: Install Flutter 3.0.0 or higher
2. **Python Environment**: Python 3.11+ with the backend dependencies installed
3. **Japanese spaCy Model**: Install one of the Japanese language models:
   ```bash
   # Install using uv (recommended)
   uv pip install https://github.com/explosion/spacy-models/releases/download/ja_core_news_sm-3.7.0/ja_core_news_sm-3.7.0-py3-none-any.whl
   
   # Or install GINZA for higher accuracy
   uv run python -m pip install 'ginza[ja]'
   ```

### Setup

1. Clone the repository and navigate to the Flutter app directory:
   ```bash
   cd flutter_app
   ```

2. Install Flutter dependencies:
   ```bash
   flutter pub get
   ```

3. Generate model code:
   ```bash
   flutter packages pub run build_runner build
   ```

4. Run the application:
   ```bash
   flutter run -d windows  # For Windows
   flutter run -d macos    # For macOS  
   flutter run -d linux    # For Linux
   ```

## Usage

### Basic Workflow

1. **Open a PDF**: Use File > Open or drag and drop a PDF file
2. **Start Detection**: Click the "Detect" button to analyze the document
3. **Review Results**: Check the detection results in the right panel
4. **Edit Annotations**: Create, modify, or delete annotations as needed
5. **Save**: Save the processed PDF with annotations
6. **Export Reports**: Export detection results to JSON or CSV

### Key Components

- **PDF Viewer**: Main viewing area with zoom and pan controls
- **Thumbnails Panel**: Page navigation on the left
- **Results Panel**: List of detected personal information on the right
- **Properties Panel**: Details and editing for selected annotations
- **Settings**: Comprehensive configuration options

### Supported Entity Types

- **PERSON (人名)**: Names and personal identifiers
- **LOCATION (場所)**: Addresses and location information  
- **PHONE_NUMBER (電話)**: Phone numbers
- **DATE_TIME (日時)**: Date and time information
- **INDIVIDUAL_NUMBER (マイナンバー)**: Japanese Individual Numbers
- **YEAR (年号)**: Japanese Era years
- **PROPER_NOUN (固有名詞)**: Proper nouns and specific terms

### Configuration Options

#### Detection Settings
- Entity type selection
- Confidence thresholds per entity type
- spaCy model selection (ja_core_news_sm, ja_core_news_md, ja_ginza, ja_ginza_electra)

#### Masking Settings
- Masking method: annotation, highlight, or both
- Text display mode: verbose, minimal, or silent
- Operation mode: clear all, append, or reset and append

#### Processing Options
- Deduplication modes and overlap handling
- File output options (suffix, backup, reports)
- Verbose logging

## Architecture

The application follows a clean architecture pattern:

```
flutter_app/
├── lib/
│   ├── main.dart              # Application entry point
│   ├── models/                # Data models
│   │   ├── detection_result.dart
│   │   └── settings.dart
│   ├── services/              # Business logic
│   │   ├── app_state.dart
│   │   ├── presidio_service.dart
│   │   └── settings_service.dart
│   ├── screens/               # Main screens
│   │   ├── main_screen.dart
│   │   └── settings_screen.dart
│   └── widgets/               # Reusable widgets
│       ├── pdf_viewer_widget.dart
│       ├── toolbar_widget.dart
│       ├── thumbnail_panel.dart
│       ├── results_panel.dart
│       └── properties_panel.dart
├── pubspec.yaml               # Dependencies
└── README.md                  # This file
```

### Communication with Python Backend

The Flutter app communicates with the Python backend (`pdf_presidio_processor.py`) through:

1. **Subprocess execution**: Runs the Python script as a child process
2. **JSON configuration**: Passes settings via temporary JSON files
3. **Result parsing**: Reads detection results from stdout or temporary files
4. **File-based workflows**: Uses file paths for input/output operations

## Development

### Building for Production

```bash
# Build for current platform
flutter build windows
flutter build macos
flutter build linux

# Build with specific configurations
flutter build windows --release
```

### Code Generation

When modifying model classes with JSON serialization:

```bash
flutter packages pub run build_runner build --delete-conflicting-outputs
```

### Dependencies

Key Flutter packages used:

- `pdfx`: PDF rendering and viewing
- `provider`: State management
- `file_picker`: File selection dialogs
- `desktop_drop`: Drag and drop support
- `split_view`: Resizable panel layouts
- `json_annotation`: JSON serialization
- `path_provider`: File system access

## Troubleshooting

### Common Issues

1. **Python dependencies not found**: Ensure the Python environment is properly set up and accessible
2. **spaCy model not available**: Install the required Japanese language model
3. **PDF not loading**: Check file permissions and PDF format compatibility
4. **Performance issues**: Try using a smaller spaCy model (ja_core_news_sm) for better performance

### Debug Mode

Run in debug mode for detailed logging:

```bash
flutter run --debug -d windows
```

Enable verbose output in settings for more detailed processing information.

## License

This project uses various open-source packages. See the licenses page in the application for full details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

For major changes, please open an issue first to discuss the proposed changes.