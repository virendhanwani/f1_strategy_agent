from __future__ import annotations

from agents.jolpica_mcp_client import get_lap_times, get_pit_stops
from agents.errors import handle_tool_errors, tool_error
from analysis.pit_strategy import (
    build_position_timeline,
    build_pit_stops_df,
    find_strategy_swaps,
    summarize_swaps,
)


@handle_tool_errors
async def analyze_race_strategy(season: str, round_: str, max_stop_gap: int = 5) -> dict:
    """
    The tool function: given a season + round, fetches lap times and pit
    stops via the MCP server, detects undercut/overcut swaps, and returns
    both a structured event list and plain-English summaries.
    """
    if max_stop_gap < 1:
        return tool_error("invalid_input", "max_stop_gap must be at least 1.",
                          "Use 5 laps for the default pit-stop matching window.")
    laps = await get_lap_times(season, round_)
    if "error" in laps:
        return laps
    laps_df = build_position_timeline(laps)
    if laps_df.empty:
        return tool_error("no_data", "No lap positions are available for this race.",
                          "Pit strategy cannot be analyzed without lap positions.")
    pits = await get_pit_stops(season, round_)
    if "error" in pits:
        return pits

    pits_df = build_pit_stops_df(pits)

    if pits_df.empty:
        return {
            "race_name": laps.get("race_name", "unknown"),
            "events": [],
            "max_stop_gap": max_stop_gap,
            "summary": ["No pit stops recorded for this race — nothing to analyze."],
        }

    events_df = find_strategy_swaps(laps_df, pits_df, max_stop_gap=max_stop_gap)
    summaries = summarize_swaps(events_df)

    return {
        "race_name": laps.get("race_name", "unknown"),
        "events": events_df.to_dict(orient="records"),
        "summary": summaries,
        "max_stop_gap": max_stop_gap,
        "evaluated_sequences": events_df.attrs["evaluated_sequences"],
        "limitations": "Possible effects only: safety cars, traffic, penalties, and different race strategies are not accounted for.",
    }
