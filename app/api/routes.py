from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_telegram_user
from app.api.schemas import UserMeResponse
from app.db.models import User

router = APIRouter(prefix="/api/v1", tags=["user"])


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get the authenticated chat user",
)
async def me(user: User = Depends(get_current_telegram_user)) -> UserMeResponse:
    """Return the same user record used by the Telegram bot."""
    return UserMeResponse.model_validate(user)
