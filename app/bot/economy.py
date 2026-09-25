from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.engine import get_session
from app.services.economy import claim_daily, get_balance, gift_item, list_shop_items, list_transactions, purchase_item
from app.services.shop import get_inventory, get_user_by_username_for_gift
from app.services.users import sync_telegram_user

router = Router(name="economy")


CATEGORY_NAMES = {
    "title": "🏷️ Титулы",
    "boost": "⚡ Улучшения",
    "gift": "🎁 Подарки",
    "exclusive": "🏆 Эксклюзивы",
}


def shop_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Титулы", callback_data="shop_cat:title"),
         InlineKeyboardButton(text="⚡ Улучшения", callback_data="shop_cat:boost")],
        [InlineKeyboardButton(text="🎁 Подарки", callback_data="shop_cat:gift"),
         InlineKeyboardButton(text="🏆 Эксклюзивы", callback_data="shop_cat:exclusive")],
        [InlineKeyboardButton(text="📦 Мои предметы", callback_data="shop_inventory")],
    ])


def items_keyboard(items) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{item.name} · 🪙 {Decimal(item.price):.1f}",
            callback_data=f"shop_buy:{item.id}",
        )]
        for item in items
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Категории", callback_data="shop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_shop(message: Message, category: str | None = None, *, edit: bool = False) -> None:
    if message.from_user is None:
        return
    async for session in get_session():
        user, _ = await sync_telegram_user(session, message.from_user)
        balance = await get_balance(session, user.id)
        items = await list_shop_items(session, category)

    if category:
        title = CATEGORY_NAMES.get(category, "🛒 Магазин")
        lines = [f"🛒 <b>{title}</b>", "", f"🪙 Баланс: <b>{balance:.1f}</b>", ""]
        for item in items:
            lines.append(f"<b>#{item.id} {item.name}</b> — 🪙 {item.price:.1f}")
            lines.append(item.description)
            lines.append("")
        text = "\n".join(lines)
        markup = items_keyboard(items)
    else:
        text = (
            "🛒 <b>Магазин WhiteBelStudio</b>\n\n"
            f"🪙 Баланс: <b>{balance:.1f}</b>\n\n"
            "Выбери раздел:"
        )
        markup = shop_categories_keyboard()
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.message(Command("balance"))
async def balance_handler(message: Message) -> None:
    if message.from_user is None:
        return
    async for session in get_session():
        user, _ = await sync_telegram_user(session, message.from_user)
        balance = await get_balance(session, user.id)
    await message.answer(f"🪙 <b>Твой баланс: {balance:.1f}</b>")


@router.message(Command("daily"))
async def daily_handler(message: Message) -> None:
    if message.from_user is None:
        return
    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            result = await claim_daily(session, user.id)
        if not result.claimed:
            await message.answer(
                f"🎁 {result.message}\n🔥 Серия: <b>{result.streak} дней</b>"
            )
            return
        await message.answer(
            f"🎁 <b>Ежедневная награда получена!</b>\n\n"
            f"🪙 +{result.amount:.1f}\n"
            f"🔥 Серия: <b>{result.streak} дней</b>"
        )
    except Exception as exc:
        print(f"[economy] daily failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось получить ежедневную награду.")

@router.message(Command("shop"))
async def shop_handler(message: Message) -> None:
    if message.from_user is None:
        return
    await show_shop(message)


@router.message(Command("inventory"))
async def inventory_handler(message: Message) -> None:
    if message.from_user is None:
        return
    async for session in get_session():
        user, _ = await sync_telegram_user(session, message.from_user)
        rows = await get_inventory(session, user.id)
    if not rows:
        await message.answer("📦 Инвентарь пуст. Открой /shop.")
        return
    lines = ["📦 <b>Мои предметы</b>", ""]
    for inventory, item in rows:
        lines.append(f"{item.name} × <b>{inventory.quantity}</b> — {item.description}")
    await message.answer("
".join(lines))


@router.message(Command("coinhistory"))
async def coin_history_handler(message: Message) -> None:
    if message.from_user is None:
        return
    async for session in get_session():
        user, _ = await sync_telegram_user(session, message.from_user)
        rows = await list_transactions(session, user.id, 15)
    if not rows:
        await message.answer("📜 История операций пока пуста.")
        return
    lines = ["📜 <b>История монет</b>", ""]
    for row in rows:
        sign = "+" if row.amount > 0 else ""
        lines.append(f"{sign}{row.amount:.1f} 🪙 · {row.reason}")
    await message.answer("
".join(lines))


@router.callback_query(F.data == "shop")
async def shop_callback(callback: CallbackQuery) -> None:
    if callback.message is not None:
        await show_shop(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("shop_cat:"))
async def shop_category_callback(callback: CallbackQuery) -> None:
    if callback.message is not None:
        category = (callback.data or "").split(":", 1)[1]
        await show_shop(callback.message, category, edit=True)
    await callback.answer()


@router.callback_query(F.data == "shop_inventory")
async def shop_inventory_callback(callback: CallbackQuery) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer()
        return
    async for session in get_session():
        user, _ = await sync_telegram_user(session, callback.from_user)
        rows = await get_inventory(session, user.id)
    if not rows:
        text = "📦 <b>Мои предметы</b>

Инвентарь пока пуст."
    else:
        lines = ["📦 <b>Мои предметы</b>", ""]
        for inventory, item in rows:
            lines.append(f"{item.name} × <b>{inventory.quantity}</b>")
        text = "
".join(lines)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 В магазин", callback_data="shop")]
    ])
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("shop_buy:"))
async def shop_buy_callback(callback: CallbackQuery) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer()
        return
    try:
        item_id = int((callback.data or "").split(":", 1)[1])
        async for session in get_session():
            user, _ = await sync_telegram_user(session, callback.from_user)
            item, _, new_balance = await purchase_item(session, user.id, item_id)
        await callback.message.edit_text(
            f"✅ <b>Покупка выполнена!</b>

"
            f"{item.name}
{item.description}

"
            f"🪙 Остаток: <b>{new_balance:.1f}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Вернуться в магазин", callback_data="shop")]
            ]),
        )
    except ValueError as exc:
        if str(exc) == "insufficient_funds":
            await callback.answer("Недостаточно монет.", show_alert=True)
        else:
            await callback.answer("Товар недоступен.", show_alert=True)
        return
    except Exception as exc:
        print(f"[economy] purchase failed: {exc}", flush=True)
        await callback.answer("Не удалось выполнить покупку.", show_alert=True)
        return
    await callback.answer("Покупка выполнена")


@router.message(Command("gift"))
async def gift_handler(message: Message) -> None:
    if message.from_user is None:
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Использование: <code>/gift @username ID_товара</code>")
        return
    try:
        item_id = int(parts[2])
    except ValueError:
        await message.answer("ID товара должен быть числом.")
        return

    try:
        async for session in get_session():
            sender, _ = await sync_telegram_user(session, message.from_user)
            recipient = await get_user_by_username_for_gift(session, parts[1])
            if recipient is None:
                raise ValueError("recipient_not_found")
            item, new_balance = await gift_item(session, sender.id, recipient.id, item_id)
        await message.answer(
            f"🎁 <b>Подарок отправлен!</b>

"
            f"{item.name} → @{recipient.username or recipient.first_name}
"
            f"🪙 Остаток: <b>{new_balance:.1f}</b>"
        )
    except ValueError as exc:
        messages = {
            "recipient_not_found": "❌ Получатель не найден.",
            "self_gift": "🙂 Нельзя подарить предмет самому себе.",
            "insufficient_funds": "🪙 Недостаточно монет.",
            "item_not_found": "❌ Такой подарок не найден.",
        }
        await message.answer(messages.get(str(exc), "⚠️ Не удалось отправить подарок."))
    except Exception as exc:
        print(f"[economy] gift failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось отправить подарок.")


@router.message(Command("economy"))
async def economy_handler(message: Message) -> None:
    if message.from_user is None:
        return
    await message.answer(
        "🪙 <b>Экономика</b>

"
        "/balance — баланс
"
        "/daily — ежедневная награда
"
        "/shop — магазин
"
        "/inventory — мои предметы
"
        "/coinhistory — история монет
"
        "/gift @username ID — подарить подарок"
    )
