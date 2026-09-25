from app.bot.games import (
    games_keyboard,
    regular_games_keyboard,
    pvp_games_keyboard,
    pvp_challenge_keyboard,
)
from app.services.minigames import start_game
from app.services.pvp import PVP_KINDS


def _callback_data(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_unified_games_menu_has_pvp_and_minigames():
    assert _callback_data(games_keyboard()) == ["games:pvp", "games:mini"]


def test_all_mini_game_buttons_use_unified_namespace():
    data = _callback_data(regular_games_keyboard())
    starts = [value for value in data if value and value.startswith("game:start:")]
    assert len(starts) == 12
    assert "games:mini" not in data
    assert data[-1] == "games"


def test_all_pvp_modes_are_exposed():
    data = _callback_data(pvp_games_keyboard())
    assert {value.rsplit(":", 1)[-1] for value in data if value and value.startswith("pvp:create:")} == set(PVP_KINDS)
    assert data[-1] == "games"


def test_pvp_challenge_actions_use_unified_namespace():
    data = _callback_data(pvp_challenge_keyboard(42))
    assert data == ["pvp:accept:42", "pvp:decline:42"]


def test_all_mini_game_kinds_start():
    kinds = ["math", "code", "word", "sequence", "logic", "anagram", "tower", "algorithm", "counter", "space", "quiz", "chain"]
    for index, kind in enumerate(kinds, start=1):
        game = start_game(900000 + index, kind)
        assert game.kind == kind
        assert game.attempts_left > 0
