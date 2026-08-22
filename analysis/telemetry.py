from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


def load_laps(year: int, race: str, session_type: str = "R") -> pd.DataFrame:
    slug = f"{year}_{race.replace(' ', '_')}_{session_type}"
    path = PROCESSED_DIR / f"{slug}_laps.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No cached laps for {slug} — run ingestion/fetch_sessions.py first")
    return pd.read_parquet(path)


def driver_stints(laps: pd.DataFrame, driver: str) -> pd.DataFrame:
    """One row per stint for a driver: compound, lap range, stint length."""
    d = laps[laps["Driver"] == driver].sort_values("LapNumber")
    return (
        d.groupby("Stint")
        .agg(
            compound=("Compound", "first"),
            start_lap=("LapNumber", "min"),
            end_lap=("LapNumber", "max"),
            laps_on_stint=("LapNumber", "count"),
        )
        .reset_index()
    )


def tire_degradation(laps: pd.DataFrame, driver: str, stint: int | None = None) -> pd.DataFrame:
    """
    Lap time vs tire age for a driver, optionally scoped to one stint.
    Drops in/out laps (pit entry/exit distorts lap time) and laps over 115%
    of the stint median (safety car / red flag laps) — neither reflects real
    tire wear, and including them would wreck the degradation trend.
    """
    d = laps[laps["Driver"] == driver].copy()
    if stint is not None:
        d = d[d["Stint"] == stint]

    d = d[d["PitOutTime"].isna() & d["PitInTime"].isna()]
    d["LapTimeSeconds"] = d["LapTime"].dt.total_seconds()

    if not d.empty:
        median = d["LapTimeSeconds"].median()
        d = d[d["LapTimeSeconds"] <= median * 1.15]

    return d[["LapNumber", "TyreLife", "Compound", "Stint", "LapTimeSeconds"]].sort_values("LapNumber")


def degradation_rate(laps: pd.DataFrame, driver: str, stint: int) -> float | None:
    """
    Seconds lost per lap of tire age, via linear fit over one stint's clean
    laps. Positive = slowing down, as expected. None if too few clean laps
    remain after filtering to fit a meaningful trend.
    """
    d = tire_degradation(laps, driver, stint=stint)
    if len(d) < 3:
        return None
    slope = np.polyfit(d["TyreLife"], d["LapTimeSeconds"], 1)[0]
    return round(float(slope), 3)


def compare_drivers_pace(laps: pd.DataFrame, drivers: list[str]) -> pd.DataFrame:
    """Median clean-lap time per driver — a quick head-to-head pace comparison."""
    rows = []
    for drv in drivers:
        d = tire_degradation(laps, drv)
        if not d.empty:
            rows.append({"driver": drv, "median_lap_time": d["LapTimeSeconds"].median(), "clean_laps": len(d)})
    return pd.DataFrame(rows).sort_values("median_lap_time")


def speed_trace(year: int, race: str, driver: str, lap_number: int, session_type: str = "R") -> pd.DataFrame:
    """
    Speed/throttle/brake trace for ONE specific lap.

    This is the genuinely slow path — raw telemetry isn't part of what
    fetch_sessions.py caches to parquet, so this loads the full FastF1
    session live. Only call this for a narrow, specific drill-down question
    (e.g. "show me lap 42's speed trace"), never as a first-pass tool.
    """
    import fastf1

    session = fastf1.get_session(year, race, session_type)
    session.load(laps=True, telemetry=True, weather=False)
    lap = session.laps.pick_driver(driver).pick_lap(lap_number)
    car_data = lap.get_car_data().add_distance()
    return car_data[["Distance", "Speed", "Throttle", "Brake", "nGear"]]
