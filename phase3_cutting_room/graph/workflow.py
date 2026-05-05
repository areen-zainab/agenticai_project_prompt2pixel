"""
phase3_cutting_room/graph/workflow.py
──────────────────────────────────────
LangGraph workflow for Phase 3 (Cutting Room).

Pipeline graph:

  START
    │
    ▼
  scene_collector   → discovers per-scene MP4s from Phase 2
    │
    ▼  (error → END)
  normalizer        → re-encodes clips to uniform spec
    │
    ▼  (error → END)
  transition_engine → applies xfade / cut transitions
    │
    ▼  (error → END)
  subtitle_burner   → generates SRT and optionally burns it in
    │
    ▼
  exporter          → writes final_output.mp4 + phase3_manifest.json
    │
    ▼
  END
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from phase3_cutting_room.graph.state import Phase3State


# ── Node wrappers ────────────────────────────────────────────────────────────

def scene_collector_node(state: Phase3State) -> dict[str, Any]:
    from phase3_cutting_room.agents.scene_collector import run
    return run(state)


def normalizer_node(state: Phase3State) -> dict[str, Any]:
    from phase3_cutting_room.agents.normalizer import run
    return run(state)


def transition_engine_node(state: Phase3State) -> dict[str, Any]:
    from phase3_cutting_room.agents.transition_engine import run
    return run(state)


def subtitle_burner_node(state: Phase3State) -> dict[str, Any]:
    from phase3_cutting_room.agents.subtitle_burner import run
    return run(state)


def exporter_node(state: Phase3State) -> dict[str, Any]:
    from phase3_cutting_room.agents.exporter import run
    return run(state)


# ── Routing helpers ──────────────────────────────────────────────────────────

def _route_or_end(next_node: str):
    """Return a router function that proceeds to next_node or aborts to END on error."""
    def _router(state: Phase3State) -> str:
        if state.get("error"):
            return END
        return next_node
    return _router


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_phase3_graph():
    """Build and compile the Phase 3 LangGraph workflow."""
    graph = StateGraph(Phase3State)

    # Register nodes
    graph.add_node("scene_collector",   scene_collector_node)
    graph.add_node("normalizer",        normalizer_node)
    graph.add_node("transition_engine", transition_engine_node)
    graph.add_node("subtitle_burner",   subtitle_burner_node)
    graph.add_node("exporter",          exporter_node)

    # Edges
    graph.add_edge(START, "scene_collector")

    graph.add_conditional_edges(
        "scene_collector",
        _route_or_end("normalizer"),
        {"normalizer": "normalizer", END: END},
    )
    graph.add_conditional_edges(
        "normalizer",
        _route_or_end("transition_engine"),
        {"transition_engine": "transition_engine", END: END},
    )
    graph.add_conditional_edges(
        "transition_engine",
        _route_or_end("subtitle_burner"),
        {"subtitle_burner": "subtitle_burner", END: END},
    )
    graph.add_edge("subtitle_burner", "exporter")
    graph.add_edge("exporter", END)

    return graph.compile()
