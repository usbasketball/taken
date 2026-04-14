"""
Match sync router.

POST /seasons/{season_name}/matches/sync

Two modes controlled by the ``preview`` query-param:

  ?preview=true   (default)
      Fetch foys.io, compute the diff, return it without writing to the DB.
      The response highlights any conflicts (foys.io changed a match that was
      manually edited locally).

  ?preview=false
      Apply the diff.  Conflicts default to "keep" (local wins) unless the
      caller includes an explicit resolution in the request body per ``match_id``.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import Season, Match, SyncLog
from app.dependencies import get_db
from app.middleware.auth import require_auth
from app.schemas.match import (
    SyncApplyRequest,
    SyncApplyResponse,
    SyncPreviewResponse,
    SyncAddedItem,
    SyncUpdatedItem,
    SyncRemovedItem,
    SyncChangeItem,
)
from app.services.foys import fetch_home_matches, compute_sync_diff, NormalizedMatch
from app.services.timeslot import find_or_create_timeslot, link_match_to_timeslot

router = APIRouter(prefix="/seasons/{season_name}/matches", tags=["sync"])


def _get_season_or_404(season_name: str, db: Session) -> Season:
    season = db.get(Season, season_name)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")
    return season


def _to_added_item(m: NormalizedMatch) -> SyncAddedItem:
    return SyncAddedItem(
        match_id=m.match_id,
        home_team_code=m.home_team_code,
        home_team_name=m.home_team_name,
        away_team_name=m.away_team_name,
        date=m.date,
        start_time=m.start_time,
        field_name=m.field_name,
    )


def _to_updated_item(updated, is_manually_edited: bool) -> SyncUpdatedItem:
    return SyncUpdatedItem(
        match_id=updated.match.match_id,
        home_team_code=updated.match.home_team_code,
        home_team_name=updated.match.home_team_name,
        is_manually_edited=is_manually_edited,
        changes=[SyncChangeItem(field=c.field, old=c.old, new=c.new) for c in updated.changes],
    )


def _apply_match_to_row(row: Match, match: NormalizedMatch) -> None:
    """Overwrite the mutable fields of an existing Match row."""
    row.date = match.date
    row.start_time = match.start_time
    row.away_team_name = match.away_team_name
    row.away_team_code = match.away_team_code
    row.field_name = match.field_name
    row.competition = match.competition
    row.use_nbb_ref = match.use_nbb_ref
    row.use_24s = match.use_24s
    row.status = match.status
    row.is_manually_edited = False  # Overwrite cleared the manual edit flag


def _add_match(db: Session, season_id: str, match: NormalizedMatch) -> Match:
    row = Match(
        season_id=season_id,
        match_id=match.match_id,
        home_team_name=match.home_team_name,
        home_team_code=match.home_team_code,
        away_team_name=match.away_team_name,
        away_team_code=match.away_team_code,
        date=match.date,
        start_time=match.start_time,
        field_name=match.field_name,
        competition=match.competition,
        use_nbb_ref=match.use_nbb_ref,
        use_24s=match.use_24s,
        status=match.status,
    )
    db.add(row)
    db.flush()  # Populate row.id
    ts = find_or_create_timeslot(db, season_id, match.date, match.start_time)
    link_match_to_timeslot(db, row.id, ts.id)
    return row


@router.post("/sync", status_code=200)
def sync_matches(
    season_name: str,
    db: Annotated[Session, Depends(get_db)],
    _auth: Annotated[str, Depends(require_auth)],
    preview: Annotated[bool, Query(description="If true, return diff without applying")] = True,
    body: SyncApplyRequest = None,
) -> SyncPreviewResponse | SyncApplyResponse:
    _get_season_or_404(season_name, db)

    incoming = fetch_home_matches()
    existing = db.query(Match).filter_by(season_id=season_name).all()
    diff = compute_sync_diff(incoming, existing)

    # ---- build existing-match index for quick lookup ----
    existing_by_mid: dict[str, Match] = {
        m.match_id: m for m in existing
    }

    if preview:
        normal_updated = []
        conflicts = []
        for u in diff.updated:
            row = existing_by_mid.get(u.match.match_id)
            manually = row.is_manually_edited if row else False
            item = _to_updated_item(u, manually)
            if manually:
                conflicts.append(item)
            else:
                normal_updated.append(item)

        return SyncPreviewResponse(
            added=[_to_added_item(m) for m in diff.added],
            updated=normal_updated,
            removed=[SyncRemovedItem(**r) for r in diff.removed],
            conflicts=conflicts,
        )

    # ---- apply mode ----
    if body is None:
        body = SyncApplyRequest()

    resolution_map = {r.match_id: r.action for r in body.resolutions}
    matches_added = 0
    matches_updated = 0
    matches_removed = 0
    conflicts_skipped = 0

    # Add new matches
    for match in diff.added:
        _add_match(db, season_name, match)
        matches_added += 1

    # Update or skip modified matches
    for updated in diff.updated:
        row = existing_by_mid.get(updated.match.match_id)
        if row is None:
            continue
        if row.is_manually_edited:
            action = resolution_map.get(updated.match.match_id, "keep")
            if action == "keep":
                conflicts_skipped += 1
                continue
        _apply_match_to_row(row, updated.match)
        ts = find_or_create_timeslot(db, season_name, updated.match.date, updated.match.start_time)
        link_match_to_timeslot(db, row.id, ts.id)
        matches_updated += 1

    # Remove matches that are no longer in foys.io
    for removed in diff.removed:
        row = existing_by_mid.get(removed["match_id"])
        if row is not None:
            db.delete(row)
            matches_removed += 1

    # Record sync in audit log
    db.add(SyncLog(
        season_id=season_name,
        matches_added=matches_added,
        matches_updated=matches_updated,
        matches_removed=matches_removed,
    ))
    db.commit()

    return SyncApplyResponse(
        matches_added=matches_added,
        matches_updated=matches_updated,
        matches_removed=matches_removed,
        conflicts_skipped=conflicts_skipped,
    )
