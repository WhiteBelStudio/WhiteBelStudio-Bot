from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMemberStats, CommunityChat, User


async def get_or_create_chat(
    session: AsyncSession,
    telegram_chat_id: int,
    title: str,
    chat_type: str,
) -> CommunityChat:
    result = await session.execute(
        select(CommunityChat).where(CommunityChat.telegram_chat_id == telegram_chat_id)
    )
    chat = result.scalar_one_or_none()

    if chat is None:
        chat = CommunityChat(
            telegram_chat_id=telegram_chat_id,
            title=(title or "Без названия")[:255],
            chat_type=chat_type[:32],
        )
        session.add(chat)
        await session.flush()
    else:
        chat.title = (title or chat.title or "Без названия")[:255]
        chat.chat_type = chat_type[:32]
        chat.is_active = True

    return chat


async def ensure_member(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
) -> ChatMemberStats:
    result = await session.execute(
        select(ChatMemberStats).where(
            ChatMemberStats.chat_id == chat_id,
            ChatMemberStats.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()

    if member is None:
        member = ChatMemberStats(chat_id=chat_id, user_id=user_id)
        session.add(member)
        await session.flush()

    return member


async def record_chat_activity(
    session: AsyncSession,
    telegram_chat_id: int,
    title: str,
    chat_type: str,
    user: User,
    *,
    is_command: bool = False,
) -> None:
    chat = await get_or_create_chat(session, telegram_chat_id, title, chat_type)
    member = await ensure_member(session, chat.id, user.id)

    now = datetime.now(timezone.utc)
    member.message_count += 1
    if is_command:
        member.command_count += 1
    member.last_message_at = now
    member.updated_at = now

    await session.commit()


async def get_chat_stats(
    session: AsyncSession,
    telegram_chat_id: int,
) -> tuple[CommunityChat | None, int, int]:
    chat_result = await session.execute(
        select(CommunityChat).where(CommunityChat.telegram_chat_id == telegram_chat_id)
    )
    chat = chat_result.scalar_one_or_none()
    if chat is None:
        return None, 0, 0

    member_count_result = await session.execute(
        select(func.count(ChatMemberStats.id)).where(ChatMemberStats.chat_id == chat.id)
    )
    message_count_result = await session.execute(
        select(func.coalesce(func.sum(ChatMemberStats.message_count), 0)).where(
            ChatMemberStats.chat_id == chat.id
        )
    )

    return (
        chat,
        int(member_count_result.scalar_one() or 0),
        int(message_count_result.scalar_one() or 0),
    )


async def get_member_stats(
    session: AsyncSession,
    telegram_chat_id: int,
    user_id: int,
) -> ChatMemberStats | None:
    result = await session.execute(
        select(ChatMemberStats)
        .join(CommunityChat, CommunityChat.id == ChatMemberStats.chat_id)
        .where(
            CommunityChat.telegram_chat_id == telegram_chat_id,
            ChatMemberStats.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()
