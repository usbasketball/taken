"""
Bidirectional mapping between team codes and team metadata.

Team codes: D1-D6 (dames/women), H1-H6 (heren/men)
Full names:  VSE-1-VSE-6 (dames), MSE-1-MSE-6 (heren)
Levels: 1 = highest, 6 = lowest
NBB teams (receive federation referees): H1, H2, D1
Teams requiring tafel-3 (24-sec clock): H1-H4, D1-D3
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TeamInfo:
    code: str
    full_name: str
    gender: str   # "dames" | "heren"
    level: int    # 1-6
    is_nbb: bool
    needs_tafel3: bool


_TEAMS: list[TeamInfo] = [
    TeamInfo("D1", "VSE-1", "dames", 1, is_nbb=True,  needs_tafel3=True),
    TeamInfo("D2", "VSE-2", "dames", 2, is_nbb=False, needs_tafel3=True),
    TeamInfo("D3", "VSE-3", "dames", 3, is_nbb=False, needs_tafel3=True),
    TeamInfo("D4", "VSE-4", "dames", 4, is_nbb=False, needs_tafel3=False),
    TeamInfo("D5", "VSE-5", "dames", 5, is_nbb=False, needs_tafel3=False),
    TeamInfo("D6", "VSE-6", "dames", 6, is_nbb=False, needs_tafel3=False),
    TeamInfo("H1", "MSE-1", "heren", 1, is_nbb=True,  needs_tafel3=True),
    TeamInfo("H2", "MSE-2", "heren", 2, is_nbb=True,  needs_tafel3=True),
    TeamInfo("H3", "MSE-3", "heren", 3, is_nbb=False, needs_tafel3=True),
    TeamInfo("H4", "MSE-4", "heren", 4, is_nbb=False, needs_tafel3=True),
    TeamInfo("H5", "MSE-5", "heren", 5, is_nbb=False, needs_tafel3=False),
    TeamInfo("H6", "MSE-6", "heren", 6, is_nbb=False, needs_tafel3=False),
]

_BY_CODE: dict[str, TeamInfo] = {t.code: t for t in _TEAMS}
_BY_FULL_NAME: dict[str, TeamInfo] = {t.full_name: t for t in _TEAMS}

# All valid team codes and full names
ALL_CODES: frozenset[str] = frozenset(_BY_CODE)
ALL_FULL_NAMES: frozenset[str] = frozenset(_BY_FULL_NAME)


def get_by_code(code: str) -> TeamInfo | None:
    """Look up team by code, e.g. 'H3' → TeamInfo(code='H3', full_name='MSE-3', ...)."""
    return _BY_CODE.get(code)


def get_by_full_name(full_name: str) -> TeamInfo | None:
    """Look up team by full name, e.g. 'MSE-3' → TeamInfo(code='H3', ...)."""
    return _BY_FULL_NAME.get(full_name)


def code_to_full_name(code: str) -> str | None:
    """'H3' → 'MSE-3'"""
    t = _BY_CODE.get(code)
    return t.full_name if t else None


def full_name_to_code(full_name: str) -> str | None:
    """'MSE-3' → 'H3'"""
    t = _BY_FULL_NAME.get(full_name)
    return t.code if t else None


def is_nbb_team(code: str) -> bool:
    """Returns True if the team uses federation (NBB) referees: H1, H2, D1."""
    t = _BY_CODE.get(code)
    return t.is_nbb if t else False


def needs_tafel3(code: str) -> bool:
    """Returns True if games for this team require a 24-sec shot clock operator."""
    t = _BY_CODE.get(code)
    return t.needs_tafel3 if t else False


def get_level(code: str) -> int | None:
    """Returns the competition level (1=highest, 6=lowest) for a team code."""
    t = _BY_CODE.get(code)
    return t.level if t else None


def infer_team_code_from_name(home_team_name: str) -> str | None:
    """
    Extract a team code from a foys.io home team name like 'U.S. - MSE-3'.
    Returns 'H3', or None if no match found.
    """
    for full_name, info in _BY_FULL_NAME.items():
        if full_name in home_team_name:
            return info.code
    return None


def all_teams() -> list[TeamInfo]:
    """Return all 12 teams in order (D1-D6, H1-H6)."""
    return list(_TEAMS)
