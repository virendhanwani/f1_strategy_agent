"""Offline checks: uv run python -m tests.test_strategy_request."""
from datetime import datetime, timezone
from agents.strategy_request import Event, Team, resolve_strategy_request, strategy_year


def dt(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def main():
    now = dt("2026-09-30T10:00:00")
    teams = [Team(year, "red_bull", "Red Bull Racing", ("Redbull",)) for year in (2024, 2026)]
    events = [Event(year, 10, "example", "Example Grand Prix", "Example Circuit",
                    dt(f"{year}-07-20T13:00:00"), ("Example GP",)) for year in (2024, 2026)]
    request = resolve_strategy_request("redbull", "Example GP", teams=teams, events=events, now=now)
    assert request.year == 2026
    assert request.cutoff == events[1].race_start
    historic = resolve_strategy_request("Red Bull Racing", "example", teams=teams,
                                        events=events, year=2024, now=now)
    assert historic.team.year == historic.event.year == historic.year == 2024
    assert historic.cutoff == events[0].race_start
    args = dict(year=2024, round_number=10, session_type="FP2",
                ended_at=dt("2024-07-19T14:00:00"), available_at=dt("2024-07-19T15:00:00"))
    assert historic.allows_session(**args)
    for changes in ({"year": 2023}, {"round_number": 11}, {"session_type": "R"},
                    {"available_at": historic.cutoff}):
        assert not historic.allows_session(**(args | changes))
    early = resolve_strategy_request("redbull", "example", teams=teams, events=events,
                                     now=dt("2026-07-01T00:00:00"))
    assert early.cutoff == dt("2026-07-01T00:00:00")
    assert strategy_year(now=dt("2025-12-31T20:00:00")) == 2026
    for changes in ({"team": "Unknown"}, {"year": 2025},
                    {"events": events + [events[1]]}, {"year": True}):
        try:
            resolve_strategy_request(**(dict(team="redbull", circuit="example", teams=teams,
                                            events=events, now=now) | changes))
        except ValueError:
            pass
        else:
            raise AssertionError(f"Should reject {changes}")
    print("Passed: name resolution, year isolation, ambiguity, and evidence cutoffs.")


if __name__ == "__main__":
    main()
