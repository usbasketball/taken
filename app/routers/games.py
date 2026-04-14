"""
Games router.

Phase 2: read-only listing endpoint.
Phase 3 will add POST/PUT/DELETE for manual game management.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Season, Game
from app.dependencies import get_db
from app.schemas.game import GameRead

router = APIRouter(prefix="/seasons/{season_id}/games", tags=["games"])


def _get_season_or_404(season_id: int, db: Session) -> Season:
    season = db.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")
    return season


@router.get("", response_model=list[GameRead])
def list_games(
    season_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> list[Game]:
    _get_season_or_404(season_id, db)
    return (
        db.query(Game)
        .filter_by(season_id=season_id)
        .order_by(Game.date, Game.start_time)
        .all()
    )
