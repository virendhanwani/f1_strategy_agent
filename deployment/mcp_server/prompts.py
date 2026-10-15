from fastmcp.prompts import Message


def register(mcp) -> None:
    """Registers all prompts onto the given FastMCP server instance."""

    @mcp.prompt()
    def race_results_prompt(season: str, round: str = "last") -> list[Message]:
        """Get and summarize the results of a specific race by round number."""
        return [
            Message(
                f"Use get_race_results to fetch results for season {season}, round {round}, "
                f"then summarize the top 5 finishers and any notable retirements or penalties."
            )
        ]

    @mcp.prompt()
    def race_results_by_name_prompt(season: str, race_name: str) -> list[Message]:
        """Get and summarize the results of a specific race by name."""
        return [
            Message(
                f"Use get_race_results_by_name to fetch results for the {race_name} race in {season}, "
                f"then summarize the top 5 finishers and any notable retirements or penalties."
            )
        ]

    @mcp.prompt()
    def qualifying_summary_prompt(season: str, round: str = "last") -> list[Message]:
        """Get and summarize qualifying results for a race."""
        return [
            Message(
                f"Use get_qualifying_results to fetch qualifying for season {season}, round {round}, "
                f"then summarize who took pole and how close the top 3 times were."
            )
        ]

    @mcp.prompt()
    def pit_stops_summary_prompt(season: str, round: str) -> list[Message]:
        """Get and summarize pit stop activity for a race."""
        return [
            Message(
                f"Use get_pit_stops to fetch pit stop data for season {season}, round {round}, "
                f"then summarize the fastest stop and any drivers with more than 2 stops."
            )
        ]

    @mcp.prompt()
    def driver_standings_prompt(season: str = "current") -> list[Message]:
        """Get and summarize the drivers' championship standings."""
        return [
            Message(
                f"Use get_driver_standings to fetch the {season} driver standings, "
                f"then summarize the top 5 and the points gap between 1st and 2nd."
            )
        ]

    @mcp.prompt()
    def constructor_standings_prompt(season: str = "current") -> list[Message]:
        """Get and summarize the constructors' championship standings."""
        return [
            Message(
                f"Use get_constructor_standings to fetch the {season} constructor standings, "
                f"then summarize the top 3 and how tight the battle is between them."
            )
        ]

    @mcp.prompt()
    def lap_times_prompt(season: str, round: str, driver_id: str) -> list[Message]:
        """Summarize a driver's lap-by-lap pace across a race."""
        return [
            Message(
                f"Use get_lap_times to fetch {driver_id}'s laps for season {season}, round {round}, "
                f"then summarize their pace trend — any laps notably slower or faster than their average."
            )
        ]

    @mcp.prompt()
    def driver_info_prompt(driver_id: str) -> list[Message]:
        """Get a quick bio summary for a driver."""
        return [Message(f"Use get_driver_info to look up {driver_id} and summarize who they are.")]

    @mcp.prompt()
    def race_schedule_prompt(season: str) -> list[Message]:
        """Summarize the full race calendar for a season."""
        return [
            Message(
                f"Use get_race_schedule to fetch the {season} calendar and list all races in order with their dates."
            )
        ]
