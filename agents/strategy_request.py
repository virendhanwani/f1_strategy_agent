"""Resolve strategy requests against season metadata before loading performance.

The ingestion layer supplies events and teams for the selected season. Metadata
may include the full calendar/roster; performance must pass allows_session().
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import unicodedata
from zoneinfo import ZoneInfo


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", value.lower())


def strategy_year(year: int | None = None, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use a timezone-aware current time.")
    selected = now.astimezone(ZoneInfo("Asia/Kolkata")).year if year is None else year
    if isinstance(selected, bool) or not isinstance(selected, int) or selected < 1950:
        raise ValueError("Year must be an integer from 1950 onward.")
    return selected


@dataclass(frozen=True)
class Team:
    year: int
    team_id: str
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Event:
    year: int
    round_number: int
    circuit_id: str
    name: str
    circuit_name: str
    race_start: datetime
    aliases: tuple[str, ...] = ()


def _match(query, candidates, names, kind):
    key = normalize(query)
    matches = [item for item in candidates if key and key in {normalize(n) for n in names(item)}]
    if len(matches) != 1:
        choices = ", ".join(item.name for item in (matches or candidates)) or "none available"
        reason = "Ambiguous" if matches else "Unknown or unavailable"
        raise ValueError(f"{reason} {kind}: {query!r}. Choices: {choices}.")
    return matches[0]


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Session and cutoff times must include a timezone.")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class StrategyRequest:
    year: int
    team: Team
    event: Event
    cutoff: datetime

    def allows_session(self, *, year: int, round_number: int,
                       session_type: str, ended_at: datetime,
                       available_at: datetime) -> bool:
        """Require completed, published, same-season evidence before the cutoff.

        available_at is when the source first made the data available, not the
        time our application downloaded it. Unknown times must not be guessed.
        """
        ended_at, available_at = _aware(ended_at), _aware(available_at)
        return (
            year == self.year
            and 1 <= round_number <= self.event.round_number
            and not (round_number == self.event.round_number and session_type.upper() == "R")
            and ended_at <= available_at < self.cutoff
        )


def resolve_strategy_request(team: str, circuit: str, *, teams: list[Team],
                             events: list[Event], year: int | None = None,
                             now: datetime | None = None,
                             as_of: datetime | None = None) -> StrategyRequest:
    """Resolve exact names/IDs/explicit aliases; never guess ambiguous matches.

    For completed races, default to immediately before race start. For upcoming
    races, default to now. An explicit as_of can move the cutoff earlier only.
    """
    now = _aware(now or datetime.now(timezone.utc))
    selected_year = strategy_year(year, now=now)
    selected_team = _match(team, [t for t in teams if t.year == selected_year],
                           lambda t: (t.team_id, t.name, *t.aliases), "team")
    selected_event = _match(circuit, [e for e in events if e.year == selected_year],
                            lambda e: (e.circuit_id, e.name, e.circuit_name, *e.aliases), "event")
    cutoff = min(now, _aware(selected_event.race_start))
    if as_of is not None:
        cutoff = min(cutoff, _aware(as_of))
    return StrategyRequest(selected_year, selected_team, selected_event, cutoff)
