"""
Matches router.

Phase 2: read-only listing endpoint.
Phase 3 will add POST/PUT/DELETE for manual match management.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Season, Match
from app.dependencies import get_db
from app.schemas.match import MatchRead

router = APIRouter(prefix="/seasons/{season_name}/matches", tags=["matches"])


def _get_season_or_404(season_name: str, db: Session) -> Season:
    season = db.get(Season, season_name)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found")
    return season


@router.get("", response_model=list[MatchRead])
def list_matches(
    season_name: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[Match]:
    _get_season_or_404(season_name, db)
    return (
        db.query(Match)
        .filter_by(season_id=season_name)
        .order_by(Match.date, Match.start_time)
        .all()
    )
