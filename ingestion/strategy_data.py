"""Calendar-wide strategy ingestion; run with --help for selection options."""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

import fastf1
import pandas as pd

from agents.strategy_request import Event, Team, strategy_year
from agents.tools import get_race_schedule, get_constructor_standings
from ingestion.fetch_sessions import setup_cache, PROCESSED_DIR

ROOT = PROCESSED_DIR / "strategy"


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str))
    temporary.replace(path)


def parse_metadata(year, races, constructors):
    """Keep season identity from Jolpica; missing race times remain unresolved."""
    events, missing = [], []
    for race in races:
        if not race.get("time"):
            missing.append(race["race_name"])
            continue
        circuit = race["circuit"]
        events.append(Event(year, int(race["round"]), circuit["circuit_id"],
                            race["race_name"], circuit["circuit_name"],
                            datetime.fromisoformat(race["date"] + "T" + race["time"].replace("Z", "+00:00")),
                            tuple(filter(None, (circuit.get("locality"),)))))
    teams = [Team(year, c["constructor_id"], c["name"]) for c in constructors]
    return events, teams, missing


async def fetch_metadata(year, root=ROOT):
    schedule = await get_race_schedule.ainvoke({"season": str(year)})
    if schedule.get("error"):
        raise ValueError(schedule["error"])
    if str(schedule["season"]) != str(year):
        raise ValueError("Race schedule does not match the requested season.")
    standings = await get_constructor_standings.ainvoke({"season": str(year)})
    # Standings are used only for team identity, never as pre-race performance.
    if standings.get("error"):
        constructors = []
    else:
        if str(standings["season"]) != str(year):
            raise ValueError("Team metadata does not match the requested season.")
        constructors = [entry["constructor"] for entry in standings["standings"]]
    races = schedule["races"]
    events, teams, missing = parse_metadata(year, races, constructors)
    save_json(root / str(year) / "metadata.json", {
        "year": year, "source": "Jolpica", "fetched_at": datetime.now(timezone.utc),
        "events": [asdict(e) for e in events], "teams": [asdict(t) for t in teams],
        "events_missing_start_time": missing,
        "team_metadata_error": standings.get("error"),
    })
    return events, teams


def load_metadata(year, root=ROOT):
    data = json.loads((root / str(year) / "metadata.json").read_text())
    if data["year"] != year:
        raise ValueError("Metadata season does not match the requested season.")
    events = [Event(**(e | {"race_start": datetime.fromisoformat(e["race_start"]),
                            "aliases": tuple(e["aliases"])})) for e in data["events"]]
    teams = [Team(**(t | {"aliases": tuple(t["aliases"])})) for t in data["teams"]]
    return events, teams


def save_session(session, directory):
    """Save components independently and report partial coverage explicitly."""
    directory.mkdir(parents=True, exist_ok=True)
    report = {"source": "FastF1", "fetched_at": datetime.now(timezone.utc).isoformat(),
              "ended_at": None, "available_at": None, "components": {}, "telemetry": {}}
    save_json(directory / "manifest.json", {"status": "loading"})
    # FastF1 doesn't establish the original publication time. Do not substitute
    # download time: historical recommendation eligibility remains unknown.
    for name, attribute in (("laps", "laps"), ("results", "results"),
                            ("weather", "weather_data"), ("track_status", "track_status_data"),
                            ("race_control", "race_control_messages"), ("session_status", "session_status")):
        try:
            frame = getattr(session, attribute)
            if frame.empty:
                raise ValueError("No rows available")
            frame.to_parquet(directory / f"{name}.parquet")
            report["components"][name] = {"status": "ok", "rows": len(frame)}
        except Exception as exc:
            report["components"][name] = {"status": "missing", "reason": str(exc)}
    try:
        corners = session.get_circuit_info().corners
        if corners.empty:
            raise ValueError("No corner markers available")
        corners.to_parquet(directory / "corners.parquet")
        report["components"]["corners"] = {"status": "ok", "rows": len(corners), "approximate": True}
    except Exception as exc:
        report["components"]["corners"] = {"status": "missing", "reason": str(exc)}
    try:
        laps = session.laps
        for _, lap in laps.iterlaps():
            driver, number = str(lap["DriverNumber"]), lap["LapNumber"]
            if pd.isna(number) or not driver.isdigit():
                continue
            key = f"{driver}_{int(number)}"
            try:
                # Merges position and car channels; includes time, distance,
                # speed, throttle, brake, gear, DRS and XYZ where supplied.
                trace = lap.get_telemetry()
                if trace.empty:
                    raise ValueError("No telemetry samples")
                trace.to_parquet(directory / f"telemetry_{key}.parquet")
                report["telemetry"][key] = {"status": "ok", "rows": len(trace)}
            except Exception as exc:
                report["telemetry"][key] = {"status": "missing", "reason": str(exc)}
    except Exception as exc:
        report["components"]["telemetry"] = {"status": "missing", "reason": str(exc)}
    save_json(directory / "manifest.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--round", type=int, dest="round_number")
    parser.add_argument("--sessions", nargs="+", default=["FP1", "FP2", "FP3", "Q", "S", "SQ", "R"])
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    year = strategy_year(args.year)
    setup_cache()
    events, _ = asyncio.run(fetch_metadata(year))
    if args.metadata_only:
        return
    if args.round_number is not None and args.round_number not in {e.round_number for e in events}:
        parser.error("Round unavailable or missing a confirmed race start time.")
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    for event in events:
        if args.round_number is not None and event.round_number != args.round_number:
            continue
        weekend = schedule.get_event_by_round(event.round_number)
        for kind in args.sessions:
            directory = ROOT / str(year) / str(event.round_number) / kind
            try:
                start = pd.Timestamp(weekend.get_session_date(kind, utc=True))
                if not pd.isna(start):
                    start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
                if pd.isna(start) or start >= pd.Timestamp.now(tz="UTC"):
                    print(f"Skipping future/undated session: {event.name} {kind}")
                    continue
                session = weekend.get_session(kind)
                session.load(laps=True, telemetry=True, weather=True, messages=True)
                report = save_session(session, directory)
                print(f"Saved {event.name} {kind}: {len(report['telemetry'])} lap records; see manifest for gaps")
            except Exception as exc:
                save_json(directory / "failure.json", {"error": str(exc), "attempted_at": datetime.now(timezone.utc)})
                print(f"Unavailable: {event.name} {kind}: {exc}")


if __name__ == "__main__":
    main()
