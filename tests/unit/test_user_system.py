from app.db.models import User, UserSettings


def test_user_profile_columns_exist() -> None:
    columns = User.__table__.c

    assert columns.telegram_id.unique is True
    assert columns.is_active.nullable is False
    assert columns.bio.nullable is True
    assert columns.city.nullable is True
    assert columns.last_seen_at.nullable is False


def test_user_settings_model() -> None:
    assert UserSettings.__tablename__ == "user_settings"
    assert UserSettings.__table__.c.user_id.primary_key is True
    assert UserSettings.__table__.c.notifications_enabled.nullable is False
    assert UserSettings.__table__.c.show_profile.nullable is False
