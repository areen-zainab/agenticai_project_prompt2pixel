"""Heuristic intent classifier for Phase 5 edits."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field


class EditIntent(BaseModel):
    intent: str
    target: Literal["audio", "video_frame", "video", "script"]
    scope: str = "all"
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5


def _scope_from_query(query: str) -> str:
    lowered = query.lower()
    scene_match = re.search(r"scene\s*(\d+)", lowered)
    if scene_match:
        return f"scene:{scene_match.group(1)}"
    if "narrator" in lowered:
        return "character:Narrator"
    if "character" in lowered:
        return "character:all"
    return "all"


def _has_any(query: str, keywords: list[str]) -> bool:
    return any(keyword in query for keyword in keywords)


def classify_intent(edit_query: str) -> EditIntent:
    """Classify a free-text edit request into a structured edit intent."""
    query = edit_query.strip().lower()
    scope = _scope_from_query(edit_query)

    if _has_any(query, ["rewrite", "regenerate the script", "regenerate script", "rewrite scene", "dialogue", "story", "add scene", "remove scene"]):
        return EditIntent(
            intent="rewrite_script",
            target="script",
            scope=scope,
            parameters={"query": edit_query},
            confidence=0.96,
        )

    if _has_any(query, ["subtitle", "subtitles", "transition", "fade", "wipe", "dissolve", "composite", "final video", "render", "recompose", "speed up this scene", "slow down this scene"]):
        return EditIntent(
            intent="update_video_composition",
            target="video",
            scope=scope,
            parameters={"query": edit_query},
            confidence=0.94,
        )

    if _has_any(query, ["voice", "background music", "music", "silence", "audio speed", "sound", "narrator sound", "tone", "sad", "happy"]):
        return EditIntent(
            intent="update_audio",
            target="audio",
            scope=scope,
            parameters={"query": edit_query},
            confidence=0.93,
        )

    if _has_any(query, ["darken", "darker", "lighten", "color", "colour", "character design", "design", "scene style", "visual look", "visual", "appearance", "frame"]):
        return EditIntent(
            intent="update_visual_frame",
            target="video_frame",
            scope=scope,
            parameters={"query": edit_query},
            confidence=0.91,
        )

    return EditIntent(
        intent="general_video_update",
        target="video",
        scope=scope,
        parameters={"query": edit_query},
        confidence=0.55,
    )
