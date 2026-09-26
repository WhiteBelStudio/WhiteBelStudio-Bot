from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from app.bot.economy import router as economy_router
from app.bot.games import router as games_router
from main import dp


pytestmark = pytest.mark.asyncio


def _callback(data: str, *, telegram_id: int = 910000201) -> CallbackQuery:
    user = User(
        id=telegram_id,
        is_bot=False,
        first_name="Callback",
        username="callback_e2e",
    )
    chat = Chat(id=telegram_id, type="private")
    message = Message(
        message_id=100,
        date=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        chat=chat,
        from_user=user,
        text="callback",
    )
    return CallbackQuery(
        id=f"callback-{telegram_id}-{abs(hash(data))}",
        from_user=user,
        chat_instance="integration",
        message=message,
        data=data,
    )


async def _feed(data: str, *, telegram_id: int = 910000201) -> CallbackQuery:
    callback = _callback(data, telegram_id=telegram_id)
    update = Update(
        update_id=910000000 + telegram_id % 1000,
        callback_query=callback,
    )
    bot = Bot("123456:TEST")
    try:
        await dp.feed_update(bot, update)
    finally:
        await bot.session.close()
    return callback


async def test_menu_callbacks_are_dispatched_end_to_end() -> None:
    with (
        patch("app.bot.core.profile_handler", new=AsyncMock()) as profile,
        patch("app.bot.core.rep_handler", new=AsyncMock()) as reputation,
        patch("app.bot.core.rules_handler", new=AsyncMock()) as rules,
        patch("app.bot.economy.show_shop", new=AsyncMock()) as shop,
        patch("app.bot.core.show_help_categories", new=AsyncMock()) as help_menu,
        patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer,
    ):
        callbacks = await _feed("menu_profile")
        await _feed("menu_reputation")
        await _feed("menu_rules")
        await _feed("shop")
        await _feed("menu_help")

    assert profile.await_count == 1
    assert reputation.await_count == 1
    assert rules.await_count == 1
    assert shop.await_count == 1
    assert help_menu.await_count == 1
    assert answer.await_count == 5


@pytest.mark.parametrize(
    "data, expected_category",
    [
        ("help_category:general", "general"),
        ("help_category:game", "game"),
        ("help_category:moderation", "moderation"),
    ],
)
async def test_help_callbacks_are_dispatched_end_to_end(
    data: str,
    expected_category: str,
) -> None:
    with (
        patch("app.bot.core.show_help_category", new=AsyncMock()) as handler,
        patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer,
    ):
        await _feed(data)

    handler.assert_awaited_once()
    assert handler.await_args.args[1] == expected_category
    answer.assert_awaited_once()


async def test_help_back_callback_is_dispatched_end_to_end() -> None:
    with (
        patch("app.bot.core.show_help_categories", new=AsyncMock()) as handler,
        patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer,
    ):
        await _feed("help_categories")

    handler.assert_awaited_once()
    answer.assert_awaited_once()


@pytest.mark.parametrize(
    "data, target",
    [
        ("games", "games"),
        ("games:mini", "mini"),
        ("games:pvp", "pvp"),
    ],
)
async def test_game_navigation_callbacks_are_dispatched_end_to_end(
    data: str,
    target: str,
) -> None:
    targets = {
        "games": ("app.bot.games.show_games", True),
        "mini": ("app.bot.games.show_mini_games", True),
        "pvp": ("app.bot.games.show_pvp_category", True),
    }
    patch_target, _ = targets[target]
    with (
        patch(patch_target, new=AsyncMock()) as handler,
        patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer,
    ):
        await _feed(data)

    handler.assert_awaited_once()
    assert handler.await_args.kwargs["edit"] is True
    answer.assert_awaited_once()


@pytest.mark.parametrize(
    "data, kind",
    [
        ("game:start:math", "math"),
        ("game:start:code", "code"),
        ("game:start:word", "word"),
        ("game:start:sequence", "sequence"),
        ("game:start:logic", "logic"),
        ("game:start:anagram", "anagram"),
        ("game:start:tower", "tower"),
        ("game:start:algorithm", "algorithm"),
        ("game:start:counter", "counter"),
        ("game:start:space", "space"),
        ("game:start:quiz", "quiz"),
        ("game:start:chain", "chain"),
    ],
)
async def test_every_mini_game_callback_reaches_handler(data: str, kind: str) -> None:
    with (
        patch("app.bot.games.start_mini_game", new=AsyncMock()) as handler,
        patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer,
    ):
        await _feed(data)

    handler.assert_awaited_once()
    assert handler.await_args.args[1] == kind
    answer.assert_awaited_once()


@pytest.mark.parametrize(
    "data, kind",
    [
        ("pvp:create:math", "math"),
        ("pvp:create:sequence", "sequence"),
        ("pvp:create:quiz", "quiz"),
    ],
)
async def test_every_pvp_create_callback_reaches_handler(data: str, kind: str) -> None:
    with (
        patch("app.bot.games.send_pvp_challenge", new=AsyncMock()) as handler,
        patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer,
    ):
        await _feed(data)

    handler.assert_awaited_once()
    assert handler.await_args.args[1] == kind
    answer.assert_awaited_once()


@pytest.mark.parametrize(
    "data",
    ["pvp:accept:42", "pvp:decline:42"],
)
async def test_pvp_action_callbacks_reach_handler(data: str) -> None:
    with (
        patch("app.bot.games.pvp_callback", new=AsyncMock()) as handler,
        patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer,
    ):
        await _feed(data)

    handler.assert_awaited_once()
    assert handler.await_args.args[1] == data
    answer.assert_awaited_once()


@pytest.mark.parametrize(
    "data, target",
    [
        ("shop", "shop"),
        ("shop_cat:title", "category"),
        ("shop_cat:boost", "category"),
        ("shop_cat:gift", "category"),
        ("shop_cat:exclusive", "category"),
    ],
)
async def test_shop_navigation_callbacks_are_dispatched_end_to_end(
    data: str,
    target: str,
) -> None:
    with (
        patch("app.bot.economy.show_shop", new=AsyncMock()) as handler,
        patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer,
    ):
        await _feed(data)

    handler.assert_awaited_once()
    if target == "shop":
        assert handler.await_args.args[0] is not None
    else:
        assert handler.await_args.args[1] == data.split(":", 1)[1]
    assert handler.await_args.kwargs["edit"] is True
    answer.assert_awaited_once()


async def test_shop_buy_callback_handles_invalid_payload_without_crashing() -> None:
    with patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer:
        callback = await _feed("shop_buy:not-an-id")

    answer.assert_awaited_once()
    assert answer.await_args.kwargs["show_alert"] is True
    assert callback.data == "shop_buy:not-an-id"


async def test_unknown_callback_is_not_reported_as_handled() -> None:
    with patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer:
        callback = await _feed("unknown:callback")

    answer.assert_not_awaited()
    assert callback.data == "unknown:callback"


async def test_callback_with_missing_message_does_not_crash() -> None:
    user = User(id=910000202, is_bot=False, first_name="Callback")
    callback = CallbackQuery(
        id="callback-no-message",
        from_user=user,
        chat_instance="integration",
        message=None,
        data="menu_help",
    )
    update = Update(update_id=910000202, callback_query=callback)
    bot = Bot("123456:TEST")

    with patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer:
        try:
            await dp.feed_update(bot, update)
        finally:
            await bot.session.close()

    answer.assert_awaited_once()
