from __future__ import annotations

from agents.jolpica_mcp_client import get_lap_times, get_pit_stops
from analysis.pit_strategy import (
    build_position_timeline,
    build_pit_stops_df,
    find_strategy_swaps,
    summarize_swaps,
)


async def analyze_race_strategy(season: str, round_: str) -> dict:
    """
    The tool function: given a season + round, fetches lap times and pit
    stops via the MCP server, detects undercut/overcut swaps, and returns
    both a structured event list and plain-English summaries.
    """
    laps = await get_lap_times(season, round_)
    pits = await get_pit_stops(season, round_)

    laps_df = build_position_timeline(laps)
    pits_df = build_pit_stops_df(pits)

    if pits_df.empty:
        return {
            "race_name": laps.get("race_name", "unknown"),
            "events": [],
            "summary": ["No pit stops recorded for this race — nothing to analyze."],
        }

    events_df = find_strategy_swaps(laps_df, pits_df)
    summaries = summarize_swaps(events_df)

    return {
        "race_name": laps.get("race_name", "unknown"),
        "events": events_df.to_dict(orient="records"),
        "summary": summaries,
    }
