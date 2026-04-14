import re
from datetime import datetime

from pydantic import BaseModel, field_validator

_SEASON_NAME_RE = re.compile(r"^\d{4}-\d{4}$")


def _validate_season_name(v: str) -> str:
    if not _SEASON_NAME_RE.match(v):
        raise ValueError("Season name must be in the format 'YYYY-YYYY' (e.g. '2025-2026')")
    return v


class SeasonCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_format(cls, v: str) -> str:
        return _validate_season_name(v)


class SeasonUpdate(BaseModel):
    name: str | None = None


class SeasonResponse(BaseModel):
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
