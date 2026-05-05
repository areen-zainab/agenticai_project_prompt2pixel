"""
Voice Synthesis Agent — dialogue → WAV via MCP voice_cloning_synthesizer.

Passes per-line dialogue entries so the MCP handler can assign a unique
neural voice to each character via edge-tts.
"""

from __future__ import annotations

from typing import Any

from phase2_studio_floor.graph.state import Phase2SceneState, add_event
from shared.mcp_server.client import discover_tool, invoke_tool


def _dialogue_text(scene: dict[str, Any]) -> str:
    """Concatenated dialogue for backward-compatible 'text' field."""
    lines = []
    for d in scene.get("dialogue", []) or []:
        sp = d.get("speaker", "")
        line = d.get("line", "")
        lines.append(f"{sp}: {line}")
    return "\n".join(lines).strip()


def _dialogue_entries(scene: dict[str, Any], character_db: dict[str, Any]) -> list[dict[str, str]]:
    """Extract dialogue with character appearance traits for voice mapping."""
    entries = []
    char_list = character_db.get("characters", []) or []
    
    # Pre-map character descriptions for faster lookup
    descriptions = {str(c.get("name", "")).upper(): str(c.get("appearance_description", "")) for c in char_list}

    for d in scene.get("dialogue", []) or []:
        speaker = d.get("speaker", "NARRATOR").upper()
        entries.append({
            "speaker": speaker,
            "line": d.get("line", ""),
            "emotion": d.get("emotion", ""),
            "traits": descriptions.get(speaker, ""),
        })
    return entries


def run(state: Phase2SceneState) -> dict[str, Any]:
    scene = state["scene"]
    character_db = state.get("character_db", {})
    scene_id = int(scene.get("scene_id", 1))
    add_event(state, agent="voice_synth", message=f"Synthesizing voice track for scene {scene_id}...")
    text = _dialogue_text(scene)
    if not text:
        err = "No dialogue in scene for voice synthesis."
        add_event(state, agent="voice_synth", level="error", message=err)
        return {"voice_error": err}

    if discover_tool("voice_cloning_synthesizer") is None:
        err = "MCP tool 'voice_cloning_synthesizer' not found."
        add_event(state, agent="voice_synth", level="error", message=err)
        return {"voice_error": err}

    primary = (scene.get("characters") or [""])[0]
    out = invoke_tool(
        "voice_cloning_synthesizer",
        {
            "text": text,
            "scene_id": scene_id,
            "character_name": primary,
            "dialogue_entries": _dialogue_entries(scene, character_db),
        },
        timeout=300,  # real TTS can take longer than tone stub
    )
    wav = out.get("wav_path", "")
    stub = out.get("stub", False)
    add_event(
        state,
        agent="voice_synth",
        level="success",
        message="Voice track generated" + (" (real TTS)" if not stub else " (fallback tone)"),
        data={"wav_path": wav, "stub": stub, "duration_sec": out.get("duration_sec")},
    )
    return {
        "voice_wav_path": wav,
        "line_durations": out.get("line_durations", []),
    }
