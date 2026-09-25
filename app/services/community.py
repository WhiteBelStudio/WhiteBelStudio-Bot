from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, CommunityChat, CommunityReputationVote, ReputationEvent, User


async def get_chat_by_telegram_id(session: AsyncSession, telegram_chat_id: int) -> CommunityChat | None:
    result = await session.execute(
        select(CommunityChat).where(CommunityChat.telegram_chat_id == telegram_chat_id)
    )
    return result.scalar_one_or_none()


async def get_reputation_score(session: AsyncSession, user_id: int, chat_id: int | None = None) -> int:
    query = select(func.coalesce(func.sum(ReputationEvent.delta), 0)).where(
        ReputationEvent.user_id == user_id
    )
    if chat_id is not None:
        query = query.where(ReputationEvent.chat_id == chat_id)
    result = await session.execute(query)
    return int(result.scalar_one() or 0)


async def add_reputation_event(
    session: AsyncSession,
    user_id: int,
    delta: int,
    reason: str,
    actor_id: int | None = None,
    chat_id: int | None = None,
) -> int:
    if delta == 0:
        return await get_reputation_score(session, user_id, chat_id)
    if not reason.strip():
        raise ValueError("Reputation event reason cannot be empty")
    session.add(
        ReputationEvent(
            chat_id=chat_id,
            user_id=user_id,
            actor_id=actor_id,
            delta=delta,
            reason=reason.strip()[:128],
        )
    )
    await session.commit()
    return await get_reputation_score(session, user_id, chat_id)


async def set_chat_reputation_vote(
    session: AsyncSession,
    chat_id: int,
    rater_id: int,
    rated_id: int,
    score: int,
) -> tuple[bool, int]:
    """Set a per-chat +1/-1 vote. Returns (changed, new reputation)."""
    if rater_id == rated_id:
        return False, await get_reputation_score(session, rated_id, chat_id)
    if score not in (-1, 1):
        raise ValueError("score must be -1 or 1")

    result = await session.execute(
        select(CommunityReputationVote).where(
            CommunityReputationVote.chat_id == chat_id,
            CommunityReputationVote.rater_id == rater_id,
            CommunityReputationVote.rated_id == rated_id,
        )
    )
    vote = result.scalar_one_or_none()
    if vote is not None and vote.score == score:
        return False, await get_reputation_score(session, rated_id, chat_id)

    old_score = vote.score if vote is not None else 0
    if vote is None:
        vote = CommunityReputationVote(
            chat_id=chat_id,
            rater_id=rater_id,
            rated_id=rated_id,
            score=score,
        )
        session.add(vote)
    else:
        vote.score = score
        vote.updated_at = datetime.utcnow()

    delta = score - old_score
    session.add(
        ReputationEvent(
            chat_id=chat_id,
            user_id=rated_id,
            actor_id=rater_id,
            delta=delta,
            reason="Положительная оценка участника" if score > 0 else "Отрицательная оценка участника",
        )
    )
    await session.commit()
    return True, await get_reputation_score(session, rated_id, chat_id)


async def get_reputation_history(
    session: AsyncSession,
    user_id: int,
    limit: int = 10,
    chat_id: int | None = None,
) -> list[ReputationEvent]:
    query = select(ReputationEvent).where(ReputationEvent.user_id == user_id)
    if chat_id is not None:
        query = query.where(ReputationEvent.chat_id == chat_id)
    result = await session.execute(
        query.order_by(ReputationEvent.created_at.desc(), ReputationEvent.id.desc()).limit(max(1, min(limit, 50)))
    )
    return list(result.scalars().all())


async def get_reputation_top(
    session: AsyncSession,
    limit: int = 10,
    chat_id: int | None = None,
) -> list[tuple[int, str, int]]:
    query = select(
        User.id,
        User.first_name,
        User.last_name,
        func.coalesce(func.sum(ReputationEvent.delta), 0).label("score"),
    ).join(ReputationEvent, ReputationEvent.user_id == User.id).where(
        User.is_active.is_(True), User.is_bot.is_(False)
    )
    if chat_id is not None:
        query = query.where(ReputationEvent.chat_id == chat_id)
    result = await session.execute(
        query.group_by(User.id, User.first_name, User.last_name)
        .order_by(func.sum(ReputationEvent.delta).desc(), User.first_name.asc(), User.id.asc())
        .limit(max(1, min(limit, 50)))
    )
    return [
        (user_id, " ".join(part for part in (first_name, last_name) if part) or "Участник", int(score))
        for user_id, first_name, last_name, score in result.all()
    ]


def reputation_level(score: int) -> tuple[str, int]:
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


def format_community_reputation(name: str, score: int, history: list[ReputationEvent]) -> str:
    level, next_threshold = reputation_level(score)
    lines = [f"⭐ <b>Репутация {name}</b>", f"Баланс: <b>{score}</b>", f"Уровень: <b>{level}</b>"]
    if next_threshold > score:
        lines.append(f"До следующего уровня: <b>{next_threshold - score}</b>")
    if history:
        lines.extend(["", "Последние изменения:"])
        for event in history:
            sign = "+" if event.delta > 0 else ""
            lines.append(f"• {sign}{event.delta} — {event.reason}")
    return "\n".join(lines)
