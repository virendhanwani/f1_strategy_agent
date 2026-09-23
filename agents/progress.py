"""Translate graph events into progress updates for a chat interface."""

import json

from langchain_core.messages import ToolMessage
from agents.errors import error_response


async def stream_progress(graph, state):
    """Yield tool_start/tool_end/tool_error, then complete or error.

    Tool events carry a run_id so concurrent calls can be tracked separately.
    Only complete carries the updated conversation state. On error, the UI
    should keep its previous history and display the error message.
    """
    try:
        async for event in graph.astream_events(state, version="v2", stream_mode="values"):
            kind = event["event"]
            data = event["data"]
            tool = event["name"]
            run_id = event["run_id"]

            if kind == "on_tool_start":
                yield {
                    "type": "tool_start", "tool": tool, "run_id": run_id,
                    "input": data.get("input"),
                    "message": (
                        "Loading detailed telemetry; this may take a little while."
                        if tool == "get_speed_trace" else f"Running {tool}…"
                    ),
                }
            elif kind == "on_tool_end":
                output = data.get("output")
                value = output.content if isinstance(output, ToolMessage) else output
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (ValueError, TypeError):
                        pass
                # Existing tools sometimes return {"error": ...} instead of raising.
                error = value.get("error") if isinstance(value, dict) else None
                if isinstance(output, ToolMessage) and output.status == "error":
                    error = error or output.content
                yield {
                    "type": "tool_error" if error else "tool_end",
                    "tool": tool, "run_id": run_id, "output": value,
                    "message": str(error) if error else f"Finished {tool}.",
                }
            elif kind == "on_tool_error":
                yield {
                    "type": "tool_error", "tool": tool, "run_id": run_id,
                    "message": str(data.get("error", "Tool failed.")),
                }
            elif kind == "on_chain_end" and not event["parent_ids"]:
                result = data["output"]
                yield {
                    "type": "complete", "state": result,
                    "answer": result["messages"][-1].content,
                }
    except Exception as error:
        failure = error_response(error)
        yield {"type": "error", "message": failure["error"], **failure}
