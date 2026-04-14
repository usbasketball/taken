"""
Game sync router.

POST /seasons/{season_id}/games/sync

Two modes controlled by the ``preview`` query-param:

  ?preview=true   (default)
      Fetch foys.io, compute the diff, return it without touching the DB.
      The response highlights any conflicts (foys.io changed a game that was
      manually edited locally).

  ?preview=false
      Apply the diff.  Conflicts default to "keep" (local wins) unless the
      caller includes an explicit resolution in the request body.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import Season, Game, SyncLog
from app.dependencies import get_db
from app.middleware.auth import require_auth
from app.schemas.game import (
    SyncApplyRequest,
    SyncApplyResponse,
    SyncPreviewResponse,
    SyncAddedItem,
    SyncUpdatedItem,
    SyncRemovedItem,
    SyncChangeItem,
)
from app.services.foys import fetch_home_matches, compute_sync_diff, NormalizedMatch
from app.services.timeslot import find_or_create_timeslot, link_game_to_timeslot

router = APIRouter(prefix="/seasons/{season_name}/games", tags=["sync"])


def _get_season_or_404(season_name: str, db: Session) -> Season:
    season = db.get(Season, season_name)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")
    return season


def _to_added_item(m: NormalizedMatch) -> SyncAddedItem:
    return SyncAddedItem(
        external_id=m.external_id,
        home_team_code=m.home_team_code,
        home_team_name=m.home_team_name,
        away_team_name=m.away_team_name,
        date=m.date,
        start_time=m.start_time,
        field_name=m.field_name,
    )


def _to_updated_item(updated, is_manually_edited: bool) -> SyncUpdatedItem:
    return SyncUpdatedItem(
        external_id=updated.match.external_id,
        home_team_code=updated.match.home_team_code,
        home_team_name=updated.match.home_team_name,
        is_manually_edited=is_manually_edited,
        changes=[SyncChangeItem(field=c.field, old=c.old, new=c.new) for c in updated.changes],
    )


def _apply_match_to_game(game: Game, match: NormalizedMatch) -> None:
    """Overwrite the mutable fields of an existing Game row."""
    game.date = match.date
    game.start_time = match.start_time
    game.away_team_name = match.away_team_name
    game.away_team_code = match.away_team_code
    game.field_name = match.field_name
    game.competition = match.competition
    game.needs_nbb_referees = match.needs_nbb_referees
    game.use_24s = match.use_24s
    game.is_manually_edited = False  # Overwrite cleared the manual edit flag


def _add_game(db: Session, season_id: str, match: NormalizedMatch) -> Game:
    game = Game(
        season_id=season_id,
        external_id=match.external_id,
        home_team_name=match.home_team_name,
        home_team_code=match.home_team_code,
        away_team_name=match.away_team_name,
        away_team_code=match.away_team_code,
        date=match.date,
        start_time=match.start_time,
        field_name=match.field_name,
        competition=match.competition,
        needs_nbb_referees=match.needs_nbb_referees,
        use_24s=match.use_24s,
    )
    db.add(game)
    db.flush()  # Populate game.id
    ts = find_or_create_timeslot(db, season_id, match.date, match.start_time)
    link_game_to_timeslot(db, game.id, ts.id)
    return game


@router.post("/sync", status_code=200)
def sync_games(
    season_name: str,
    db: Annotated[Session, Depends(get_db)],
    _auth: Annotated[str, Depends(require_auth)],
    preview: Annotated[bool, Query(description="If true, return diff without applying")] = True,
    body: SyncApplyRequest = None,
) -> SyncPreviewResponse | SyncApplyResponse:
    _get_season_or_404(season_name, db)

    incoming = fetch_home_matches()
    existing = db.query(Game).filter_by(season_id=season_name).all()
    diff = compute_sync_diff(incoming, existing)

    # ---- build existing-game index for quick lookup ----
    existing_by_ext: dict[str, Game] = {
        g.external_id: g for g in existing if g.external_id
    }

    if preview:
        normal_updated = []
        conflicts = []
        for u in diff.updated:
            game = existing_by_ext.get(u.match.external_id)
            manually = game.is_manually_edited if game else False
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

    resolution_map = {r.external_id: r.action for r in body.resolutions}
    games_added = 0
    games_updated = 0
    games_removed = 0
    conflicts_skipped = 0

    # Add new games
    for match in diff.added:
        _add_game(db, season_name, match)
        games_added += 1

    # Update or skip modified games
    for updated in diff.updated:
        game = existing_by_ext.get(updated.match.external_id)
        if game is None:
            continue
        if game.is_manually_edited:
            action = resolution_map.get(updated.match.external_id, "keep")
            if action == "keep":
                conflicts_skipped += 1
                continue
        _apply_match_to_game(game, updated.match)
        # Re-link timeslot if date/time changed
        ts = find_or_create_timeslot(db, season_name, updated.match.date, updated.match.start_time)
        link_game_to_timeslot(db, game.id, ts.id)
        games_updated += 1

    # Remove games that are no longer in foys.io
    for removed in diff.removed:
        game = existing_by_ext.get(removed["external_id"])
        if game is not None:
            db.delete(game)
            games_removed += 1

    # Record sync in audit log
    db.add(SyncLog(
        season_id=season_name,
        games_added=games_added,
        games_updated=games_updated,
        games_removed=games_removed,
    ))
    db.commit()

    return SyncApplyResponse(
        games_added=games_added,
        games_updated=games_updated,
        games_removed=games_removed,
        conflicts_skipped=conflicts_skipped,
    )
