# Contributing to `django-recur`

## Overview

**What you will learn:**

- How to set up a local Python and TypeScript development environment.
- How to run tests, linters, type checks, and the Zensical documentation build.

Contributions are welcome. Follow these steps to verify changes locally before opening a pull request.

## Prerequisites

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).
- Node.js 20+ and `npm` (for `<django-recur-widget>`).

## Development Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/lino/django-recur.git
   cd django-recur
   ```

2. Install Python dependencies with `uv`:

   ```bash
   uv sync --all-extras --dev
   ```

3. Install frontend dependencies for the TypeScript widget:

   ```bash
   cd frontend
   npm install
   cd ..
   ```

## Running Tests & Quality Checks

1. Run the Python test suite:

   ```bash
   uv run pytest
   ```

2. Run Ruff lint and format checks:

   ```bash
   uv run ruff check src tests
   uv run ruff format --check src tests
   ```

3. Run Mypy static type checking:

   ```bash
   uv run mypy src
   ```

4. Run frontend typechecking, Vitest tests, and the Vite build:

   ```bash
   cd frontend
   npm run typecheck
   npm test
   npm run build
   ```

5. Build the Zensical documentation locally:

   ```bash
   uv run zensical build --clean
   ```

## Expected Outcome

All Python tests, Ruff checks, Mypy checks, frontend Vitest tests, and the Zensical documentation build exit with status `0`.
