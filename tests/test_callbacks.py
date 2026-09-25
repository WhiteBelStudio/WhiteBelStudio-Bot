from __future__ import annotations

import asyncio

from app.bot import economy, games
import main


class FakeMessage:
    def __init__(self):
        self.edits = []
        self.answers = []

    async def edit_text(self, text, reply_markup=None):
        self.edits.append((text, reply_markup))

    async def answer(self, text, reply_markup=None):
        self.answers.append((text, reply_markup))


class FakeCallback:
    def __init__(self, data, user_id=123):
        self.data = data
        self.message = FakeMessage()
        self.from_user = type("User", (), {"id": user_id})()
        self.answered = []

    async def answer(self, text=None, **kwargs):
        self.answered.append((text, kwargs))


def run(coro):
    return asyncio.run(coro)


def test_help_callbacks_round_trip():
    categories = FakeCallback("help_categories")
    run(main.help_categories_callback(categories))
    assert categories.answered == [(None, {})]
    assert categories.message.edits
    assert "Помощь WhiteBelStudio" in categories.message.edits[-1][0]

    category = FakeCallback("help_category:game")
    run(main.help_category_callback(category))
    assert category.answered == [(None, {})]
    assert "Игровые команды" in category.message.edits[-1][0]


def test_games_callbacks_round_trip():
    for data, marker in (
        ("games", "Выбери режим"),
        ("games:mini", "Мини-игры"),
        ("games:pvp", "PvP"),
    ):
        callback = FakeCallback(data)
        handler = {
            "games": games.games_callback,
            "games:mini": games.mini_callback,
            "games:pvp": games.pvp_menu_callback,
        }[data]
        run(handler(callback))
        assert callback.answered == [(None, {})]
        assert callback.message.edits
        assert marker in callback.message.edits[-1][0]


def test_shop_callback_routes_to_shop(monkeypatch):
    calls = []

    async def fake_show_shop(message, category=None, *, edit=False):
        calls.append((message, category, edit))

    monkeypatch.setattr(economy, "show_shop", fake_show_shop)
    callback = FakeCallback("shop")
    run(economy.shop_callback(callback))
    assert calls == [(callback.message, None, True)]
    assert callback.answered == [(None, {})]


def test_game_start_callback_routes_to_requested_kind(monkeypatch):
    calls = []

    async def fake_start(message, kind):
        calls.append((message, kind))

    monkeypatch.setattr(games, "start_mini_game", fake_start)
    callback = FakeCallback("game:start:quiz")
    run(games.game_start_callback(callback))
    assert calls == [(callback.message, "quiz")]
    assert callback.answered == [(None, {})]


def test_callback_namespaces_have_no_retired_social_actions():
    source = open("main.py", encoding="utf-8").read()
    assert 'callback_data="help_category:social"' not in source
    assert 'callback_data="friends"' not in source
    assert 'callback_data="find"' not in source
    assert 'Command("find")' not in source
    assert 'Command("friends")' not in source
