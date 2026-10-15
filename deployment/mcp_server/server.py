"""
MCP server exposing Jolpica-F1 data as tools.
"""

from fastmcp import FastMCP
from client import JolpicaClient
import prompts

mcp = FastMCP("f1-mcp")

_client = JolpicaClient()

prompts.register(mcp)

@mcp.tool()
async def get_race_results(season: str, round: str = "last") -> dict:
    """Get results for a specific F1 race.

    Args:
        season: Season year, e.g. "2024". Use "current" for the current season.
        round: Round number as a string, e.g. "1". Use "last" for the most recent race.
    """
    result = await _client.get_race_results(season, round)
    return result.model_dump()


@mcp.tool()
async def get_qualifying_results(season: str, round: str = "last") -> dict:
    """Get qualifying results for a specific F1 race weekend.

    Args:
        season: Season year, e.g. "2024".
        round: Round number as a string. Use "last" for the most recent.
    """
    result = await _client.get_qualifying(season, round)
    return result.model_dump()


@mcp.tool()
async def get_pit_stops(season: str, round: str) -> dict:
    """Get all pit stops for a specific race. Only available from the 2011 season onward.

    Args:
        season: Season year, e.g. "2024".
        round: Round number as a string, e.g. "1".
    """
    result = await _client.get_pit_stops(season, round)
    return result.model_dump()


@mcp.tool()
async def get_driver_standings(season: str = "current") -> dict:
    """Get the F1 drivers' championship standings for a season.

    Args:
        season: Season year, e.g. "2024". Defaults to the current season.
    """
    result = await _client.get_driver_standings(season)
    return result.model_dump()


@mcp.tool()
async def get_constructor_standings(season: str = "current") -> dict:
    """Get the F1 constructors' championship standings for a season.

    Args:
        season: Season year, e.g. "2024". Defaults to the current season.
    """
    result = await _client.get_constructor_standings(season)
    return result.model_dump()

@mcp.tool()
async def get_race_results_by_name(season: str, race_name: str) -> dict:
    """Get results for a specific F1 race using its name instead of round number.

    Args:
        season: Season year, e.g. "2024".
        race_name: Race name, nickname, or host city — e.g. "Monaco", "Monaco GP",
                    "Monaco Grand Prix", or "Silverstone" all work.
    """
    result = await _client.get_race_results_by_name(season, race_name)
    return result.model_dump()

@mcp.tool()
async def get_lap_times(season: str, round: str, driver_id: str | None = None) -> dict:
    """Get lap-by-lap times and positions for a race, optionally filtered to one driver.

    Args:
        season: Season year, e.g. "2024".
        round: Round number as a string, e.g. "1".
        driver_id: Optional driver ID (e.g. "max_verstappen") to filter to just their laps.
    """
    result = await _client.get_lap_times(season, round, driver_id)
    return result.model_dump()


@mcp.tool()
async def get_lap_times_by_driver_name(season: str, round: str, driver_name: str) -> dict:
    """Get lap-by-lap times for one driver, using their name instead of Jolpica's internal ID.

    Args:
        season: Season year, e.g. "2024".
        round: Round number, e.g. "6".
        driver_name: Driver's name, nickname, or 3-letter code — e.g. "Perez", "Sergio Perez", "PER".
    """
    result = await _client.get_lap_times_by_name(season, round, driver_name)
    return result.model_dump()


@mcp.tool()
async def get_driver_info(driver_id: str) -> dict:
    """Get biographical info for a driver (name, nationality, date of birth, car number).

    Args:
        driver_id: Driver ID, e.g. "max_verstappen", "hamilton".
    """
    result = await _client.get_driver_info(driver_id)
    return result.model_dump()


@mcp.tool()
async def get_circuit_info(circuit_id: str) -> dict:
    """Get details about a circuit (location, country, coordinates).

    Args:
        circuit_id: Circuit ID, e.g. "monaco", "monza", "silverstone".
    """
    result = await _client.get_circuit_info(circuit_id)
    return result.model_dump()


@mcp.tool()
async def get_race_schedule(season: str) -> dict:
    """Get the full race calendar for a season — every round, its circuit, and date.

    Args:
        season: Season year, e.g. "2024". Use "current" for the current season.
    """
    result = await _client.get_race_schedule_typed(season)
    return result.model_dump()


@mcp.tool()
async def get_driver_info_by_name(name: str, season: str = "current") -> dict:
    """Get biographical info for a driver by name instead of driver ID.

    Args:
        name: Driver's name, nickname, or 3-letter code — e.g. "Verstappen", "Max Verstappen", "VER".
        season: Season to search within for name resolution. Defaults to current season.
    """
    result = await _client.get_driver_info_by_name(name, season)
    return result.model_dump()


@mcp.tool()
async def get_circuit_info_by_name(name: str) -> dict:
    """Get details about a circuit by name instead of circuit ID.

    Args:
        name: Circuit name, nickname, or host city — e.g. "Monza", "Silverstone", "Spa".
    """
    result = await _client.get_circuit_info_by_name(name)
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()