"""
Face Swap Agent — identity validation + face_swapper MCP.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phase2_studio_floor.graph.state import Phase2SceneState, add_event
from shared.config.config import IMAGE_ASSETS_DIR
from shared.mcp_server.client import discover_tool, invoke_tool


def _resolve_reference_image(scene: dict[str, Any], character_db: dict[str, Any]) -> str | None:
    names = [str(n).strip().upper() for n in (scene.get("characters") or [])]
    for ch in character_db.get("characters", []) or []:
        if str(ch.get("name", "")).strip().upper() in names:
            p = ch.get("image_path")
            if p and Path(p).exists():
                return str(p)
            safe = "".join(c if c.isalnum() else "_" for c in str(ch.get("name", "char")))
            guess = IMAGE_ASSETS_DIR / f"{safe}.png"
            if guess.exists():
                return str(guess)
    return None


def run(state: Phase2SceneState) -> dict[str, Any]:
    scene = state["scene"]
    scene_id = int(scene.get("scene_id", 1))
    add_event(state, agent="face_swap", message=f"Starting face mapping for scene {scene_id}...")
    frames_dir = state.get("video_frames_dir") or ""
    if state.get("voice_error") or state.get("video_error"):
        parts = [p for p in (state.get("voice_error"), state.get("video_error")) if p]
        err = "; ".join(parts)
        add_event(state, agent="face_swap", level="error", message=f"Upstream: {err}")
        return {"error": err, "status": "error"}

    if not frames_dir or not Path(frames_dir).is_dir():
        err = "face_swap: missing video_frames_dir"
        add_event(state, agent="face_swap", level="error", message=err)
        return {"error": err, "status": "error"}

    ref = _resolve_reference_image(scene, state["character_db"])
    frames = sorted(Path(frames_dir).glob("*.png")) + sorted(Path(frames_dir).glob("*.jpg"))
    first = str(frames[0]) if frames else ""

    if discover_tool("identity_validator") is not None and ref and first:
        iv = invoke_tool(
            "identity_validator",
            {
                "character_name": (scene.get("characters") or ["unknown"])[0],
                "reference_image_path": ref,
                "frame_path": first,
            },
            timeout=60,
        )
        if not iv.get("valid", True):
            err = "identity_validator rejected face mapping"
            add_event(state, agent="face_swap", level="error", message=err, data=iv)
            return {"error": err, "status": "error"}

    if discover_tool("face_swapper") is None:
        err = "MCP tool 'face_swapper' not found."
        add_event(state, agent="face_swap", level="error", message=err)
        return {"error": err, "status": "error"}

    out = invoke_tool(
        "face_swapper",
        {
            "scene_id": scene_id,
            "frames_dir": frames_dir,
            "reference_image_path": ref or "",
        },
        timeout=300,
    )
    face_dir = out.get("frames_dir", frames_dir)
    add_event(
        state,
        agent="face_swap",
        level="success",
        message="Face-mapped frames ready",
        data={"face_frames_dir": face_dir, "stub": out.get("stub")},
    )
    return {"face_frames_dir": face_dir}
