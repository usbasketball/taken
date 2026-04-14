from datetime import datetime
from pydantic import BaseModel


class SeasonCreate(BaseModel):
    name: str


class SeasonUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class SeasonResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    is_published: bool
    published_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
