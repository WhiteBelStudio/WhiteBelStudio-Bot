from app.services.communication import _pair


def test_conversation_pair_is_stable() -> None:
    assert _pair(2, 9) == (2, 9)
    assert _pair(9, 2) == (2, 9)
