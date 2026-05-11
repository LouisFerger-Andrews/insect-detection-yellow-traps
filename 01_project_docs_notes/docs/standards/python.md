# Python Standards

## Target

- Python `3.11+` for backend and project scripts.

## Style

- Follow PEP 8.
- Prefer type hints on public functions and module boundaries.
- Use descriptive names; avoid single-letter variables except local indices.
- Keep functions focused and small.

## Imports

- Standard library
- Third-party
- Local imports

Separate groups with one blank line.

## Errors and Validation

- Validate external input early.
- Raise explicit exceptions with actionable messages.
- In API code, map errors to clear HTTP responses.

## API and DB Patterns

- Keep route handlers thin.
- Put business logic in services/helpers.
- Keep SQLAlchemy queries readable and composable.
- Avoid hidden side effects in model methods.

## Testing

- Add tests for new behavior and regressions.
- Prefer deterministic tests (no network unless mocked).
- Use fixtures for repeated setup.

## Recommended Tooling

Recommended industry baseline:
- `ruff` for linting (and import sorting)
- `black` for formatting
- `pytest` for tests

Example commands:

```bash
ruff check .
black .
pytest
```

