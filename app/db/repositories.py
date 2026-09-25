from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserSettings


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    first_name: str,
    username: str | None = None,
    last_name: str | None = None,
    language_code: str | None = None,
    is_bot: bool = False,
) -> User:
    user = User(
        telegram_id=telegram_id,
        first_name=first_name,
        username=username,
        last_name=last_name,
        language_code=language_code,
        is_bot=is_bot,
    )
    session.add(user)
    await session.flush()

    settings = UserSettings(
        user_id=user.id,
        language=(language_code or "ru")[:16],
    )
    session.add(settings)

    await session.commit()
    await session.refresh(user)
    return user


async def sync_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    first_name: str,
    username: str | None = None,
    last_name: str | None = None,
    language_code: str | None = None,
    is_bot: bool = False,
) -> tuple[User, bool]:
    user = await get_user_by_telegram_id(session, telegram_id)

    if user is None:
        return await create_user(
            session,
            telegram_id=telegram_id,
            first_name=first_name,
            username=username,
            last_name=last_name,
            language_code=language_code,
            is_bot=is_bot,
        ), True

    user.first_name = first_name
    user.last_name = last_name
    user.username = username
    user.language_code = language_code
    user.is_bot = is_bot
    user.is_active = True
    user.last_seen_at = datetime.now(timezone.utc)

    if user.settings is None:
        user.settings = UserSettings(
            user_id=user.id,
            language=(language_code or "ru")[:16],
        )

    await session.commit()
    await session.refresh(user)
    return user, False


async def get_user_settings(session: AsyncSession, user_id: int) -> UserSettings | None:
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_user_profile(
    session: AsyncSession,
    user: User,
    *,
    bio: str | None = None,
    city: str | None = None,
    avatar_file_id: str | None = None,
) -> User:
    if bio is not None:
        user.bio = bio[:2000]
    if city is not None:
        user.city = city[:128]
    if avatar_file_id is not None:
        user.avatar_file_id = avatar_file_id

    await session.commit()
    await session.refresh(user)
    return user


async def set_user_active(
    session: AsyncSession,
    user: User,
    active: bool,
) -> User:
    user.is_active = active
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    normalized = username.strip().lstrip("@").lower()
    if not normalized:
        return None
    result = await session.execute(
        select(User).where(User.username.is_not(None), User.username.ilike(normalized))
    )
    return result.scalar_one_or_none()
