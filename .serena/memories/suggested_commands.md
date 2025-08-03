# Essential Commands for PresidioPDF Development

## Package Management (ALWAYS use uv, NEVER pip)
```bash
uv sync                        # Install dependencies
uv sync --extra dev           # Install with dev dependencies
uv sync --extra web           # Install with web dependencies
uv add package-name           # Add new dependency
uv add --dev package-name     # Add dev dependency
```

## Development Workflow
```bash
# Run CLI application
uv run python -m src.cli path/to/file.pdf
uv run python -m src.cli path/to/file.pdf --read-mode
uv run python -m src.cli path/to/file.pdf --restore-mode

# Run web application
uv run python src/web_main.py
uv run python src/web_main.py --gpu --port 8080
```

## Quality Assurance (MANDATORY before commits)
```bash
uv run black .                # Format code
uv run mypy src/             # Type checking
uv run pytest --cov=src     # Run tests with coverage
```

## Testing
```bash
uv run pytest               # Run all tests
uv run pytest -v           # Verbose output
uv run pytest tests/test_*.py  # Specific tests

# Web application testing
uv run python src/web_main.py &
uv run python tests/web_app_test.py
```

## System Commands (Linux)
```bash
which command               # Check command location
ls -la                     # List files with details
grep -r pattern            # Search in files
find . -name "*.py"        # Find Python files
```