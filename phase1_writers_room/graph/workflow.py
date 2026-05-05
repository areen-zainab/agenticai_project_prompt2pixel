"""
graph/workflow.py
────────────────────────────────────────────────────────────────────────────
LangGraph StateGraph — PROJECT MONTAGE Phase 1

Nodes:
  mode_selector  → routes to validator (manual) or scriptwriter (auto)
  validator      → checks and parses manually uploaded scripts
  scriptwriter   → generates a screenplay via MCP
  hitl           → human approval checkpoint
  character      → extracts characters and builds profiles
  image          → generates character reference images via MCP
  memory_commit  → persists final outputs to ChromaDB

All node bodies delegate to the real agent modules. The stub comments
have been removed; only the actual calls remain.
"""

import json

from langgraph.graph import StateGraph, END
from phase1_writers_room.graph.state import AgentState


# ─────────────────────────────────────────────────────────────────────────────
# Node implementations
# ─────────────────────────────────────────────────────────────────────────────

def mode_selector_node(state: AgentState) -> AgentState:
    """
    Entry node — determines whether we are in auto or manual mode.
    input_mode is already set by initial_state(); this node is a pure router.
    """
    print(f"\n[mode_selector] input_mode = {state['input_mode']}")
    return state


def validator_node(state: AgentState) -> AgentState:
    """Manual mode: validate the uploaded script."""
    from phase1_writers_room.agents.validator import run
    return run(state)


def scriptwriter_node(state: AgentState) -> AgentState:
    """Auto mode: generate a script from the user prompt via MCP."""
    from phase1_writers_room.agents.scriptwriter import run
    return run(state)


def hitl_node(state: AgentState) -> AgentState:
    """Human checkpoint: present draft script, await approve/reject."""
    from phase1_writers_room.agents.hitl import run
    return run(state)


def character_node(state: AgentState) -> AgentState:
    """Extract characters and build full identity profiles."""
    from phase1_writers_room.agents.character_designer import run
    return run(state)


def image_node(state: AgentState) -> AgentState:
    """Generate character reference images via MCP."""
    from phase1_writers_room.agents.image_synthesizer import run
    return run(state)


def memory_commit_node(state: AgentState) -> AgentState:
    """
    Final node: commit the completed scene manifest and character profiles
    to ChromaDB vector memory and mark the pipeline as complete.
    """
    from shared.config.config import SCENE_MANIFEST_PATH, CHARACTER_DB_PATH

    from shared.mcp_server.client import discover_tool, invoke_tool
    from phase1_writers_room.graph.state import add_event

    tool_schema = discover_tool("commit_memory")
    if tool_schema is None:
        state["status"] = "error"
        state["error"] = "MCP tool 'commit_memory' not found in registry."
        add_event(state, agent="memory_commit", level="error", message=state["error"])
        return state

    add_event(state, agent="memory_commit", message="Committing final outputs to vector memory (MCP)…")

    # Commit full scene manifest
    if state.get("script"):
        script_text = json.dumps(state["script"])
        invoke_tool(
            "commit_memory",
            {
                "text": script_text,
                "metadata": {"type": "scene_manifest", "scenes": len(state["script"]["scenes"])},
                "doc_id": "scene_manifest_latest",
            },
            timeout=120,
        )
        add_event(
            state,
            agent="memory_commit",
            level="success",
            message=f"scene_manifest committed ({len(state['script']['scenes'])} scene(s))",
        )

    # Commit individual character summaries (already committed in character_designer,
    # but we re-upsert with final image_path included)
    for char in state.get("characters", []):
        summary = (
            f"Character: {char['name']}. "
            f"Traits: {', '.join(char.get('personality_traits', []))}. "
            f"Appearance: {char.get('appearance_description', '')}. "
            f"Image: {char.get('image_path', 'none')}."
        )
        doc_id = f"char_{char['name'].lower().replace(' ', '_')}_final"
        invoke_tool(
            "commit_memory",
            {"text": summary, "metadata": {"type": "character", "name": char["name"]}, "doc_id": doc_id},
            timeout=120,
        )
    if state.get("characters"):
        add_event(
            state,
            agent="memory_commit",
            level="success",
            message=f"{len(state['characters'])} character(s) committed",
        )

    state["status"] = "complete"
    add_event(
        state,
        agent="memory_commit",
        level="success",
        message="Pipeline complete.",
        data={
            "scene_manifest": str(SCENE_MANIFEST_PATH),
            "character_db": str(CHARACTER_DB_PATH),
            "images": len(state.get("images", [])),
        },
    )
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Conditional routing
# ─────────────────────────────────────────────────────────────────────────────

def route_by_mode(state: AgentState) -> str:
    """
    After mode_selector: branch to the correct next node.

    Important: Streamlit HITL approval re-invokes the graph with an existing
    script in state. In that case we must NOT regenerate/re-validate the script;
    we should continue from HITL instead.
    """
    if state.get("script") and state.get("status") in ("awaiting_hitl", "approved", "rejected"):
        return "hitl"
    return "validator" if state["input_mode"] == "manual" else "scriptwriter"


def route_by_hitl(state: AgentState) -> str:
    """After hitl_node: continue if approved, stop if rejected or errored."""
    if state.get("status") == "error":
        print("[router] Pipeline errored before HITL — stopping.")
        return "end"
    if state.get("hitl_approved"):
        return "character"
    print("[router] Script rejected by user — stopping pipeline.")
    return "end"


def route_after_validator(state: AgentState) -> str:
    """After validator: go to hitl if ok, end if validation failed."""
    if state.get("status") == "error":
        print(f"[router] Validation failed — stopping. Error: {state.get('error')}")
        return "end"
    return "hitl"


def route_after_scriptwriter(state: AgentState) -> str:
    """After scriptwriter: go to hitl if script was generated, end on error."""
    if state.get("status") == "error" or not state.get("script"):
        print(f"[router] Scriptwriter failed — stopping. Error: {state.get('error')}")
        return "end"
    return "hitl"


# ─────────────────────────────────────────────────────────────────────────────
# Build graph
# ─────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # ── Register nodes ───────────────────────────────────────────────────────
    graph.add_node("mode_selector", mode_selector_node)
    graph.add_node("validator",     validator_node)
    graph.add_node("scriptwriter",  scriptwriter_node)
    graph.add_node("hitl",          hitl_node)
    graph.add_node("character",     character_node)
    graph.add_node("image",         image_node)
    graph.add_node("memory_commit", memory_commit_node)

    # ── Entry point ──────────────────────────────────────────────────────────
    graph.set_entry_point("mode_selector")

    # ── mode_selector → validator OR scriptwriter ────────────────────────────
    graph.add_conditional_edges(
        "mode_selector",
        route_by_mode,
        {"validator": "validator", "scriptwriter": "scriptwriter", "hitl": "hitl"},
    )

    # ── validator → hitl (if valid) OR END (if error) ────────────────────────
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {"hitl": "hitl", "end": END},
    )

    # ── scriptwriter → hitl (if ok) OR END (if error) ──────────────────────────
    graph.add_conditional_edges(
        "scriptwriter",
        route_after_scriptwriter,
        {"hitl": "hitl", "end": END},
    )

    # ── hitl → character (approved) OR END (rejected/error) ─────────────────
    graph.add_conditional_edges(
        "hitl",
        route_by_hitl,
        {"character": "character", "end": END},
    )

    # ── Linear tail ───────────────────────────────────────────────────────────
    graph.add_edge("character",     "image")
    graph.add_edge("image",         "memory_commit")
    graph.add_edge("memory_commit", END)

    return graph.compile()