from __future__ import annotations

from datetime import date, time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class GameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: str
    external_id: str | None
    home_team_name: str
    home_team_code: str
    away_team_name: str
    away_team_code: str | None
    date: date
    start_time: time
    field_name: str | None
    competition: str | None
    needs_nbb_referees: bool
    needs_tafel3: bool
    is_cancelled: bool
    is_manually_edited: bool


# ---------------------------------------------------------------------------
# Sync preview / apply
# ---------------------------------------------------------------------------

class SyncChangeItem(BaseModel):
    field: str
    old: str
    new: str


class SyncAddedItem(BaseModel):
    external_id: str
    home_team_code: str
    home_team_name: str
    away_team_name: str
    date: date
    start_time: time
    field_name: str | None


class SyncUpdatedItem(BaseModel):
    external_id: str
    home_team_code: str
    home_team_name: str
    is_manually_edited: bool
    changes: list[SyncChangeItem]


class SyncRemovedItem(BaseModel):
    external_id: str
    description: str


class SyncPreviewResponse(BaseModel):
    added: list[SyncAddedItem]
    updated: list[SyncUpdatedItem]
    removed: list[SyncRemovedItem]
    conflicts: list[SyncUpdatedItem] = Field(
        default_factory=list,
        description="Updated games that are also manually edited — requires explicit resolution",
    )


class ConflictResolution(BaseModel):
    external_id: str
    action: Annotated[str, Field(pattern=r"^(keep|overwrite)$")]


class SyncApplyRequest(BaseModel):
    resolutions: list[ConflictResolution] = Field(default_factory=list)


class SyncApplyResponse(BaseModel):
    games_added: int
    games_updated: int
    games_removed: int
    conflicts_skipped: int
