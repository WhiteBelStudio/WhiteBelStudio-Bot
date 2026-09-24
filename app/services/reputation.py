from __future__ import annotations

from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReputationRating, User


async def get_reputation(session: AsyncSession, user_id: int) -> dict[str, object]:
    result = await session.execute(
        select(
            func.count(ReputationRating.id),
            func.coalesce(func.avg(ReputationRating.score), 0),
        ).where(ReputationRating.rated_id == user_id)
    )
    count, average = result.one()

    return {
        "count": int(count or 0),
        "average": float(average or 0),
    }


def format_reputation(data: dict[str, object], name: str) -> str:
    return (
        f"⭐ <b>Репутация {escape(name)}</b>\n"
        f"Оценок: <b>{int(data['count'])}</b>\n"
        f"Средняя оценка: <b>{float(data['average']):.1f}/5</b>"
    )
