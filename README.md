# WhiteBelStudio Bot

Production Telegram community platform by WhiteBelStudio.

## What it contains

- Telegram bot on aiogram 3.x
- PostgreSQL persistence
- Alembic migrations
- FastAPI API
- Telegram Mini App authentication
- economy, shop, achievements, games and PvP
- community reputation
- moderation/admin functionality
- structured logging and request IDs
- CI/CD and release automation
- Pterodactyl production runtime

The retired social/friends subsystem is intentionally not part of the current architecture.

## Architecture

```text
Telegram Bot ──┐
               ├──> Services ──> DB layer ──> PostgreSQL
FastAPI API ───┘
     ↑
Mini App (Vercel)
```

The Mini App never connects directly to PostgreSQL. Telegram identity is verified through signed Mini App `initData` and resolved against the same `users` table used by the bot.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Stack

- Python 3.12+
- aiogram 3.x
- FastAPI
- SQLAlchemy async + asyncpg
- PostgreSQL
- Alembic
- Pydantic
- pytest
- Ruff
- GitHub Actions
- Pterodactyl
- Vercel for the Mini App

## Production

Pterodactyl starts the application with:

```bash
python start.py
```

The bootstrap:

1. validates required environment;
2. updates the Git checkout when enabled;
3. installs dependencies;
4. compiles the application;
5. waits for PostgreSQL;
6. runs Alembic migrations;
7. verifies the migrated schema;
8. starts the bot and API.

Production deployment documentation: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Configuration

Start from:

```text
.env.example
```

Never commit real secrets.

Important production variables include:

- `BOT_TOKEN`
- `OWNER_ID`
- `DATABASE_URL`
- `APP_ENV`
- `GITHUB_REPOSITORY`
- `GITHUB_BRANCH`
- `GITHUB_UPDATE_ENABLED`
- `API_HOST`
- `API_PORT`
- `API_CORS_ORIGINS`
- `MINI_APP_INIT_DATA_MAX_AGE`

## Development

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run fast checks:

```bash
python -m compileall -q app main.py start.py tests
python -m ruff check app tests main.py start.py
python -m pytest -m "not integration"
```

Integration tests require PostgreSQL:

```bash
python -m pytest -m integration
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## API

Base API prefix:

```text
/api/v1
```

Health:

- `/health`
- `/health/live`
- `/health/ready`
- `/api/v1/health`

Protected business endpoints require Telegram signed `X-Telegram-Init-Data`.

See [docs/API.md](docs/API.md).

## Operations

For incidents, deployment failures, database issues and API troubleshooting, see [docs/OPERATIONS.md](docs/OPERATIONS.md).

## CI/CD

GitHub Actions validates:

- Ruff;
- Python compilation;
- unit/API tests;
- PostgreSQL integration tests;
- migration state;
- dependency audit;
- source artifact creation.

Tagged releases use the release workflow. Production deployment uses the configured Pterodactyl deployment workflow.

A green CI run proves repository gates passed; it does not by itself prove that the live server is healthy.

## Documentation map

| Document | Purpose |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Components, boundaries and data ownership |
| [Deployment](docs/DEPLOYMENT.md) | Pterodactyl production deployment |
| [Development](docs/DEVELOPMENT.md) | Local development and contribution workflow |
| [API](docs/API.md) | HTTP endpoints and authentication |
| [Operations](docs/OPERATIONS.md) | Incident and troubleshooting runbook |

## Production rule

A feature is production-ready only when implementation, tests, documentation and runtime verification are all complete.