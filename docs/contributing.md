# Contributing to `django-recurrence-jscalendar`

Contributions are welcome! Please read this guide to set up your local development environment and run the test suite.

## Development Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/lino/django-recurrence-jscalendar.git
   cd django-recurrence-jscalendar
   ```

2. Install Python dependencies using [`uv`](https://docs.astral.sh/uv/):

   ```bash
   uv sync --all-extras --dev
   ```

3. Install frontend dependencies for the `<dj-recurrence-widget>` TypeScript pipeline:

   ```bash
   cd frontend
   npm install
   cd ..
   ```

## Running Tests & Quality Checks

Run the Python test suite with coverage:

```bash
uv run pytest
```

Run Ruff linting and formatting checks:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
```

Run Mypy static type checking:

```bash
uv run mypy src
```

Run frontend TypeScript type checking, Vitest tests, and Vite bundle build:

```bash
cd frontend
npm run typecheck
npm test
npm run build
```

Build the Zensical documentation locally:

```bash
uv run zensical build --clean
```
