# Operations Runbook

## First response to an outage

1. Check Pterodactyl console/logs.
2. Look for `bootstrap_failed`, `database_not_ready`, `database_schema_ok`, and `bot_polling_start`.
3. Check `GET /health/live`.
4. Check `GET /health/ready`.
5. Check PostgreSQL availability.
6. Check the current Git commit and Alembic revision.
7. Do not delete the database as a first response.

## Bot is not starting

Check:

- `BOT_TOKEN`;
- Python version;
- dependency installation;
- compile check;
- GitHub checkout;
- PostgreSQL connection;
- Alembic migration output.

The production process should stop rather than run with an invalid database schema.

## Database errors

Check:

```bash
python -m alembic current
python -m alembic check
```

If a migration partially changed the schema, investigate before changing application code.

Prefer forward-compatible migrations and a new corrective migration over manual production table edits.

## API unhealthy

Check:

- FastAPI process;
- `API_HOST` / `API_PORT`;
- CORS configuration;
- PostgreSQL readiness;
- Mini App `X-Telegram-Init-Data`;
- request ID from the client response.

## Telegram updates fail

Check bot token and Telegram connectivity. If a proxy is configured:

```env
TELEGRAM_PROXY=socks5://...
```

Do not paste proxy credentials into public issues or logs.

## Deployment failure

The deployment workflow can restart the configured Pterodactyl server. A restart alone is not a complete health proof.

After deployment, verify:

1. server process is running;
2. readiness endpoint is healthy;
3. Telegram responds;
4. structured logs show the new commit/startup;
5. database revision is correct.

## Backups

Backups are operationally required for production PostgreSQL. Configure backups at the PostgreSQL/provider level and verify restore procedures separately.

The repository's `backups/` directory is not a substitute for durable database backups.

## Security

Immediately rotate any secret that was accidentally exposed.

Never put tokens, passwords, DATABASE_URL values, Telegram initData, or private keys in GitHub issues, commits, logs, screenshots, or chat messages.
