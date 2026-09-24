# Pterodactyl Production Setup

## 1. Server files

The server directory must be a real Git checkout of this repository. Do not upload a ZIP over the top of it.

Recommended first setup:

```bash
git clone https://github.com/WhiteBelStudio/WhiteBelStudio-Bot.git .
```

If the server already contains the project, make sure the `.git` directory exists.

## 2. Python

Use Python 3.12.

Check:

```bash
python --version
```

Expected major/minor version: `3.12`.

## 3. Startup command

Set the Pterodactyl startup command to:

```bash
python start.py
```

Do not use `python main.py` for production, because that bypasses the updater and health checks.

## 4. Environment

Set these variables in Pterodactyl. Never commit real secrets to GitHub.

Required:

- `BOT_TOKEN`
- `OWNER_ID`
- `DATABASE_URL`

GitHub updater:

- `GITHUB_REPOSITORY=WhiteBelStudio/WhiteBelStudio-Bot`
- `GITHUB_BRANCH=main`
- `GITHUB_UPDATE_ENABLED=true`
- `GITHUB_TOKEN` only when the repository is private

Application:

- `APP_ENV=production`
- `LOG_LEVEL=INFO`
- `API_HOST=0.0.0.0`
- `API_PORT=8080`

## 5. What happens on every restart

`start.py`:

1. creates runtime directories;
2. validates required environment;
3. verifies that the project is a Git checkout;
4. fetches the configured GitHub branch;
5. updates code when a new commit exists;
6. installs `requirements.txt`;
7. compiles the application as a health check;
8. runs Alembic migrations when the migration environment exists;
9. performs a second health check;
10. starts `main.py`.

Runtime data is kept outside Git:

- `.env`
- `data/`
- `logs/`
- `backups/`
- `.runtime/`

The updater does not run `git clean`, so ignored runtime data is not removed.

## 6. Failed update

If code was changed and bootstrap fails before the bot starts, `start.py` resets the code to the previous Git commit and attempts to restore the previous revision's Python dependencies.

Database migrations are deliberately a separate production concern: once a migration has been applied, code rollback cannot automatically undo a database schema change. Database backup/restore will be added together with the PostgreSQL migration system.

## 7. First launch verification

After saving the variables, restart the server and look for:

```text
WhiteBelStudio Bot production bootstrap
...
Health check: OK
Bootstrap ready at <commit>
```

Then the bot process should remain running.

If startup fails, send the complete Pterodactyl console output from the first `[start]` line through the traceback. Do not send the bot token.
