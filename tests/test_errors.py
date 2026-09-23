"""Run offline checks with local cached data: python -m tests.test_errors."""

import asyncio

import pandas as pd
from fastmcp.exceptions import ToolError

from agents.errors import error_response
from agents.telemetry_tool import compare_pace, get_tire_strategy, get_lap_speed_trace
from analysis.pit_strategy import build_position_timeline, build_pit_stops_df, find_strategy_swaps
from analysis.telemetry import load_laps, compare_drivers_pace, degradation_rate


async def main():
    missing = await get_tire_strategy(2023, "Nonexistent race", "VER")
    assert missing["code"] == "missing_cache"
    assert set(missing) == {"error", "code", "hint", "retryable"}

    empty = await compare_pace(2023, "Monaco", [])
    assert empty["code"] == "invalid_input"
    unknown = await compare_pace(2023, "Monaco", ["UNKNOWN"])
    assert unknown["code"] == "no_data"
    unknown_stints = await get_tire_strategy(2023, "Monaco", "UNKNOWN")
    assert unknown_stints["code"] == "no_data"
    partial = await compare_pace(2023, "Monaco", ["VER", "UNKNOWN"])
    assert partial["missing_drivers"] == ["UNKNOWN"]
    assert partial["comparison"][0]["driver"] == "VER"

    invalid_lap = await get_lap_speed_trace(2023, "Monaco", "VER", 0)
    assert invalid_lap["code"] == "invalid_input"

    laps = load_laps(2023, "Monaco")
    assert compare_drivers_pace(laps.iloc[:0], ["VER"]).empty
    laps["TyreLife"] = float("nan")
    assert degradation_rate(laps, "VER", 1) is None
    empty_laps = build_position_timeline({"laps": []})
    empty_pits = build_pit_stops_df({"pit_stops": []})
    assert find_strategy_swaps(empty_laps, empty_pits).empty
    assert find_strategy_swaps(empty_laps, pd.DataFrame([{"lap": 5, "driver_id": "perez"}])).empty

    limited = error_response(ToolError("Rate limited by upstream API, please retry later"))
    assert limited["code"] == "rate_limited" and limited["retryable"]
    not_found = error_response(ToolError("No race data found for path=/2099/1/laps.json"))
    assert not_found["code"] == "not_found" and not not_found["retryable"]
    assert error_response(TimeoutError())["code"] == "timeout"
    print("Passed: missing cache, invalid inputs, unknown drivers, partial pace, empty data, and service errors.")


if __name__ == "__main__":
    asyncio.run(main())
