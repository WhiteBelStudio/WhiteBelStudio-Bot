from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, *, telegram_id: int, first_name: str,
                      username: str | None = None, last_name: str | None = None) -> User:
    user = User(
        telegram_id=telegram_id,
        first_name=first_name,
        username=username,
        last_name=last_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_or_create_user(session: AsyncSession, *, telegram_id: int, first_name: str,
                             username: str | None = None, last_name: str | None = None) -> tuple[User, bool]:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is not None:
        return user, False
    return await create_user(
        session,
        telegram_id=telegram_id,
        first_name=first_name,
        username=username,
        last_name=last_name,
    ), True
