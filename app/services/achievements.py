from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Achievement, CoinTransaction, Conversation, EconomyAccount, GameProfile, MessageRecord, PvpMatch, ReputationEvent, CommunityReputationVote, UserAchievement

@dataclass(frozen=True, slots=True)
class AchievementSpec:
    code: str
    name: str
    description: str
    target: int
    metric: str

ACHIEVEMENTS = (
    AchievementSpec("first_game", "🎮 Первый шаг", "Сыграть первую игру", 1, "games"),
    AchievementSpec("ten_games", "🎯 Десяточка", "Сыграть 10 игр", 10, "games"),
    AchievementSpec("first_win", "🏆 Первая победа", "Одержать первую победу", 1, "wins"),
    AchievementSpec("ten_wins", "🔥 Победная серия", "Одержать 10 побед", 10, "wins"),
    AchievementSpec("fifty_wins", "👑 Чемпион", "Одержать 50 побед", 50, "wins"),
    AchievementSpec("level_5", "⭐ Опытный игрок", "Достичь 5 уровня", 5, "level"),
    AchievementSpec("level_10", "💎 Ветеран", "Достичь 10 уровня", 10, "level"),
    AchievementSpec("games_25", "🎮 Игровой разгон", "Достичь 25 по показателю «games»", 25, "games"),
    AchievementSpec("games_50", "🎮 Игровой ветеран", "Достичь 50 по показателю «games»", 50, "games"),
    AchievementSpec("games_100", "🎮 Игровой марафон", "Достичь 100 по показателю «games»", 100, "games"),
    AchievementSpec("games_250", "🎮 Большой игрок", "Достичь 250 по показателю «games»", 250, "games"),
    AchievementSpec("games_500", "🎮 Игровая история", "Достичь 500 по показателю «games»", 500, "games"),
    AchievementSpec("games_1000", "🎮 Игровая эпоха", "Достичь 1000 по показателю «games»", 1000, "games"),
    AchievementSpec("wins_5", "🏆 Победитель", "Достичь 5 по показателю «wins»", 5, "wins"),
    AchievementSpec("wins_25", "🏆 Опытный чемпион", "Достичь 25 по показателю «wins»", 25, "wins"),
    AchievementSpec("wins_100", "🏆 Ветеран побед", "Достичь 100 по показателю «wins»", 100, "wins"),
    AchievementSpec("wins_250", "🏆 Гроза соперников", "Достичь 250 по показателю «wins»", 250, "wins"),
    AchievementSpec("wins_500", "🏆 Великий чемпион", "Достичь 500 по показателю «wins»", 500, "wins"),
    AchievementSpec("wins_1000", "🏆 Легендарный победитель", "Достичь 1000 по показателю «wins»", 1000, "wins"),
    AchievementSpec("wins_2500", "🏆 Зал славы", "Достичь 2500 по показателю «wins»", 2500, "wins"),
    AchievementSpec("losses_10", "💠 Первые испытания", "Достичь 10 по показателю «losses»", 10, "losses"),
    AchievementSpec("losses_50", "💠 Стойкость", "Достичь 50 по показателю «losses»", 50, "losses"),
    AchievementSpec("draws_1", "🤝 Первая ничья", "Достичь 1 по показателю «draws»", 1, "draws"),
    AchievementSpec("draws_10", "🤝 Мирный игрок", "Достичь 10 по показателю «draws»", 10, "draws"),
    AchievementSpec("draws_50", "🤝 Мастер ничьих", "Достичь 50 по показателю «draws»", 50, "draws"),
    AchievementSpec("level_15", "⭐ Продвинутый игрок", "Достичь 15 по показателю «level»", 15, "level"),
    AchievementSpec("level_20", "⭐ Мастер уровня", "Достичь 20 по показателю «level»", 20, "level"),
    AchievementSpec("level_30", "💎 Высшая лига", "Достичь 30 по показателю «level»", 30, "level"),
    AchievementSpec("level_50", "💎 Элита", "Достичь 50 по показателю «level»", 50, "level"),
    AchievementSpec("level_100", "💎 Вершина", "Достичь 100 по показателю «level»", 100, "level"),
    AchievementSpec("xp_100", "⭐ Первые очки", "Достичь 100 по показателю «xp»", 100, "xp"),
    AchievementSpec("xp_250", "⭐ Начинающий", "Достичь 250 по показателю «xp»", 250, "xp"),
    AchievementSpec("xp_500", "⭐ Опытный", "Достичь 500 по показателю «xp»", 500, "xp"),
    AchievementSpec("xp_1000", "⭐ Мастер XP", "Достичь 1000 по показателю «xp»", 1000, "xp"),
    AchievementSpec("xp_2500", "⭐ Большой опыт", "Достичь 2500 по показателю «xp»", 2500, "xp"),
    AchievementSpec("xp_5000", "⭐ Опытный ветеран", "Достичь 5000 по показателю «xp»", 5000, "xp"),
    AchievementSpec("xp_10000", "⭐ Ветеран", "Достичь 10000 по показателю «xp»", 10000, "xp"),
    AchievementSpec("xp_25000", "⭐ Гранд-мастер", "Достичь 25000 по показателю «xp»", 25000, "xp"),
    AchievementSpec("xp_50000", "⭐ Легенда XP", "Достичь 50000 по показателю «xp»", 50000, "xp"),
    AchievementSpec("xp_100000", "⭐ Абсолютный опыт", "Достичь 100000 по показателю «xp»", 100000, "xp"),
    AchievementSpec("messages_1", "💬 Первое сообщение", "Достичь 1 по показателю «messages»", 1, "messages"),
    AchievementSpec("messages_50", "💬 Болтун", "Достичь 50 по показателю «messages»", 50, "messages"),
    AchievementSpec("messages_100", "💬 Активист", "Достичь 100 по показателю «messages»", 100, "messages"),
    AchievementSpec("messages_250", "💬 Разговорчивый", "Достичь 250 по показателю «messages»", 250, "messages"),
    AchievementSpec("messages_500", "💬 Постоянный участник", "Достичь 500 по показателю «messages»", 500, "messages"),
    AchievementSpec("messages_1000", "💬 Частый собеседник", "Достичь 1000 по показателю «messages»", 1000, "messages"),
    AchievementSpec("messages_2500", "💬 Голос сообщества", "Достичь 2500 по показателю «messages»", 2500, "messages"),
    AchievementSpec("messages_5000", "💬 Легенда чата", "Достичь 5000 по показателю «messages»", 5000, "messages"),
    AchievementSpec("messages_10000", "💬 История чата", "Достичь 10000 по показателю «messages»", 10000, "messages"),
    AchievementSpec("messages_25000", "💬 Энциклопедия общения", "Достичь 25000 по показателю «messages»", 25000, "messages"),
    AchievementSpec("conversations_1", "🤝 Первый диалог", "Достичь 1 по показателю «conversations»", 1, "conversations"),
    AchievementSpec("conversations_5", "🤝 Собеседник", "Достичь 5 по показателю «conversations»", 5, "conversations"),
    AchievementSpec("conversations_10", "🤝 Общительный", "Достичь 10 по показателю «conversations»", 10, "conversations"),
    AchievementSpec("conversations_25", "🤝 Своя компания", "Достичь 25 по показателю «conversations»", 25, "conversations"),
    AchievementSpec("conversations_50", "🤝 Большой круг общения", "Достичь 50 по показателю «conversations»", 50, "conversations"),
    AchievementSpec("friends_1", "👥 Первый друг", "Достичь 1 по показателю «friends»", 1, "friends"),
    AchievementSpec("friends_3", "👥 Компания", "Достичь 3 по показателю «friends»", 3, "friends"),
    AchievementSpec("friends_5", "👥 Своя тусовка", "Достичь 5 по показателю «friends»", 5, "friends"),
    AchievementSpec("friends_10", "👥 Общительная сеть", "Достичь 10 по показателю «friends»", 10, "friends"),
    AchievementSpec("friends_25", "👥 Большой круг", "Достичь 25 по показателю «friends»", 25, "friends"),
    AchievementSpec("friends_50", "👥 Знакомый всем", "Достичь 50 по показателю «friends»", 50, "friends"),
    AchievementSpec("friends_100", "👥 Социальная сеть", "Достичь 100 по показателю «friends»", 100, "friends"),
    AchievementSpec("reputation_1", "🛡️ Первая репутация", "Достичь 1 по показателю «reputation»", 1, "reputation"),
    AchievementSpec("reputation_10", "🛡️ Уважаемый", "Достичь 10 по показателю «reputation»", 10, "reputation"),
    AchievementSpec("reputation_25", "🛡️ Надёжный", "Достичь 25 по показателю «reputation»", 25, "reputation"),
    AchievementSpec("reputation_50", "🛡️ Авторитет", "Достичь 50 по показателю «reputation»", 50, "reputation"),
    AchievementSpec("reputation_100", "🛡️ Высокая репутация", "Достичь 100 по показателю «reputation»", 100, "reputation"),
    AchievementSpec("rep_voters_5", "🛡️ Голос сообщества", "Достичь 5 по показателю «rep_voters»", 5, "rep_voters"),
    AchievementSpec("rep_voters_10", "🛡️ Доверие", "Достичь 10 по показателю «rep_voters»", 10, "rep_voters"),
    AchievementSpec("rep_voters_25", "🛡️ Уважаемый участник", "Достичь 25 по показателю «rep_voters»", 25, "rep_voters"),
    AchievementSpec("balance_100", "💰 Накопитель", "Достичь 100 по показателю «balance»", 100, "balance"),
    AchievementSpec("balance_500", "💰 Копилка", "Достичь 500 по показателю «balance»", 500, "balance"),
    AchievementSpec("balance_1000", "💰 Богач", "Достичь 1000 по показателю «balance»", 1000, "balance"),
    AchievementSpec("balance_5000", "💰 Казначей", "Достичь 5000 по показателю «balance»", 5000, "balance"),
    AchievementSpec("lifetime_earned_1000", "💰 Первые накопления", "Достичь 1000 по показателю «lifetime_earned»", 1000, "lifetime_earned"),
    AchievementSpec("lifetime_earned_5000", "💰 Большой заработок", "Достичь 5000 по показателю «lifetime_earned»", 5000, "lifetime_earned"),
    AchievementSpec("lifetime_spent_1000", "🛍️ Первые траты", "Достичь 1000 по показателю «lifetime_spent»", 1000, "lifetime_spent"),
    AchievementSpec("transactions_100", "💳 Активный кошелёк", "Достичь 100 по показателю «transactions»", 100, "transactions"),
    AchievementSpec("pvp_matches_1", "⚔️ Первый PvP", "Достичь 1 по показателю «pvp_matches»", 1, "pvp_matches"),
    AchievementSpec("pvp_matches_10", "⚔️ PvP-игрок", "Достичь 10 по показателю «pvp_matches»", 10, "pvp_matches"),
    AchievementSpec("pvp_matches_25", "⚔️ PvP-соперник", "Достичь 25 по показателю «pvp_matches»", 25, "pvp_matches"),
    AchievementSpec("pvp_matches_50", "⚔️ PvP-ветеран", "Достичь 50 по показателю «pvp_matches»", 50, "pvp_matches"),
    AchievementSpec("pvp_wins_1", "⚔️ Первая PvP-победа", "Достичь 1 по показателю «pvp_wins»", 1, "pvp_wins"),
    AchievementSpec("pvp_wins_10", "⚔️ PvP-чемпион", "Достичь 10 по показателю «pvp_wins»", 10, "pvp_wins"),
    AchievementSpec("pvp_wins_25", "⚔️ PvP-мастер", "Достичь 25 по показателю «pvp_wins»", 25, "pvp_wins"),
    AchievementSpec("pvp_wins_50", "⚔️ PvP-ветеран", "Достичь 50 по показателю «pvp_wins»", 50, "pvp_wins"),
    AchievementSpec("pvp_opponents_10", "⚔️ Круг соперников", "Достичь 10 по показателю «pvp_opponents»", 10, "pvp_opponents"),
    AchievementSpec("active_days_3", "📅 Возвращайся", "Достичь 3 по показателю «active_days»", 3, "active_days"),
    AchievementSpec("active_days_7", "📅 Неделя в деле", "Достичь 7 по показателю «active_days»", 7, "active_days"),
    AchievementSpec("active_days_30", "📅 Месяц в деле", "Достичь 30 по показателю «active_days»", 30, "active_days"),
    AchievementSpec("multi_games_wins", "🎯 Универсальный чемпион", "Сыграть минимум 3 игры и одержать победу", 3, "multi_games_wins"),
    AchievementSpec("social_gamer", "🎮 Социальный игрок", "Сыграть минимум 10 игр и иметь друга", 10, "social_gamer"),
    AchievementSpec("gamer_rep", "🏆 Уважаемый игрок", "Сыграть минимум 25 игр и иметь 10 репутации", 25, "gamer_rep"),
    AchievementSpec("rich_gamer", "💰 Игрок с капиталом", "Сыграть минимум 50 игр и иметь 500 монет", 50, "rich_gamer"),
    AchievementSpec("pvp_social", "⚔️ Командный дух", "Сыграть PvP и иметь минимум 3 друзей", 3, "pvp_social"),
    AchievementSpec("collector_25", "🏅 Коллекционер", "Получить 25 других достижений", 25, "earned_achievements"),
    AchievementSpec("collector_50", "🏅 Большой коллекционер", "Получить 50 других достижений", 50, "earned_achievements"),
    AchievementSpec("collector_75", "🏅 Мастер достижений", "Получить 75 других достижений", 75, "earned_achievements"),
    AchievementSpec("collector_90", "🏅 Почти всё", "Получить 90 других достижений", 90, "earned_achievements"),
    AchievementSpec("collector_99", "🏅 Почти полный набор", "Получить 99 других достижений", 99, "earned_achievements"),
)

async def ensure_achievements(session: AsyncSession) -> None:
    if len(ACHIEVEMENTS) != 100: raise RuntimeError(f"Achievement catalog must contain exactly 100 items, got {len(ACHIEVEMENTS)}")
    codes=[a.code for a in ACHIEVEMENTS]
    if len(codes)!=len(set(codes)): raise RuntimeError("Achievement catalog contains duplicate codes")
    existing={r.code:r for r in (await session.execute(select(Achievement))).scalars().all()}
    for spec in ACHIEVEMENTS:
        row=existing.get(spec.code)
        if row is None: session.add(Achievement(code=spec.code,name=spec.name,description=spec.description,target=spec.target,is_active=True))
        else:
            row.name=spec.name; row.description=spec.description; row.target=spec.target; row.is_active=True
    for row in existing.values():
        if row.code not in set(codes): row.is_active=False
    await session.flush()

async def _metrics(session: AsyncSession,user_id:int)->dict[str,int]:
    p=(await session.execute(select(GameProfile).where(GameProfile.user_id==user_id))).scalar_one_or_none()
    a=(await session.execute(select(EconomyAccount).where(EconomyAccount.user_id==user_id))).scalar_one_or_none()
    scalar=lambda stmt: session.scalar(stmt)
    return {
        "games":p.games_played if p else 0,"wins":p.wins if p else 0,"losses":p.losses if p else 0,"draws":p.draws if p else 0,"level":p.level if p else 0,"xp":p.experience if p else 0,
        "messages":int(await scalar(select(func.count(MessageRecord.id)).where(MessageRecord.sender_id==user_id)) or 0),
        "conversations":int(await scalar(select(func.count(Conversation.id)).where(or_(Conversation.user_low_id==user_id,Conversation.user_high_id==user_id))) or 0),
        "friends":int(await scalar(select(func.count(Friendship.id)).where(or_(Friendship.user_low_id==user_id,Friendship.user_high_id==user_id))) or 0),
        "reputation":int(await scalar(select(func.coalesce(func.sum(ReputationEvent.delta),0)).where(ReputationEvent.user_id==user_id)) or 0),
        "rep_voters":int(await scalar(select(func.count(func.distinct(CommunityReputationVote.rater_id))).where(CommunityReputationVote.rated_id==user_id)) or 0),
        "balance":int(a.balance) if a else 0,"lifetime_earned":int(a.lifetime_earned) if a else 0,"lifetime_spent":int(a.lifetime_spent) if a else 0,
        "transactions":int(await scalar(select(func.count(CoinTransaction.id)).where(CoinTransaction.user_id==user_id)) or 0),
        "pvp_matches":int(await scalar(select(func.count(PvpMatch.id)).where(or_(PvpMatch.creator_id==user_id,PvpMatch.opponent_id==user_id))) or 0),
        "pvp_wins":int(await scalar(select(func.count(PvpMatch.id)).where(PvpMatch.winner_id==user_id)) or 0),
        "pvp_opponents":int(await scalar(select(func.count(func.distinct(case((PvpMatch.creator_id==user_id,PvpMatch.opponent_id),else_=PvpMatch.creator_id)))).where(or_(PvpMatch.creator_id==user_id,PvpMatch.opponent_id==user_id),PvpMatch.opponent_id.is_not(None))) or 0),
        "active_days":int(await scalar(select(func.count(func.distinct(func.date(MessageRecord.created_at)))).where(MessageRecord.sender_id==user_id)) or 0),
        "earned_achievements":int(await scalar(select(func.count(UserAchievement.id)).where(UserAchievement.user_id==user_id)) or 0)}

def _unlocked(s:AchievementSpec,m:dict[str,int])->bool:
    if s.metric in m: return m[s.metric]>=s.target
    return {"multi_games_wins":m["games"]>=3 and m["wins"]>=1,"rich_gamer":m["games"]>=50 and m["balance"]>=500}.get(s.metric,False)

async def check_and_unlock_achievements(session:AsyncSession,user_id:int)->list[AchievementSpec]:
    await ensure_achievements(session); m=await _metrics(session,user_id)
    rows=(await session.execute(select(Achievement,UserAchievement).outerjoin(UserAchievement,(UserAchievement.achievement_id==Achievement.id)&(UserAchievement.user_id==user_id)).where(Achievement.is_active.is_(True)))).all()
    specs={a.code:a for a in ACHIEVEMENTS}; unlocked=[]
    for a,ua in rows:
        s=specs.get(a.code)
        if s and ua is None and _unlocked(s,m):
            session.add(UserAchievement(user_id=user_id,achievement_id=a.id)); unlocked.append(s)
    if unlocked: await session.commit()
    else: await session.flush()
    return unlocked

async def list_user_achievements(session:AsyncSession,user_id:int)->tuple[list[AchievementSpec],list[AchievementSpec]]:
    await ensure_achievements(session); await session.commit()
    earned=set((await session.execute(select(Achievement.code).join(UserAchievement,UserAchievement.achievement_id==Achievement.id).where(UserAchievement.user_id==user_id))).scalars().all())
    return ([a for a in ACHIEVEMENTS if a.code in earned],[a for a in ACHIEVEMENTS if a.code not in earned])

async def get_achievement_progress(session:AsyncSession,user_id:int)->dict[str,tuple[int,int]]:
    await ensure_achievements(session); m=await _metrics(session,user_id)
    earned=set((await session.execute(select(Achievement.code).join(UserAchievement,UserAchievement.achievement_id==Achievement.id).where(UserAchievement.user_id==user_id))).scalars().all())
    out={}
    for s in ACHIEVEMENTS:
        value=m.get(s.metric,s.target if _unlocked(s,m) else 0)
        out[s.code]=(s.target if s.code in earned else min(value,s.target),s.target)
    return out
