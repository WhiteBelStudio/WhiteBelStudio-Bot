from app.services.social import _pair


def test_pair_is_order_independent() -> None:
    assert _pair(20, 5) == (5, 20)
    assert _pair(5, 20) == (5, 20)
    assert _pair(7, 7) == (7, 7)
