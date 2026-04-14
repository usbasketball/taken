"""
Hardcoded team data for the 12 US Basketball Amsterdam club teams.

Team codes: D1-D6 (dames/women), H1-H6 (heren/men)
Full names:  VSE-1-VSE-6 (dames), MSE-1-MSE-6 (heren)
NBB teams (use federation referees): H1, H2, D1
Teams using 24-sec shot clock: H1-H4, D1-D3
team_id: foys.io organisation/team identifier (27358 = US Basketball Amsterdam)
"""
from dataclasses import dataclass

# U.S.
organisationId = "2f1e5e8e-e2c5-4d8b-9d21-1584bc6c8d5a"

@dataclass(frozen=True)
class TeamInfo:
    code: str
    full_name: str
    team_id: int   # foys.io team ID
    use_nbb_ref: bool
    use_24s: bool


_TEAMS: list[TeamInfo] = [
    TeamInfo("D1", "VSE-1", 27358, use_nbb_ref=True,  use_24s=True),
    TeamInfo("D2", "VSE-2", 27385, use_nbb_ref=False, use_24s=True),
    TeamInfo("D3", "VSE-3", 27380, use_nbb_ref=False, use_24s=True),
    TeamInfo("D4", "VSE-4", 27392, use_nbb_ref=False, use_24s=False),
    TeamInfo("D5", "VSE-5", 27347, use_nbb_ref=False, use_24s=False),
    TeamInfo("D6", "VSE-6", 27394, use_nbb_ref=False, use_24s=False),
    TeamInfo("H1", "MSE-1", 27404, use_nbb_ref=True,  use_24s=True),
    TeamInfo("H2", "MSE-2", 27409, use_nbb_ref=True,  use_24s=True),
    TeamInfo("H3", "MSE-3", 27412, use_nbb_ref=False, use_24s=True),
    TeamInfo("H4", "MSE-4", 27417, use_nbb_ref=False, use_24s=True),
    TeamInfo("H5", "MSE-5", 27398, use_nbb_ref=False, use_24s=False),
    TeamInfo("H6", "MSE-6", 28086, use_nbb_ref=False, use_24s=False),
]

_BY_CODE: dict[str, TeamInfo] = {t.code: t for t in _TEAMS}
_BY_FULL_NAME: dict[str, TeamInfo] = {t.full_name: t for t in _TEAMS}
_BY_TEAM_ID: dict[int, TeamInfo] = {t.team_id: t for t in _TEAMS}

ALL_CODES: frozenset[str] = frozenset(_BY_CODE)
ALL_FULL_NAMES: frozenset[str] = frozenset(_BY_FULL_NAME)


def get_by_code(code: str) -> TeamInfo | None:
    """Look up team by code, e.g. 'H3' → TeamInfo(code='H3', full_name='MSE-3', ...)."""
    return _BY_CODE.get(code)


def get_by_team_id(team_id: int) -> TeamInfo | None:
    """Look up team by foys.io team ID, e.g. 27412 → TeamInfo(code='H3', ...)."""
    return _BY_TEAM_ID.get(team_id)


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
