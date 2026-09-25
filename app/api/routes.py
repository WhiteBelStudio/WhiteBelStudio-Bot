from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_telegram_user
from app.db.models import User

router = APIRouter(prefix="/api/v1", tags=["user"])


@router.get("/me")
async def me(user: User = Depends(get_current_telegram_user)) -> dict:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code,
        "bio": user.bio,
        "city": user.city,
        "avatar_file_id": user.avatar_file_id,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }
