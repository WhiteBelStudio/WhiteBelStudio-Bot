from __future__ import annotations

import asyncio
import os
from decimal import Decimal

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import CommunityChat, User
from app.services.chat import get_chat_stats, record_chat_activity
from app.services.communication import get_messages, send_message
from app.services.economy import change_balance, get_balance
from app.services.pvp import accept_challenge, create_challenge, submit_answer
from app.services.community import get_reputation_score, set_chat_reputation_vote


pytestmark = pytest.mark.integration


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        pytest.skip("DATABASE_URL is required for integration tests")
    if value.startswith("postgresql://"):
        return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
    if value.startswith("postgres://"):
        return "postgresql+asyncpg://" + value.removeprefix("postgres://")
    return value


async def _scenario() -> None:
    engine = create_async_engine(_database_url(), pool_pre_ping=True)
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
            session.add_all([creator, opponent])
            await session.flush()

            # Economy: persisted balance + transaction.
            balance = await change_balance(session, creator.id, Decimal("10.0"), "integration_test")
            assert balance == Decimal("10.0")
            assert await get_balance(session, creator.id) == Decimal("10.0")

            # Community/chat activity: chat, member and counters persist.
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

            # Community reputation: vote creates a durable score and is idempotent.
            assert await get_reputation_score(session, opponent.id, chat.id) == 0
            changed, score = await set_chat_reputation_vote(
                session, chat.id, creator.id, opponent.id, 1
            )
            assert changed is True
            assert score == 1

            changed, score = await set_chat_reputation_vote(
                session, chat.id, creator.id, opponent.id, 1
            )
            assert changed is False
            assert score == 1

            changed, score = await set_chat_reputation_vote(
                session, chat.id, creator.id, opponent.id, -1
            )
            assert changed is True
            assert score == -1

            # Communication: conversation/message persistence no longer depends on
            # the retired friendship subsystem.
            status, record = await send_message(
                session, creator.id, opponent.id, "integration hello"
            )
            assert status == "sent"
            assert record is not None

            messages = await get_messages(session, opponent.id, creator.id)
            assert [item.text for item in messages] == ["integration hello"]
            assert messages[0].read_at is not None

            # PvP: challenge -> accept -> both answers -> terminal match state.
            match = await create_challenge(session, creator.id, "math")
            accepted = await accept_challenge(session, match.id, opponent.id)
            assert accepted.status == "active"

            first = await submit_answer(
                session, match.id, creator.id, match.answer
            )
            assert first[0] == "correct"

            second = await submit_answer(
                session, match.id, opponent.id, match.answer
            )
            assert second[0] == "finished"
            assert second[1].status == "draw"

            # The old social tables must not exist after the current migration head.
            social_table = (
                await session.execute(
                    text(
                        "SELECT to_regclass('public.friendships'), "
                        "to_regclass('public.friend_requests')"
                    )
                )
            ).one()
            assert social_table == (None, None)

    finally:
        async with Session() as session:
            if creator.id is not None:
                await session.execute(delete(User).where(User.id.in_([creator.id, opponent.id])))
                await session.commit()
        await engine.dispose()


def test_postgresql_integration() -> None:
    asyncio.run(_scenario())
