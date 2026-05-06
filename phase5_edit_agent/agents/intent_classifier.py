"""Structured intent classifier for Phase 5 edits."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field
from shared.llm_client import chat_json


class EditIntent(BaseModel):
    intent: str
    target: Literal["audio", "video_frame", "video", "script"]
    scope: str = "all"
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5


class _EditIntentEnvelope(BaseModel):
    intent: str
    target: Literal["audio", "video_frame", "video", "script"]
    scope: str = "all"
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5


SYSTEM_PROMPT = """
You are an edit intent classifier for an AI video pipeline.
Return a strict JSON object with fields:
- intent: snake_case action id
- target: one of "audio", "video_frame", "video", "script"
- scope: one of "all", "scene:<id>", "character:<name>"
- parameters: object with extracted parameters
- confidence: number from 0.0 to 1.0

Parameter extraction rules:
- "tone/voice emotion" -> {"tone": "<value>"}
- "background music" -> {"music_action": "add|remove|change"}
- "darker/brighter/color/style" -> {"look": "<value>"}
- "subtitle" -> {"add_subtitles": true|false}
- "speed up/slow down" -> {"speed": <float>}
- "transition style" -> {"transition_style": "fade|cut|wipe_left|wipe_right|dissolve|fade_black"}
- rewrite/regenerate script -> {"rewrite_scope": "<value>"}
Output valid JSON only.
"""


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


def _heuristic_fallback(edit_query: str) -> EditIntent:
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
        params: dict[str, Any] = {"query": edit_query}
        intent_name = "update_video_composition"
        if "remove" in query and ("subtitle" in query or "subtitles" in query):
            params["add_subtitles"] = False
            intent_name = "remove_subtitle"
        if "add" in query and ("subtitle" in query or "subtitles" in query):
            params["add_subtitles"] = True
        if "speed up" in query:
            params["speed"] = 1.25
            intent_name = "speed_up_scene"
        if "slow down" in query:
            params["speed"] = 0.8
            intent_name = "slow_down_scene"
        if "wipe left" in query:
            params["transition_style"] = "wipe_left"
        elif "wipe right" in query:
            params["transition_style"] = "wipe_right"
        elif "fade black" in query:
            params["transition_style"] = "fade_black"
        elif "dissolve" in query:
            params["transition_style"] = "dissolve"
        elif "cut" in query:
            params["transition_style"] = "cut"
        elif "fade" in query:
            params["transition_style"] = "fade"
        return EditIntent(
            intent=intent_name,
            target="video",
            scope=scope,
            parameters=params,
            confidence=0.94,
        )

    if _has_any(query, ["voice", "background music", "music", "silence", "audio speed", "sound", "narrator sound", "tone", "sad", "happy"]):
        params = {"query": edit_query}
        intent_name = "update_audio"
        if "sad" in query:
            params["tone"] = "sad"
            intent_name = "change_voice_tone"
        elif "happy" in query:
            params["tone"] = "happy"
            intent_name = "change_voice_tone"
        elif "whisper" in query:
            params["tone"] = "whispered"
            intent_name = "change_voice_tone"
        if "background music" in query:
            params["music_action"] = "add" if "add" in query else "change"
            intent_name = "add_background_music"
        return EditIntent(
            intent=intent_name,
            target="audio",
            scope=scope,
            parameters=params,
            confidence=0.93,
        )

    if _has_any(query, ["darken", "darker", "lighten", "color", "colour", "character design", "design", "scene style", "visual look", "visual", "appearance", "frame"]):
        params = {"query": edit_query}
        intent_name = "update_visual_frame"
        if "darker" in query:
            params["look"] = "darker"
            intent_name = "make_scene_darker"
        elif "brighter" in query:
            params["look"] = "brighter"
            intent_name = "make_scene_brighter"
        if "character design" in query:
            params["design_update"] = True
            intent_name = "change_character_design"
        return EditIntent(
            intent=intent_name,
            target="video_frame",
            scope=scope,
            parameters=params,
            confidence=0.91,
        )

    return EditIntent(
        intent="general_video_update",
        target="video",
        scope=scope,
        parameters={"query": edit_query},
        confidence=0.55,
    )


def _classify_with_llm(edit_query: str) -> EditIntent | None:
    try:
        payload = chat_json(system=SYSTEM_PROMPT, user=edit_query, temperature=0.1)
        validated = _EditIntentEnvelope.model_validate(payload)
        return EditIntent.model_validate(validated.model_dump())
    except Exception:
        return None


def classify_intent(edit_query: str) -> EditIntent:
    """Classify a free-text edit request into a structured edit intent."""
    llm_result = _classify_with_llm(edit_query)
    if llm_result is not None:
        return llm_result
    return _heuristic_fallback(edit_query)
