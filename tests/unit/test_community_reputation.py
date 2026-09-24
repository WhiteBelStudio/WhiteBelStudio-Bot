from app.services.community import reputation_level


def test_reputation_levels() -> None:
    assert reputation_level(-1)[0] == "Под наблюдением"
    assert reputation_level(0)[0] == "Новичок"
    assert reputation_level(10)[0] == "Участник"
    assert reputation_level(25)[0] == "Активный участник"
    assert reputation_level(50)[0] == "Авторитет"
    assert reputation_level(100)[0] == "Легенда"


def test_reputation_next_thresholds() -> None:
    assert reputation_level(0)[1] == 10
    assert reputation_level(10)[1] == 25
    assert reputation_level(25)[1] == 50
    assert reputation_level(50)[1] == 100
    assert reputation_level(100)[1] == 100
