from types import SimpleNamespace

from app.bot.middleware import is_trackable_community_message


def test_group_message_is_trackable(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup"),
        from_user=SimpleNamespace(is_bot=False),
    )
    assert is_trackable_community_message(message)


def test_private_message_is_not_trackable(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    message = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(is_bot=False),
    )
    assert not is_trackable_community_message(message)


def test_bot_message_is_not_trackable(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    message = SimpleNamespace(
        chat=SimpleNamespace(type="group"),
        from_user=SimpleNamespace(is_bot=True),
    )
    assert not is_trackable_community_message(message)


def test_tracking_disabled_without_database(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    message = SimpleNamespace(
        chat=SimpleNamespace(type="group"),
        from_user=SimpleNamespace(is_bot=False),
    )
    assert not is_trackable_community_message(message)
