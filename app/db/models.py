"""
Phase 1 models: seasons, games, timeslots, game_timeslots, sync_log.
Phase 3 will add: members, assignments, balance_adjustments, config, audit_log.
"""
from datetime import date, time, datetime

from sqlalchemy import (
    Integer, String, Boolean, Date, Time, DateTime,
    ForeignKey, UniqueConstraint, PrimaryKeyConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.engine import Base


class Season(Base):
    __tablename__ = "seasons"
    # name is the PK — format enforced by Pydantic (SeasonCreate) and a DB
    # CHECK constraint in the Postgres migration (e.g. "2025-2026").

    name: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[str] = mapped_column(
        String, ForeignKey("seasons.name", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)   # foys.io match ID
    home_team_name: Mapped[str] = mapped_column(String, nullable=False)      # "U.S. - MSE-3"
    home_team_code: Mapped[str] = mapped_column(String, nullable=False)      # "H3"
    away_team_code: Mapped[str | None] = mapped_column(String, nullable=True)
    away_team_name: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String, nullable=True)    # "Veld 1"
    competition: Mapped[str | None] = mapped_column(String, nullable=True)
    needs_nbb_referees: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    use_24s: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_manually_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Timeslot(Base):
    """One unique date+time combination per season. Zaaldienst is per timeslot."""
    __tablename__ = "timeslots"
    __table_args__ = (UniqueConstraint("season_id", "date", "start_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[str] = mapped_column(
        String, ForeignKey("seasons.name", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    # FK to members.id added in Phase 3 migration once members table exists
    zaaldienst_member_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class GameTimeslot(Base):
    """Many-to-many: games belong to timeslots (multiple games can share one timeslot)."""
    __tablename__ = "game_timeslots"
    __table_args__ = (PrimaryKeyConstraint("game_id", "timeslot_id"),)

    game_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    timeslot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("timeslots.id", ondelete="CASCADE"), nullable=False
    )


class SyncLog(Base):
    """Records each foys.io sync operation for auditing."""
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[str] = mapped_column(
        String, ForeignKey("seasons.name", ondelete="CASCADE"), nullable=False
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    games_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    games_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    games_removed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
