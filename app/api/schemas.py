from __future__ import annotations

from datetime import datetime

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
