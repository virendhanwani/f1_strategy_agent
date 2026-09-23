from __future__ import annotations
import asyncio
from agents.errors import handle_tool_errors, tool_error

from analysis.telemetry import (
    load_laps,
    driver_stints,
    tire_degradation,
    degradation_rate,
    compare_drivers_pace,
    speed_trace,
)


@handle_tool_errors
async def get_tire_strategy(year: int, race: str, driver: str, session_type: str = "R") -> dict:
    """
    Fast path — reads cached parquet only. Returns every stint for a driver
    plus a degradation rate (sec/lap) per stint.
    """
    try:
        laps = load_laps(year, race, session_type)
    except FileNotFoundError as e:
        return tool_error("missing_cache", str(e), "Ingest this session before requesting tire analysis.")

    stints = driver_stints(laps, driver)
    if stints.empty:
        return tool_error("no_data", f"No stint data found for driver '{driver}' in {year} {race}.",
                          "Check the three-letter driver code and race.")

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


@handle_tool_errors
async def compare_pace(year: int, race: str, drivers: list[str], session_type: str = "R") -> dict:
    """Fast path — median clean-lap pace across multiple drivers."""
    if not drivers:
        return tool_error("invalid_input", "No drivers were supplied.", "Provide driver codes such as VER and HAM.")
    try:
        laps = load_laps(year, race, session_type)
    except FileNotFoundError as e:
        return tool_error("missing_cache", str(e), "Ingest this session before comparing pace.")

    comparison = compare_drivers_pace(laps, drivers)
    if comparison.empty:
        return tool_error("no_data", "No clean laps were found for the requested drivers.",
                          "Check the driver codes and race; pace cannot be compared without clean laps.")
    missing = [driver for driver in drivers if driver not in comparison["driver"].values]
    return {
        "year": year,
        "race": race,
        "comparison": comparison.to_dict(orient="records"),
        "missing_drivers": missing,
    }


@handle_tool_errors
async def get_lap_speed_trace(year: int, race: str, driver: str, lap_number: int, session_type: str = "R") -> dict:
    """
    SLOW PATH — loads a full FastF1 session live (15-30s on first call for
    an uncached session). Only call this for a narrow, specific drill-down
    question about one lap's raw telemetry — never as a default/first tool.
    """
    if lap_number < 1:
        return tool_error("invalid_input", "Lap number must be positive.", "Use a lap number starting at 1.")
    # Keep the event loop available to deliver progress during the slow load.
    trace = await asyncio.to_thread(speed_trace, year, race, driver, lap_number, session_type)
    if trace.empty:
        return tool_error("no_data", f"No telemetry is available for {driver} on lap {lap_number}.",
                          "Check the driver and lap; retired drivers may not have completed that lap.")
    return {
        "year": year,
        "race": race,
        "driver": driver,
        "lap_number": lap_number,
        "trace": trace.to_dict(orient="records"),
    }
