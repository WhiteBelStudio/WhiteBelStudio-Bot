from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ShopItem, User, UserInventory


async def get_inventory(session: AsyncSession, user_id: int) -> list[tuple[UserInventory, ShopItem]]:
    result = await session.execute(
        select(UserInventory, ShopItem)
        .join(ShopItem, ShopItem.id == UserInventory.item_id)
        .where(UserInventory.user_id == user_id, UserInventory.quantity > 0)
        .order_by(ShopItem.category, ShopItem.price, ShopItem.id)
    )
    return list(result.all())


async def get_user_by_username_for_gift(session: AsyncSession, username: str) -> User | None:
    normalized = username.strip().lstrip("@").lower()
    if not normalized:
        return None
    result = await session.execute(select(User).where(User.username.ilike(normalized)))
    return result.scalar_one_or_none()
