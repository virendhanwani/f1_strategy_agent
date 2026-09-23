from __future__ import annotations
from langchain_core.tools import tool

from agents.jolpica_mcp_client import call_mcp_tool
from agents.pit_strategy_tool import analyze_race_strategy
from agents.telemetry_tool import get_tire_strategy, compare_pace, get_lap_speed_trace
from agents.rules_rag_tool import answer_regulation_question

# ---- MCP — fast, always try first ---------------------

@tool
async def get_race_results(season: str, race_name: str) -> dict:
    """Get official race results (finishing order, points, retirements).
    FAST — use first for any "who won/finished/retired" question.
    """
    return await call_mcp_tool("get_race_results_by_name", season=season, race_name=race_name)


@tool
async def get_qualifying_results(season: str, round: str = "last") -> dict:
    """Get qualifying results (grid order, Q1/Q2/Q3 times).
    FAST — use for pole position / grid order questions.
    """
    return await call_mcp_tool("get_qualifying_results", season=season, round=round)


@tool
async def get_pit_stops(season: str, round: str) -> dict:
    """Get the pit stop log (lap, duration) for a race.
    FAST — use for pit stop timing/count, not tire physics.
    """
    return await call_mcp_tool("get_pit_stops", season=season, round=round)


@tool
async def get_lap_times(season: str, round: str, driver_name: str | None = None) -> dict:
    """Get lap-by-lap times and track positions, optionally for one driver.
    FAST — use for "who was leading at lap X" or position-change questions
    that DON'T need tire/telemetry detail.
    """
    if driver_name:
        return await call_mcp_tool("get_lap_times_by_driver_name", season=season, round=round, driver_name=driver_name)
    return await call_mcp_tool("get_lap_times", season=season, round=round)


@tool
async def get_driver_standings(season: str = "current") -> dict:
    """Get the drivers' championship standings.
    FAST — use for "who is leading the championship" questions.
    """
    return await call_mcp_tool("get_driver_standings", season=season)


@tool
async def get_constructor_standings(season: str = "current") -> dict:
    """Get the constructors' championship standings.
    FAST — use for constructors' title battle questions.
    """
    return await call_mcp_tool("get_constructor_standings", season=season)


@tool
async def get_race_schedule(season: str) -> dict:
    """Get the full race calendar — every round, circuit, and date.
    FAST — use for upcoming-race or season-schedule questions.
    """
    return await call_mcp_tool("get_race_schedule", season=season)


# ---- Strategy analysis on MCP data — no FastF1 needed -------

@tool
async def analyze_pit_strategy(season: str, round: str, max_stop_gap: int = 5) -> dict:
    """Detect possible undercut/overcut gains after both drivers have pitted.
    max_stop_gap: Maximum laps between the two stops; defaults to 5.
    Unmatched stops are unclassified; position changes do not prove causation.
    FAST — built from lap times + pit stops only, no telemetry load.
    Try this BEFORE tire telemetry for any "why" question about a
    strategy decision or position change around a pit stop.
    """
    return await analyze_race_strategy(season, round, max_stop_gap=max_stop_gap)


# ---- FastF1 — SLOW, only when Tier 1 truly can't answer -------

@tool
async def get_tire_degradation(year: int, race: str, driver: str) -> dict:
    """Get tire stint breakdown and degradation rate (sec/lap) for a driver.
    SLOWER than the tools above — only use for questions specifically about
    tire wear, tire age, or compound performance. Try analyze_pit_strategy
    first for general strategy "why" questions.
    """
    return await get_tire_strategy(year, race, driver)


@tool
async def compare_driver_pace(year: int, race: str, drivers: list[str]) -> dict:
    """Compare median lap pace across multiple drivers.
    SLOWER — requires cached FastF1 session data.
    """
    return await compare_pace(year, race, drivers)


@tool
async def get_speed_trace(year: int, race: str, driver: str, lap_number: int) -> dict:
    """Get raw speed/throttle/brake telemetry for ONE specific lap.
    SLOWEST tool — can take 15-30s on an uncached session. Only use for a
    narrow, explicit request about one lap's telemetry — never by default.
    """
    return await get_lap_speed_trace(year, race, driver, lap_number)


# ---- Regulations RAG --------------------------------------------------

@tool
async def ask_about_regulations(question: str, year: int = 2026) -> dict:
    """Answer rules questions using the available 2026 FIA regulations only.
    Pass the year relevant to the user's question or race, including follow-ups.
    Resolve relative years using today's date. Other years return a limitation;
    never substitute 2026 rules for a historical race. For a general question
    without a year, default to 2026 and explicitly identify that scope.
    """
    return await answer_regulation_question(question, year=year)

ALL_TOOLS = [
    get_race_results,
    get_qualifying_results,
    get_pit_stops,
    get_lap_times,
    get_driver_standings,
    get_constructor_standings,
    get_race_schedule,
    analyze_pit_strategy,
    get_tire_degradation,
    compare_driver_pace,
    get_speed_trace,
    ask_about_regulations,
]
