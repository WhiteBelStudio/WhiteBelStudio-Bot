from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, User


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


async def get_reputation_score(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(ReputationEvent.delta), 0))
        .where(ReputationEvent.user_id == user_id)
    )
    return int(result.scalar_one() or 0)


async def add_reputation_event(
    session: AsyncSession,
    user_id: int,
    delta: int,
    reason: str,
    actor_id: int | None = None,
) -> int:
    session.add(
        ReputationEvent(
            user_id=user_id,
            actor_id=actor_id,
            delta=delta,
            reason=reason[:128],
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
        .order_by(ReputationEvent.created_at.desc())
        .limit(max(1, min(limit, 50)))
    )
    return list(result.scalars().all())


def format_community_reputation(name: str, score: int, history: list[ReputationEvent]) -> str:
    lines = [
        f"⭐ <b>Репутация {name}</b>",
        f"Баланс: <b>{score}</b>",
    ]
    if history:
        lines.extend(["", "Последние изменения:"])
        for event in history:
            sign = "+" if event.delta > 0 else ""
            lines.append(f"• {sign}{event.delta} — {event.reason}")
    return "\n".join(lines)
