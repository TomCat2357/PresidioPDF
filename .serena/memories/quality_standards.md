# Quality Standards and Code Conventions

## Zero Warning Policy
- All warnings are treated as errors and must be fixed
- No exceptions to this rule

## Type Safety
- mypy type checking is mandatory
- Avoid `Any` types wherever possible
- Use strict type hints for all functions and methods

## Code Style
- black formatting is required (line-length = 88)
- Follow PEP 8 conventions
- Use descriptive variable and function names

## Testing Requirements
- Test-Driven Development approach
- Maintain 80%+ test coverage
- Write tests before implementing features
- Use pytest framework

## Task Completion Checklist
When completing any task, ALWAYS run:
1. `uv run black .` (code formatting)
2. `uv run mypy src/` (type checking)
3. `uv run pytest --cov=src` (tests with coverage)

## Documentation
- Use clear docstrings for all public functions
- Follow Google-style docstring format
- Document complex algorithms and business logic