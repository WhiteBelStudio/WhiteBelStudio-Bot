from __future__ import annotations

from app.bot.admin import admin_menu_keyboard, is_admin


def test_admin_access_is_owner_only(monkeypatch):
    monkeypatch.setenv("OWNER_ID", "12345")
    assert is_admin(12345)
    assert not is_admin(54321)
    assert not is_admin(None)


def test_admin_access_rejects_invalid_owner_id(monkeypatch):
    monkeypatch.setenv("OWNER_ID", "not-a-number")
    assert not is_admin(12345)


def test_admin_menu_contains_protected_actions(monkeypatch):
    monkeypatch.setenv("OWNER_ID", "12345")
    keyboard = admin_menu_keyboard()
    callbacks = {
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data
    }
    assert {"admin:stats", "admin:health", "admin:user_help", "admin:close"} <= callbacks
