from __future__ import annotations

import asyncio
import os
from decimal import Decimal

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.health import REQUIRED_TABLES
from app.db.models import User
from app.services.chat import get_chat_stats, record_chat_activity
from app.services.communication import get_messages, send_message
from app.services.community import get_reputation_score, set_chat_reputation_vote
from app.services.economy import change_balance, get_balance, list_transactions
from app.services.pvp import accept_challenge, create_challenge, submit_answer

pytestmark = pytest.mark.integration


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        pytest.fail("DATABASE_URL is required for integration tests")

    if value.startswith("postgresql://"):
        return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
    if value.startswith("postgres://"):
        return "postgresql+asyncpg://" + value.removeprefix("postgres://")
    if not value.startswith("postgresql+asyncpg://"):
        pytest.fail("Integration tests require PostgreSQL via asyncpg")
    return value


async def _new_engine():
    return create_async_engine(
        _database_url(),
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"timeout": 10},
    )


async def _assert_schema(session: AsyncSession) -> None:
    revision = (
        await session.execute(text("SELECT version_num FROM alembic_version"))
    ).scalar_one_or_none()
    assert revision, "Alembic migration head is missing"

    tables = set(
        (
            await session.execute(
                text(
                    "SELECT table_name "
                    "FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        ).scalars()
    )
    assert REQUIRED_TABLES <= tables


async def _scenario() -> None:
    engine = await _new_engine()
    Session = async_sessionmaker(engine, expire_on_commit=False)

    creator = User(
        telegram_id=910000001,
        first_name="Integration Creator",
        username="integration_creator",
        is_bot=False,
        is_active=True,
    )
    opponent = User(
        telegram_id=910000002,
        first_name="Integration Opponent",
        username="integration_opponent",
        is_bot=False,
        is_active=True,
    )
    chat_id = -910000001

    try:
        async with Session() as session:
            await _assert_schema(session)

            session.add_all([creator, opponent])
            await session.flush()

            # Economy: balance and transaction survive a real PostgreSQL commit.
            assert await change_balance(
                session, creator.id, Decimal("10.0"), "integration_test"
            ) == Decimal("10.0")
            transactions = await list_transactions(session, creator.id, limit=50)
            assert len(transactions) == 1
            assert transactions[0].amount == Decimal("10.0")
            assert await get_balance(session, creator.id) == Decimal("10.0")

            # Community activity creates chat/member state and counters.
            await record_chat_activity(
                session,
                chat_id,
                "Integration Chat",
                "supergroup",
                creator,
                is_command=True,
            )
            chat, member_count, message_count = await get_chat_stats(session, chat_id)
            assert chat is not None
            assert member_count == 1
            assert message_count == 1

            # Community reputation: create, repeat and change a vote.
            assert await get_reputation_score(session, opponent.id, chat.id) == 0
            changed, score = await set_chat_reputation_vote(
                session, chat.id, creator.id, opponent.id, 1
            )
            assert (changed, score) == (True, 1)

            changed, score = await set_chat_reputation_vote(
                session, chat.id, creator.id, opponent.id, 1
            )
            assert (changed, score) == (False, 1)

            changed, score = await set_chat_reputation_vote(
                session, chat.id, creator.id, opponent.id, -1
            )
            assert (changed, score) == (True, -1)

            # Communication: create conversation/message and verify read persistence.
            status, record = await send_message(
                session, creator.id, opponent.id, "integration hello"
            )
            assert status == "sent"
            assert record is not None

            messages = await get_messages(session, opponent.id, creator.id)
            assert [item.text for item in messages] == ["integration hello"]
            assert messages[0].read_at is not None

            # PvP: challenge -> accept -> both correct answers -> terminal draw.
            match = await create_challenge(session, creator.id, "math")
            accepted = await accept_challenge(session, match.id, opponent.id)
            assert accepted.status == "active"

            first = await submit_answer(session, match.id, creator.id, match.answer)
            assert first[0] == "correct"

            second = await submit_answer(session, match.id, opponent.id, match.answer)
            assert second[0] == "finished"
            assert second[1].status == "draw"

        # Re-open a separate connection/session: verify committed state is durable.
        async with Session() as session:
            await _assert_schema(session)

            persisted_creator = (
                await session.execute(
                    text(
                        "SELECT telegram_id FROM users "
                        "WHERE telegram_id = :telegram_id"
                    ),
                    {"telegram_id": creator.telegram_id},
                )
            ).scalar_one()
            assert persisted_creator == creator.telegram_id

            persisted_balance = await get_balance(session, creator.id)
            assert persisted_balance == Decimal("10.0")

            persisted_messages = await get_messages(session, creator.id, opponent.id)
            assert [item.text for item in persisted_messages] == ["integration hello"]

            social_tables = (
                await session.execute(
                    text(
                        "SELECT to_regclass('public.friendships'), "
                        "to_regclass('public.friend_requests')"
                    )
                )
            ).one()
            assert social_tables == (None, None)

    finally:
        async with Session() as session:
            if creator.id is not None:
                await session.execute(
                    delete(User).where(User.id.in_([creator.id, opponent.id]))
                )
                await session.commit()
        await engine.dispose()


def test_postgresql_integration() -> None:
    asyncio.run(_scenario())
