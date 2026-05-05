"""
Phase 2 per-scene state (LangGraph). Kept separate from Phase 1 AgentState.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Literal, NotRequired, TypedDict

_events_lock = threading.Lock()


class Phase2Event(TypedDict):
    ts: str
    level: Literal["info", "success", "warning", "error"]
    agent: str
    message: str
    data: dict[str, Any]


class Phase2SceneState(TypedDict, total=False):
    """State for processing a single scene through the Studio Floor graph."""

    scene: dict[str, Any]
    character_db: dict[str, Any]
    task_graph: dict[str, Any] | None
    voice_wav_path: str | None
    video_frames_dir: str | None
    scene_video_path: str | None  # concatenated stock footage video (real motion)
    face_frames_dir: str | None
    raw_mp4_path: str | None
    # Parallel branch failures (avoid concurrent writes to a single `error` key)
    voice_error: str | None
    video_error: str | None
    status: Literal["pending", "running", "complete", "error"]
    error: str | None
    events: list[Phase2Event]
    # Precision timing alignment
    line_durations: list[float] | None
    # Optional metrics for logs / rubric
    alignment: NotRequired[dict[str, Any]]


def add_event(
    state: Phase2SceneState,
    *,
    agent: str,
    message: str,
    level: Literal["info", "success", "warning", "error"] = "info",
    data: dict[str, Any] | None = None,
) -> None:
    # ── Console logging ──
    color = {
        "info": "\033[94m",    # blue
        "success": "\033[92m", # green
        "warning": "\033[93m", # yellow
        "error": "\033[91m",   # red
    }.get(level, "")
    reset = "\033[0m"
    agent_tag = f"[{agent.replace('_', ' ').title()}]"
    print(f"{color}{agent_tag:20} {message}{reset}")

    with _events_lock:
        if "events" not in state or state["events"] is None:
            state["events"] = []
        state["events"].append(
            Phase2Event(
                ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                level=level,
                agent=agent,
                message=message,
                data=data or {},
            )
        )


def initial_scene_state(scene: dict[str, Any], character_db: dict[str, Any]) -> Phase2SceneState:
    return Phase2SceneState(
        scene=scene,
        character_db=character_db,
        task_graph=None,
        voice_wav_path=None,
        video_frames_dir=None,
        scene_video_path=None,
        face_frames_dir=None,
        raw_mp4_path=None,
        voice_error=None,
        video_error=None,
        status="pending",
        error=None,
        line_durations=None,
        events=[],
    )
