from __future__ import annotations

from datetime import date, time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class MatchRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "season_id": "2025-2026",
                "match_id": "266795",
                "home_team_name": "U.S. - MSE-3",
                "home_team_code": "H3",
                "away_team_name": "LUSV Basketbal - VSE-1",
                "away_team_code": None,
                "date": "2025-10-05",
                "start_time": "15:15:00",
                "field_name": "Veld 2",
                "competition": "Competitie - Regionaal",
                "use_nbb_ref": False,
                "use_24s": True,
                "status": "Scheduled",
                "is_manually_edited": False,
            }
        },
    )

    id: int
    season_id: str
    match_id: str = Field(description="foys.io integer match ID, stored as a string")
    home_team_name: str = Field(description='Full name including org prefix, e.g. "U.S. - MSE-3"')
    home_team_code: str = Field(description='Short code from teams.py, e.g. "H3" or "D1"')
    away_team_name: str
    away_team_code: str | None = Field(description="Set only when the opponent is also a US Basketball team (internal match), otherwise null")
    date: date
    start_time: time
    field_name: str | None
    competition: str | None
    use_nbb_ref: bool = Field(description="Per-team flag (from teams.py): whether NBB supplies the referee")
    use_24s: bool = Field(description="Per-team flag (from teams.py): whether the 24-second shot clock is used")
    status: str = Field(description='Mirrors foys.io values: "Scheduled", "Final", etc.')
    is_manually_edited: bool = Field(description="True if an admin has locally overridden this record; gates conflict resolution during sync")


# ---------------------------------------------------------------------------
# Sync preview / apply
# ---------------------------------------------------------------------------

class SyncChangeItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"field": "date", "old": "2025-10-05", "new": "2025-10-12"}}
    )

    field: str
    old: str
    new: str


class SyncAddedItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "match_id": "266795",
                "home_team_code": "H3",
                "home_team_name": "U.S. - MSE-3",
                "away_team_name": "LUSV Basketbal - VSE-1",
                "date": "2025-10-05",
                "start_time": "15:15:00",
                "field_name": "Veld 2",
            }
        }
    )

    match_id: str
    home_team_code: str
    home_team_name: str
    away_team_name: str
    date: date
    start_time: time
    field_name: str | None


class SyncUpdatedItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "match_id": "266795",
                "home_team_code": "H3",
                "home_team_name": "U.S. - MSE-3",
                "is_manually_edited": False,
                "changes": [{"field": "date", "old": "2025-10-05", "new": "2025-10-12"}],
            }
        }
    )

    match_id: str
    home_team_code: str
    home_team_name: str
    is_manually_edited: bool
    changes: list[SyncChangeItem]


class SyncRemovedItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "match_id": "266795",
                "description": "U.S. - MSE-3 vs LUSV Basketbal - VSE-1 on 2025-10-05",
            }
        }
    )

    match_id: str
    description: str


class SyncPreviewResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "added": [
                    {
                        "match_id": "266795",
                        "home_team_code": "H3",
                        "home_team_name": "U.S. - MSE-3",
                        "away_team_name": "LUSV Basketbal - VSE-1",
                        "date": "2025-10-05",
                        "start_time": "15:15:00",
                        "field_name": "Veld 2",
                    }
                ],
                "updated": [],
                "removed": [],
                "conflicts": [],
            }
        }
    )

    added: list[SyncAddedItem]
    updated: list[SyncUpdatedItem]
    removed: list[SyncRemovedItem]
    conflicts: list[SyncUpdatedItem] = Field(
        default_factory=list,
        description="Updated matches that are also manually edited — requires explicit resolution",
    )


class ConflictResolution(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"match_id": "266795", "action": "overwrite"}}
    )

    match_id: str
    action: Annotated[str, Field(pattern=r"^(keep|overwrite)$")]


class SyncApplyRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resolutions": [{"match_id": "266795", "action": "overwrite"}]
            }
        }
    )

    resolutions: list[ConflictResolution] = Field(default_factory=list)


class SyncApplyResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "matches_added": 3,
                "matches_updated": 1,
                "matches_removed": 0,
                "conflicts_skipped": 1,
            }
        }
    )

    matches_added: int
    matches_updated: int
    matches_removed: int
    conflicts_skipped: int
