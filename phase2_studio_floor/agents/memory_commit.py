"""Optional Phase 2 checkpoint — commit scene summary to vector memory."""

from __future__ import annotations

import json
from typing import Any

from phase2_studio_floor.graph.state import Phase2SceneState, add_event
from shared.mcp_server.client import discover_tool, invoke_tool


def run(state: Phase2SceneState) -> dict[str, Any]:
    scene = state["scene"]
    scene_id = int(scene.get("scene_id", 1))
    add_event(state, agent="memory_commit", message=f"Committing scene {scene_id} metadata to memory...")

    if discover_tool("commit_memory") is None:
        add_event(state, agent="memory_commit", level="warning", message="commit_memory unavailable")
        return {}

    summary = {
        "phase": 2,
        "scene_id": scene_id,
        "voice_wav_path": state.get("voice_wav_path"),
        "video_frames_dir": state.get("video_frames_dir"),
        "face_frames_dir": state.get("face_frames_dir"),
        "raw_mp4_path": state.get("raw_mp4_path"),
        "alignment": state.get("alignment"),
    }
    invoke_tool(
        "commit_memory",
        {
            "text": json.dumps(summary),
            "metadata": {"type": "phase2_scene_complete", "scene_id": str(scene_id)},
            "doc_id": f"phase2_scene_{scene_id:02d}_complete",
        },
        timeout=120,
    )
    add_event(state, agent="memory_commit", level="success", message="Phase 2 scene committed to memory")
    return {}
