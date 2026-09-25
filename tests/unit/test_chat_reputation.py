from types import SimpleNamespace

from app.bot.middleware import _command_args


def test_reputation_command_parsing() -> None:
    message = SimpleNamespace(text="/rep+ @alice")
    assert _command_args(message) == ("/rep+", ["@alice"])


def test_reputation_command_with_bot_username() -> None:
    message = SimpleNamespace(text="/toprep@WhiteBelStudioBot")
    assert _command_args(message) == ("/toprep", [])
