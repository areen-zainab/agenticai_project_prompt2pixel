"""
Thin HTTP client used by agents to discover and invoke MCP tools.
Agents import this instead of duplicating _invoke_mcp / _discover_tool.
"""

import httpx

from shared.config.config import MCP_BASE_URL

_TOOLS_URL = f"{MCP_BASE_URL.rstrip('/')}/tools"
_INVOKE_URL = f"{MCP_BASE_URL.rstrip('/')}/invoke"


def discover_tool(tool_name: str) -> dict | None:
    """Query /tools and return the schema for tool_name, or None if not found."""
    try:
        resp = httpx.get(_TOOLS_URL, timeout=10)
        resp.raise_for_status()
        return next((t for t in resp.json() if t["name"] == tool_name), None)
    except Exception as e:
        raise RuntimeError(f"MCP tool discovery failed: {e}")


def invoke_tool(tool_name: str, tool_input: dict, timeout: int = 120) -> dict:
    """POST to /invoke and return the output dict."""
    try:
        resp = httpx.post(
            _INVOKE_URL,
            json={"tool": tool_name, "input": tool_input},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["output"]
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", str(e))
        raise RuntimeError(f"MCP invoke '{tool_name}' failed: {detail}")
