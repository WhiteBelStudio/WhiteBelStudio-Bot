from decimal import Decimal

import pytest

from app.services.economy import (
    GAME_REWARD_CAP,
    GAME_REWARD_RESULT_LIMIT,
    calculate_game_reward,
)


def test_game_reward_win() -> None:
    assert calculate_game_reward(
        game_kind="math",
        result="win",
        earned_today=Decimal("0.0"),
        result_count=0,
    ) == Decimal("1.0")


def test_game_reward_respects_daily_coin_cap() -> None:
    assert calculate_game_reward(
        game_kind="algorithm",
        result="win",
        earned_today=GAME_REWARD_CAP - Decimal("0.5"),
        result_count=3,
    ) == Decimal("0.5")


def test_game_reward_stops_after_result_limit() -> None:
    assert calculate_game_reward(
        game_kind="math",
        result="win",
        earned_today=Decimal("0.0"),
        result_count=GAME_REWARD_RESULT_LIMIT,
    ) == Decimal("0.0")


def test_game_reward_unknown_game_uses_safe_base_reward() -> None:
    assert calculate_game_reward(
        game_kind="unknown",
        result="win",
        earned_today=Decimal("0.0"),
        result_count=0,
    ) == Decimal("1.0")


def test_game_reward_rejects_invalid_result() -> None:
    with pytest.raises(ValueError):
        calculate_game_reward(
            game_kind="math",
            result="invalid",
            earned_today=Decimal("0.0"),
            result_count=0,
        )
