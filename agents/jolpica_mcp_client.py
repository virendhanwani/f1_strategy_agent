import asyncio
import os
from pathlib import Path
from weakref import WeakKeyDictionary

from dotenv import load_dotenv
from fastmcp import Client
from agents.errors import handle_tool_errors, tool_error

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

_clients = WeakKeyDictionary()


def get_mcp_server_path() -> Path:
    """Resolve relative overrides against the project, never the launch directory."""
    configured = os.environ.get("MCP_SERVER_PATH", "").strip()
    path = Path(configured or "../f1-mcp/src/server.py").expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"MCP server file not found: {path}")
    return path


def get_mcp_client() -> Client:
    """Create on demand, sharing only within the current async event loop.

    Separate asyncio.run() calls must not reuse a client's async resources.
    The async context in call_mcp_tool still owns connection cleanup.
    """
    loop = asyncio.get_running_loop()
    if loop not in _clients:
        _clients[loop] = Client(str(get_mcp_server_path()))
    return _clients[loop]


@handle_tool_errors
async def call_mcp_tool(tool_name: str, **kwargs) -> dict:
    try:
        client = get_mcp_client()
    except FileNotFoundError as error:
        return tool_error("missing_mcp_server", str(error),
                          "Set MCP_SERVER_PATH to the server.py file in your f1-mcp checkout.")
    async with client:
        result = await client.call_tool(tool_name, kwargs)
        if not isinstance(result.data, dict):
            return tool_error("invalid_response", "The MCP server returned an unexpected response.",
                              "Check the MCP server logs before retrying.")
        return result.data

async def get_lap_times(season: str, round_: str, driver_id: str | None = None) -> dict:
    return await call_mcp_tool("get_lap_times", season=season, round=round_, driver_id=driver_id)

async def get_pit_stops(season: str, round_: str) -> dict:
    return await call_mcp_tool("get_pit_stops", season=season, round=round_)
