"""Unified games router: mini-games and PvP."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.engine import get_session
from app.services.achievements import check_and_unlock_achievements
from app.services.economy import award_game_coins
from app.services.games import get_game_leaderboard, get_game_profile, record_game_result
from app.services.minigames import cancel_game, check_answer, game_catalog_text, get_game, start_game
from app.services.pvp import PVP_KINDS, accept_challenge, create_challenge, decline_challenge, get_active_match, get_display_name, submit_answer
from app.services.users import sync_telegram_user

router = Router(name="games")

def games_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚔️ PvP", callback_data="games:pvp"),
        InlineKeyboardButton(text="🎮 Мини-игры", callback_data="games:mini"),
    ]])

def regular_games_keyboard():
    rows = [
        [("🧮 Штурм","math"),("🔐 Взломщик","code")],
        [("🔤 Шифровальщик","word")],
        [("🔢 Последовательность","sequence"),("🧩 Логика","logic")],
        [("🔀 Анаграмма PRO","anagram")],
        [("🧱 Башня","tower"),("🧪 Алгоритм","algorithm")],
        [("🧮 Счётчик","counter"),("🌌 Космический маршрут","space")],
        [("🏆 Викторина","quiz"),("🔤 Словесная цепочка","chain")],
    ]
    keyboard=[[InlineKeyboardButton(text=t,callback_data=f"game:start:{k}") for t,k in row] for row in rows]
    keyboard.append([InlineKeyboardButton(text="⬅️ К играм",callback_data="games")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def pvp_games_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Математика",callback_data="pvp:create:math")],
        [InlineKeyboardButton(text="🔢 Последовательность",callback_data="pvp:create:sequence")],
        [InlineKeyboardButton(text="🏆 Викторина",callback_data="pvp:create:quiz")],
        [InlineKeyboardButton(text="⬅️ К играм",callback_data="games")],
    ])

def pvp_challenge_keyboard(match_id:int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚔️ Принять вызов",callback_data=f"pvp:accept:{match_id}"),
        InlineKeyboardButton(text="❌ Отклонить",callback_data=f"pvp:decline:{match_id}"),
    ]])

def mini_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕹 Все мини-игры",callback_data="games:mini")]
    ])

async def show_games(message:Message,edit=False):
    text="🎮 <b>Игры</b>\n\nВыбери режим:"
    if edit: await message.edit_text(text,reply_markup=games_keyboard())
    else: await message.answer(text,reply_markup=games_keyboard())

async def show_mini_games(message:Message,edit=False):
    if edit: await message.edit_text(game_catalog_text(),reply_markup=regular_games_keyboard())
    else: await message.answer(game_catalog_text(),reply_markup=regular_games_keyboard())

async def show_pvp_category(message:Message,edit=False):
    text=("⚔️ <b>PvP</b>\n\nВыбери режим соревнования. Оба участника решают одну задачу.\n"
          "⏱ Вызов действует 5 минут.\n🏆 Победа — по результату ответа.\n"
          "🪙 Ставок нет: только игра, XP и награды.")
    if edit: await message.edit_text(text,reply_markup=pvp_games_keyboard())
    else: await message.answer(text,reply_markup=pvp_games_keyboard())

async def send_pvp_challenge(message:Message,kind:str):
    if message.from_user is None:return
    try:
        async for session in get_session():
            user,_=await sync_telegram_user(session,message.from_user)
            match=await create_challenge(session,user.id,kind)
            name=f"@{user.username}" if user.username else user.first_name
    except ValueError as exc:
        errors={"active_match":"⚠️ У тебя уже есть активное соревнование.","unknown pvp kind":"⚠️ Этот режим PvP недоступен."}
        await message.answer(errors.get(str(exc),"⚠️ Не удалось создать вызов."))
        return
    await message.answer(
        f"⚔️ <b>Вызов на PvP!</b>\n\n👤 От: <b>{name}</b>\n🎮 Игра: <b>{PVP_KINDS[kind]}</b>\n\n"
        f"Задача: {match.prompt}\n\nНажми «Принять вызов», чтобы начать.",
        reply_markup=pvp_challenge_keyboard(match.id))

async def pvp_callback(message:Message,action:str):
    if message.from_user is None:return
    try: match_id=int(action.rsplit(":",1)[1])
    except (ValueError,IndexError):
        await message.answer("⚠️ Некорректный вызов.");return
    try:
        async for session in get_session():
            user,_=await sync_telegram_user(session,message.from_user)
            if action.startswith("pvp:accept:"):
                match=await accept_challenge(session,match_id,user.id)
                await message.answer(f"⚔️ <b>PvP началось!</b>\n\n🎮 {PVP_KINDS[match.kind]}\n{match.prompt}\n\nОтправь ответ обычным сообщением.")
                return
            await decline_challenge(session,match_id,user.id)
            await message.answer("❌ Вызов отклонён.")
    except ValueError as exc:
        errors={"self":"⚠️ Нельзя принять собственный вызов.","active_match":"⚠️ У тебя уже есть активное соревнование.","creator":"⚠️ Создатель вызова не может отклонить его.","unavailable":"⚠️ Этот вызов уже недоступен."}
        await message.answer(errors.get(str(exc),"⚠️ Действие недоступно."))

async def start_mini_game(message:Message,kind:str):
    if message.from_user is None:return
    if get_game(message.from_user.id) is not None:
        await message.answer("⚠️ У тебя уже есть активная мини-игра. Закончи её или отправь /cancelgame.");return
    try: game=start_game(message.from_user.id,kind)
    except ValueError:
        await message.answer("⚠️ Такая мини-игра недоступна.");return
    await message.answer(f"🎮 <b>Игра началась!</b>\n\n{game.prompt}\n\n🎯 Попыток: <b>{game.attempts_left}</b>\nОтправь ответ обычным сообщением.",reply_markup=mini_back_keyboard())

async def finish_regular(message:Message,kind:str,result:str,xp:int,data:dict):
    coins=0
    try:
        async for session in get_session():
            await record_game_result(session,message.from_user.id,result=result,experience=xp)
            await check_and_unlock_achievements(session,message.from_user.id)
            coins=await award_game_coins(session,message.from_user.id,game_kind=kind,result=result)
    except Exception as exc: print(f"[minigame] result save failed: {exc}",flush=True)
    if result=="win":
        extra=f"\n🧱 Башня пройдена: <b>{data.get('floors',0)}/5 этажей</b>" if kind=="tower" else ""
        await message.answer(f"🏆 <b>Победа!</b>\n✨ +{xp} XP\n🪙 +{coins:.1f} монет{extra}\n\nСыграй ещё раз.",reply_markup=games_keyboard())
    else:
        await message.answer(f"💥 <b>Игра окончена.</b>\nПравильный ответ: <b>{data.get('answer','неизвестен')}</b>\n✨ +{xp} XP\n🪙 +{coins:.1f} монет.",reply_markup=games_keyboard())

async def finish_pvp(message:Message,session,user_id:int,match):
    if match.status=="draw":
        await record_game_result(session,user_id,result="draw",experience=20); await check_and_unlock_achievements(session,user_id)
        coins=await award_game_coins(session,user_id,game_kind="pvp",result="draw")
        other=match.opponent_id if match.creator_id==user_id else match.creator_id
        if other is not None:
            await record_game_result(session,other,result="draw",experience=20); await check_and_unlock_achievements(session,other); await award_game_coins(session,other,game_kind="pvp",result="draw")
        await message.answer(f"🤝 <b>Ничья!</b>\n✨ +20 XP\n🪙 +{coins:.1f} монет",reply_markup=games_keyboard()); return
    winner=await get_display_name(session,match.winner_id)
    if match.winner_id==user_id:
        await record_game_result(session,user_id,result="win",experience=50); await check_and_unlock_achievements(session,user_id)
        coins=await award_game_coins(session,user_id,game_kind="pvp",result="win")
        loser=match.opponent_id if match.creator_id==user_id else match.creator_id
        if loser is not None:
            await record_game_result(session,loser,result="loss",experience=10); await check_and_unlock_achievements(session,loser); await award_game_coins(session,loser,game_kind="pvp",result="loss")
        await message.answer(f"🏆 <b>Ты победил!</b>\n✨ +50 XP\n🪙 +{coins:.1f} монет",reply_markup=games_keyboard())
    else:
        await record_game_result(session,user_id,result="loss",experience=10); await check_and_unlock_achievements(session,user_id)
        coins=await award_game_coins(session,user_id,game_kind="pvp",result="loss")
        await message.answer(f"🏁 <b>Соревнование завершено.</b>\nПобедитель: {winner}\n🪙 Тебе: +{coins:.1f} монет",reply_markup=games_keyboard())

async def handle_game_answer(message:Message):
    if message.from_user is None or not (message.text or "").strip() or (message.text or "").startswith("/"): return False
    try:
        async for session in get_session():
            user,_=await sync_telegram_user(session,message.from_user)
            match=await get_active_match(session,user.id)
            if match and match.status=="active":
                status,match=await submit_answer(session,match.id,user.id,message.text or "")
                if status=="correct": await message.answer("✅ Ответ принят. Ждём соперника.")
                elif status=="wrong": await message.answer("❌ Ответ неверный. Ждём соперника.")
                elif status=="already": await message.answer("ℹ️ Ты уже ответил в этом соревновании.")
                elif status=="finished": await finish_pvp(message,session,user.id,match)
                elif status=="expired": await message.answer("⏱ Соревнование истекло.")
                return True
    except Exception as exc:
        print(f"[pvp] answer failed: {exc}",flush=True); return True
    game=get_game(message.from_user.id)
    if game is None:return False
    status,finished,data=check_answer(message.from_user.id,message.text or "")
    if status=="invalid": await message.answer("❌ Некорректный формат ответа. Попробуй ещё раз.")
    elif status=="tower_progress": await message.answer(f"✅ Этаж {data['floor']-1} пройден!\n\n{data['prompt']}\n\n🎯 Попыток на этаж: <b>2</b>",reply_markup=mini_back_keyboard())
    elif status in {"progress","wrong"}:
        if status=="progress" and game.kind=="code": await message.answer(f"🔎 Точных: <b>{data['exact']}</b>\n🟡 Частичных: <b>{data['partial']}</b>\n🎯 Осталось: <b>{data['attempts_left']}</b>")
        else: await message.answer(f"❌ Неверно. Осталось попыток: <b>{data['attempts_left']}</b>")
    elif status=="win":
        xp={"math":40,"code":65,"word":50,"sequence":70,"logic":80,"anagram":85,"tower":90,"algorithm":100,"counter":80,"space":95,"quiz":60,"chain":55}.get(finished.kind,40)
        await finish_regular(message,finished.kind,"win",xp,data)
    elif status=="loss": await finish_regular(message,finished.kind,"loss",10,data)
    return True

@router.callback_query(F.data=="games")
async def games_callback(callback:CallbackQuery):
    await show_games(callback.message,edit=True); await callback.answer()

@router.callback_query(F.data.in_({"games:mini","mini_games","mini_games:regular"}))
async def mini_callback(callback:CallbackQuery):
    await show_mini_games(callback.message,edit=True); await callback.answer()

@router.callback_query(F.data.in_({"games:pvp","mini_games:pvp"}))
async def pvp_menu_callback(callback:CallbackQuery):
    await show_pvp_category(callback.message,edit=True); await callback.answer()

@router.callback_query(F.data.startswith("game:start:"))
async def game_start_callback(callback:CallbackQuery):
    await start_mini_game(callback.message,callback.data.rsplit(":",1)[1]); await callback.answer()

@router.callback_query(F.data.startswith("pvp:create:"))
async def pvp_create_callback(callback:CallbackQuery):
    await send_pvp_challenge(callback.message,callback.data.rsplit(":",1)[1]); await callback.answer()

@router.callback_query(F.data.startswith("pvp:accept:") | F.data.startswith("pvp:decline:"))
async def pvp_action_callback(callback:CallbackQuery):
    await pvp_callback(callback.message,callback.data); await callback.answer()

@router.message(Command("games"))
async def games_command(message:Message): await show_games(message)

@router.message(Command("pvp"))
async def pvp_command(message:Message): await show_pvp_category(message)

@router.message(Command("cancelgame"))
async def cancelgame_command(message:Message):
    if message.from_user is None:return
    if get_game(message.from_user.id) is None: await message.answer("ℹ️ Активной игры нет."); return
    cancel_game(message.from_user.id); await message.answer("🛑 Игра отменена.")

@router.message(Command("game"))
async def game_command(message:Message):
    if message.from_user is None:return
    try:
        async for session in get_session():
            user,_=await sync_telegram_user(session,message.from_user); profile=await get_game_profile(session,user.id)
        await message.answer("🎮 <b>Игровой профиль</b>\n\n"+f"👤 {user.first_name}\n⭐ Уровень: <b>{profile.level}</b>\n✨ Опыт: <b>{profile.experience}</b>\n📈 До следующего уровня: <b>{profile.experience_to_next}</b>\n\n🎯 Игр: <b>{profile.games_played}</b>\n🏆 Побед: <b>{profile.wins}</b>\n💠 Поражений: <b>{profile.losses}</b>\n🤝 Ничьих: <b>{profile.draws}</b>")
    except Exception as exc: print(f"[game] profile failed: {exc}",flush=True); await message.answer("⚠️ Не удалось загрузить игровой профиль.")

@router.message(Command("gametop"))
async def gametop_command(message:Message):
    try:
        async for session in get_session(): rows=await get_game_leaderboard(session,10)
        if not rows: await message.answer("🎮 Пока никто не играл."); return
        lines=["🏆 <b>Топ игроков</b>",""]
        for i,(_,name,level,experience) in enumerate(rows,1): lines.append(f"{i}. {name} — ур. <b>{level}</b> · {experience} XP")
        await message.answer("\n".join(lines))
    except Exception as exc: print(f"[game] leaderboard failed: {exc}",flush=True); await message.answer("⚠️ Не удалось загрузить топ игроков.")

@router.message(F.text & ~F.text.startswith("/"))
async def game_answer_message(message:Message):
    await handle_game_answer(message)
