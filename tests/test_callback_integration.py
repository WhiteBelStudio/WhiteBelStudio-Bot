from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from sqlalchemy import delete, select

from app.db.engine import get_session
from app.db.models import User as DbUser
from app.services.pvp import get_active_match
from app.services.users import sync_telegram_user
from main import dp


pytestmark = pytest.mark.integration


def _update(data: str, telegram_id: int) -> Update:
    tg_user = User(
        id=telegram_id,
        is_bot=False,
        first_name=f"Callback {telegram_id}",
        username=f"callback_{telegram_id}",
    )
    message = Message(
        message_id=telegram_id,
        date=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        chat=Chat(id=telegram_id, type="private"),
        from_user=tg_user,
        text="callback",
    )
    return Update(
        update_id=telegram_id,
        callback_query=CallbackQuery(
            id=f"db-callback-{telegram_id}-{data.replace(':', '-')}",
            from_user=tg_user,
            chat_instance="integration",
            message=message,
            data=data,
        ),
    )


async def _session_call(factory):
    async for session in get_session():
        return await factory(session)
    raise AssertionError("database session was not created")


async def _user_id(session, telegram_id: int) -> int:
    user = (
        await session.execute(
            select(DbUser).where(DbUser.telegram_id == telegram_id)
        )
    ).scalar_one()
    return user.id


async def _create_users(session, creator_id: int, opponent_id: int) -> None:
    await sync_telegram_user(
        session,
        User(id=creator_id, is_bot=False, first_name="Creator", username="creator"),
    )
    await sync_telegram_user(
        session,
        User(id=opponent_id, is_bot=False, first_name="Opponent", username="opponent"),
    )


@pytest.mark.asyncio
async def test_pvp_callback_create_and_accept_persist_real_postgresql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123456:INTEGRATION")
    creator_id = 910000301
    opponent_id = 910000302
    bot = Bot("123456:INTEGRATION")

    await _session_call(lambda session: _create_users(session, creator_id, opponent_id))

    try:
        with (
            patch.object(Message, "answer", new=AsyncMock()) as message_answer,
            patch.object(CallbackQuery, "answer", new=AsyncMock()) as callback_answer,
        ):
            await dp.feed_update(bot, _update("pvp:create:math", creator_id))

        assert message_answer.await_count >= 1
        callback_answer.assert_awaited_once()

        async def get_creator_match(session):
            return await get_active_match(session, await _user_id(session, creator_id))

        match = await _session_call(get_creator_match)
        assert match is not None
        assert match.status == "pending"
        match_id = match.id

        with (
            patch.object(Message, "answer", new=AsyncMock()) as message_answer,
            patch.object(CallbackQuery, "answer", new=AsyncMock()) as callback_answer,
        ):
            await dp.feed_update(
                bot,
                _update(f"pvp:accept:{match_id}", opponent_id),
            )

        assert message_answer.await_count >= 1
        callback_answer.assert_awaited_once()

        async def get_opponent_match(session):
            return await get_active_match(session, await _user_id(session, opponent_id))

        match = await _session_call(get_opponent_match)
        assert match is not None
        assert match.id == match_id
        assert match.status == "active"
        assert match.opponent_id == await _user_id_from_session(match, opponent_id)
    finally:
        async for session in get_session():
            await session.execute(
                delete(DbUser).where(
                    DbUser.telegram_id.in_([creator_id, opponent_id])
                )
            )
            await session.commit()
        await bot.session.close()


async def _user_id_from_session(match, telegram_id: int) -> int:
    # Kept async so assertions remain independent of SQLAlchemy session lifetime.
    async for session in get_session():
        return await _user_id(session, telegram_id)
    raise AssertionError("database session was not created")
