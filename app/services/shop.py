from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ShopItem, User, UserInventory


SHOP_CATALOG: tuple[dict[str, object], ...] = (
    {"code": "title_activist", "name": "🏷️ Активист", "description": "Титул для профиля.", "category": "title", "price": Decimal("5.0")},
    {"code": "title_veteran", "name": "🏷️ Ветеран", "description": "Титул для профиля.", "category": "title", "price": Decimal("15.0")},
    {"code": "title_gamer", "name": "🎮 Игрок", "description": "Титул для профиля.", "category": "title", "price": Decimal("10.0")},
    {"code": "title_brain", "name": "🧠 Мозг", "description": "Титул для профиля.", "category": "title", "price": Decimal("20.0")},
    {"code": "boost_attempt", "name": "⚡ +1 попытка", "description": "Одноразовое игровое улучшение.", "category": "boost", "price": Decimal("2.5")},
    {"code": "boost_hint", "name": "💡 Подсказка", "description": "Одноразовая подсказка для поддерживаемых игр.", "category": "boost", "price": Decimal("1.0")},
    {"code": "boost_streak", "name": "🔥 Заморозка серии", "description": "Защищает игровую серию от одного пропуска.", "category": "boost", "price": Decimal("5.0")},
    {"code": "gift_heart", "name": "❤️ Сердце", "description": "Виртуальный подарок участнику.", "category": "gift", "price": Decimal("0.5")},
    {"code": "gift_star", "name": "⭐ Звезда", "description": "Виртуальный подарок участнику.", "category": "gift", "price": Decimal("1.0")},
    {"code": "gift_fire", "name": "🔥 Огонь", "description": "Виртуальный подарок участнику.", "category": "gift", "price": Decimal("2.5")},
    {"code": "gift_crown", "name": "👑 Корона", "description": "Виртуальный подарок участнику.", "category": "gift", "price": Decimal("5.0")},
    {"code": "gift_diamond", "name": "💎 Алмаз", "description": "Виртуальный подарок участнику.", "category": "gift", "price": Decimal("10.0")},
    {"code": "exclusive_100wins", "name": "🏆 100 побед", "description": "Эксклюзивный предмет за достижение.", "category": "exclusive", "price": Decimal("25.0")},
    {"code": "exclusive_30days", "name": "🔥 30 дней активности", "description": "Эксклюзивный предмет за серию.", "category": "exclusive", "price": Decimal("30.0")},
    {"code": "exclusive_500games", "name": "🎮 500 игр", "description": "Эксклюзивный предмет за игровой прогресс.", "category": "exclusive", "price": Decimal("50.0")},
    {"code": "exclusive_365days", "name": "💎 365 дней", "description": "Эксклюзивный предмет за год активности.", "category": "exclusive", "price": Decimal("100.0")},
)


async def ensure_shop_catalog(session: AsyncSession) -> int:
    """Restore any missing built-in shop items without duplicating existing rows."""
    result = await session.execute(select(ShopItem.code))
    existing = set(result.scalars().all())
    added = 0

    for data in SHOP_CATALOG:
        code = str(data["code"])
        if code in existing:
            continue
        session.add(
            ShopItem(
                code=code,
                name=str(data["name"]),
                description=str(data["description"]),
                category=str(data["category"]),
                price=Decimal(data["price"]),
                is_active=True,
            )
        )
        added += 1

    if added:
        await session.commit()
    return added


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
