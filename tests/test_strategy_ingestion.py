"""Offline metadata checks, without network calls or test frameworks."""
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone

from agents.strategy_request import resolve_strategy_request
from ingestion.strategy_data import parse_metadata, save_json, load_metadata


def main():
    races = [{"round": "1", "race_name": "Example Grand Prix", "date": "2024-03-01",
              "time": "14:00:00Z", "circuit": {"circuit_id": "example",
              "circuit_name": "Example Circuit", "locality": "Example City"}}]
    constructors = [{"constructor_id": "red_bull", "name": "Red Bull"}]
    events, teams, missing = parse_metadata(2024, races, constructors)
    assert not missing
    assert events[0].race_start.hour == 14
    assert events[0].race_start.utcoffset().total_seconds() == 0
    with TemporaryDirectory() as temp:
        root = Path(temp)
        save_json(root / "2024" / "metadata.json", {"year": 2024,
                  "events": [asdict(e) for e in events], "teams": [asdict(t) for t in teams]})
        loaded_events, loaded_teams = load_metadata(2024, root)
        request = resolve_strategy_request("Redbull", "Example City", year=2024,
                    teams=loaded_teams, events=loaded_events,
                    now=datetime(2024, 2, 1, tzinfo=timezone.utc))
        assert request.team.team_id == "red_bull"
        assert request.event.circuit_id == "example"
    races[0].pop("time")
    events, _, missing = parse_metadata(2024, races, constructors)
    assert not events and missing == ["Example Grand Prix"]
    print("Passed: metadata parsing, cache roundtrip, resolver integration, missing times.")


if __name__ == "__main__":
    main()
