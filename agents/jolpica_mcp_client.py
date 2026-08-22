from fastmcp import Client

MCP_SERVER_PATH = "../f1-mcp/src/server.py"

_client: Client | None = None


async def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(MCP_SERVER_PATH)
        await _client.__aenter__()  # opens the subprocess + session once
    return _client


async def get_lap_times(season: str, round_: str) -> dict:
    client = await get_client()
    result = await client.call_tool("get_lap_times", {"season": season, "round": round_})
    return result.data


async def get_pit_stops(season: str, round_: str) -> dict:
    client = await get_client()
    result = await client.call_tool("get_pit_stops", {"season": season, "round": round_})
    return result.data