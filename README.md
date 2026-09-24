# WhiteBelStudio Bot

Production Telegram bot platform by WhiteBelStudio.

## Stack

- Python 3.12+
- aiogram 3.x
- PostgreSQL for production
- FastAPI for API services
- Pterodactyl for the bot runtime
- Vercel for the Mini App
- GitHub as the source of truth

## Pterodactyl

Set the server startup command to:

```bash
python start.py
```

The bootstrap performs:

1. environment validation;
2. safe GitHub update from `GITHUB_REPOSITORY` / `GITHUB_BRANCH`;
3. dependency installation;
4. database migrations when configured;
5. Python health/compile checks;
6. bot startup.

Runtime data is kept outside the Git-tracked application code:

- `.env` — secrets/configuration;
- `data/` — runtime data and database files if used;
- `logs/` — logs;
- `backups/` — backups.

Do not commit real secrets.

## Environment

Copy `.env.example` to `.env` and configure at minimum:

- `BOT_TOKEN`
- `OWNER_ID`
- `DATABASE_URL` for PostgreSQL production

For the GitHub updater:

- `GITHUB_REPOSITORY=WhiteBelStudio/WhiteBelStudio-Bot`
- `GITHUB_BRANCH=main`
- `GITHUB_UPDATE_ENABLED=true`

A GitHub token is only needed if the deployment requires access to a private repository.

## Development

```bash
python -m pip install -r requirements.txt
python -m compileall -q .
python -m pytest
```

Production is started through `start.py`.
