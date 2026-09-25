from app.services.games import experience_for_level, level_from_experience


def test_experience_curve() -> None:
    assert experience_for_level(1) == 0
    assert experience_for_level(2) == 100
    assert experience_for_level(3) == 300


def test_level_from_experience() -> None:
    assert level_from_experience(0) == 1
    assert level_from_experience(99) == 1
    assert level_from_experience(100) == 2
    assert level_from_experience(299) == 2
    assert level_from_experience(300) == 3
