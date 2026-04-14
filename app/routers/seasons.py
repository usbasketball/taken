from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Season
from app.dependencies import get_db
from app.middleware.auth import require_auth
from app.schemas.season import SeasonCreate, SeasonResponse, SeasonUpdate

router = APIRouter(prefix="/seasons", tags=["seasons"])

DbDep = Annotated[Session, Depends(get_db)]
AuthDep = Annotated[str, Depends(require_auth)]


@router.get("", response_model=list[SeasonResponse])
def list_seasons(db: DbDep) -> list[Season]:
    return db.query(Season).order_by(Season.created_at.desc()).all()


@router.get("/active", response_model=SeasonResponse | None)
def get_active_season(db: DbDep) -> Season | None:
    return db.query(Season).filter(Season.is_active.is_(True)).first()


@router.get("/{season_id}", response_model=SeasonResponse)
def get_season(season_id: int, db: DbDep) -> Season:
    season = db.get(Season, season_id)
    if not season:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return season


@router.post("", response_model=SeasonResponse, status_code=status.HTTP_201_CREATED)
def create_season(body: SeasonCreate, db: DbDep, _: AuthDep) -> Season:
    season = Season(name=body.name)
    db.add(season)
    db.commit()
    db.refresh(season)
    return season


@router.put("/{season_id}", response_model=SeasonResponse)
def update_season(season_id: int, body: SeasonUpdate, db: DbDep, _: AuthDep) -> Season:
    season = db.get(Season, season_id)
    if not season:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")

    if body.name is not None:
        season.name = body.name

    if body.is_active is True:
        # Deactivate all other seasons first
        db.query(Season).filter(Season.id != season_id).update({"is_active": False})
        season.is_active = True
    elif body.is_active is False:
        season.is_active = False

    db.commit()
    db.refresh(season)
    return season


@router.delete("/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_season(season_id: int, db: DbDep, _: AuthDep) -> None:
    season = db.get(Season, season_id)
    if not season:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    if season.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the active season",
        )
    db.delete(season)
    db.commit()
