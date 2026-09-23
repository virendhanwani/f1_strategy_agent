"""Small offline examples for the five-lap pit-stop matching rule."""

import pandas as pd

from analysis.pit_strategy import find_strategy_swaps, summarize_swaps


def example(first_position=2, second_stop=25, extra_stops=None):
    laps = pd.DataFrame([
        {"lap": 19, "driver_id": "A", "position": first_position},
        {"lap": 19, "driver_id": "B", "position": 3 - first_position},
        {"lap": second_stop + 1, "driver_id": "A", "position": 3 - first_position},
        {"lap": second_stop + 1, "driver_id": "B", "position": first_position},
    ])
    pits = pd.DataFrame([
        {"driver_id": "A", "lap": 20},
        {"driver_id": "B", "lap": second_stop},
        *(extra_stops or []),
    ])
    return laps, pits


def main():
    laps, pits = example()
    events = find_strategy_swaps(laps, pits)
    assert len(events) == 1
    assert events.iloc[0].driver == "A" and events.iloc[0].strategy == "undercut"
    assert events.iloc[0].lap == 26  # after the second stop, not first stop + 3
    print(summarize_swaps(events)[0])

    events = find_strategy_swaps(*example(first_position=1))
    assert len(events) == 1
    assert events.iloc[0].driver == "B" and events.iloc[0].strategy == "overcut"
    print(summarize_swaps(events)[0])

    assert find_strategy_swaps(*example(second_stop=26)).empty
    assert len(find_strategy_swaps(*example(second_stop=26), max_stop_gap=6)) == 1
    assert find_strategy_swaps(*example(second_stop=20)).empty
    assert find_strategy_swaps(*example(extra_stops=[{"driver_id": "A", "lap": 23}])).empty
    assert find_strategy_swaps(laps, pits.iloc[:1]).empty
    assert find_strategy_swaps(laps[laps.lap == 19], pits).empty

    unchanged = laps.copy()
    unchanged.loc[unchanged.lap == 26, "position"] = [2, 1]
    events = find_strategy_swaps(unchanged, pits)
    assert events.empty and events.attrs["evaluated_sequences"] == 1
    assert "No relative-order gains" in summarize_swaps(events)[0]
    print("Passed: undercut, overcut, five-lap boundary, custom window, same-lap/repeated/unmatched stops, missing positions, unchanged order.")


if __name__ == "__main__":
    main()
