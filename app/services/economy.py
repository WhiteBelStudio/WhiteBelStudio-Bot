from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import desc, func, select
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
GAME_REWARD_CAP = Decimal("10.0")
GAME_REWARD_RESULT_LIMIT = 20
GAME_REWARDS: dict[str, dict[str, Decimal]] = {
    "math": {"win": Decimal("1.0"), "loss": Decimal("0.1"), "draw": Decimal("0.5")},
    "code": {"win": Decimal("1.5"), "loss": Decimal("0.1"), "draw": Decimal("0.7")},
    "word": {"win": Decimal("1.0"), "loss": Decimal("0.1"), "draw": Decimal("0.5")},
    "sequence": {"win": Decimal("1.5"), "loss": Decimal("0.1"), "draw": Decimal("0.7")},
    "logic": {"win": Decimal("1.5"), "loss": Decimal("0.1"), "draw": Decimal("0.7")},
    "anagram": {"win": Decimal("1.5"), "loss": Decimal("0.1"), "draw": Decimal("0.7")},
    "tower": {"win": Decimal("2.0"), "loss": Decimal("0.1"), "draw": Decimal("1.0")},
    "algorithm": {"win": Decimal("2.0"), "loss": Decimal("0.1"), "draw": Decimal("1.0")},
    "counter": {"win": Decimal("1.5"), "loss": Decimal("0.1"), "draw": Decimal("0.7")},
    "space": {"win": Decimal("2.0"), "loss": Decimal("0.1"), "draw": Decimal("1.0")},
    "quiz": {"win": Decimal("1.0"), "loss": Decimal("0.1"), "draw": Decimal("0.5")},
    "chain": {"win": Decimal("1.0"), "loss": Decimal("0.1"), "draw": Decimal("0.5")},
    "pvp": {"win": Decimal("2.0"), "loss": Decimal("0.5"), "draw": Decimal("1.0")},
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
    await session.refresh(account, with_for_update=True)
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
    await session.refresh(account, with_for_update=True)

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


def calculate_game_reward(
    *,
    game_kind: str,
    result: str,
    earned_today: Decimal,
    result_count: int,
) -> Decimal:
    """Calculate a capped game reward without touching the database."""
    if result not in {"win", "loss", "draw"}:
        raise ValueError("result must be win, loss or draw")
    if result_count >= GAME_REWARD_RESULT_LIMIT:
        return Decimal("0.0")

    reward = GAME_REWARDS.get(game_kind, GAME_REWARDS["math"]).get(result, Decimal("0.0"))
    allowed = max(Decimal("0.0"), GAME_REWARD_CAP - Decimal(earned_today))
    return min(reward, allowed).quantize(Decimal("0.1"))


async def award_game_coins(
    session: AsyncSession,
    user_id: int,
    *,
    game_kind: str,
    result: str,
    now: datetime | None = None,
) -> Decimal:
    """Award non-wagered game coins with a per-user UTC daily anti-farm cap."""

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_utc = now.astimezone(timezone.utc)
    day_start = datetime.combine(now_utc.date(), datetime.min.time(), tzinfo=timezone.utc)

    account = await get_or_create_economy(session, user_id)
    await session.refresh(account, with_for_update=True)

    result_count_query = await session.execute(
        select(func.count(CoinTransaction.id)).where(
            CoinTransaction.user_id == user_id,
            CoinTransaction.reason == "game_reward",
            CoinTransaction.created_at >= day_start,
        )
    )
    result_count = int(result_count_query.scalar_one() or 0)
    if result_count >= GAME_REWARD_RESULT_LIMIT:
        return Decimal("0.0")

    earned_query = await session.execute(
        select(func.coalesce(func.sum(CoinTransaction.amount), 0)).where(
            CoinTransaction.user_id == user_id,
            CoinTransaction.reason == "game_reward",
            CoinTransaction.created_at >= day_start,
            CoinTransaction.amount > 0,
        )
    )
    earned_today = Decimal(earned_query.scalar_one() or 0).quantize(Decimal("0.1"))
    reward = calculate_game_reward(
        game_kind=game_kind,
        result=result,
        earned_today=earned_today,
        result_count=result_count,
    )
    if reward <= 0:
        return Decimal("0.0")

    new_balance = await change_balance(session, user_id, reward, "game_reward")
    await session.commit()
    return reward


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


async def get_inventory(
    session: AsyncSession,
    user_id: int,
) -> list[tuple[UserInventory, ShopItem]]:
    result = await session.execute(
        select(UserInventory, ShopItem)
        .join(ShopItem, ShopItem.id == UserInventory.item_id)
        .where(UserInventory.user_id == user_id)
        .order_by(UserInventory.acquired_at.desc(), UserInventory.id.desc())
    )
    return list(result.all())


async def purchase_item(session: AsyncSession, user_id: int, item_id: int) -> tuple[ShopItem, UserInventory, Decimal]:
    item = await session.get(ShopItem, item_id, with_for_update=True)
    if item is None or not item.is_active:
        raise ValueError("item_not_found")

    account = await get_or_create_economy(session, user_id)
    await session.refresh(account, with_for_update=True)
    balance = account.balance
    price = Decimal(item.price).quantize(Decimal("0.1"))
    if price < 0:
        raise ValueError("invalid_item_price")
    if balance < price:
        raise ValueError("insufficient_funds")

    new_balance = await change_balance(session, user_id, -price, "shop_purchase", item_id=item.id)
    result = await session.execute(
        select(UserInventory).where(
            UserInventory.user_id == user_id,
            UserInventory.item_id == item.id,
        )
    )
    inventory = result.scalar_one_or_none()
    if inventory is None:
        inventory = UserInventory(user_id=user_id, item_id=item.id, quantity=1)
        session.add(inventory)
    else:
        inventory.quantity += 1
    await session.flush()
    await session.commit()
    return item, inventory, new_balance


async def gift_item(
    session: AsyncSession,
    sender_id: int,
    recipient_id: int,
    item_id: int,
) -> tuple[ShopItem, Decimal]:
    if sender_id == recipient_id:
        raise ValueError("self_gift")
    item = await session.get(ShopItem, item_id, with_for_update=True)
    if item is None or not item.is_active or item.category != "gift":
        raise ValueError("item_not_found")

    sender = await get_or_create_economy(session, sender_id)
    await session.refresh(sender, with_for_update=True)
    balance = sender.balance
    price = Decimal(item.price).quantize(Decimal("0.1"))
    if price < 0:
        raise ValueError("invalid_item_price")
    if balance < price:
        raise ValueError("insufficient_funds")

    new_balance = await change_balance(
        session, sender_id, -price, "gift_sent",
        reference_user_id=recipient_id, item_id=item.id,
    )
    result = await session.execute(
        select(UserInventory).where(
            UserInventory.user_id == recipient_id,
            UserInventory.item_id == item.id,
        )
    )
    inventory = result.scalar_one_or_none()
    if inventory is None:
        session.add(UserInventory(user_id=recipient_id, item_id=item.id, quantity=1))
    else:
        inventory.quantity += 1

    session.add(CoinTransaction(
        user_id=recipient_id,
        amount=Decimal("0.0"),
        balance_after=await get_balance(session, recipient_id),
        reason="gift_received",
        reference_user_id=sender_id,
        item_id=item.id,
    ))
    await session.commit()
    return item, new_balance
