"""Check lazy setup without model downloads, credentials, or API calls."""

import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from agents.orchestrator import app, get_agent_llm
from agents.llm import get_llm
from agents.jolpica_mcp_client import get_mcp_client
from agents.rules_rag_tool import _load_collection
from agents.tools import ALL_TOOLS


async def check_mcp_client():
    client = get_mcp_client()
    assert client is get_mcp_client()
    return client  # Constructing it does not start the MCP subprocess.


def main():
    assert app is not None
    assert any(tool.name == "get_race_results" for tool in ALL_TOOLS)
    assert get_llm.cache_info().currsize == 0
    assert get_agent_llm.cache_info().currsize == 0
    assert _load_collection.cache_info().currsize == 0
    assert "chromadb" not in sys.modules
    assert "sentence_transformers" not in sys.modules
    assert "langchain_openrouter" not in sys.modules

    with TemporaryDirectory() as directory:
        for _ in range(2):
            try:
                _load_collection(Path(directory))
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("Missing regulations should report a setup error")
        assert not list(Path(directory).iterdir())
        assert _load_collection.cache_info().currsize == 0

    first = asyncio.run(check_mcp_client())
    second = asyncio.run(check_mcp_client())
    assert first is not second
    print("Passed: graph imports without resource setup, missing RAG stays isolated, MCP clients are cached per loop.")


if __name__ == "__main__":
    main()
