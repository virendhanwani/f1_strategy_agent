"""
Maps FastF1's time-based track_status_data onto lap numbers, so it can be
joined against laps_df in pit_strategy.py and telemetry.py.
"""
import pandas as pd

STATUS_LABELS = {
    "1": "clear", "2": "yellow", "4": "safety_car",
    "5": "red_flag", "6": "vsc", "7": "vsc_ending",
}


def laps_under_caution(laps: pd.DataFrame, track_status: pd.DataFrame) -> set[int]:
    """Returns the set of lap numbers where track status was NOT clear (1)."""
    caution_windows = track_status[track_status["Status"] != "1"]
    caution_laps = set()
    for _, row in caution_windows.iterrows():
        # find laps whose start time falls within this status window
        matching = laps[laps["LapStartTime"] >= row["Time"]]
        if not matching.empty:
            # naive: mark from this status change onward until the next one — refine
            # once you see real data shape; good enough as a first pass
            caution_laps.update(matching["LapNumber"].tolist())
    return caution_laps