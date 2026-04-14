"""
foys.io API client, response normalization, and sync diff computation.

foys.io is an external scheduling platform.  Game data for the club is
fetched from the public match API and filtered to only home games of our
organisation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

import httpx

from app.config import settings

FOYS_API_URL = "https://api.foys.io/competition/public-api/v1/matches/all"


@dataclass
class NormalizedMatch:
    external_id: str
    home_team_name: str
    home_team_code: str
    away_team_name: str
    away_team_code: str | None
    date: date
    start_time: time
    field_name: str | None
    competition: str | None
    needs_nbb_referees: bool
    use_24s: bool


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
    """'1' → 'Veld 1', 'Veld 2' → 'Veld 2', None / '' → None."""
    if not raw:
        return None
    stripped = raw.strip()
    if re.match(r"^\d+$", stripped):
        return f"Veld {stripped}"
    return stripped or None


def normalize_team_name(name: str) -> str:
    """Strip asterisks foys.io sometimes appends to team names."""
    return name.replace("*", "").strip()


def _away_full_name(m: dict[str, Any]) -> str:
    away_org = m.get("awayOrganisation")
    away_name = normalize_team_name(m.get("awayTeamName", ""))
    if away_org and away_org.get("name"):
        return f"{away_org['name']} - {away_name}"
    return away_name


# ---------------------------------------------------------------------------
# Main normalisation / filtering
# ---------------------------------------------------------------------------

def normalize_matches(raw_matches: list[dict[str, Any]]) -> list[NormalizedMatch]:
    """
    Filter the full foys.io match list to our club's home games and convert
    each match to a NormalizedMatch.  Games whose home team code cannot be
    inferred (i.e. not one of our 12 teams) are silently skipped.
    """
    from app.services.teams import infer_team_code_from_name, get_by_code

    result: list[NormalizedMatch] = []
    for m in raw_matches:
        # Only our home games
        home_org = m.get("homeOrganisation") or {}
        if home_org.get("id") != settings.foys_home_org_id:
            continue

        home_team_raw = normalize_team_name(m.get("homeTeamName", ""))
        home_team_code = infer_team_code_from_name(home_team_raw)
        if home_team_code is None:
            continue  # Unrecognised team — youth or exhibition game

        home_team_name = f"{home_org.get('name', 'U.S.')} - {home_team_raw}"

        # Away team code only when opponent is also our club (internal match)
        away_org = m.get("awayOrganisation") or {}
        away_team_code: str | None = None
        if away_org.get("id") == settings.foys_home_org_id:
            away_raw = normalize_team_name(m.get("awayTeamName", ""))
            away_team_code = infer_team_code_from_name(away_raw)

        away_team_name = _away_full_name(m)

        # Date / time
        date_str: str = m.get("date") or ""
        if "T" in date_str:
            date_str = date_str.split("T")[0]
        start_time_str = (m.get("startTime") or "00:00")[:5]

        try:
            game_date = date.fromisoformat(date_str)
            game_time = time.fromisoformat(start_time_str)
        except ValueError:
            continue

        field_nm = normalize_field_name(m.get("fieldName"))
        competition: str | None = None
        comp = m.get("competition")
        if isinstance(comp, dict):
            competition = comp.get("name")

        team_info = get_by_code(home_team_code)
        needs_nbb = team_info.use_nbb_ref if team_info else False
        use_24s = team_info.use_24s if team_info else False

        result.append(NormalizedMatch(
            external_id=str(m["id"]),
            home_team_name=home_team_name,
            home_team_code=home_team_code,
            away_team_name=away_team_name,
            away_team_code=away_team_code,
            date=game_date,
            start_time=game_time,
            field_name=field_nm,
            competition=competition,
            needs_nbb_referees=needs_nbb,
            use_24s=use_24s,
        ))

    return result


def fetch_home_matches() -> list[NormalizedMatch]:
    """Fetch and normalise home matches from the foys.io API."""
    headers = {"x-federationid": settings.foys_federation_id}
    with httpx.Client(timeout=30) as client:
        resp = client.get(FOYS_API_URL, headers=headers)
        resp.raise_for_status()
        raw = resp.json()

    # API may wrap matches in a top-level key
    if isinstance(raw, dict):
        raw = raw.get("matches", raw.get("data", []))

    return normalize_matches(raw)


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

    incoming_by_id = {m.external_id: m for m in incoming}
    existing_by_id = {g.external_id: g for g in existing_games if g.external_id}

    # New games
    for ext_id, match in incoming_by_id.items():
        if ext_id not in existing_by_id:
            diff.added.append(match)

    # Updated or removed
    for ext_id, game in existing_by_id.items():
        if ext_id not in incoming_by_id:
            diff.removed.append({
                "external_id": ext_id,
                "description": f"{game.home_team_name} vs {game.away_team_name} on {game.date}",
            })
        else:
            match = incoming_by_id[ext_id]
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

            if changes:
                diff.updated.append(UpdatedMatch(match=match, changes=changes))

    return diff
