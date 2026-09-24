from app.db.models import User


def test_user_table_definition() -> None:
    assert User.__tablename__ == "users"
    assert User.__table__.c.telegram_id.unique is True
    assert User.__table__.c.telegram_id.nullable is False
    assert User.__table__.c.first_name.nullable is False
