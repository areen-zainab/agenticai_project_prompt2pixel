"""Dispatch edit intents to the appropriate phase rerun."""

from __future__ import annotations

import glob
import json
import os
import shutil
from pathlib import Path
from typing import Any

from backend.orchestrator import get_orchestrator
from phase5_edit_agent.agents.intent_classifier import EditIntent
from phase5_edit_agent.state_manager import StateManager
from shared.config.config import BASE_DIR

state_manager = StateManager()
EDITS_DIR = BASE_DIR / "outputs_phase5" / "edits"
EDITS_DIR.mkdir(parents=True, exist_ok=True)


def _parse_scope_scene(scope: str) -> int | None:
    if scope.startswith("scene:"):
        try:
            return int(scope.split(":", 1)[1])
        except Exception:
            return None
    return None


def _normalize_transition_style(raw: str | None) -> str:
    if not raw:
        return "fade"
    style = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "wipeleft": "wipe_left",
        "wiperight": "wipe_right",
        "fadeblack": "fade_black",
    }
    style = aliases.get(style, style)
    allowed = {"fade", "cut", "wipe_left", "wipe_right", "dissolve", "fade_black"}
    return style if style in allowed else "fade"


def _parse_scope_character(scope: str) -> str | None:
    if scope.startswith("character:"):
        value = scope.split(":", 1)[1].strip()
        return value or None
    return None


def _collect_current_assets() -> list[str]:
    patterns = [
        "outputs_phase2/raw_scenes/**/*.mp4",
        "outputs_phase2/stock/**/*.mp4",
        "outputs_phase3/*.mp4",
        "outputs_phase3/*.srt",
        "outputs/image_assets/*.png",
        "outputs/*.json",
    ]
    assets: list[str] = []
    for pattern in patterns:
        for item in glob.glob(str(BASE_DIR / pattern), recursive=True):
            if os.path.isfile(item):
                assets.append(os.path.abspath(item))
    return sorted(set(assets))


def _load_scene_manifest() -> dict[str, Any]:
    manifest_path = BASE_DIR / "outputs" / "scene_manifest.json"
    if not manifest_path.is_file():
        return {}
    with open(manifest_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _phase2_scene_path(scene_id: int) -> Path | None:
    candidates = [
        BASE_DIR / "outputs_phase2" / "raw_scenes" / f"scene_{scene_id:02d}.mp4",
        BASE_DIR / "outputs_phase2" / "raw_scenes" / f"scene_{scene_id}.mp4",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _save_edit_clip(scene_id: int | None, source_path: Path | None, edit_version: int) -> str | None:
    if scene_id is None or source_path is None or not source_path.is_file():
        return None
    target = EDITS_DIR / f"v{edit_version}_scene_{scene_id:02d}.mp4"
    shutil.copy2(source_path, target)
    return target.name


def _save_before_clip(scene_id: int | None, source_path: Path | None, before_version: int) -> str | None:
    if scene_id is None or source_path is None or not source_path.is_file():
        return None
    target = EDITS_DIR / f"v{before_version}_scene_{scene_id:02d}_before.mp4"
    shutil.copy2(source_path, target)
    return target.name


def _rerun_phase1(intent: EditIntent, current_state: dict[str, Any], scene_id: int | None) -> dict[str, Any]:
    orchestrator = get_orchestrator()
    base_prompt = current_state.get("query") or intent.parameters.get("query") or "Revise the existing story"
    if scene_id is not None:
        base_prompt = f"Scene {scene_id}: {base_prompt}"
    output = orchestrator.run_phase1(
        prompt=f"{base_prompt}. Edit request: {intent.intent}. Details: {intent.parameters}"
    )
    updated: dict[str, Any] = {"phase1_output": output.model_dump()}
    if scene_id is not None:
        phase2_output = orchestrator.run_phase2(scene_id=scene_id)
        updated["phase2_output"] = phase2_output.model_dump()
    return updated


def _rerun_phase2(intent: EditIntent, current_state: dict[str, Any], scene_id: int | None) -> dict[str, Any]:
    orchestrator = get_orchestrator()
    selected_scene_id = scene_id if scene_id is not None else _parse_scope_scene(intent.scope)
    if selected_scene_id is None:
        # granular default: keep edits scoped where possible
        selected_scene_id = current_state.get("selected_scene_id")
    output = orchestrator.run_phase2(scene_id=selected_scene_id)
    return {
        "phase2_output": output.model_dump(),
        "edited_scope": {
            "scene_id": selected_scene_id,
            "character": _parse_scope_character(intent.scope),
            "target": intent.target,
        },
    }


def _rerun_phase3(intent: EditIntent, current_state: dict[str, Any]) -> dict[str, Any]:
    from phase3_cutting_room.graph.state import initial_phase3_state
    from phase3_cutting_room.graph.workflow import build_phase3_graph

    scene_manifest = _load_scene_manifest()
    transition_style = _normalize_transition_style(intent.parameters.get("transition_style"))
    add_subtitles = bool(intent.parameters.get("add_subtitles", True))
    state = initial_phase3_state(
        scene_manifest=scene_manifest,
        transition_style=transition_style,
        add_subtitles=add_subtitles,
    )
    graph = build_phase3_graph()
    result = graph.invoke(state)
    return {
        "phase3_output": result,
        "composition_changes": {
            "transition_style": transition_style,
            "add_subtitles": add_subtitles,
            "speed": intent.parameters.get("speed"),
        },
    }


def execute_edit(intent: EditIntent, current_state: dict[str, Any], state_mgr: StateManager | None = None) -> dict[str, Any]:
    """Execute an edit and store before/after snapshots."""
    manager = state_mgr or state_manager
    scene_id = current_state.get("scene_id") or current_state.get("selected_scene_id")
    before_assets = _collect_current_assets()
    original_scene_path = _phase2_scene_path(scene_id) if scene_id is not None else None
    before_version = manager.snapshot(
        state_json={"query": current_state.get("query"), "current_state": current_state, "intent": intent.model_dump()},
        description=f"Before edit: {intent.intent}",
        asset_paths=before_assets,
    )
    before_clip_name = _save_before_clip(scene_id, original_scene_path, before_version)

    if intent.target == "script":
        updated = _rerun_phase1(intent, current_state, scene_id)
    elif intent.target in {"audio", "video_frame"}:
        updated = _rerun_phase2(intent, current_state, scene_id)
    elif intent.target == "video":
        updated = _rerun_phase3(intent, current_state)
    else:
        raise ValueError(f"Unknown target: {intent.target}")

    selected_scene_id = scene_id if scene_id is not None else _parse_scope_scene(intent.scope)
    preview_video_url = "/api/phase3/video" if intent.target == "video" else None
    if intent.target != "video" and selected_scene_id is not None:
        preview_video_url = f"/api/phase2/video/{selected_scene_id}"

    after_state = {
        **current_state,
        **updated,
        "classified_intent": intent.model_dump(),
        "selected_scene_id": selected_scene_id,
        "preview_video_url": preview_video_url,
    }
    after_assets = _collect_current_assets()
    after_version = manager.snapshot(
        state_json=after_state,
        description=f"After edit: {intent.intent}",
        asset_paths=after_assets,
    )
    edited_scene_path = _phase2_scene_path(selected_scene_id) if selected_scene_id is not None else None
    edited_clip_name = _save_edit_clip(selected_scene_id, edited_scene_path, after_version)

    return {
        "classified_intent": intent.model_dump(),
        "updated_state": after_state,
        "selected_scene_id": selected_scene_id,
        "preview_video_url": preview_video_url,
        "original_video_url": (
            f"/api/edit/clip/{before_clip_name}" if before_clip_name else None
        ),
        "edited_clip_url": (
            f"/api/edit/clip/{edited_clip_name}" if edited_clip_name else None
        ),
        "edit_saved": bool(edited_clip_name),
        "before_version": before_version,
        "after_version": after_version,
        "history": manager.history(),
    }
