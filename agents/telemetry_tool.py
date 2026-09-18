from __future__ import annotations

from analysis.telemetry import (
    load_laps,
    driver_stints,
    tire_degradation,
    degradation_rate,
    compare_drivers_pace,
    speed_trace,
)


async def get_tire_strategy(year: int, race: str, driver: str, session_type: str = "R") -> dict:
    """
    Fast path — reads cached parquet only. Returns every stint for a driver
    plus a degradation rate (sec/lap) per stint.
    """
    try:
        laps = load_laps(year, race, session_type)
    except FileNotFoundError as e:
        return {"error": str(e), "hint": "This session hasn't been ingested yet — run ingestion/fetch_sessions.py for it first."}

    stints = driver_stints(laps, driver)
    if stints.empty:
        return {"error": f"No stint data found for driver '{driver}' in {year} {race}"}

    stint_details = []
    for _, s in stints.iterrows():
        rate = degradation_rate(laps, driver, stint=int(s["Stint"]))
        stint_details.append(
            {
                "stint": int(s["Stint"]),
                "compound": s["compound"],
                "laps": f"{int(s['start_lap'])}-{int(s['end_lap'])}",
                "stint_length": int(s["laps_on_stint"]),
                "degradation_sec_per_lap": rate,
            }
        )

    return {"year": year, "race": race, "driver": driver, "stints": stint_details}


async def compare_pace(year: int, race: str, drivers: list[str], session_type: str = "R") -> dict:
    """Fast path — median clean-lap pace across multiple drivers."""
    try:
        laps = load_laps(year, race, session_type)
    except FileNotFoundError as e:
        return {"error": str(e)}

    comparison = compare_drivers_pace(laps, drivers)
    return {
        "year": year,
        "race": race,
        "comparison": comparison.to_dict(orient="records"),
    }


async def get_lap_speed_trace(year: int, race: str, driver: str, lap_number: int, session_type: str = "R") -> dict:
    """
    SLOW PATH — loads a full FastF1 session live (15-30s on first call for
    an uncached session). Only call this for a narrow, specific drill-down
    question about one lap's raw telemetry — never as a default/first tool.
    """
    trace = speed_trace(year, race, driver, lap_number, session_type)
    return {
        "year": year,
        "race": race,
        "driver": driver,
        "lap_number": lap_number,
        "trace": trace.to_dict(orient="records"),
    }
