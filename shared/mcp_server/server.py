"""
mcp_server/server.py
────────────────────────────────────────────────────────────────────────────
FastAPI MCP server.

Endpoints:
  GET  /tools         → list all available tool schemas (no handlers exposed)
  POST /invoke        → dispatch to a registered tool by name
  GET  /health        → liveness check

Start with:
  uvicorn shared.mcp_server.server:app --reload --port 8000
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path to resolve 'shared' module
# Resolves: c:/Users/Hafsa/Documents/repo/AgenticAI-Project
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from typing import Any

from shared.mcp_server.tools import TOOL_REGISTRY, TOOL_MAP

app = FastAPI(
    title="PROJECT MONTAGE — MCP Tool Server",
    description="Model Context Protocol server for the Writer's Room pipeline.",
    version="1.0.0",
)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class InvokeRequest(BaseModel):
    tool:  str
    input: dict[str, Any] = {}

    @field_validator("tool")
    @classmethod
    def tool_must_exist(cls, v: str) -> str:
        if v not in TOOL_MAP:
            raise ValueError(f"Unknown tool: '{v}'. Available: {list(TOOL_MAP.keys())}")
        return v


class ToolSchema(BaseModel):
    name:         str
    description:  str
    input_schema: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "tools_registered": len(TOOL_REGISTRY)}


@app.get("/tools", response_model=list[ToolSchema])
def list_tools() -> list[dict]:
    """
    Return all registered tool schemas.
    Agents call this endpoint at runtime to discover available tools.
    Handler callables are NOT exposed.
    """
    return [
        {
            "name":         t["name"],
            "description":  t["description"],
            "input_schema": t["input_schema"],
        }
        for t in TOOL_REGISTRY
    ]


@app.post("/invoke")
def invoke_tool(req: InvokeRequest) -> JSONResponse:
    """
    Dispatch a tool call by name and return the result.

    Body:
        { "tool": "<tool_name>", "input": { ... } }

    Returns:
        { "tool": "<tool_name>", "output": { ... } }
    """
    tool_entry = TOOL_MAP.get(req.tool)
    if tool_entry is None:
        raise HTTPException(status_code=404, detail=f"Tool '{req.tool}' not found.")

    try:
        result = tool_entry["handler"](req.input)
    except RuntimeError as e:
        # Config errors (missing API key etc.) — return 503
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        # Unexpected tool errors — return 500
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {e}")

    return JSONResponse(content={"tool": req.tool, "output": result})


if __name__ == "__main__":
    import uvicorn
    # Import 'app' as a string to allow for better hot-reloading if needed
    uvicorn.run("shared.mcp_server.server:app", host="0.0.0.0", port=8000, reload=True)
