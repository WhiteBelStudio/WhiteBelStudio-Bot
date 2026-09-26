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


async def _create_users(session, creator_id: int, opponent_id: int) -> tuple[int, int]:
    creator, _ = await sync_telegram_user(
        session,
        User(id=creator_id, is_bot=False, first_name="Creator", username="creator"),
    )
    opponent, _ = await sync_telegram_user(
        session,
        User(id=opponent_id, is_bot=False, first_name="Opponent", username="opponent"),
    )
    return creator.id, opponent.id


@pytest.mark.asyncio
async def test_pvp_callback_create_and_accept_persist_real_postgresql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123456:INTEGRATION")
    creator_tg_id = 910000301
    opponent_tg_id = 910000302
    bot = Bot("123456:INTEGRATION")

    creator_id, opponent_id = await _session_call(
        lambda session: _create_users(session, creator_tg_id, opponent_tg_id)
    )

    try:
        with (
            patch.object(Message, "answer", new=AsyncMock()) as message_answer,
            patch.object(CallbackQuery, "answer", new=AsyncMock()) as callback_answer,
        ):
            await dp.feed_update(bot, _update("pvp:create:math", creator_tg_id))

        assert message_answer.await_count >= 1
        callback_answer.assert_awaited_once()

        match = await _session_call(
            lambda session: get_active_match(session, creator_id)
        )
        assert match is not None
        assert match.creator_id == creator_id
        assert match.status == "open"
        match_id = match.id

        with (
            patch.object(Message, "answer", new=AsyncMock()) as message_answer,
            patch.object(CallbackQuery, "answer", new=AsyncMock()) as callback_answer,
        ):
            await dp.feed_update(
                bot,
                _update(f"pvp:accept:{match_id}", opponent_tg_id),
            )

        assert message_answer.await_count >= 1
        callback_answer.assert_awaited_once()

        match = await _session_call(
            lambda session: get_active_match(session, opponent_id)
        )
        assert match is not None
        assert match.id == match_id
        assert match.status == "active"
        assert match.opponent_id == opponent_id
    finally:
        async for session in get_session():
            await session.execute(
                delete(DbUser).where(
                    DbUser.telegram_id.in_([creator_tg_id, opponent_tg_id])
                )
            )
            await session.commit()
        await bot.session.close()
