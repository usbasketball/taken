"""
Timeslot management helpers.

A Timeslot represents a unique (season_id, date, start_time) combination.
Multiple matches can share a timeslot (same court block), and one zaaldienst
member is assigned per timeslot.

Adjacency: two matches are considered adjacent when they are on the same day
and within 150 minutes of each other.  Adjacent duties count as a "single"
duty (×1) in the balance formula; non-adjacent duties count as "double" (×2).
"""
from __future__ import annotations

from datetime import date, time

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import Timeslot, MatchTimeslot


_ADJACENCY_WINDOW_MINUTES = 150


def are_adjacent(date1: date, time1: time, date2: date, time2: time) -> bool:
    """Return True when two match slots are on the same day and ≤150 min apart."""
    if date1 != date2:
        return False
    t1_minutes = time1.hour * 60 + time1.minute
    t2_minutes = time2.hour * 60 + time2.minute
    return abs(t1_minutes - t2_minutes) <= _ADJACENCY_WINDOW_MINUTES


def find_or_create_timeslot(
    db: Session,
    season_id: str,
    match_date: date,
    start_time: time,
) -> Timeslot:
    """
    Return the existing Timeslot for (season_id, date, start_time), or create
    a new one.  Handles the rare race condition via an IntegrityError retry.
    """
    ts = (
        db.query(Timeslot)
        .filter_by(season_id=season_id, date=match_date, start_time=start_time)
        .first()
    )
    if ts is not None:
        return ts

    ts = Timeslot(season_id=season_id, date=match_date, start_time=start_time)
    db.add(ts)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        ts = (
            db.query(Timeslot)
            .filter_by(season_id=season_id, date=match_date, start_time=start_time)
            .one()
        )
    return ts


def link_match_to_timeslot(db: Session, match_row_id: int, timeslot_id: int) -> None:
    """Create a MatchTimeslot row if it doesn't already exist."""
    exists = (
        db.query(MatchTimeslot)
        .filter_by(match_row_id=match_row_id, timeslot_id=timeslot_id)
        .first()
    )
    if exists is None:
        db.add(MatchTimeslot(match_row_id=match_row_id, timeslot_id=timeslot_id))
        db.flush()
