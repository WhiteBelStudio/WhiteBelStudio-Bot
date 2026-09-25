from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Achievement, GameProfile, UserAchievement


@dataclass(frozen=True, slots=True)
class AchievementSpec:
    code: str
    name: str
    description: str
    target: int


ACHIEVEMENTS = (
    AchievementSpec("first_game", "🎮 Первый шаг", "Сыграть первую игру", 1),
    AchievementSpec("ten_games", "🎯 Десяточка", "Сыграть 10 игр", 10),
    AchievementSpec("first_win", "🏆 Первая победа", "Одержать первую победу", 1),
    AchievementSpec("ten_wins", "🔥 Победная серия", "Одержать 10 побед", 10),
    AchievementSpec("fifty_wins", "👑 Чемпион", "Одержать 50 побед", 50),
    AchievementSpec("level_5", "⭐ Опытный игрок", "Достичь 5 уровня", 5),
    AchievementSpec("level_10", "💎 Ветеран", "Достичь 10 уровня", 10),
)


async def ensure_achievements(session: AsyncSession) -> None:
    existing = {
        row.code: row
        for row in (await session.execute(select(Achievement))).scalars().all()
    }
    for spec in ACHIEVEMENTS:
        if spec.code not in existing:
            session.add(
                Achievement(
                    code=spec.code,
                    name=spec.name,
                    description=spec.description,
                    target=spec.target,
                    is_active=True,
                )
            )
    await session.flush()


def _unlocked(spec: AchievementSpec, profile: GameProfile) -> bool:
    values = {
        "first_game": profile.games_played,
        "ten_games": profile.games_played,
        "first_win": profile.wins,
        "ten_wins": profile.wins,
        "fifty_wins": profile.wins,
        "level_5": profile.level,
        "level_10": profile.level,
    }
    return values[spec.code] >= spec.target


async def check_and_unlock_achievements(
    session: AsyncSession,
    user_id: int,
) -> list[AchievementSpec]:
    await ensure_achievements(session)
    profile = (
        await session.execute(
            select(GameProfile).where(GameProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        return []

    rows = (
        await session.execute(
            select(Achievement, UserAchievement)
            .outerjoin(
                UserAchievement,
                (UserAchievement.achievement_id == Achievement.id)
                & (UserAchievement.user_id == user_id),
            )
            .where(Achievement.is_active.is_(True))
        )
    ).all()

    unlocked: list[AchievementSpec] = []
    specs = {item.code: item for item in ACHIEVEMENTS}
    for achievement, user_achievement in rows:
        spec = specs.get(achievement.code)
        if spec is None or user_achievement is not None or not _unlocked(spec, profile):
            continue
        session.add(
            UserAchievement(user_id=user_id, achievement_id=achievement.id)
        )
        unlocked.append(spec)

    if unlocked:
        await session.commit()
    return unlocked


async def list_user_achievements(
    session: AsyncSession,
    user_id: int,
) -> tuple[list[AchievementSpec], list[AchievementSpec]]:
    await ensure_achievements(session)
    earned_codes = set(
        (
            await session.execute(
                select(Achievement.code)
                .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
                .where(UserAchievement.user_id == user_id)
            )
        ).scalars().all()
    )
    all_specs = list(ACHIEVEMENTS)
    return (
        [item for item in all_specs if item.code in earned_codes],
        [item for item in all_specs if item.code not in earned_codes],
    )
