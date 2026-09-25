from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_telegram_user, get_database_session
from app.api.schemas import (
    AchievementProgressResponse,
    AchievementResponse,
    AchievementsResponse,
    EconomyResponse,
    GameProfileResponse,
    InventoryItemResponse,
    MessageResponse,
    MessagesResponse,
    ReputationResponse,
    ShopItemResponse,
    TransactionResponse,
    UserMeResponse,
)
from app.db.models import User
from app.services.achievements import (
    get_achievement_progress,
    list_user_achievements,
)
from app.services.communication import get_messages
from app.services.economy import (
    get_or_create_economy,
    get_inventory,
    list_shop_items,
    list_transactions,
)
from app.services.games import get_game_profile, to_game_profile_view
from app.services.reputation import get_reputation

router = APIRouter(prefix="/api/v1", tags=["business"])


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get the authenticated chat user",
)
async def me(user: User = Depends(get_current_telegram_user)) -> UserMeResponse:
    """Return the same user record used by the Telegram bot."""
    return UserMeResponse.model_validate(user)


@router.get(
    "/economy",
    response_model=EconomyResponse,
    summary="Get the authenticated user's economy account",
)
async def economy(
    user: User = Depends(get_current_telegram_user),
    session=Depends(get_database_session),
) -> EconomyResponse:
    account = await get_or_create_economy(session, user.id)
    await session.commit()
    return EconomyResponse.model_validate(account)


@router.get(
    "/economy/transactions",
    response_model=list[TransactionResponse],
    summary="Get the authenticated user's transaction history",
)
async def economy_transactions(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_telegram_user),
    session=Depends(get_database_session),
) -> list[TransactionResponse]:
    rows = await list_transactions(session, user.id, limit)
    return [TransactionResponse.model_validate(row) for row in rows]


@router.get(
    "/games/profile",
    response_model=GameProfileResponse,
    summary="Get the authenticated user's game profile",
)
async def games_profile(
    user: User = Depends(get_current_telegram_user),
    session=Depends(get_database_session),
) -> GameProfileResponse:
    profile = await get_game_profile(session, user.id)
    return GameProfileResponse(
        user_id=profile.user_id,
        level=profile.level,
        experience=profile.experience,
        experience_to_next=profile.experience_to_next,
        games_played=profile.games_played,
        wins=profile.wins,
        losses=profile.losses,
        draws=profile.draws,
    )


@router.get(
    "/reputation",
    response_model=ReputationResponse,
    summary="Get the authenticated user's reputation",
)
async def reputation(
    user: User = Depends(get_current_telegram_user),
    session=Depends(get_database_session),
) -> ReputationResponse:
    data = await get_reputation(session, user.id)
    return ReputationResponse.model_validate(data)


@router.get(
    "/achievements",
    response_model=AchievementsResponse,
    summary="Get the authenticated user's achievements",
)
async def achievements(
    user: User = Depends(get_current_telegram_user),
    session=Depends(get_database_session),
) -> AchievementsResponse:
    earned, available = await list_user_achievements(session, user.id)
    return AchievementsResponse(
        earned=[AchievementResponse.model_validate(item.__dict__) for item in earned],
        available=[AchievementResponse.model_validate(item.__dict__) for item in available],
    )


@router.get(
    "/achievements/progress",
    response_model=list[AchievementProgressResponse],
    summary="Get the authenticated user's achievement progress",
)
async def achievements_progress(
    user: User = Depends(get_current_telegram_user),
    session=Depends(get_database_session),
) -> list[AchievementProgressResponse]:
    progress = await get_achievement_progress(session, user.id)
    return [
        AchievementProgressResponse(code=code, current=current, target=target)
        for code, (current, target) in progress.items()
    ]


@router.get(
    "/shop/items",
    response_model=list[ShopItemResponse],
    summary="List active shop items",
)
async def shop_items(
    category: str | None = Query(default=None, min_length=1, max_length=32),
    user: User = Depends(get_current_telegram_user),
    session=Depends(get_database_session),
) -> list[ShopItemResponse]:
    rows = await list_shop_items(session, category)
    return [ShopItemResponse.model_validate(row) for row in rows]


@router.get(
    "/shop/inventory",
    response_model=list[InventoryItemResponse],
    summary="Get the authenticated user's inventory",
)
async def shop_inventory(
    user: User = Depends(get_current_telegram_user),
    session=Depends(get_database_session),
) -> list[InventoryItemResponse]:
    rows = await get_inventory(session, user.id)
    return [
        InventoryItemResponse(
            item_id=item.id,
            code=shop_item.code,
            name=shop_item.name,
            category=shop_item.category,
            quantity=item.quantity,
            acquired_at=item.acquired_at,
        )
        for item, shop_item in rows
    ]


@router.get(
    "/conversations/{other_user_id}/messages",
    response_model=MessagesResponse,
    summary="Get messages with another existing chat user",
)
async def conversation_messages(
    other_user_id: int,
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_telegram_user),
    session=Depends(get_database_session),
) -> MessagesResponse:
    rows = await get_messages(session, user.id, other_user_id, limit)
    return MessagesResponse(
        user_id=user.id,
        other_user_id=other_user_id,
        messages=[
            MessageResponse(
                id=row.id,
                sender_id=row.sender_id,
                text=row.text,
                created_at=row.created_at,
                read_at=row.read_at,
            )
            for row in rows
        ],
    )
