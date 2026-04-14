"""
Tests for Phase 2: foys.io sync service and matches endpoints.

Integration tests mock `fetch_home_matches` so no real HTTP calls are made.
"""
from __future__ import annotations

from datetime import date, time
from unittest.mock import patch

import pytest

from app.services.foys import (
    NormalizedMatch,
    SyncChange,
    UpdatedMatch,
    compute_sync_diff,
    normalize_field_name,
    normalize_matches,
    normalize_team_name,
)
from app.services.timeslot import are_adjacent

HOME_ORG_ID = "2f1e5e8e-e2c5-4d8b-9d21-1584bc6c8d5a"


# ---------------------------------------------------------------------------
# Helper: build a minimal foys.io management API match dict
# ---------------------------------------------------------------------------

def _raw(
    match_id: int = 1,
    home_team_id: int = 27412,        # H3 = MSE-3
    home_team_name: str = "MSE-3",
    home_org_name: str = "U.S.",
    away_team_id: int = 99999,
    away_team_name: str = "MSE-1",
    away_org_id: str = "other-org",
    away_org_name: str = "Zijlkwartier",
    date_str: str = "2025-10-05T00:00:00Z",
    start_time: str = "14:00:00",
    field_name: str | None = "Veld 2",
    competition_type: str | None = "NBB Basketbal Heren 3",
    status: str = "Scheduled",
) -> dict:
    return {
        "id": match_id,
        "homeOrganisation": {"id": HOME_ORG_ID, "name": home_org_name},
        "awayOrganisation": {"id": away_org_id, "name": away_org_name},
        "homeTeam": {"id": home_team_id, "name": home_team_name},
        "awayTeam": {"id": away_team_id, "name": away_team_name},
        "date": date_str,
        "startTime": start_time,
        "field": {"name": field_name} if field_name else None,
        "competitionType": {"name": competition_type} if competition_type else None,
        "status": status,
    }


def _match(
    match_id: str = "1",
    home_team_code: str = "H3",
    away_team_name: str = "Zijlkwartier - MSE-1",
    game_date: date = date(2025, 10, 5),
    start_time: time = time(14, 0),
    field_name: str | None = "Veld 2",
    status: str = "Scheduled",
) -> NormalizedMatch:
    return NormalizedMatch(
        match_id=match_id,
        home_team_name="U.S. - MSE-3",
        home_team_code=home_team_code,
        away_team_name=away_team_name,
        away_team_code=None,
        date=game_date,
        start_time=start_time,
        field_name=field_name,
        competition="NBB Basketbal Heren 3",
        use_nbb_ref=False,
        use_24s=True,
        status=status,
    )


# ---------------------------------------------------------------------------
# Unit tests — no database
# ---------------------------------------------------------------------------

def test_normalize_field_name_digit():
    assert normalize_field_name("1") == "Veld 1"
    assert normalize_field_name("3") == "Veld 3"


def test_normalize_field_name_already_named():
    assert normalize_field_name("Veld 2") == "Veld 2"


def test_normalize_field_name_none():
    assert normalize_field_name(None) is None
    assert normalize_field_name("") is None


def test_normalize_team_name_strips_asterisk():
    assert normalize_team_name("MSE-3*") == "MSE-3"
    assert normalize_team_name("MSE-3") == "MSE-3"


def test_normalize_matches_unknown_team_skipped():
    """A match with an unrecognised homeTeam.id should be skipped."""
    raw = [_raw(home_team_id=99999, home_team_name="YOUTH-1")]
    results = normalize_matches(raw)
    assert results == []


def test_normalize_matches_field_name_passthrough():
    """field.name from the management API ('Veld 2') passes through unchanged."""
    results = normalize_matches([_raw(field_name="Veld 2")])
    assert results[0].field_name == "Veld 2"


def test_normalize_matches_field_name_digit_normalised():
    """Bare digit field names are still normalised as a safety net."""
    results = normalize_matches([_raw(field_name="2")])
    assert results[0].field_name == "Veld 2"


def test_normalize_matches_team_code_from_team_id():
    """home_team_code is derived from homeTeam.id, not name string."""
    results = normalize_matches([_raw(home_team_id=27417, home_team_name="MSE-4")])
    assert results[0].home_team_code == "H4"


def test_normalize_matches_date_parsed():
    results = normalize_matches([_raw(date_str="2025-11-15T00:00:00Z")])
    assert results[0].date == date(2025, 11, 15)


def test_normalize_matches_status():
    results = normalize_matches([_raw(status="Final")])
    assert results[0].status == "Final"


def test_normalize_matches_competition_type():
    results = normalize_matches([_raw(competition_type="Competitie - Regionaal")])
    assert results[0].competition == "Competitie - Regionaal"


def test_compute_sync_diff_added():
    incoming = [_match(match_id="100")]
    diff = compute_sync_diff(incoming, [])
    assert len(diff.added) == 1
    assert diff.added[0].match_id == "100"
    assert diff.updated == []
    assert diff.removed == []


def test_compute_sync_diff_removed():
    class FakeMatch:
        match_id = "200"
        home_team_name = "U.S. - MSE-3"
        away_team_name = "Zijlkwartier - MSE-1"
        date = date(2025, 10, 5)

    diff = compute_sync_diff([], [FakeMatch()])
    assert len(diff.removed) == 1
    assert diff.removed[0]["match_id"] == "200"


def test_compute_sync_diff_updated_date():
    class FakeMatch:
        match_id = "300"
        home_team_name = "U.S. - MSE-3"
        away_team_name = "Zijlkwartier - MSE-1"
        date = date(2025, 10, 5)
        start_time = time(14, 0)
        field_name = "Veld 2"
        status = "Scheduled"

    new_match = _match(match_id="300", game_date=date(2025, 10, 6))
    diff = compute_sync_diff([new_match], [FakeMatch()])
    assert len(diff.updated) == 1
    assert any(c.field == "date" for c in diff.updated[0].changes)


def test_compute_sync_diff_updated_status():
    class FakeMatch:
        match_id = "301"
        home_team_name = "U.S. - MSE-3"
        away_team_name = "Zijlkwartier - MSE-1"
        date = date(2025, 10, 5)
        start_time = time(14, 0)
        field_name = "Veld 2"
        status = "Scheduled"

    new_match = _match(match_id="301", status="Final")
    diff = compute_sync_diff([new_match], [FakeMatch()])
    assert len(diff.updated) == 1
    assert any(c.field == "status" for c in diff.updated[0].changes)


def test_compute_sync_diff_no_changes():
    class FakeMatch:
        match_id = "400"
        home_team_name = "U.S. - MSE-3"
        away_team_name = "Zijlkwartier - MSE-1"
        date = date(2025, 10, 5)
        start_time = time(14, 0)
        field_name = "Veld 2"
        status = "Scheduled"

    m = _match(match_id="400")
    diff = compute_sync_diff([m], [FakeMatch()])
    assert diff.added == []
    assert diff.updated == []
    assert diff.removed == []


def test_are_adjacent_same_day_within_window():
    assert are_adjacent(date(2025, 10, 5), time(14, 0), date(2025, 10, 5), time(15, 30))


def test_are_adjacent_different_day():
    assert not are_adjacent(date(2025, 10, 5), time(14, 0), date(2025, 10, 6), time(14, 0))


def test_are_adjacent_outside_window():
    # 14:00 vs 17:00 = 180 min > 150 min
    assert not are_adjacent(date(2025, 10, 5), time(14, 0), date(2025, 10, 5), time(17, 0))


# ---------------------------------------------------------------------------
# Integration tests — use the test DB via the `client` fixture
# ---------------------------------------------------------------------------

def _create_season(client, auth_headers) -> str:
    resp = client.post("/seasons", json={"name": "2025-2026"}, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["name"]


def test_list_matches_empty(client, auth_headers):
    sid = _create_season(client, auth_headers)
    resp = client.get(f"/seasons/{sid}/matches")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_matches_season_not_found(client):
    resp = client.get("/seasons/9999/matches")
    assert resp.status_code == 404


def test_sync_preview_returns_diff(client, auth_headers):
    sid = _create_season(client, auth_headers)
    matches = [_match()]

    with patch("app.routers.matches_sync.fetch_home_matches", return_value=matches):
        resp = client.post(
            f"/seasons/{sid}/matches/sync?preview=true",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["added"]) == 1
    assert data["updated"] == []
    assert data["removed"] == []
    assert data["conflicts"] == []

    # Preview must not persist anything
    assert client.get(f"/seasons/{sid}/matches").json() == []


def test_sync_apply_adds_matches_and_creates_timeslot(client, auth_headers):
    sid = _create_season(client, auth_headers)
    matches = [_match(match_id="42")]

    with patch("app.routers.matches_sync.fetch_home_matches", return_value=matches):
        resp = client.post(
            f"/seasons/{sid}/matches/sync?preview=false",
            json={"resolutions": []},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["matches_added"] == 1
    assert data["matches_updated"] == 0
    assert data["matches_removed"] == 0

    result = client.get(f"/seasons/{sid}/matches").json()
    assert len(result) == 1
    assert result[0]["match_id"] == "42"
    assert result[0]["home_team_code"] == "H3"
    assert result[0]["field_name"] == "Veld 2"
    assert result[0]["status"] == "Scheduled"


def test_sync_apply_updates_changed_match(client, auth_headers):
    sid = _create_season(client, auth_headers)

    initial = [_match(match_id="10", game_date=date(2025, 10, 5))]
    with patch("app.routers.matches_sync.fetch_home_matches", return_value=initial):
        client.post(f"/seasons/{sid}/matches/sync?preview=false", json={}, headers=auth_headers)

    updated = [_match(match_id="10", game_date=date(2025, 10, 12))]
    with patch("app.routers.matches_sync.fetch_home_matches", return_value=updated):
        resp = client.post(
            f"/seasons/{sid}/matches/sync?preview=false", json={}, headers=auth_headers
        )

    assert resp.json()["matches_updated"] == 1
    result = client.get(f"/seasons/{sid}/matches").json()
    assert result[0]["date"] == "2025-10-12"


def test_sync_apply_removes_missing_match(client, auth_headers):
    sid = _create_season(client, auth_headers)

    initial = [_match(match_id="99")]
    with patch("app.routers.matches_sync.fetch_home_matches", return_value=initial):
        client.post(f"/seasons/{sid}/matches/sync?preview=false", json={}, headers=auth_headers)

    with patch("app.routers.matches_sync.fetch_home_matches", return_value=[]):
        resp = client.post(
            f"/seasons/{sid}/matches/sync?preview=false", json={}, headers=auth_headers
        )

    assert resp.json()["matches_removed"] == 1
    assert client.get(f"/seasons/{sid}/matches").json() == []


def test_sync_apply_conflict_keep_by_default(client, auth_headers):
    """A manually-edited match with an upstream change is kept when no resolution given."""
    sid = _create_season(client, auth_headers)

    initial = [_match(match_id="55", game_date=date(2025, 10, 5))]
    with patch("app.routers.matches_sync.fetch_home_matches", return_value=initial):
        client.post(f"/seasons/{sid}/matches/sync?preview=false", json={}, headers=auth_headers)


def test_sync_preview_shows_conflicts_for_manually_edited(client, auth_headers, db):
    """Preview must surface conflicts for manually-edited matches."""
    sid = _create_season(client, auth_headers)

    initial = [_match(match_id="77")]
    with patch("app.routers.matches_sync.fetch_home_matches", return_value=initial):
        client.post(f"/seasons/{sid}/matches/sync?preview=false", json={}, headers=auth_headers)

    from app.db.models import Match as MatchModel
    match = db.query(MatchModel).filter_by(match_id="77").one()
    match.is_manually_edited = True
    db.commit()

    changed = [_match(match_id="77", game_date=date(2025, 12, 1))]
    with patch("app.routers.matches_sync.fetch_home_matches", return_value=changed):
        resp = client.post(
            f"/seasons/{sid}/matches/sync?preview=true",
            headers=auth_headers,
        )

    data = resp.json()
    assert len(data["conflicts"]) == 1
    assert data["conflicts"][0]["match_id"] == "77"
    assert data["conflicts"][0]["is_manually_edited"] is True
    assert data["updated"] == []


def test_sync_apply_conflict_overwrite(client, auth_headers, db):
    """Passing action=overwrite for a manually-edited match should apply the change."""
    sid = _create_season(client, auth_headers)

    initial = [_match(match_id="88")]
    with patch("app.routers.matches_sync.fetch_home_matches", return_value=initial):
        client.post(f"/seasons/{sid}/matches/sync?preview=false", json={}, headers=auth_headers)

    from app.db.models import Match as MatchModel
    match = db.query(MatchModel).filter_by(match_id="88").one()
    match.is_manually_edited = True
    db.commit()

    changed = [_match(match_id="88", game_date=date(2025, 12, 15))]
    with patch("app.routers.matches_sync.fetch_home_matches", return_value=changed):
        resp = client.post(
            f"/seasons/{sid}/matches/sync?preview=false",
            json={"resolutions": [{"match_id": "88", "action": "overwrite"}]},
            headers=auth_headers,
        )

    assert resp.json()["matches_updated"] == 1
    result = client.get(f"/seasons/{sid}/matches").json()
    assert result[0]["date"] == "2025-12-15"
    assert result[0]["is_manually_edited"] is False


def test_sync_requires_auth(client):
    resp = client.post("/seasons/1/matches/sync")
    assert resp.status_code == 401
