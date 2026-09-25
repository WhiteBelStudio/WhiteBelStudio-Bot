# WhiteBelStudio — Architecture

## 1. Purpose

WhiteBelStudio is a Telegram-first community platform with games, economy, moderation, API services, and a future Mini App.

The architecture is modular so that each subsystem can be implemented and tested independently without putting business logic into Telegram handlers.

## 2. Runtime components

- **Telegram Bot** — aiogram 3.x; receives updates and calls application services.
- **Application services** — business use-cases; the main boundary for user, reputation, game, economy, moderation, and admin operations.
- **Repositories** — database access only; no Telegram UI logic.
- **PostgreSQL** — production database and source of persistent application state.
- **Alembic** — schema migrations.
- **FastAPI** — HTTP/API layer for the Mini App and integrations.
- **Mini App** — Vercel-hosted frontend; communicates with the API, never directly with PostgreSQL.
- **Pterodactyl** — production Telegram bot runtime.
- **GitHub** — source control, CI/CD, releases, and deployment source.
- **Runtime storage** — logs, backups, and local runtime files are outside tracked source code.

## 3. Dependency direction

The dependency direction is intentionally one-way:

```text
Telegram handlers ───────┐
                         ├──> Application services
FastAPI routes ──────────┘            │
                                      v
                                Repositories
                                      │
                                      v
                                 PostgreSQL

Mini App ──> FastAPI ──> Application services

Application services MUST NOT depend on Telegram handlers.
Repositories MUST NOT depend on Telegram or FastAPI.
The Mini App MUST NOT access PostgreSQL directly.
```

## 4. Planned source layout

```text
app/
├── bot/              # Telegram routers, filters, keyboards
├── api/              # FastAPI routes and API schemas
├── core/             # configuration, logging, security, shared primitives
├── db/               # database engine, sessions, migrations integration
├── models/           # persistent/domain models
├── repositories/     # database repositories
├── services/         # business use-cases
├── schemas/          # validation/request/response models
└── integrations/     # Telegram/external service adapters

migrations/           # Alembic migrations
tests/
├── unit/
├── integration/
└── e2e/

docs/                 # architecture and operational documentation
```

## 5. Module boundaries

### Core
Owns configuration, logging, error types, security primitives, and application lifecycle helpers.

### Bot
Contains Telegram-specific code only: routers, handlers, keyboards, callback data, and Telegram presentation.

### API
Contains HTTP routing, authentication/validation at the API boundary, and response serialization.

### Services
Contains business rules and use-cases. Services may call repositories and integrations, but should not know about Telegram message objects or FastAPI request objects.

### Repositories
Contains persistence operations. Repositories expose application-oriented methods and hide SQL/ORM details.

### Models and schemas
Models describe persistent/domain data. Schemas describe validated input/output contracts. They are not interchangeable by default.

### Integrations
Contains adapters for Telegram and any future external providers. External SDK details stay behind this layer.

## 6. Data ownership

Each subsystem owns its data and service boundary:

- Users/profile → user domain
- Community/reputation → reputation domain
- Reputation → reputation domain
- Games/PvP → game domain
- Economy → economy domain
- Achievements/quests → progression domain
- Moderation/admin → moderation domain
- Analytics → analytics domain

Cross-domain operations go through services rather than direct table manipulation from handlers.

## 7. Deployment model

### GitHub
Source of truth for application code, migrations, tests, CI/CD, and release metadata.

### Pterodactyl
Production runtime. Secrets are supplied through environment variables. Runtime data is not committed.

The current lightweight Pterodactyl setup may keep `main.py`, `.env`, and `requirements.txt` locally while the rest of the project remains in GitHub. If the updater is enabled, this deployment mode must not overwrite those local runtime-owned files.

### Vercel
Hosts the Mini App frontend. It consumes the FastAPI API.

## 8. Rules

1. No business logic in Telegram handlers.
2. No database queries directly from Telegram handlers or API routes.
3. No secrets in Git.
4. No direct PostgreSQL access from the Mini App.
5. Every schema change uses an Alembic migration.
6. New features receive tests before being marked production-ready.
7. A checklist item becomes green only after implementation and verification.
8. Production code must remain compatible with Python 3.12.

## 9. Current implementation boundary

The repository currently uses main.py as the composition root and keeps Telegram feature routers under app/bot/. Business logic is concentrated in app/services/, persistence primitives in app/db/, and migrations in migrations/.

Current enforced boundaries:

- The retired social/friends subsystem is not a runtime dependency.
- Telegram routers own presentation and update handling; services own domain operations.
- Database access is centralized through app/db/engine.py and repository/service layers.
- Global error handling is centralized at the dispatcher boundary; expected domain errors are handled locally.
- Production startup validates environment, compiles the application, applies migrations, and verifies the resulting schema before starting the bot.

Future extraction of main.py into dedicated bot modules is a maintainability improvement, not a prerequisite for the current runtime boundary.
