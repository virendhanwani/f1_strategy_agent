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
    return pd.DataFrame(rows, columns=["lap", "driver_id", "position", "time"])


def build_pit_stops_df(pit_stops_data: dict) -> pd.DataFrame:
    """Flattens the get_pit_stops MCP tool's response into a flat DataFrame."""
    return pd.DataFrame(pit_stops_data["pit_stops"], columns=["driver_id", "lap", "stop", "time", "duration"])


def find_strategy_swaps(
    laps_df: pd.DataFrame, pits_df: pd.DataFrame, max_stop_gap: int = 5
) -> pd.DataFrame:
    """Find possible gains between neighboring drivers' paired pit stops.

    The rival must stop 1..max_stop_gap laps after the first driver. Neither
    can stop again before the comparison, made at the end of the lap after
    the second stop (allowing for pit exits across the timing line). Missing
    positions, same-lap stops, and unmatched stops are left unclassified.
    """
    if max_stop_gap < 1:
        raise ValueError("max_stop_gap must be at least 1")
    events = []
    evaluated = 0
    if laps_df.empty or pits_df.empty:
        result = pd.DataFrame(events)
        result.attrs["evaluated_sequences"] = evaluated
        return result

    stops = pits_df.sort_values("lap").drop_duplicates(["driver_id", "lap"])
    for _, first in stops.iterrows():
        early, first_lap = first.driver_id, int(first.lap)
        before_lap = first_lap - 1
        before = laps_df[laps_df.lap == before_lap]
        early_before = before[before.driver_id == early]
        if early_before.empty:
            continue
        early_position = int(early_before.iloc[0].position)
        neighbors = before[before.position.isin([early_position - 1, early_position + 1])]

        for _, neighbor in neighbors.iterrows():
            late = neighbor.driver_id
            rival_stops = stops[(stops.driver_id == late) & (stops.lap >= first_lap)]
            if rival_stops.empty:
                continue
            second_lap = int(rival_stops.iloc[0].lap)
            if not 1 <= second_lap - first_lap <= max_stop_gap:
                continue
            check_lap = second_lap + 1
            # Do not combine two separate pit cycles or compare during another stop.
            extra_early = stops[(stops.driver_id == early) & stops.lap.between(first_lap + 1, check_lap)]
            extra_late = stops[(stops.driver_id == late) & stops.lap.between(second_lap + 1, check_lap)]
            if not extra_early.empty or not extra_late.empty:
                continue

            after = laps_df[laps_df.lap == check_lap]
            early_after = after[after.driver_id == early]
            late_after = after[after.driver_id == late]
            if early_after.empty or late_after.empty:
                continue
            evaluated += 1
            late_position = int(neighbor.position)
            early_final = int(early_after.iloc[0].position)
            late_final = int(late_after.iloc[0].position)

            if early_position > late_position and early_final < late_final:
                driver, rival, strategy = early, late, "undercut"
                driver_stop, rival_stop = first_lap, second_lap
                positions = early_position, late_position, early_final, late_final
            elif early_position < late_position and early_final > late_final:
                driver, rival, strategy = late, early, "overcut"
                driver_stop, rival_stop = second_lap, first_lap
                positions = late_position, early_position, late_final, early_final
            else:
                continue

            events.append({
                "lap": check_lap,
                "driver": driver, "rival": rival, "strategy": strategy,
                "classification": "possible",
                "driver_pit_lap": driver_stop, "rival_pit_lap": rival_stop,
                "comparison_before_lap": before_lap,
                "position_before": positions[0], "rival_position_before": positions[1],
                "position_after": positions[2], "rival_position_after": positions[3],
            })

    result = pd.DataFrame(events)
    result.attrs["evaluated_sequences"] = evaluated
    return result


def summarize_swaps(events_df: pd.DataFrame) -> list[str]:
    """Describe possible gains, naming the gaining driver and the losing rival."""
    if events_df.empty:
        if events_df.attrs.get("evaluated_sequences", 0) == 0:
            return ["No comparable matched pit-stop sequences found within the configured window; unmatched stops remain unclassified."]
        return ["No relative-order gains detected in the matched pit-stop sequences."]

    return [
        f"Possible {e.strategy}: {e.driver} pitted on lap {int(e.driver_pit_lap)}, "
        f"{e.rival} on lap {int(e.rival_pit_lap)}. "
        f"Between laps {int(e.comparison_before_lap)} and {int(e.lap)}, "
        f"{e.driver} moved from behind {e.rival} to ahead "
        f"(P{int(e.position_before)} → P{int(e.position_after)}); "
        f"{e.rival} lost the relative position "
        f"(P{int(e.rival_position_before)} → P{int(e.rival_position_after)}). "
        "Position data alone does not prove the cause."
        for _, e in events_df.iterrows()
    ]
