"""
Scene Parser Agent — task graph via MCP get_task_graph + task graph log + commit_memory.
"""

from __future__ import annotations

import json
from typing import Any

from phase2_studio_floor.graph.state import Phase2SceneState, add_event
from shared.config.config import PHASE2_TASK_GRAPH_LOGS_DIR
from shared.mcp_server.client import discover_tool, invoke_tool


def run(state: Phase2SceneState) -> dict[str, Any]:
    scene = state["scene"]
    scene_id = int(scene.get("scene_id", 1))
    add_event(state, agent="scene_parser", message=f"Parsing task graph for scene {scene_id}...")

    if discover_tool("get_task_graph") is None:
        err = "MCP tool 'get_task_graph' not found."
        add_event(state, agent="scene_parser", level="error", message=err)
        return {"error": err, "status": "error"}

    task_graph = invoke_tool(
        "get_task_graph",
        {
            "scene_id": scene_id,
            "scene_summary": scene.get("location", ""),
        },
        timeout=60,
    )

    log_path = PHASE2_TASK_GRAPH_LOGS_DIR / f"scene_{scene_id:02d}.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scene_id": scene_id,
        "task_graph": task_graph,
        "location": scene.get("location"),
    }
    log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if discover_tool("commit_memory") is not None:
        invoke_tool(
            "commit_memory",
            {
                "text": json.dumps(payload),
                "metadata": {"type": "phase2_task_graph", "scene_id": str(scene_id)},
                "doc_id": f"phase2_task_graph_scene_{scene_id:02d}",
            },
            timeout=120,
        )

    add_event(
        state,
        agent="scene_parser",
        level="success",
        message=f"Task graph written to {log_path}",
        data={"task_graph_log": str(log_path)},
    )
    return {"task_graph": task_graph, "status": "running"}
