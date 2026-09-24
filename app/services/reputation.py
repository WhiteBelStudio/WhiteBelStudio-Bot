from __future__ import annotations

from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Friendship, ReputationRating, User


def _pair(left_id: int, right_id: int) -> tuple[int, int]:
    return (left_id, right_id) if left_id < right_id else (right_id, left_id)


async def _are_friends(session: AsyncSession, left_id: int, right_id: int) -> bool:
    low, high = _pair(left_id, right_id)
    result = await session.execute(
        select(Friendship.id).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
        )
    )
    return result.scalar_one_or_none() is not None


async def rate_user(
    session: AsyncSession,
    rater_id: int,
    rated_id: int,
    score: int,
    comment: str | None = None,
) -> str:
    if rater_id == rated_id:
        return "self"
    if score < 1 or score > 5:
        return "invalid_score"
    if not await _are_friends(session, rater_id, rated_id):
        return "not_friends"

    rated = await session.get(User, rated_id)
    if rated is None or not rated.is_active or rated.is_bot:
        return "unavailable"

    normalized_comment = (comment or "").strip()
    if len(normalized_comment) > 500:
        return "comment_too_long"

    result = await session.execute(
        select(ReputationRating).where(
            ReputationRating.rater_id == rater_id,
            ReputationRating.rated_id == rated_id,
        )
    )
    rating = result.scalar_one_or_none()

    if rating is None:
        rating = ReputationRating(
            rater_id=rater_id,
            rated_id=rated_id,
            score=score,
            comment=normalized_comment or None,
        )
        session.add(rating)
        status = "created"
    else:
        rating.score = score
        rating.comment = normalized_comment or None
        status = "updated"

    await session.commit()
    return status


async def get_reputation(session: AsyncSession, user_id: int) -> dict[str, object]:
    result = await session.execute(
        select(
            func.count(ReputationRating.id),
            func.coalesce(func.avg(ReputationRating.score), 0),
        ).where(ReputationRating.rated_id == user_id)
    )
    count, average = result.one()

    reviews = await session.execute(
        select(ReputationRating, User)
        .join(User, User.id == ReputationRating.rater_id)
        .where(ReputationRating.rated_id == user_id)
        .order_by(ReputationRating.updated_at.desc())
        .limit(10)
    )

    return {
        "count": int(count or 0),
        "average": float(average or 0),
        "reviews": list(reviews.all()),
    }


def format_reputation(data: dict[str, object], name: str) -> str:
    count = int(data["count"])
    average = float(data["average"])
    reviews = data["reviews"]

    safe_name = escape(name)
    lines = [
        f"⭐ <b>Репутация {safe_name}</b>",
        f"Оценок: <b>{count}</b>",
        f"Средняя оценка: <b>{average:.1f}/5</b>",
    ]

    if reviews:
        lines.append("")
        lines.append("Последние оценки:")
        for rating, user in reviews:
            username = f"@{escape(user.username)}" if user.username else "без username"
            comment = f" — {escape(rating.comment)}" if rating.comment else ""
            lines.append(f"⭐ {rating.score}/5 — {username}{comment}")

    return "
".join(lines)
