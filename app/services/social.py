from __future__ import annotations

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FriendRequest, Friendship, User


def _pair(left_id: int, right_id: int) -> tuple[int, int]:
    return (left_id, right_id) if left_id < right_id else (right_id, left_id)


async def find_users(session: AsyncSession, user_id: int, query: str | None = None, limit: int = 10) -> list[User]:
    stmt = select(User).where(
        User.id != user_id,
        User.is_active.is_(True),
        User.is_bot.is_(False),
        User.settings.has(show_profile=True),
    ).order_by(User.last_seen_at.desc()).limit(max(1, min(limit, 25)))

    if query:
        q = query.strip().lstrip("@")
        stmt = stmt.where(
            or_(
                User.username.ilike(f"%{q}%"),
                User.first_name.ilike(f"%{q}%"),
                User.last_name.ilike(f"%{q}%"),
            )
        )

    return list((await session.execute(stmt)).scalars().all())


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    normalized = username.strip().lstrip("@")
    result = await session.execute(
        select(User).where(User.username.ilike(normalized), User.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def are_friends(session: AsyncSession, left_id: int, right_id: int) -> bool:
    low, high = _pair(left_id, right_id)
    result = await session.execute(
        select(Friendship.id).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
        )
    )
    return result.scalar_one_or_none() is not None


async def send_friend_request(session: AsyncSession, sender_id: int, recipient_id: int) -> str:
    if sender_id == recipient_id:
        return "self"

    recipient = await session.get(User, recipient_id)
    if recipient is None or not recipient.is_active or recipient.is_bot:
        return "unavailable"

    if await are_friends(session, sender_id, recipient_id):
        return "friends"

    existing = await session.execute(
        select(FriendRequest).where(
            or_(
                and_(FriendRequest.sender_id == sender_id, FriendRequest.recipient_id == recipient_id),
                and_(FriendRequest.sender_id == recipient_id, FriendRequest.recipient_id == sender_id),
            )
        )
    )
    request = existing.scalars().first()

    if request is not None:
        return "outgoing" if request.sender_id == sender_id else "incoming"

    session.add(FriendRequest(sender_id=sender_id, recipient_id=recipient_id))
    await session.commit()
    return "created"


async def list_incoming_requests(session: AsyncSession, user_id: int) -> list[tuple[FriendRequest, User]]:
    result = await session.execute(
        select(FriendRequest, User)
        .join(User, User.id == FriendRequest.sender_id)
        .where(FriendRequest.recipient_id == user_id)
        .order_by(FriendRequest.created_at.desc())
    )
    return list(result.all())


async def respond_to_request(session: AsyncSession, recipient_id: int, sender_id: int, accept: bool) -> str:
    result = await session.execute(
        select(FriendRequest).where(
            FriendRequest.sender_id == sender_id,
            FriendRequest.recipient_id == recipient_id,
        )
    )
    request = result.scalar_one_or_none()

    if request is None:
        return "missing"

    await session.delete(request)

    if accept:
        low, high = _pair(sender_id, recipient_id)
        existing = await session.execute(
            select(Friendship).where(
                Friendship.user_low_id == low,
                Friendship.user_high_id == high,
            )
        )
        if existing.scalar_one_or_none() is None:
            session.add(Friendship(user_low_id=low, user_high_id=high))

    await session.commit()
    return "accepted" if accept else "declined"


async def list_friends(session: AsyncSession, user_id: int) -> list[User]:
    result = await session.execute(
        select(User)
        .join(
            Friendship,
            or_(
                and_(Friendship.user_low_id == user_id, Friendship.user_high_id == User.id),
                and_(Friendship.user_high_id == user_id, Friendship.user_low_id == User.id),
            ),
        )
        .where(User.is_active.is_(True))
        .order_by(User.first_name.asc())
    )
    return list(result.scalars().all())


async def remove_friend(session: AsyncSession, user_id: int, friend_id: int) -> bool:
    low, high = _pair(user_id, friend_id)
    result = await session.execute(
        delete(Friendship).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
        )
    )
    await session.commit()
    return result.rowcount > 0


def format_social_user(user: User) -> str:
    name = " ".join(p for p in (user.first_name, user.last_name) if p)
    username = f"@{user.username}" if user.username else "без username"
    return f"👤 <b>{name}</b> — {username}"
