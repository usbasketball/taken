from __future__ import annotations

from datetime import date, time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: str
    match_id: str
    home_team_name: str
    home_team_code: str
    away_team_name: str
    away_team_code: str | None
    date: date
    start_time: time
    field_name: str | None
    competition: str | None
    use_nbb_ref: bool
    use_24s: bool
    status: str
    is_manually_edited: bool


# ---------------------------------------------------------------------------
# Sync preview / apply
# ---------------------------------------------------------------------------

class SyncChangeItem(BaseModel):
    field: str
    old: str
    new: str


class SyncAddedItem(BaseModel):
    match_id: str
    home_team_code: str
    home_team_name: str
    away_team_name: str
    date: date
    start_time: time
    field_name: str | None


class SyncUpdatedItem(BaseModel):
    match_id: str
    home_team_code: str
    home_team_name: str
    is_manually_edited: bool
    changes: list[SyncChangeItem]


class SyncRemovedItem(BaseModel):
    match_id: str
    description: str


class SyncPreviewResponse(BaseModel):
    added: list[SyncAddedItem]
    updated: list[SyncUpdatedItem]
    removed: list[SyncRemovedItem]
    conflicts: list[SyncUpdatedItem] = Field(
        default_factory=list,
        description="Updated matches that are also manually edited — requires explicit resolution",
    )


class ConflictResolution(BaseModel):
    match_id: str
    action: Annotated[str, Field(pattern=r"^(keep|overwrite)$")]


class SyncApplyRequest(BaseModel):
    resolutions: list[ConflictResolution] = Field(default_factory=list)


class SyncApplyResponse(BaseModel):
    matches_added: int
    matches_updated: int
    matches_removed: int
    conflicts_skipped: int
