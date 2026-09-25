from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    settings: Mapped["UserSettings | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_profile: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="ru", nullable=False)
    user: Mapped[User] = relationship(back_populates="settings")


class FriendRequest(Base):
    __tablename__ = "friend_requests"
    __table_args__ = (UniqueConstraint("sender_id", "recipient_id", name="uq_friend_request_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("user_low_id", "user_high_id", name="uq_friendship_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_low_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_high_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("user_low_id", "user_high_id", name="uq_conversation_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_low_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_high_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MessageRecord(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReputationRating(Base):
    __tablename__ = "reputation_ratings"
    __table_args__ = (
        UniqueConstraint("rater_id", "rated_id", name="uq_reputation_rating_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rater_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rated_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CommunityChat(Base):
    __tablename__ = "community_chats"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chat_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rules_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ChatMemberStats(Base):
    __tablename__ = "chat_member_stats"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_chat_member_stats_chat_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("community_chats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    command_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CommunityReputationVote(Base):
    __tablename__ = "community_reputation_votes"
    __table_args__ = (
        UniqueConstraint("chat_id", "rater_id", "rated_id", name="uq_community_rep_vote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("community_chats.id", ondelete="CASCADE"), nullable=False, index=True)
    rater_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rated_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int | None] = mapped_column(ForeignKey("community_chats.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GameProfile(Base):
    __tablename__ = "game_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_game_profile_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    games_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    draws: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EconomyAccount(Base):
    __tablename__ = "economy_accounts"
    __table_args__ = (UniqueConstraint("user_id", name="uq_economy_account_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 1), default=Decimal("0.0"), nullable=False)
    daily_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_daily_claim_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lifetime_earned: Mapped[Decimal] = mapped_column(Numeric(14, 1), default=Decimal("0.0"), nullable=False)
    lifetime_spent: Mapped[Decimal] = mapped_column(Numeric(14, 1), default=Decimal("0.0"), nullable=False)


class ShopItem(Base):
    __tablename__ = "shop_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserInventory(Base):
    __tablename__ = "user_inventory"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_inventory_user_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("shop_items.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 1), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("shop_items.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
