import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

_SEASON_NAME_RE = re.compile(r"^\d{4}-\d{4}$")


def _validate_season_name(v: str) -> str:
    if not _SEASON_NAME_RE.match(v):
        raise ValueError("Season name must be in the format 'YYYY-YYYY' (e.g. '2025-2026')")
    return v


class SeasonCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"name": "2025-2026"}})

    name: str

    @field_validator("name")
    @classmethod
    def name_format(cls, v: str) -> str:
        return _validate_season_name(v)


class SeasonUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"name": "2025-2026"}})

    name: str | None = None


class SeasonResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "2025-2026",
                "created_at": "2026-04-14T12:00:00Z",
            }
        },
    )

    name: str
    created_at: datetime
