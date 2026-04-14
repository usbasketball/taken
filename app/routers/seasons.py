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


@router.get("/{season_name}", response_model=SeasonResponse)
def get_season(season_name: str, db: DbDep) -> Season:
    season = db.get(Season, season_name)
    if not season:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return season


@router.post("", response_model=SeasonResponse, status_code=status.HTTP_201_CREATED)
def create_season(body: SeasonCreate, db: DbDep, _: AuthDep) -> Season:
    if db.get(Season, body.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Season '{body.name}' already exists",
        )
    season = Season(name=body.name)
    db.add(season)
    db.commit()
    db.refresh(season)
    return season


@router.put("/{season_name}", response_model=SeasonResponse)
def update_season(season_name: str, body: SeasonUpdate, db: DbDep, _: AuthDep) -> Season:
    season = db.get(Season, season_name)
    if not season:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")

    if body.name is not None:
        season.name = body.name

    db.commit()
    db.refresh(season)
    return season


@router.delete("/{season_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_season(season_name: str, db: DbDep, _: AuthDep) -> None:
    season = db.get(Season, season_name)
    if not season:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    db.delete(season)
    db.commit()
