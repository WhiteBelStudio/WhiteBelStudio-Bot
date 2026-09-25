"""WhiteBelStudio Bot entrypoint."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.db.engine import close_db, get_session
from app.db.health import check_database_connection
from app.bot.middleware import ChatReputationMiddleware
from app.bot.economy import router as economy_router
from app.services.community import (
    format_community_reputation,
    get_reputation_history,
    get_reputation_score,
    get_reputation_top,
)
from app.services.games import get_game_leaderboard, get_game_profile, record_game_result
from app.services.economy import award_game_coins
from app.services.minigames import cancel_game, check_answer, game_catalog_text, get_game, start_game
from app.services.pvp import PVP_KINDS, accept_challenge, create_challenge, decline_challenge, get_active_match, get_display_name, submit_answer
from app.services.social import (
    find_users,
    format_social_user,
    get_user_by_username,
    list_friends,
    list_incoming_requests,
    remove_friend,
    respond_to_request,
    send_friend_request,
)
from app.services.users import format_user_profile, sync_telegram_user

load_dotenv()


dp = Dispatcher()
dp.message.middleware(ChatReputationMiddleware())
dp.include_router(economy_router)



@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    database_ok = False
    created = False

    if message.from_user is not None and os.getenv("DATABASE_URL", "").strip():
        try:
            async for session in get_session():
                _, created = await sync_telegram_user(session, message.from_user)
            database_ok = True
        except Exception as exc:
            print(f"[db] user sync failed: {exc}", flush=True)

    suffix = "\n\n🗄 База данных: подключена" if database_ok else ""
    account_status = "🆕 Аккаунт создан" if created else "♻️ Аккаунт обновлён"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
                InlineKeyboardButton(text="⭐ Репутация", callback_data="menu_reputation"),
            ],
            [
                InlineKeyboardButton(text="📜 Правила", callback_data="menu_rules"),
                InlineKeyboardButton(text="🛒 Магазин", callback_data="shop"),
                InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help"),
            ],
        ]
    )

    await message.answer(
        "👋 Привет!\n\n"
        "Добро пожаловать в WhiteBelStudio.\n"
        f"{account_status}\n\n"
        "👤 /profile — профиль\n"
        "⭐ /rep — твоя репутация\n"
        "🏆 /toprep — топ участников\n"
        "📜 /rules — правила\n"
        "❓ /help — помощь"
        + suffix,
        reply_markup=keyboard,
    )


@dp.callback_query()
async def menu_callback_handler(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return

    action = callback.data or ""

    if action == "menu_profile":
        await profile_handler(callback.message)
    elif action == "menu_reputation":
        await rep_handler(callback.message)
    elif action == "menu_rules":
        await rules_handler(callback.message)
    elif action == "shop":
        from app.bot.economy import show_shop
        await show_shop(callback.message, edit=True)
    elif action == "menu_help":
        await show_help_categories(callback.message, edit=True)
    elif action == "help_categories":
        await show_help_categories(callback.message, edit=True)
    elif action.startswith("help_category:"):
        await show_help_category(callback.message, action.split(":", 1)[1])
    elif action == "mini_games":
        await show_mini_games(callback.message, edit=True)
    elif action == "mini_games:regular":
        await callback.message.edit_text("🎮 <b>Обычные мини-игры</b>\\n\\nВыбери игру:", reply_markup=regular_games_keyboard())
    elif action == "mini_games:pvp":
        await show_pvp_category(callback.message, edit=True)
    elif action.startswith("pvp_create:"):
        await send_pvp_challenge(callback.message, action.split(":", 1)[1])
    elif action.startswith("pvp_accept:") or action.startswith("pvp_decline:"):
        await pvp_callback(callback.message, action)
    elif action.startswith("mini_start:"):
        await start_mini_game(callback.message, action.split(":", 1)[1])

    await callback.answer()


HELP_CATEGORIES = {
    "general": (
        "👤 <b>Основные команды</b>\n\n"
        "👤 /profile — посмотреть свой профиль\n"
        "⭐ /rep — посмотреть свою репутацию\n"
        "➕ /rep+ — положительная оценка участнику (в группе)\n"
        "➖ /rep- — отрицательная оценка участнику (в группе)\n"
        "🏆 /toprep — топ участников по репутации\n"
        "📜 /rules — правила сообщества"
    ),
    "social": (
        "👥 <b>Социальные команды</b>\n\n"
        "🔎 /find [запрос] — найти участника\n"
        "👥 /friends — список друзей\n"
        "📨 /requests — входящие заявки в друзья\n"
        "➕ /addfriend @username — отправить заявку\n"
        "✅ /accept @username — принять заявку\n"
        "❌ /decline @username — отклонить заявку\n"
        "🗑 /removefriend @username — удалить из друзей"
    ),
    "game": (
        "🎮 <b>Игровые команды</b>\n\n"
        "🎮 /game — игровой профиль\n"
        "🏆 /gametop — топ игроков\n"
        "🕹 /games — мини-игры\n"
        "🛑 /cancelgame — отменить активную мини-игру\n⚔️ /pvp — соревнование 1 на 1\n\n"
        "🪙 /balance — баланс монет\n"
        "🎁 /daily — ежедневная награда\n"
        "🛒 /shop — магазин\n"
        "📦 /inventory — мои предметы\n"
        "📜 /coinhistory — история монет\n"
        "🎁 /gift @username ID — подарить подарок"
    ),
    "moderation": (
        "🛡 <b>Модерация</b>\n\n"
        "Модерационные команды будут доступны после подключения системы модерации."
    ),
}


def help_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Основные", callback_data="help_category:general"),
                InlineKeyboardButton(text="👥 Социальные", callback_data="help_category:social"),
            ],
            [
                InlineKeyboardButton(text="🎮 Игровые", callback_data="help_category:game"),
                InlineKeyboardButton(text="🛡 Модерация", callback_data="help_category:moderation"),
            ],
        ]
    )


def help_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К категориям", callback_data="help_categories")]
        ]
    )


async def show_help_categories(message: Message, *, edit: bool = False) -> None:
    text = (
        "❓ <b>Помощь WhiteBelStudio</b>\n\n"
        "Выбери категорию команд, чтобы посмотреть доступные команды и краткие гайды."
    )
    if edit:
        await message.edit_text(text, reply_markup=help_categories_keyboard())
    else:
        await message.answer(text, reply_markup=help_categories_keyboard())


async def show_help_category(message: Message, category: str) -> None:
    content = HELP_CATEGORIES.get(category)
    if content is None:
        await message.answer("⚠️ Категория помощи не найдена.")
        return
    await message.edit_text(content, reply_markup=help_back_keyboard())


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await show_help_categories(message)


@dp.message(Command("rules"))
async def rules_handler(message: Message) -> None:
    await message.answer(
        "📜 <b>Правила сообщества</b>\n\n"
        "1. Уважай других участников.\n"
        "2. Не спамь и не флуди.\n"
        "3. Не публикуй запрещённый или опасный контент.\n"
        "4. Не выдавай себя за другого участника.\n"
        "5. Выполняй требования модераторов.\n\n"
        "Нарушения могут влиять на репутацию и приводить к ограничениям."
    )


@dp.message(Command("rep"))
async def rep_handler(message: Message) -> None:
    if message.from_user is None:
        return
    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            score = await get_reputation_score(session, user.id)
            history = await get_reputation_history(session, user.id)
        name = " ".join(p for p in (user.first_name, user.last_name) if p)
        await message.answer(format_community_reputation(name, score, history))
    except Exception as exc:
        print(f"[reputation] load failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить репутацию.")


@dp.message(Command("toprep"))
async def top_rep_handler(message: Message) -> None:
    try:
        async for session in get_session():
            rows = await get_reputation_top(session, 10)

        if not rows:
            await message.answer("🏆 Пока нет участников с изменениями репутации.")
            return

        lines = ["🏆 <b>Топ репутации</b>", ""]
        for index, (_, name, score) in enumerate(rows, 1):
            lines.append(f"{index}. {name} — <b>{score}</b>")
        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[reputation] top failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить топ.")



def mini_games_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎮 Обычные игры", callback_data="mini_games:regular"),
                InlineKeyboardButton(text="⚔️ Соревнования", callback_data="mini_games:pvp"),
            ],
        ]
    )


def regular_games_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧮 Штурм", callback_data="mini_start:math"), InlineKeyboardButton(text="🔐 Взломщик", callback_data="mini_start:code")],
            [InlineKeyboardButton(text="🔤 Шифровальщик", callback_data="mini_start:word")],
            [InlineKeyboardButton(text="🔢 Последовательность", callback_data="mini_start:sequence"), InlineKeyboardButton(text="🧩 Логика", callback_data="mini_start:logic")],
            [InlineKeyboardButton(text="🔀 Анаграмма PRO", callback_data="mini_start:anagram")],
            [InlineKeyboardButton(text="🧱 Башня", callback_data="mini_start:tower"), InlineKeyboardButton(text="🧪 Алгоритм", callback_data="mini_start:algorithm")],
            [InlineKeyboardButton(text="🧮 Счётчик", callback_data="mini_start:counter"), InlineKeyboardButton(text="🌌 Космический маршрут", callback_data="mini_start:space")],
            [InlineKeyboardButton(text="🏆 Викторина", callback_data="mini_start:quiz"), InlineKeyboardButton(text="🔤 Словесная цепочка", callback_data="mini_start:chain")],
            [InlineKeyboardButton(text="⬅️ К категориям", callback_data="mini_games")],
        ]
    )


def pvp_games_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧮 Математика", callback_data="pvp_create:math")],
            [InlineKeyboardButton(text="🔢 Последовательность", callback_data="pvp_create:sequence")],
            [InlineKeyboardButton(text="🏆 Викторина", callback_data="pvp_create:quiz")],
            [InlineKeyboardButton(text="⬅️ К категориям", callback_data="mini_games")],
        ]
    )


def pvp_challenge_keyboard(match_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="⚔️ Принять вызов", callback_data=f"pvp_accept:{match_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pvp_decline:{match_id}"),
        ]]
    )


def mini_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🕹 Все мини-игры", callback_data="mini_games")]
        ]
    )


async def show_mini_games(message: Message, *, edit: bool = False) -> None:
    text = game_catalog_text()
    keyboard = mini_games_keyboard()
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def show_pvp_category(message: Message, *, edit: bool = False) -> None:
    text = (
        "⚔️ <b>Соревнования</b>\\n\\n"
        "Выбери игру для вызова. Оба участника решают одну и ту же задачу.\\n"
        "⏱ Вызов действует 5 минут.\\n"
        "🏆 Победа определяется по правильному ответу.\\n"
        "🪙 Ставок монет нет — только навык и XP."
    )
    keyboard = pvp_games_keyboard()
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def send_pvp_challenge(message: Message, kind: str) -> None:
    if message.from_user is None:
        return
    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            match = await create_challenge(session, user.id, kind)
            creator_name = f"@{user.username}" if user.username else user.first_name
    except ValueError as exc:
        msg = "⚠️ У тебя уже есть активное соревнование." if str(exc) == "active_match" else "⚠️ Не удалось создать вызов."
        await message.answer(msg)
        return
    await message.answer(
        f"⚔️ <b>Вызов на соревнование!</b>\\n\\n"
        f"👤 От: <b>{creator_name}</b>\\n"
        f"🎮 Игра: <b>{PVP_KINDS[kind]}</b>\\n\\n"
        f"Задача: {match.prompt}\\n\\n"
        "Нажми «Принять вызов», чтобы начать."
        ,
        reply_markup=pvp_challenge_keyboard(match.id),
    )


async def pvp_callback(message: Message, action: str) -> None:
    if message.from_user is None:
        return
    try:
        match_id = int(action.split(":", 1)[1])
    except (ValueError, IndexError):
        await message.answer("⚠️ Некорректный вызов.")
        return
    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            if action.startswith("pvp_accept:"):
                match = await accept_challenge(session, match_id, user.id)
                await message.answer(
                    f"⚔️ <b>Соревнование началось!</b>\\n\\n"
                    f"🎮 {PVP_KINDS[match.kind]}\\n"
                    f"{match.prompt}\\n\\n"
                    "Отправь ответ обычным сообщением."
                )
                return
            await decline_challenge(session, match_id, user.id)
            await message.answer("❌ Вызов отклонён.")
    except ValueError as exc:
        errors = {
            "self": "⚠️ Нельзя вызвать самого себя.",
            "active_match": "⚠️ У тебя уже есть активное соревнование.",
            "creator": "⚠️ Создатель вызова не может отклонить его.",
            "unavailable": "⚠️ Этот вызов уже недоступен.",
        }
        await message.answer(errors.get(str(exc), "⚠️ Действие недоступно."))




async def start_mini_game(message: Message, kind: str) -> None:
    if message.from_user is None:
        return
    if get_game(message.from_user.id) is not None:
        await message.answer("⚠️ У тебя уже есть активная игра. Закончи её или отправь /cancelgame.")
        return
    try:
        game = start_game(message.from_user.id, kind)
        sent = await message.answer(
            f"🎮 <b>Игра началась!</b>\n\n{game.prompt}\n\n"
            f"🎯 Попыток: <b>{game.attempts_left}</b>\n"
            "Отправь ответ обычным сообщением.",
            reply_markup=mini_back_keyboard(),
        )
    except ValueError:
        await message.answer("⚠️ Такая игра пока недоступна.")


@dp.message(Command("games"))
async def mini_games_handler(message: Message) -> None:
    await show_mini_games(message)


@dp.message(Command("cancelgame"))
async def cancel_game_handler(message: Message) -> None:
    if message.from_user is None:
        return
    if get_game(message.from_user.id) is None:
        await message.answer("ℹ️ Активной игры нет.")
        return
    cancel_game(message.from_user.id)
    await message.answer("🛑 Игра отменена.")


@dp.message()
async def mini_game_answer_handler(message: Message) -> None:
    if message.from_user is None or not (message.text or "").strip():
        return
    if (message.text or "").startswith("/"):
        return
    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            pvp_match = await get_active_match(session, user.id)
            if pvp_match and pvp_match.status == "active":
                status, match = await submit_answer(session, pvp_match.id, user.id, message.text or "")
                if status == "correct":
                    await message.answer("✅ Ответ принят. Ждём соперника.")
                elif status == "wrong":
                    await message.answer("❌ Ответ неверный. Ждём соперника.")
                elif status == "already":
                    await message.answer("ℹ️ Ты уже ответил в этом соревновании.")
                elif status == "finished":
                    if match.status == "draw":
                        await record_game_result(session, user.id, result="draw", experience=20)
                        coins = await award_game_coins(session, user.id, game_kind="pvp", result="draw")
                        other_id = match.opponent_id if match.creator_id == user.id else match.creator_id
                        if other_id is not None:
                            await record_game_result(session, other_id, result="draw", experience=20)
                            await award_game_coins(session, other_id, game_kind="pvp", result="draw")
                        await message.answer(
                            f"🤝 <b>Ничья!</b> Оба игрока ответили одинаково.\\n"
                            f"✨ +20 XP\\n🪙 +{coins:.1f} монет"
                        )
                    else:
                        winner = await get_display_name(session, match.winner_id)
                        if match.winner_id == user.id:
                            await record_game_result(session, user.id, result="win", experience=50)
                            coins = await award_game_coins(session, user.id, game_kind="pvp", result="win")
                            await message.answer(
                                f"🏆 <b>Ты победил!</b>\\n✨ +50 XP\\n🪙 +{coins:.1f} монет"
                            )
                            loser_id = match.opponent_id if match.creator_id == user.id else match.creator_id
                            if loser_id is not None:
                                await record_game_result(session, loser_id, result="loss", experience=10)
                                await award_game_coins(session, loser_id, game_kind="pvp", result="loss")
                        else:
                            await message.answer(f"🏁 <b>Соревнование завершено.</b>\\nПобедитель: {winner}")
                            await record_game_result(session, user.id, result="loss", experience=10)
                            coins = await award_game_coins(session, user.id, game_kind="pvp", result="loss")
                            await message.answer(f"🪙 Награда за участие: +{coins:.1f} монет")
                elif status == "expired":
                    await message.answer("⏱ Соревнование истекло.")
                return
    except Exception as exc:
        print(f"[pvp] answer failed: {exc}", flush=True)

    game = get_game(message.from_user.id)
    if game is None:
        return

    status, finished_game, data = check_answer(message.from_user.id, message.text or "")
    if status == "invalid":
        await message.answer("❌ Некорректный формат ответа. Попробуй ещё раз.")
        return
    if status == "tower_progress":
        await message.answer(
            f"✅ Этаж {data['floor'] - 1} пройден!\n\n"
            f"{data['prompt']}\n\n"
            "🎯 Попыток на этаж: <b>2</b>",
            reply_markup=mini_back_keyboard(),
        )
        return

    if status in {"progress", "wrong"}:
        if status == "progress" and game.kind == "code":
            await message.answer(
                f"🔎 Точных совпадений: <b>{data['exact']}</b>\n"
                f"🟡 Частичных совпадений: <b>{data['partial']}</b>\n"
                f"🎯 Осталось попыток: <b>{data['attempts_left']}</b>"
            )
        else:
            await message.answer(f"❌ Неверно. Осталось попыток: <b>{data['attempts_left']}</b>")
        return

    if status == "win":
        xp = {"math": 40, "code": 65, "word": 50, "sequence": 70, "logic": 80, "anagram": 85, "tower": 90, "algorithm": 100, "counter": 80, "space": 95, "quiz": 60, "chain": 55}.get(finished_game.kind, 40)
        try:
            async for session in get_session():
                await record_game_result(session, message.from_user.id, result="win", experience=xp)
                coins = await award_game_coins(
                    session, message.from_user.id, game_kind=finished_game.kind, result="win"
                )
        except Exception as exc:
            coins = 0
            print(f"[minigame] win save failed: {exc}", flush=True)
        await message.answer(
            f"🏆 <b>Победа!</b>\n✨ +{xp} XP"
            + (f"\n🧱 Башня пройдена: <b>{data.get('floors', 0)}/5 этажей</b>" if finished_game.kind == "tower" else "")
            + "\n\nСыграй ещё раз и попробуй улучшить результат.",
            reply_markup=mini_games_keyboard(),
        )
        return

    if status == "loss":
        answer = data.get("answer", "неизвестен")
        try:
            async for session in get_session():
                await record_game_result(session, message.from_user.id, result="loss", experience=10)
                coins = await award_game_coins(
                    session, message.from_user.id, game_kind=finished_game.kind, result="loss"
                )
        except Exception as exc:
            coins = 0
            print(f"[minigame] loss save failed: {exc}", flush=True)
        await message.answer(
            f"💥 <b>Игра окончена.</b>\nПравильный ответ: <b>{answer}</b>\n"
            f"✨ +10 XP за попытку.\\n🪙 +{coins:.1f} монет.",
            reply_markup=mini_games_keyboard(),
        )


@dp.message(Command("game"))
async def game_handler(message: Message) -> None:
    if message.from_user is None:
        return

    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            profile = await get_game_profile(session, user.id)

        await message.answer(
            "🎮 <b>Игровой профиль</b>\n\n"
            f"👤 {user.first_name}\n"
            f"⭐ Уровень: <b>{profile.level}</b>\n"
            f"✨ Опыт: <b>{profile.experience}</b>\n"
            f"📈 До следующего уровня: <b>{profile.experience_to_next}</b>\n\n"
            f"🎯 Игр: <b>{profile.games_played}</b>\n"
            f"🏆 Побед: <b>{profile.wins}</b>\n"
            f"💠 Поражений: <b>{profile.losses}</b>\n"
            f"🤝 Ничьих: <b>{profile.draws}</b>"
        )
    except Exception as exc:
        print(f"[game] profile failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить игровой профиль.")


@dp.message(Command("gametop"))
async def game_top_handler(message: Message) -> None:
    try:
        async for session in get_session():
            rows = await get_game_leaderboard(session, 10)

        if not rows:
            await message.answer("🎮 Пока никто не играл.")
            return

        lines = ["🏆 <b>Топ игроков</b>", ""]
        for index, (_, name, level, experience) in enumerate(rows, 1):
            lines.append(f"{index}. {name} — ур. <b>{level}</b> · {experience} XP")
        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[game] leaderboard failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить топ игроков.")


@dp.message(Command("profile"))
async def profile_handler(message: Message) -> None:
    if message.from_user is None:
        return

    if not os.getenv("DATABASE_URL", "").strip():
        await message.answer("🗄 База данных пока не настроена.")
        return

    try:
        async for session in get_session():
            user, _ = await sync_telegram_user(session, message.from_user)
            text = format_user_profile(user)
        await message.answer(text)
    except Exception as exc:
        print(f"[db] profile load failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить профиль. Попробуй ещё раз.")


@dp.message(Command("find"))
async def find_handler(message: Message) -> None:
    if message.from_user is None:
        return

    query = (message.text or "").split(maxsplit=1)
    search = query[1].strip() if len(query) > 1 else None

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            users = await find_users(session, current.id, search)

        if not users:
            await message.answer("🔎 Никого не нашёл. Попробуй другой запрос.")
            return

        lines = ["🔎 <b>Люди</b>", ""]
        for user in users:
            lines.append(format_social_user(user))
        lines.append("")
        lines.append("Чтобы отправить заявку: <code>/addfriend @username</code>")
        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[social] find failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось выполнить поиск.")


@dp.message(Command("addfriend"))
async def add_friend_handler(message: Message) -> None:
    if message.from_user is None:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: <code>/addfriend @username</code>")
        return

    username = parts[1].strip().split()[0]

    try:
        async for session in get_session():
            sender, _ = await sync_telegram_user(session, message.from_user)
            target = await get_user_by_username(session, username)

            if target is None:
                result = "not_found"
            else:
                result = await send_friend_request(session, sender.id, target.id)

        responses = {
            "not_found": "❌ Пользователь не найден.",
            "self": "🙂 Нельзя добавить самого себя.",
            "unavailable": "❌ Пользователь недоступен.",
            "friends": "👥 Вы уже друзья.",
            "outgoing": "📨 Заявка уже отправлена.",
            "incoming": "📨 Этот пользователь уже отправил тебе заявку. Используй /requests.",
            "created": "✅ Заявка в друзья отправлена.",
        }
        await message.answer(responses.get(result, "⚠️ Не удалось отправить заявку."))
    except Exception as exc:
        print(f"[social] add friend failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось отправить заявку.")


@dp.message(Command("requests"))
async def requests_handler(message: Message) -> None:
    if message.from_user is None:
        return

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            requests = await list_incoming_requests(session, current.id)

        if not requests:
            await message.answer("📨 Новых заявок в друзья нет.")
            return

        lines = ["📨 <b>Заявки в друзья</b>", ""]
        for _, user in requests:
            name = " ".join(p for p in (user.first_name, user.last_name) if p)
            username = f"@{user.username}" if user.username else "без username"
            lines.append(f"👤 <b>{name}</b> — {username}")
        lines.extend([
            "",
            "Принять: <code>/accept @username</code>",
            "Отклонить: <code>/decline @username</code>",
        ])
        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[social] requests failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить заявки.")


@dp.message(Command("accept"))
async def accept_handler(message: Message) -> None:
    await _respond_to_request(message, True)


@dp.message(Command("decline"))
async def decline_handler(message: Message) -> None:
    await _respond_to_request(message, False)


async def _respond_to_request(message: Message, accept: bool) -> None:
    if message.from_user is None:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажи username: <code>/accept @username</code>")
        return

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            sender = await get_user_by_username(session, parts[1].strip().split()[0])
            if sender is None:
                result = "missing"
            else:
                result = await respond_to_request(session, current.id, sender.id, accept)

        if result == "missing":
            await message.answer("❌ Такая заявка не найдена.")
        elif accept:
            await message.answer("🤝 Заявка принята. Теперь вы друзья!")
        else:
            await message.answer("❌ Заявка отклонена.")
    except Exception as exc:
        print(f"[social] request response failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось обработать заявку.")


@dp.message(Command("friends"))
async def friends_handler(message: Message) -> None:
    if message.from_user is None:
        return

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            friends = await list_friends(session, current.id)

        if not friends:
            await message.answer("👥 Друзей пока нет. Используй /find.")
            return

        lines = ["👥 <b>Твои друзья</b>", ""]
        for user in friends:
            lines.append(format_social_user(user))
        lines.extend(["", "Удалить: <code>/removefriend @username</code>"])
        await message.answer("\n".join(lines))
    except Exception as exc:
        print(f"[social] friends failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось загрузить список друзей.")


@dp.message(Command("removefriend"))
async def remove_friend_handler(message: Message) -> None:
    if message.from_user is None:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: <code>/removefriend @username</code>")
        return

    try:
        async for session in get_session():
            current, _ = await sync_telegram_user(session, message.from_user)
            target = await get_user_by_username(session, parts[1].strip().split()[0])
            removed = False if target is None else await remove_friend(session, current.id, target.id)

        await message.answer(
            "✅ Пользователь удалён из друзей." if removed else "❌ Такого друга нет."
        )
    except Exception as exc:
        print(f"[social] remove friend failed: {exc}", flush=True)
        await message.answer("⚠️ Не удалось удалить друга.")




async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть меню"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="game", description="Игровой профиль"),
            BotCommand(command="gametop", description="Топ игроков"),
            BotCommand(command="games", description="Мини-игры"),
            BotCommand(command="balance", description="Баланс монет"),
            BotCommand(command="daily", description="Ежедневная награда"),
            BotCommand(command="shop", description="Магазин"),
            BotCommand(command="inventory", description="Мои предметы"),
            BotCommand(command="coinhistory", description="История монет"),
            BotCommand(command="gift", description="Подарить предмет"),
            BotCommand(command="profile", description="Мой профиль"),
            BotCommand(command="rep", description="Моя репутация"),
            BotCommand(command="toprep", description="Топ репутации"),
            BotCommand(command="rules", description="Правила сообщества"),
            BotCommand(command="find", description="Найти участника"),
            BotCommand(command="friends", description="Друзья"),
        ],
        scope=BotCommandScopeDefault(),
    )


async def main() -> None:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    proxy = os.getenv("TELEGRAM_PROXY", "").strip() or None
    session = AiohttpSession(proxy=proxy)

    bot = Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    print("========================================", flush=True)
    print(" WhiteBelStudio Bot", flush=True)
    print("========================================", flush=True)
    print(f"[bot] Telegram proxy: {'enabled' if proxy else 'disabled'}", flush=True)

    if os.getenv("DATABASE_URL", "").strip():
        try:
            await check_database_connection()
            print("[db] PostgreSQL: OK", flush=True)
        except Exception as exc:
            print(f"[db] PostgreSQL: unavailable ({exc})", flush=True)
    else:
        print("[db] DATABASE_URL: not configured", flush=True)

    try:
        await setup_bot_commands(bot)
        print("[bot] Command menu: configured", flush=True)
        print("[bot] Starting polling...", flush=True)
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())