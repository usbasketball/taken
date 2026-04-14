"""
foys.io API client, response normalization, and sync diff computation.

foys.io is an external scheduling platform. Game data for the club is fetched
from the management API, one request per team, and merged into a single list.

Example response item from:
  GET https://api.foys.io/competition/management-api/v1/matches
      ?teamId=27380&showOnlyMatchesWithOrganisationsTeams=true
      &showMatchesWhereClubIsAwayTeam=false&skipCount=0&maxResultCount=100

  {
    "id": 266795,
    "status": "Final",
    "date": "2025-10-05T00:00:00Z",
    "startTime": "15:15:00",
    "homeTeam": {"id": 27380, "name": "VSE-3"},
    "awayTeam": {"id": 27061, "name": "VSE-1*"},
    "homeOrganisation": {"id": "2f1e5e8e-...", "name": "U.S."},
    "awayOrganisation": {"id": "c9ea6090-...", "name": "LUSV Basketbal"},
    "field": {"id": "3553f8cc-...", "name": "Veld 2"},
    "competitionType": {"id": 1, "name": "Competitie - Regionaal"},
    ...
  }

The top-level response wraps items: {"totalCount": 11, "items": [...]}
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

import httpx

from app.config import settings

FOYS_API_BASE = "https://api.foys.io/competition/management-api/v1/matches"


@dataclass
class NormalizedMatch:
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
    status: str = "Scheduled"


@dataclass
class SyncChange:
    field: str
    old: str
    new: str


@dataclass
class UpdatedMatch:
    match: NormalizedMatch
    changes: list[SyncChange]


@dataclass
class SyncDiff:
    added: list[NormalizedMatch] = field(default_factory=list)
    updated: list[UpdatedMatch] = field(default_factory=list)
    removed: list[dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def normalize_field_name(raw: str | None) -> str | None:
    """'1' → 'Veld 1', 'Veld 2' → 'Veld 2', None / '' → None.

    The management API already returns 'Veld 2' style names, but this is kept
    as a safety net.
    """
    if not raw:
        return None
    stripped = raw.strip()
    if re.match(r"^\d+$", stripped):
        return f"Veld {stripped}"
    return stripped or None


def normalize_team_name(name: str) -> str:
    """Strip asterisks foys.io sometimes appends to team names."""
    return name.replace("*", "").strip()


# ---------------------------------------------------------------------------
# Main normalisation
# ---------------------------------------------------------------------------

def normalize_matches(raw_matches: list[dict[str, Any]]) -> list[NormalizedMatch]:
    """
    Convert a list of raw management API match dicts to NormalizedMatch objects.

    Matches whose homeTeam.id is not one of our 12 registered teams are skipped
    (e.g. youth or exhibition games that might appear via the management API).
    """
    from app.services.teams import get_by_team_id

    result: list[NormalizedMatch] = []
    for m in raw_matches:
        home_team = m.get("homeTeam") or {}
        home_team_id = home_team.get("id")
        team_info = get_by_team_id(home_team_id) if home_team_id else None
        if team_info is None:
            continue  # Unrecognised team — skip

        home_team_code = team_info.code
        home_org = m.get("homeOrganisation") or {}
        home_team_name = f"{home_org.get('name', 'U.S.')} - {normalize_team_name(home_team.get('name', ''))}"

        # Away team code only when opponent is also our club (internal match)
        away_org = m.get("awayOrganisation") or {}
        away_team = m.get("awayTeam") or {}
        away_team_code: str | None = None
        if away_org.get("id") == settings.foys_home_org_id:
            away_info = get_by_team_id(away_team.get("id"))
            if away_info:
                away_team_code = away_info.code

        away_team_name_raw = normalize_team_name(away_team.get("name", ""))
        away_team_name = (
            f"{away_org['name']} - {away_team_name_raw}"
            if away_org.get("name")
            else away_team_name_raw
        )

        # Date / time
        date_str: str = (m.get("date") or "").split("T")[0]
        start_time_str = (m.get("startTime") or "00:00")[:5]
        try:
            game_date = date.fromisoformat(date_str)
            game_time = time.fromisoformat(start_time_str)
        except ValueError:
            continue

        field_nm = normalize_field_name((m.get("field") or {}).get("name"))
        competition: str | None = (m.get("competitionType") or {}).get("name")
        status: str = m.get("status") or "Scheduled"

        result.append(NormalizedMatch(
            match_id=str(m["id"]),
            home_team_name=home_team_name,
            home_team_code=home_team_code,
            away_team_name=away_team_name,
            away_team_code=away_team_code,
            date=game_date,
            start_time=game_time,
            field_name=field_nm,
            competition=competition,
            use_nbb_ref=team_info.use_nbb_ref,
            use_24s=team_info.use_24s,
            status=status,
        ))

    return result


def fetch_home_matches() -> list[NormalizedMatch]:
    """Fetch and normalise home matches from the foys.io management API.

    Makes one paginated request per team (12 teams total). Each request only
    returns home games for that team due to showMatchesWhereClubIsAwayTeam=false.
    """
    from app.services.teams import all_teams

    all_raw: list[dict[str, Any]] = []
    page_size = 100

    with httpx.Client(timeout=30) as client:
        for team in all_teams():
            skip = 0
            while True:
                params = {
                    "teamId": team.team_id,
                    "showOnlyMatchesWithOrganisationsTeams": "true",
                    "showMatchesWhereClubIsAwayTeam": "false",
                    "skipCount": skip,
                    "maxResultCount": page_size,
                }
                resp = client.get(FOYS_API_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                all_raw.extend(items)
                skip += page_size
                if skip >= data.get("totalCount", 0):
                    break

    return normalize_matches(all_raw)


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------

def compute_sync_diff(
    incoming: list[NormalizedMatch],
    existing_games: list,           # list of Game ORM objects
) -> SyncDiff:
    """
    Compare incoming foys.io matches against existing DB games.

    Returns a SyncDiff describing which games to add, update, or remove.
    Games with ``is_manually_edited=True`` that have upstream changes are
    included in ``updated`` so callers can decide whether to apply or skip.
    """
    diff = SyncDiff()

    incoming_by_id = {m.match_id: m for m in incoming}
    existing_by_id = {g.match_id: g for g in existing_games if g.match_id}

    # New games
    for mid, match in incoming_by_id.items():
        if mid not in existing_by_id:
            diff.added.append(match)

    # Updated or removed
    for mid, game in existing_by_id.items():
        if mid not in incoming_by_id:
            diff.removed.append({
                "match_id": mid,
                "description": f"{game.home_team_name} vs {game.away_team_name} on {game.date}",
            })
        else:
            match = incoming_by_id[mid]
            changes: list[SyncChange] = []

            if str(match.date) != str(game.date):
                changes.append(SyncChange("date", str(game.date), str(match.date)))
            if str(match.start_time)[:5] != str(game.start_time)[:5]:
                changes.append(SyncChange(
                    "start_time", str(game.start_time)[:5], str(match.start_time)[:5]
                ))
            if match.away_team_name != game.away_team_name:
                changes.append(SyncChange(
                    "away_team_name", game.away_team_name, match.away_team_name
                ))
            if (match.field_name or "") != (game.field_name or ""):
                changes.append(SyncChange(
                    "field_name", game.field_name or "", match.field_name or ""
                ))
            if match.status != (game.status or "Scheduled"):
                changes.append(SyncChange(
                    "status", game.status or "Scheduled", match.status
                ))

            if changes:
                diff.updated.append(UpdatedMatch(match=match, changes=changes))

    return diff
