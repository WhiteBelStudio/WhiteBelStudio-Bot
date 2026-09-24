from app.services.reputation import _pair


def test_reputation_pair_is_stable() -> None:
    assert _pair(3, 8) == (3, 8)
    assert _pair(8, 3) == (3, 8)
