from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GameProfile, User


@dataclass(frozen=True, slots=True)
class GameProfileView:
    user_id: int
    level: int
    experience: int
    experience_to_next: int
    games_played: int
    wins: int
    losses: int
    draws: int


def experience_for_level(level: int) -> int:
    """Total XP required to reach the beginning of a level."""
    safe_level = max(1, level)
    return 100 * (safe_level - 1) * safe_level // 2


def level_from_experience(experience: int) -> int:
    """Return the highest level reached by non-negative XP."""
    xp = max(0, experience)
    level = 1
    while xp >= experience_for_level(level + 1):
        level += 1
    return level


async def get_or_create_game_profile(
    session: AsyncSession,
    user_id: int,
) -> GameProfile:
    result = await session.execute(
        select(GameProfile).where(GameProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if profile is not None:
        return profile

    profile = GameProfile(user_id=user_id)
    session.add(profile)
    await session.flush()
    return profile


def to_game_profile_view(profile: GameProfile) -> GameProfileView:
    level_start = experience_for_level(profile.level)
    next_level = experience_for_level(profile.level + 1)
    return GameProfileView(
        user_id=profile.user_id,
        level=profile.level,
        experience=profile.experience,
        experience_to_next=max(0, next_level - profile.experience),
        games_played=profile.games_played,
        wins=profile.wins,
        losses=profile.losses,
        draws=profile.draws,
    )


async def add_experience(
    session: AsyncSession,
    user_id: int,
    amount: int,
) -> GameProfileView:
    if amount < 0:
        raise ValueError("Experience amount cannot be negative")

    profile = await get_or_create_game_profile(session, user_id)
    profile.experience += amount
    profile.level = level_from_experience(profile.experience)
    await session.commit()
    return to_game_profile_view(profile)


async def record_game_result(
    session: AsyncSession,
    user_id: int,
    *,
    result: str,
    experience: int = 0,
) -> GameProfileView:
    if result not in {"win", "loss", "draw"}:
        raise ValueError("result must be win, loss or draw")
    if experience < 0:
        raise ValueError("Experience amount cannot be negative")

    profile = await get_or_create_game_profile(session, user_id)
    profile.games_played += 1

    if result == "win":
        profile.wins += 1
    elif result == "loss":
        profile.losses += 1
    else:
        profile.draws += 1

    profile.experience += experience
    profile.level = level_from_experience(profile.experience)
    await session.commit()
    return to_game_profile_view(profile)


async def get_game_profile(
    session: AsyncSession,
    user_id: int,
) -> GameProfileView:
    profile = await get_or_create_game_profile(session, user_id)
    await session.commit()
    return to_game_profile_view(profile)


async def get_game_leaderboard(
    session: AsyncSession,
    limit: int = 10,
) -> list[tuple[int, str, int, int]]:
    result = await session.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            GameProfile.level,
            GameProfile.experience,
        )
        .join(GameProfile, GameProfile.user_id == User.id)
        .where(User.is_active.is_(True), User.is_bot.is_(False))
        .order_by(
            GameProfile.level.desc(),
            GameProfile.experience.desc(),
            User.first_name.asc(),
            User.id.asc(),
        )
        .limit(max(1, min(limit, 50)))
    )
    return [
        (
            user_id,
            " ".join(part for part in (first_name, last_name) if part) or "Участник",
            level,
            experience,
        )
        for user_id, first_name, last_name, level, experience in result.all()
    ]
