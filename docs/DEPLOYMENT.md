# Production Deployment — WhiteBelStudio Bot

## Runtime

Production runs on Pterodactyl with Python 3.12+.

**Startup command:**

```bash
python start.py
```

The bootstrap is the production entrypoint. Do not start `main.py` directly on the production server unless debugging.

## Required environment

At minimum:

- `BOT_TOKEN`
- `DATABASE_URL` in production
- `OWNER_ID`

Recommended production values:

```env
APP_ENV=production
GITHUB_REPOSITORY=WhiteBelStudio/WhiteBelStudio-Bot
GITHUB_BRANCH=main
GITHUB_UPDATE_ENABLED=true
API_HOST=0.0.0.0
API_PORT=8080
API_DOCS_ENABLED=false
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
DB_CONNECT_TIMEOUT=10
DB_STARTUP_RETRIES=10
DB_STARTUP_RETRY_DELAY=2
API_RATE_LIMIT_IP=60
API_RATE_LIMIT_AUTHENTICATED=120
```

Keep secrets only in Pterodactyl environment variables or `.env`. Never commit them.

## Startup lifecycle

```text
Pterodactyl
  -> start.py
  -> validate environment
  -> update GitHub checkout
  -> install requirements
  -> compile Python
  -> wait for PostgreSQL
  -> Alembic upgrade head
  -> verify database schema
  -> start main.py
  -> Telegram polling + FastAPI
```

If any mandatory production step fails, the process exits instead of starting against an unsafe state.

## GitHub updater

The updater follows `GITHUB_REPOSITORY` and `GITHUB_BRANCH`.

Set:

```env
GITHUB_UPDATE_ENABLED=true
```

The updater fetches the configured branch and resets the application checkout to its remote commit. Runtime files that are ignored by Git, such as `.env`, are preserved.

If GitHub access is private, provide the appropriate server-side authentication instead of putting credentials into tracked files.

## Database

Production uses PostgreSQL and Alembic.

Every schema change must be an Alembic migration:

```bash
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

Do not use `Base.metadata.create_all()` as the production migration mechanism.

The bootstrap verifies the migration revision and required tables before starting the application.

## Database startup retries

If PostgreSQL starts slightly later than the bot container/server, the bootstrap retries:

```env
DB_STARTUP_RETRIES=10
DB_STARTUP_RETRY_DELAY=2
```

The total wait is approximately 18 seconds between the first attempt and the last attempt with the default settings.

## Health endpoints

- `GET /health` — basic process/API liveness.
- `GET /health/live` — liveness probe.
- `GET /health/ready` — verifies database readiness and reports the Alembic revision.
- `GET /api/v1/health` — API version/liveness.

Use `/health/ready` for deployment verification because it exercises the database readiness path.

## API

FastAPI listens on:

```env
API_HOST=0.0.0.0
API_PORT=8080
```

The API is intended to be reached through the deployment's public routing/reverse proxy when required. Do not expose PostgreSQL publicly.

The Mini App communicates with FastAPI and never receives database credentials.

## Telegram Mini App authentication

Protected API endpoints require the Telegram signed `X-Telegram-Init-Data` header.

The API:

1. validates Telegram's signature;
2. rejects duplicate keys and malformed data;
3. validates `auth_date`;
4. rejects stale/future data;
5. extracts the trusted Telegram user;
6. resolves that identity against the existing `users` table;
7. rejects unregistered, inactive, or bot users.

Client-supplied profile fields are not treated as an identity source.

## API rate limiting

Production API requests use shared PostgreSQL-backed fixed-window limits. Unauthenticated traffic is limited by client IP to 60 requests/minute; requests carrying Telegram Mini App initData use a separate 120 requests/minute bucket. Health endpoints are exempt. Exceeded limits return HTTP 429 with `Retry-After` and the standard request ID/error contract.

## Logs

Application logs are structured JSON on stdout.

Pterodactyl should retain stdout/stderr through its normal logging mechanism. Important events include:

- bootstrap start/failure;
- GitHub update;
- dependency installation;
- migration start/completion;
- database readiness;
- schema verification;
- bot startup;
- API startup;
- request IDs and HTTP request metadata.

Do not put tokens, passwords, database URLs, or signed Telegram initData into logs.

## Restart procedure

Normal restart:

1. Stop/restart the Pterodactyl server.
2. `python start.py` runs automatically.
3. Bootstrap updates code if enabled.
4. Dependencies and migrations are reconciled.
5. Schema health is checked.
6. Bot/API start.

Do not manually delete the production database to fix migrations.

## Failed deployment

If bootstrap fails before migrations start and a new Git commit was deployed, the bootstrap can restore the previous code revision.

After migrations have started, automatic code rollback is intentionally skipped. A database schema may already have changed, and blindly reverting application code could create an incompatible state.

For a migration-related failure:

1. keep the database intact;
2. inspect Alembic status;
3. inspect the failing migration;
4. fix forward with a new migration when appropriate;
5. redeploy and verify readiness.

## Release flow

The repository CI validates code, migrations, tests, and dependency audit. Tagged releases are published through GitHub Actions.

Production deployment is triggered through the configured deployment workflow/Pterodactyl integration.

A green CI workflow means the repository passed its configured gates; it does not by itself prove that the live Pterodactyl server is healthy.

## Operational checklist

Before declaring production healthy:

- [ ] Pterodactyl server is running.
- [ ] `BOT_TOKEN` is present.
- [ ] `DATABASE_URL` points to PostgreSQL.
- [ ] `python start.py` completes successfully.
- [ ] Alembic is at the expected head.
- [ ] `/health/ready` returns OK.
- [ ] Telegram bot responds to `/start`.
- [ ] Mini App protected API calls authenticate successfully.
- [ ] Logs contain structured request/startup events.
- [ ] No secrets appear in logs.
- [ ] CI and release gates are green.
