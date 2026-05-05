"""
phase3_cutting_room/graph/state.py
───────────────────────────────────
LangGraph TypedDict state for the Phase 3 (Cutting Room) pipeline.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

_events_lock = threading.Lock()


class Phase3Event(TypedDict):
    ts:      str
    level:   Literal["info", "success", "warning", "error"]
    agent:   str
    message: str


class Phase3State(TypedDict, total=False):
    """State flowing through the Phase 3 LangGraph workflow."""

    # ── Inputs ───────────────────────────────────────────────────────────
    scene_manifest:    dict[str, Any]   # loaded from outputs/scene_manifest.json
    transition_style:  str              # "fade" | "cut" | "wipe_left" | "wipe_right" | "dissolve" | "fade_black"
    add_subtitles:     bool             # whether to burn SRT subtitles

    # ── Scene collection ─────────────────────────────────────────────────
    scene_video_paths: list[str]        # ordered paths from Phase 2 outputs
    scene_count:       int

    # ── Normalizer ───────────────────────────────────────────────────────
    normalized_paths:  list[str]        # re-encoded clips ready for concat
    ffmpeg_exe:        str              # resolved ffmpeg path

    # ── Transition engine ────────────────────────────────────────────────
    stitched_path:     str              # post-transition video

    # ── Subtitle burner ──────────────────────────────────────────────────
    subtitled_path:    str              # post-subtitle video
    srt_path:          str              # path to generated SRT file

    # ── Exporter ─────────────────────────────────────────────────────────
    final_output_path: str              # outputs_phase3/final_output.mp4
    duration_seconds:  float
    phase3_manifest:   dict[str, Any]

    # ── Pipeline meta ─────────────────────────────────────────────────────
    status: Literal["pending", "running", "complete", "error"]
    error:  str | None
    events: list[Phase3Event]


def log_event(
    state: Phase3State,
    agent: str,
    message: str,
    level: Literal["info", "success", "warning", "error"] = "info",
) -> None:
    """Append a log entry and print to console with colour."""
    color = {
        "info":    "\033[94m",
        "success": "\033[92m",
        "warning": "\033[93m",
        "error":   "\033[91m",
    }.get(level, "")
    reset = "\033[0m"
    tag = f"[{agent.replace('_', ' ').title()}]"
    print(f"{color}{tag:22} {message}{reset}")

    with _events_lock:
        if "events" not in state or state["events"] is None:
            state["events"] = []
        state["events"].append(
            Phase3Event(
                ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                level=level,
                agent=agent,
                message=message,
            )
        )


def initial_phase3_state(
    scene_manifest: dict[str, Any],
    transition_style: str = "fade",
    add_subtitles: bool = True,
) -> Phase3State:
    return Phase3State(
        scene_manifest=scene_manifest,
        transition_style=transition_style,
        add_subtitles=add_subtitles,
        scene_video_paths=[],
        scene_count=0,
        normalized_paths=[],
        ffmpeg_exe="ffmpeg",
        stitched_path="",
        subtitled_path="",
        srt_path="",
        final_output_path="",
        duration_seconds=0.0,
        phase3_manifest={},
        status="pending",
        error=None,
        events=[],
    )
