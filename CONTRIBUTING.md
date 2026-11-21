# Contributing to django-recur

Thank you for your interest in contributing to **django-recur**!

Whether you are reporting a bug, proposing an RFC 8984 / RFC 5545 enhancement, improving the Web Component widget, or updating documentation, your contributions are welcome.

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Development Setup

This project uses:
- **[uv](https://docs.astral.sh/uv/)** for Python environment, dependency, and build management.
- **[Ruff](https://docs.astral.sh/ruff/)** for linting and code formatting.
- **[Mypy](https://mypy-lang.org/)** for static type checking.
- **[Pytest](https://docs.pytest.org/)** for testing and coverage verification.
- **[Vite](https://vite.dev/) + TypeScript** (in `frontend/`) for the `<django-recur-widget>` Web Component pipeline.
- **[Zensical](https://zensical.org/)** for documentation generation.

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/lino/django-recur.git
cd django-recur
uv sync --dev
```

### 2. Run the Python test suite & linters

```bash
# Run pytest with coverage
uv run pytest

# Run ruff linter & formatter check
uv run ruff check src tests
uv run ruff format --check src tests

# Run mypy type checker
uv run mypy src
```

### 3. Build & test the TypeScript Web Component widget

The widget source lives in `frontend/` and compiles to `src/recurrence/static/recurrence/`. Use Node.js 22.22.2 or later in the 22.x series, as CI does. The frontend manifest also lists compatible newer Node.js series.

```bash
cd frontend
npm ci
npm run test
npm run build
```

### 4. Preview documentation locally with Zensical

```bash
uv run zensical serve
```

Then visit `http://127.0.0.1:8000` in your browser.

---

## Pull Request Guidelines

1. **Keep PRs focused**: Separate bugfixes, new features, documentation improvements, and CI/tooling updates into distinct pull requests whenever possible.
2. **Maintain test coverage**: New features and bugfixes must include tests covering:
   - The modern `django_recur` RFC 8984 API
   - RFC 5545 / RFC 8984 bidirectional mapping (where applicable)
   - The `recurrence` drop-in compatibility layer (where applicable)
3. **Update documentation**: If you add or change an RFC 8984 or RFC 5545 capability, update the [RFC Compliance Matrix](docs/rfc-compliance-matrix.md) as well.
