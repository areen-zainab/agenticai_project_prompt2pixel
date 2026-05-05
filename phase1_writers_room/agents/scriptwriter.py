"""
agents/scriptwriter.py
────────────────────────────────────────────────────────────────────────────
Scriptwriter Agent — Auto mode

Queries MCP /tools to discover generate_script_segment, then calls
POST /invoke to generate a structured screenplay JSON from the user prompt.
Writes the result to outputs/scene_manifest.json.
"""

import json

from shared.config.config import SCENE_MANIFEST_PATH, DEFAULT_NUM_SCENES
from shared.mcp_server.client import discover_tool, invoke_tool
from phase1_writers_room.graph.state import AgentState, add_event


# ─────────────────────────────────────────────────────────────────────────────

def run(state: AgentState) -> AgentState:
    """
    Scriptwriter Agent entry point.

    Expects:
        state["raw_prompt"] — the story idea from the user
        state["input_mode"] == "auto"

    Produces:
        state["script"]  — Script TypedDict {"scenes": [...]}
        state["status"]  — "generating_script"
    """
    add_event(state, agent="scriptwriter", message="Discovering MCP tool: generate_script_segment…")
    tool_schema = discover_tool("generate_script_segment")
    if tool_schema is None:
        state["status"] = "error"
        state["error"]  = "MCP tool 'generate_script_segment' not found in registry."
        add_event(state, agent="scriptwriter", level="error", message=state["error"])
        return state

    prompt = state.get("raw_prompt", "")
    if not prompt:
        state["status"] = "error"
        state["error"]  = "No prompt provided in auto mode."
        add_event(state, agent="scriptwriter", level="error", message=state["error"])
        return state

    add_event(
        state,
        agent="scriptwriter",
        message=f"Generating {DEFAULT_NUM_SCENES} scene(s) from prompt…",
        data={"prompt_preview": prompt[:120]},
    )
    state["status"] = "generating_script"

    try:
        script = invoke_tool(
            "generate_script_segment",
            {"prompt": prompt, "num_scenes": DEFAULT_NUM_SCENES},
            timeout=120,
        )
    except RuntimeError as e:
        state["status"] = "error"
        state["error"]  = str(e)
        add_event(state, agent="scriptwriter", level="error", message=state["error"])
        return state

    # Validate returned structure
    if "scenes" not in script or not isinstance(script["scenes"], list):
        state["status"] = "error"
        state["error"]  = f"Invalid script structure returned by MCP: {str(script)[:200]}"
        add_event(state, agent="scriptwriter", level="error", message=state["error"])
        return state

    state["script"] = script

    # Persist to disk
    SCENE_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCENE_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2)
    add_event(
        state,
        agent="scriptwriter",
        level="success",
        message=f"scene_manifest.json written ({len(script['scenes'])} scene(s))",
        data={"path": str(SCENE_MANIFEST_PATH)},
    )

    return state
