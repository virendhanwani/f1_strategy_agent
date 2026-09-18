from fastmcp import Client

MCP_SERVER_PATH = "../f1-mcp/src/server.py"

_client = Client(MCP_SERVER_PATH)


async def call_mcp_tool(tool_name: str, **kwargs) -> dict:
    async with _client:
        result = await _client.call_tool(tool_name, kwargs)
        return result.data

async def get_lap_times(season: str, round_: str, driver_id: str | None = None) -> dict:
    return await call_mcp_tool("get_lap_times", season=season, round=round_, driver_id=driver_id)

async def get_pit_stops(season: str, round_: str) -> dict:
    return await call_mcp_tool("get_pit_stops", season=season, round=round_)