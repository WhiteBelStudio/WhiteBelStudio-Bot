from app.services.achievements import ACHIEVEMENTS, AchievementSpec, _unlocked


def test_catalog_has_exactly_100_unique_codes():
    assert len(ACHIEVEMENTS) == 100
    assert len({item.code for item in ACHIEVEMENTS}) == 100


def test_original_seven_are_preserved():
    assert {
        "first_game",
        "ten_games",
        "first_win",
        "ten_wins",
        "fifty_wins",
        "level_5",
        "level_10",
    }.issubset({item.code for item in ACHIEVEMENTS})


def test_xp_progression_is_present():
    codes = {item.code for item in ACHIEVEMENTS}
    assert {"xp_100", "xp_1000", "xp_10000", "xp_100000"} <= codes


def test_basic_metric_condition():
    spec = AchievementSpec("test", "test", "test", 10, "wins")
    assert _unlocked(spec, {"wins": 10})
    assert not _unlocked(spec, {"wins": 9})


def test_combined_conditions():
    spec = AchievementSpec("test", "test", "test", 3, "multi_games_wins")
    assert _unlocked(spec, {"games": 3, "wins": 1})
    assert not _unlocked(spec, {"games": 3, "wins": 0})
