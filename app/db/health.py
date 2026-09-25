from __future__ import annotations

from sqlalchemy import inspect, text

from app.db.engine import configure_engine


REQUIRED_TABLES = {
    "users",
    "user_settings",
    "conversations",
    "messages",
    "reputation_ratings",
    "community_chats",
    "chat_member_stats",
    "community_reputation_votes",
    "reputation_events",
    "game_profiles",
    "economy_accounts",
    "shop_items",
    "user_inventory",
    "coin_transactions",
    "pvp_matches",
    "achievements",
    "user_achievements",
}


async def check_database_connection() -> None:
    engine = configure_engine()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def check_database_schema() -> str:
    """Verify the migrated schema is present and return the Alembic revision."""
    engine = configure_engine()
    async with engine.connect() as connection:
        revision = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
        if not revision:
            raise RuntimeError("Alembic revision is missing")

        table_names = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )
        missing = sorted(REQUIRED_TABLES - table_names)
        if missing:
            raise RuntimeError("Missing database tables: " + ", ".join(missing))

        return str(revision)
