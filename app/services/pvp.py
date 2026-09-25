from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PvpMatch, User


PVP_KINDS = {
    "math": "🧮 Математика",
    "sequence": "🔢 Последовательность",
    "quiz": "🏆 Викторина",
}


@dataclass
class PvpRound:
    kind: str
    prompt: str
    answer: str


def _make_round(kind: str) -> PvpRound:
    if kind == "math":
        a, b, c = random.randint(10, 40), random.randint(3, 15), random.randint(2, 9)
        return PvpRound(kind, f"🧮 Решите: <b>{a} × {b} + {c}</b>", str(a * b + c))
    if kind == "sequence":
        start, step = random.randint(1, 10), random.randint(2, 7)
        seq = [start + step * i for i in range(4)]
        return PvpRound(kind, f"🔢 Продолжите: <b>{', '.join(map(str, seq))}, ?</b>", str(seq[-1] + step))
    questions = [
        ("Какая планета ближе всего к Солнцу?", "меркурий"),
        ("Сколько сторон у правильного шестиугольника?", "6"),
        ("Какой океан самый большой?", "тихий"),
        ("Сколько байт в одном килобайте по классическому двоичному исчислению?", "1024"),
    ]
    question, answer = random.choice(questions)
    return PvpRound("quiz", f"🏆 <b>{question}</b>", answer)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_challenge(session: AsyncSession, creator_id: int, kind: str) -> PvpMatch:
    if kind not in PVP_KINDS:
        raise ValueError("unknown pvp kind")
    active = await get_active_match(session, creator_id)
    if active:
        raise ValueError("active_match")
    round_ = _make_round(kind)
    match = PvpMatch(
        creator_id=creator_id,
        opponent_id=None,
        kind=kind,
        prompt=round_.prompt,
        answer=round_.answer,
        status="open",
        creator_answer=None,
        opponent_answer=None,
        winner_id=None,
        created_at=_now(),
        expires_at=_now() + timedelta(minutes=5),
    )
    session.add(match)
    await session.flush()
    return match


async def get_active_match(session: AsyncSession, user_id: int) -> PvpMatch | None:
    result = await session.execute(
        select(PvpMatch)
        .where(
            ((PvpMatch.creator_id == user_id) | (PvpMatch.opponent_id == user_id)),
            PvpMatch.status.in_(("open", "active")),
            PvpMatch.expires_at > _now(),
        )
        .order_by(PvpMatch.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_match(session: AsyncSession, match_id: int) -> PvpMatch | None:
    return await session.get(PvpMatch, match_id)


async def accept_challenge(session: AsyncSession, match_id: int, opponent_id: int) -> PvpMatch:
    match = await session.get(PvpMatch, match_id)
    if match is None or match.status != "open" or match.expires_at <= _now():
        raise ValueError("unavailable")
    if match.creator_id == opponent_id:
        raise ValueError("self")
    if await get_active_match(session, opponent_id):
        raise ValueError("active_match")
    match.opponent_id = opponent_id
    match.status = "active"
    return match


async def decline_challenge(session: AsyncSession, match_id: int, user_id: int) -> PvpMatch:
    match = await session.get(PvpMatch, match_id)
    if match is None or match.status != "open":
        raise ValueError("unavailable")
    if match.creator_id == user_id:
        raise ValueError("creator")
    match.status = "declined"
    return match


async def submit_answer(session: AsyncSession, match_id: int, user_id: int, value: str) -> tuple[str, PvpMatch]:
    match = await session.get(PvpMatch, match_id)
    if match is None or match.status != "active" or match.opponent_id is None:
        return "unavailable", match
    if match.expires_at <= _now():
        match.status = "expired"
        return "expired", match
    if user_id not in (match.creator_id, match.opponent_id):
        return "forbidden", match
    if user_id == match.creator_id and match.creator_answer is not None:
        return "already", match
    if user_id == match.opponent_id and match.opponent_answer is not None:
        return "already", match

    correct = value.strip().lower() == match.answer.strip().lower()
    if user_id == match.creator_id:
        match.creator_answer = correct
    else:
        match.opponent_answer = correct

    if match.creator_answer is not None and match.opponent_answer is not None:
        if match.creator_answer and not match.opponent_answer:
            match.winner_id = match.creator_id
            match.status = "finished"
        elif match.opponent_answer and not match.creator_answer:
            match.winner_id = match.opponent_id
            match.status = "finished"
        else:
            match.status = "draw"
        return "finished", match

    return ("correct" if correct else "wrong"), match


async def get_display_name(session: AsyncSession, user_id: int) -> str:
    user = await session.get(User, user_id)
    if user is None:
        return f"ID {user_id}"
    return f"@{user.username}" if user.username else user.first_name
