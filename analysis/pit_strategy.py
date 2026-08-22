"""
Detects undercut/overcut strategy swaps using only data from the Ergast MCP
server (get_pit_stops + get_lap_times) — no FastF1 session load required.

Undercut: a driver pits BEFORE a rival they were racing closely, and emerges
          ahead of them once both have made their stop.
Overcut:  a driver pits AFTER a rival (stays out longer), and still gains
          track position — usually because their tires stayed faster than
          the rival's aging ones for those extra laps.

This is a heuristic based purely on position swaps around pit windows — it
does NOT account for traffic, virtual safety cars, or penalties, since none
of that is in Jolpica's data. Good enough to flag "something interesting
happened here," not a claim of definitive cause.
"""

from __future__ import annotations
import pandas as pd


def build_position_timeline(laps_data: dict) -> pd.DataFrame:
    """Flattens the get_lap_times MCP tool's nested response into a long
    DataFrame: one row per (lap, driver) with their position that lap."""
    rows = [
        {"lap": lap["number"], "driver_id": t["driver_id"], "position": t["position"], "time": t["time"]}
        for lap in laps_data["laps"]
        for t in lap["timings"]
    ]
    return pd.DataFrame(rows)


def build_pit_stops_df(pit_stops_data: dict) -> pd.DataFrame:
    """Flattens the get_pit_stops MCP tool's response into a flat DataFrame."""
    return pd.DataFrame(pit_stops_data["pit_stops"])


def find_strategy_swaps(laps_df: pd.DataFrame, pits_df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """
    For each pit stop, looks at whoever was immediately ahead/behind on track
    the lap before, then checks `window` laps later: did the order flip?

    If it flipped and the rival hadn't pitted yet (or pitted later) -> undercut.
    If it flipped and the rival had already pitted earlier -> overcut.
    """
    events = []

    for lap_num in pits_df["lap"].unique():
        pitters_this_lap = pits_df[pits_df["lap"] == lap_num]["driver_id"].tolist()
        print(f"Lap {lap_num}: {len(pitters_this_lap)} pitters: {pitters_this_lap}")
        for driver in pitters_this_lap:
            pos_row = laps_df[(laps_df.driver_id == driver) & (laps_df.lap == lap_num - 1)]
            print(f" pos row {pos_row} driver {driver}")
            if pos_row.empty:
                continue
            pos_before = pos_row.iloc[0].position

            # drivers running immediately ahead/behind before this pit stop
            neighbors = laps_df[
                (laps_df.lap == lap_num - 1) & (laps_df.position.isin([pos_before - 1, pos_before + 1]))
            ]
            print(f"  {driver} was P{pos_before} before pitting; neighbors: {neighbors['driver_id'].tolist()}")
            for _, neighbor in neighbors.iterrows():
                rival = neighbor.driver_id
                if rival == driver:
                    continue

                rival_pits = pits_df[
                    (pits_df.driver_id == rival) & (pits_df.lap.between(lap_num - window, lap_num + window))
                ]
                rival_pit_lap = rival_pits.iloc[0].lap if not rival_pits.empty else None

                check_lap = lap_num + window
                driver_after = laps_df[(laps_df.driver_id == driver) & (laps_df.lap == check_lap)]
                rival_after = laps_df[(laps_df.driver_id == rival) & (laps_df.lap == check_lap)]
                if driver_after.empty or rival_after.empty:
                    continue

                was_ahead = pos_before < neighbor.position
                is_ahead_after = driver_after.iloc[0].position < rival_after.iloc[0].position

                if was_ahead != is_ahead_after:
                    strategy = "undercut" if (rival_pit_lap is None or lap_num < rival_pit_lap) else "overcut"
                    events.append(
                        {
                            "lap": lap_num,
                            "driver": driver,
                            "rival": rival,
                            "strategy": strategy,
                            "position_before": pos_before,
                            "rival_position_before": neighbor.position,
                            "position_after": driver_after.iloc[0].position,
                            "rival_position_after": rival_after.iloc[0].position,
                        }
                    )

    return pd.DataFrame(events)


def summarize_swaps(events_df: pd.DataFrame) -> list[str]:
    """Turns the raw events DataFrame into plain-English sentences —
    this is what actually gets handed to the LLM/agent layer."""
    if events_df.empty:
        return ["No clear undercut/overcut swaps detected in this race."]

    lines = []
    for _, e in events_df.iterrows():
        verb = "undercut" if e.strategy == "undercut" else "overcut"
        lines.append(
            f"Lap {int(e.lap)}: {e.driver} {verb} {e.rival} — "
            f"went from P{int(e.position_before)} to P{int(e.position_after)}, "
            f"while {e.rival} went from P{int(e.rival_position_before)} to P{int(e.rival_position_after)}."
        )
    return lines
