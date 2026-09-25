# Development Guide

## Local setup

Use Python 3.12+.

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure local credentials.

## Run

For normal local development:

```bash
python main.py
```

For a production-like bootstrap:

```bash
python start.py
```

The production bootstrap expects a Git checkout and a PostgreSQL database.

## Quality checks

Run before opening a pull request:

```bash
python -m compileall -q app main.py start.py tests
python -m ruff check app tests main.py start.py
python -m pytest -m "not integration"
```

Integration tests require PostgreSQL:

```bash
python -m pytest -m integration
```

CI runs unit/API, integration, lint, compilation, and dependency-audit gates.

## Database changes

Never edit an already-applied migration.

Create a new Alembic migration for every schema change. Then verify:

```bash
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

Keep application models and migrations synchronized.

## Architecture rules

- Telegram handlers contain presentation/update handling.
- FastAPI routes contain HTTP boundary logic.
- Services contain business use-cases.
- Database access belongs in the DB/repository/service layer.
- The Mini App talks to FastAPI, never PostgreSQL.
- Do not add a second user identity system.
- Do not restore the retired social/friends subsystem.
- Do not put secrets into source code.

See `docs/ARCHITECTURE.md` for the dependency model.

## Tests

Tests are grouped by purpose:

- unit/API tests — fast and suitable for normal CI;
- integration tests — require real PostgreSQL;
- callback E2E tests — exercise real aiogram dispatcher routing;
- API integration tests — exercise the API against PostgreSQL.

A checklist item should only be marked green after the relevant implementation **and verification** are complete.

## Pull requests

A good change should include:

1. implementation;
2. tests for the changed behavior;
3. migration if the database schema changed;
4. documentation when operational behavior changes;
5. no unrelated generated/runtime files.

Do not mark a production feature complete solely because the code compiles.

## Logging and errors

Use the project's logging system instead of ad-hoc `print()` calls in production paths.

Do not log:

- BOT_TOKEN;
- DATABASE_URL;
- Telegram initData;
- cookies;
- passwords;
- private credentials.

When adding API errors, preserve the request ID so operators can correlate a client error with server logs.
