from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Friendship, MessageRecord, User


def _pair(left_id: int, right_id: int) -> tuple[int, int]:
    return (left_id, right_id) if left_id < right_id else (right_id, left_id)


async def get_conversation(session: AsyncSession, left_id: int, right_id: int) -> Conversation | None:
    low, high = _pair(left_id, right_id)
    result = await session.execute(
        select(Conversation).where(
            Conversation.user_low_id == low,
            Conversation.user_high_id == high,
        )
    )
    return result.scalar_one_or_none()


async def _are_friends(session: AsyncSession, left_id: int, right_id: int) -> bool:
    low, high = _pair(left_id, right_id)
    result = await session.execute(
        select(Friendship.id).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
        )
    )
    return result.scalar_one_or_none() is not None


async def send_message(
    session: AsyncSession,
    sender_id: int,
    recipient_id: int,
    text: str,
) -> tuple[str, MessageRecord | None]:
    text = text.strip()

    if sender_id == recipient_id:
        return "self", None

    if not text:
        return "empty", None

    if len(text) > 4000:
        return "too_long", None

    recipient = await session.get(User, recipient_id)
    if recipient is None or not recipient.is_active or recipient.is_bot:
        return "unavailable", None

    if not await _are_friends(session, sender_id, recipient_id):
        return "not_friends", None

    conversation = await get_conversation(session, sender_id, recipient_id)
    if conversation is None:
        low, high = _pair(sender_id, recipient_id)
        conversation = Conversation(user_low_id=low, user_high_id=high)
        session.add(conversation)
        await session.flush()

    record = MessageRecord(
        conversation_id=conversation.id,
        sender_id=sender_id,
        text=text,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return "sent", record


async def get_messages(
    session: AsyncSession,
    user_id: int,
    other_id: int,
    limit: int = 20,
) -> list[MessageRecord]:
    conversation = await get_conversation(session, user_id, other_id)
    if conversation is None:
        return []

    result = await session.execute(
        select(MessageRecord)
        .where(MessageRecord.conversation_id == conversation.id)
        .order_by(MessageRecord.created_at.desc())
        .limit(max(1, min(limit, 50)))
    )
    messages = list(result.scalars().all())

    now = datetime.now(timezone.utc)
    for item in messages:
        if item.sender_id == other_id and item.read_at is None:
            item.read_at = now
    await session.commit()

    return list(reversed(messages))


def format_message(item: MessageRecord, current_user_id: int) -> str:
    marker = "➡️" if item.sender_id == current_user_id else "⬅️"
    return f"{marker} {item.text}"
