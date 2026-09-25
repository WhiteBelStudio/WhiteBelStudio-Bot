from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class UserMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    username: str | None
    first_name: str
    last_name: str | None
    language_code: str | None
    bio: str | None
    city: str | None
    avatar_file_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EconomyResponse(ORMResponse):
    balance: Decimal
    daily_streak: int
    last_daily_claim_at: datetime | None
    lifetime_earned: Decimal
    lifetime_spent: Decimal


class TransactionResponse(ORMResponse):
    id: int
    amount: Decimal
    balance_after: Decimal
    reason: str
    reference_user_id: int | None
    item_id: int | None
    created_at: datetime


class GameProfileResponse(BaseModel):
    user_id: int
    level: int
    experience: int
    experience_to_next: int
    games_played: int
    wins: int
    losses: int
    draws: int


class ReputationResponse(BaseModel):
    count: int
    average: float


class AchievementResponse(BaseModel):
    code: str
    name: str
    description: str
    target: int


class AchievementsResponse(BaseModel):
    earned: list[AchievementResponse]
    available: list[AchievementResponse]


class AchievementProgressResponse(BaseModel):
    code: str
    current: int
    target: int


class ShopItemResponse(ORMResponse):
    id: int
    code: str
    name: str
    description: str
    category: str
    price: Decimal
    is_active: bool


class InventoryItemResponse(BaseModel):
    item_id: int
    code: str
    name: str
    category: str
    quantity: int
    acquired_at: datetime


class MessageResponse(BaseModel):
    id: int
    sender_id: int
    text: str
    created_at: datetime
    read_at: datetime | None


class MessagesResponse(BaseModel):
    user_id: int
    other_user_id: int
    messages: list[MessageResponse]
