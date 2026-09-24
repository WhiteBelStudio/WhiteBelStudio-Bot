from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class ReputationEvent(Base):
    """Immutable community reputation event.

    Reputation is changed by explicit community/moderation actions.
    Ordinary message activity does not grant reputation automatically.
    """

    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


async def get_reputation_score(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(ReputationEvent.delta), 0)).where(
            ReputationEvent.user_id == user_id
        )
    )
    return int(result.scalar_one() or 0)


async def add_reputation_event(
    session: AsyncSession,
    user_id: int,
    delta: int,
    reason: str,
    actor_id: int | None = None,
) -> int:
    """Add one explicit reputation event and return the new balance."""

    if delta == 0:
        return await get_reputation_score(session, user_id)

    if not reason.strip():
        raise ValueError("Reputation event reason cannot be empty")

    session.add(
        ReputationEvent(
            user_id=user_id,
            actor_id=actor_id,
            delta=delta,
            reason=reason.strip()[:128],
        )
    )
    await session.commit()
    return await get_reputation_score(session, user_id)


async def get_reputation_history(
    session: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[ReputationEvent]:
    result = await session.execute(
        select(ReputationEvent)
        .where(ReputationEvent.user_id == user_id)
        .order_by(ReputationEvent.created_at.desc(), ReputationEvent.id.desc())
        .limit(max(1, min(limit, 50)))
    )
    return list(result.scalars().all())


async def get_reputation_top(
    session: AsyncSession,
    limit: int = 10,
) -> list[tuple[int, str, int]]:
    """Return (user_id, display_name, score), highest score first."""

    from app.db.models import User

    result = await session.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            func.coalesce(func.sum(ReputationEvent.delta), 0).label("score"),
        )
        .join(ReputationEvent, ReputationEvent.user_id == User.id)
        .where(User.is_active.is_(True), User.is_bot.is_(False))
        .group_by(User.id, User.first_name, User.last_name)
        .order_by(func.sum(ReputationEvent.delta).desc(), User.first_name.asc(), User.id.asc())
        .limit(max(1, min(limit, 50)))
    )

    rows = []
    for user_id, first_name, last_name, score in result.all():
        name = " ".join(part for part in (first_name, last_name) if part)
        rows.append((user_id, name or "Участник", int(score)))
    return rows


def reputation_level(score: int) -> tuple[str, int]:
    """Return a descriptive community level and the next threshold."""

    if score >= 100:
        return "Легенда", 100
    if score >= 50:
        return "Авторитет", 100
    if score >= 25:
        return "Активный участник", 50
    if score >= 10:
        return "Участник", 25
    if score >= 0:
        return "Новичок", 10
    return "Под наблюдением", 0


def format_community_reputation(
    name: str,
    score: int,
    history: list[ReputationEvent],
) -> str:
    level, next_threshold = reputation_level(score)
    lines = [
        f"⭐ <b>Репутация {name}</b>",
        f"Баланс: <b>{score}</b>",
        f"Уровень: <b>{level}</b>",
    ]

    if next_threshold > score:
        lines.append(f"До следующего уровня: <b>{next_threshold - score}</b>")

    if history:
        lines.extend(["", "Последние изменения:"])
        for event in history:
            sign = "+" if event.delta > 0 else ""
            lines.append(f"• {sign}{event.delta} — {event.reason}")

    return "\n".join(lines)
