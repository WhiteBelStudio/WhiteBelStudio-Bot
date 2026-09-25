from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CoinTransaction, EconomyAccount, ShopItem, UserInventory


DAILY_REWARDS: dict[int, Decimal] = {
    1: Decimal("0.5"),
    2: Decimal("0.5"),
    3: Decimal("1.0"),
    4: Decimal("1.0"),
    5: Decimal("1.5"),
    6: Decimal("1.5"),
    7: Decimal("2.0"),
}
MILESTONE_REWARDS: dict[int, Decimal] = {
    14: Decimal("5.0"),
    30: Decimal("15.0"),
    90: Decimal("40.0"),
    180: Decimal("100.0"),
    365: Decimal("250.0"),
}


@dataclass(frozen=True, slots=True)
class DailyResult:
    claimed: bool
    amount: Decimal
    streak: int
    message: str


async def get_or_create_economy(session: AsyncSession, user_id: int) -> EconomyAccount:
    result = await session.execute(select(EconomyAccount).where(EconomyAccount.user_id == user_id))
    account = result.scalar_one_or_none()
    if account is None:
        account = EconomyAccount(user_id=user_id)
        session.add(account)
        await session.flush()
    return account


async def get_balance(session: AsyncSession, user_id: int) -> Decimal:
    return (await get_or_create_economy(session, user_id)).balance


async def change_balance(
    session: AsyncSession,
    user_id: int,
    amount: Decimal,
    reason: str,
    *,
    reference_user_id: int | None = None,
    item_id: int | None = None,
) -> Decimal:
    amount = Decimal(amount).quantize(Decimal("0.1"))
    if amount == 0:
        return await get_balance(session, user_id)

    account = await get_or_create_economy(session, user_id)
    new_balance = account.balance + amount
    if new_balance < 0:
        raise ValueError("insufficient_funds")

    account.balance = new_balance
    if amount > 0:
        account.lifetime_earned += amount
    else:
        account.lifetime_spent += -amount

    session.add(CoinTransaction(
        user_id=user_id,
        amount=amount,
        balance_after=new_balance,
        reason=reason,
        reference_user_id=reference_user_id,
        item_id=item_id,
    ))
    await session.flush()
    return new_balance


async def claim_daily(session: AsyncSession, user_id: int, now: datetime | None = None) -> DailyResult:
    now = now or datetime.now(timezone.utc)
    account = await get_or_create_economy(session, user_id)

    if account.last_daily_claim_at is not None:
        last = account.last_daily_claim_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now.date() == last.astimezone(timezone.utc).date():
            return DailyResult(False, Decimal("0.0"), account.daily_streak, "Сегодня награда уже получена.")

    if account.last_daily_claim_at is None:
        streak = 1
    else:
        last_date = account.last_daily_claim_at
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        days = (now.astimezone(timezone.utc).date() - last_date.astimezone(timezone.utc).date()).days
        streak = account.daily_streak + 1 if days == 1 else 1

    # The normal weekly cycle repeats; long streaks additionally receive milestone bonuses.
    cycle_day = ((streak - 1) % 7) + 1
    amount = DAILY_REWARDS[cycle_day]
    milestone = MILESTONE_REWARDS.get(streak, Decimal("0.0"))
    total = amount + milestone

    account.daily_streak = streak
    account.last_daily_claim_at = now
    await change_balance(session, user_id, total, "daily_reward")
    await session.commit()

    bonus_text = f" +{milestone:.1f} за {streak} дней!" if milestone else ""
    return DailyResult(True, total, streak, f"Награда получена: +{total:.1f} монет.{bonus_text}")


async def list_transactions(session: AsyncSession, user_id: int, limit: int = 10) -> list[CoinTransaction]:
    result = await session.execute(
        select(CoinTransaction)
        .where(CoinTransaction.user_id == user_id)
        .order_by(desc(CoinTransaction.created_at), desc(CoinTransaction.id))
        .limit(max(1, min(limit, 50)))
    )
    return list(result.scalars().all())


async def list_shop_items(session: AsyncSession, category: str | None = None) -> list[ShopItem]:
    query = select(ShopItem).where(ShopItem.is_active.is_(True))
    if category:
        query = query.where(ShopItem.category == category)
    result = await session.execute(query.order_by(ShopItem.category, ShopItem.price, ShopItem.id))
    return list(result.scalars().all())


async def purchase_item(session: AsyncSession, user_id: int, item_id: int) -> tuple[ShopItem, UserInventory, Decimal]:
    item = await session.get(ShopItem, item_id)
    if item is None or not item.is_active:
        raise ValueError("item_not_found")

    balance = await get_balance(session, user_id)
    if balance < item.price:
        raise ValueError("insufficient_funds")

    await change_balance(session, user_id, -item.price, "shop_purchase", item_id=item.id)
    inventory = UserInventory(user_id=user_id, item_id=item.id, quantity=1)
    session.add(inventory)
    await session.flush()
    await session.commit()
    return item, inventory, balance - item.price


async def gift_item(
    session: AsyncSession,
    sender_id: int,
    recipient_id: int,
    item_id: int,
) -> tuple[ShopItem, Decimal]:
    if sender_id == recipient_id:
        raise ValueError("self_gift")
    item = await session.get(ShopItem, item_id)
    if item is None or not item.is_active or item.category != "gift":
        raise ValueError("item_not_found")

    balance = await get_balance(session, sender_id)
    if balance < item.price:
        raise ValueError("insufficient_funds")

    await change_balance(
        session, sender_id, -item.price, "gift_sent",
        reference_user_id=recipient_id, item_id=item.id,
    )
    session.add(UserInventory(user_id=recipient_id, item_id=item.id, quantity=1))
    session.add(CoinTransaction(
        user_id=recipient_id,
        amount=Decimal("0.0"),
        balance_after=await get_balance(session, recipient_id),
        reason="gift_received",
        reference_user_id=sender_id,
        item_id=item.id,
    ))
    await session.commit()
    return item, balance - item.price
