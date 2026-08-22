"""
Fetches and caches FastF1 session data for a set of races.
"""

from __future__ import annotations
from pathlib import Path
import fastf1
import pandas as pd

CACHE_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


SESSIONS_TO_FETCH = [
    (2023, "Monaco", "R"),
    (2023, "Singapore", "R"),
    (2022, "Zandvoort", "R"),
    (2024, "Brazil", "R"),
]

def setup_cache() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

def fetch_and_save(year: int, race: str, session_type: str) -> None:
    print(f"Loading {year} {race} ({session_type})...")
    session = fastf1.get_session(year, race, session_type)
    session.load()

    laps = session.laps
    results = session.results
    weather = session.weather_data
    track_status = session.track_status_data
    race_control = session.race_control_messages

    slug = f"{year}_{race.replace(' ', '_')}_{session_type}"
    laps.to_parquet(PROCESSED_DIR / f"{slug}_laps.parquet")
    results.to_parquet(PROCESSED_DIR / f"{slug}_results.parquet")
    weather.to_parquet(PROCESSED_DIR / f"{slug}_weather.parquet")
    track_status.to_parquet(PROCESSED_DIR / f"{slug}_track_status.parquet")
    race_control.to_parquet(PROCESSED_DIR / f"{slug}_race_control.parquet")

    print(f"  -> saved {len(laps)} laps, {len(results)} results, "
          f"{len(track_status)} track status changes, {len(race_control)} race control messages")

def main() -> None:
    setup_cache()
    for year, race, session_type in SESSIONS_TO_FETCH:
        try:
            fetch_and_save(year, race, session_type)
        except Exception as e:
            print(f"  FAILED for {year} {race}: {e}")


if __name__ == "__main__":
    main()