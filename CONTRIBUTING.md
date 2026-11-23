# Contributing to python-data-pipeline

Contributions that improve reliability, test coverage, security, and maintainability are welcome.

## Development Setup

1. Clone the repository and create an isolated Python 3.11+ virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Copy the environment configuration template:
   ```bash
   cp .env.example .env
   ```
3. Install pre-commit hooks (optional but recommended):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Coding Standards

- Follow PEP 8 with a maximum line length of 120 characters (`flake8 --max-line-length=120 .` and `ruff check src tests main.py`).
- Provide full Python type hints and Google-style docstrings on all public modules, classes, and functions.
- Keep functions cohesive (`< 50` lines) with shallow control-flow nesting (`< 3` levels).
- Use `logging.getLogger(__name__)` for operational logging; never commit raw `print()` debug statements or real credentials.
- Catch specific exception types and guarantee resource cleanup with context managers or `try/finally`.

## Testing Requirements

Every behavioral change or bug fix must include automated unit or integration tests following the Arrange-Act-Assert pattern:

```bash
make lint
make typecheck
make coverage
```

All tests must pass with `>= 80%` coverage over `src/`.

## Commit & Pull Request Guidelines

- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `ci:`, `chore:`).
- Keep pull requests focused on a single logical concern.
- Update `CHANGELOG.md` and `docs/RUNBOOK.md` when changing operational behavior or environment variables.
