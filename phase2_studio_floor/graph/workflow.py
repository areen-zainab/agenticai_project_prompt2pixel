"""
LangGraph workflow — Phase 2 single-scene pipeline.

Uses Send() to branch voice_synth and video_gen in parallel; both join at face_swap.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from phase2_studio_floor.graph.state import Phase2SceneState


def scene_parser_node(state: Phase2SceneState) -> dict[str, Any]:
    from phase2_studio_floor.agents.scene_parser import run

    return run(state)


def voice_synth_node(state: Phase2SceneState) -> dict[str, Any]:
    from phase2_studio_floor.agents.voice_synth import run

    return run(state)


def video_gen_node(state: Phase2SceneState) -> dict[str, Any]:
    from phase2_studio_floor.agents.video_gen import run

    return run(state)


def face_swap_node(state: Phase2SceneState) -> dict[str, Any]:
    from phase2_studio_floor.agents.face_swap import run

    return run(state)


def lip_sync_node(state: Phase2SceneState) -> dict[str, Any]:
    from phase2_studio_floor.agents.lip_sync import run

    return run(state)


def memory_commit_node(state: Phase2SceneState) -> dict[str, Any]:
    from phase2_studio_floor.agents.memory_commit import run

    return run(state)


def route_after_parser(state: Phase2SceneState) -> Any:
    if state.get("error"):
        return END
    return "voice_synth"


def build_scene_graph():
    graph = StateGraph(Phase2SceneState)
    graph.add_node("scene_parser", scene_parser_node)
    graph.add_node("voice_synth", voice_synth_node)
    graph.add_node("video_gen", video_gen_node)
    graph.add_node("face_swap", face_swap_node)
    graph.add_node("lip_sync", lip_sync_node)
    graph.add_node("memory_commit", memory_commit_node)

    graph.add_edge(START, "scene_parser")
    graph.add_conditional_edges(
        "scene_parser",
        route_after_parser,
        {"voice_synth": "voice_synth", END: END},
    )
    graph.add_edge("voice_synth", "video_gen")
    graph.add_edge("video_gen", "face_swap")
    graph.add_edge("face_swap", "lip_sync")
    graph.add_edge("lip_sync", "memory_commit")
    graph.add_edge("memory_commit", END)
    return graph.compile()
