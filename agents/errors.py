"""Shared error responses for tools; successful response shapes stay unchanged."""

import json
import logging
from functools import wraps

import httpx
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

logger = logging.getLogger(__name__)


def tool_error(code: str, message: str, hint: str, retryable: bool = False) -> dict:
    return {"error": message, "code": code, "hint": hint, "retryable": retryable}


def error_response(error: Exception) -> dict:
    """Translate failures without presenting internal tracebacks as answers."""
    status = getattr(error, "status_code", None)
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
    # MCP transports upstream exceptions as text, without their Python type.
    remote = str(error).lower() if isinstance(error, ToolError) else ""
    if status == 429 or "rate limit" in remote or "throttled" in remote:
        return tool_error("rate_limited", "The data provider is rate limiting requests.",
                          "Wait before trying again; do not immediately repeat this tool call.", True)
    if isinstance(error, (TimeoutError, httpx.TimeoutException)) or "timed out" in remote:
        return tool_error("timeout", "The request timed out.", "Try again later.", True)
    if isinstance(error, (ConnectionError, httpx.TransportError)) or "not connected" in remote:
        return tool_error("connection_error", "Could not connect to the service.",
                          "Check that the MCP server and network are available, then retry.", True)
    if status in (401, 403):
        return tool_error("access_denied", "The service rejected access.",
                          "Check the service credentials and permissions.")
    if status is not None and status >= 500:
        return tool_error("service_unavailable", "The service is temporarily unavailable.",
                          "Try again later.", True)
    if status == 404 or any(text in remote for text in (
        "no race data found", "no race matching", "no driver matching", "no driver found",
        "no circuit matching", "no circuit found", "no driver standings", "no constructor standings",
    )):
        return tool_error("not_found", "No data was found for the requested race, season, or participant.",
                          "Check the year, race, and driver. Future races may not have results yet.")
    if isinstance(error, ValidationError):
        return tool_error("invalid_input", "The tool arguments are invalid.",
                          "Check the required arguments and their types.")
    logger.error("Tool failed", exc_info=(type(error), error, error.__traceback__))
    return tool_error("tool_failed", "The tool could not complete this request.",
                      "Use other available data or report the failure; check the server logs for details.")


def handle_tool_errors(function):
    """Keep a failed capability from aborting the entire conversation."""
    @wraps(function)
    async def wrapped(*args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except Exception as error:
            return error_response(error)
    return wrapped


def tool_node_error(error: Exception) -> str:
    """Handle failures raised before a tool function runs (e.g. validation)."""
    if isinstance(getattr(error, "source", None), ValidationError):
        error = error.source
    return json.dumps(error_response(error))
