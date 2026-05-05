"""
Lip Sync Agent — mux speech audio + scene video into final raw_scenes/scene_XX.mp4.

Prefers the scene_video_path (real stock footage with motion) when available.
Falls back to building a slideshow from extracted frames if no scene video exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phase2_studio_floor.graph.state import Phase2SceneState, add_event
from shared.config.config import PHASE2_RAW_SCENES_DIR, IMAGE_ASSETS_DIR
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
    add_event(state, agent="lip_sync", message=f"Starting lip sync alignment for scene {scene_id}...")
    wav = state.get("voice_wav_path") or ""
    frames = state.get("face_frames_dir") or state.get("video_frames_dir") or ""
    scene_video = state.get("scene_video_path") or ""

    if state.get("error"):
        add_event(state, agent="lip_sync", level="warning", message="Skipping — upstream error")
        return {}

    if not wav or not Path(wav).is_file():
        err = "lip_sync: missing voice_wav_path"
        add_event(state, agent="lip_sync", level="error", message=err)
        return {"error": err, "status": "error"}

    # At least one of scene_video, frames_dir, or a character image must exist
    ref = _resolve_reference_image(scene, state["character_db"])
    if not scene_video and (not frames or not Path(frames).is_dir()) and not ref:
        err = "lip_sync: no video source and no character image"
        add_event(state, agent="lip_sync", level="error", message=err)
        return {"error": err, "status": "error"}

    if discover_tool("lip_sync_aligner") is None:
        err = "MCP tool 'lip_sync_aligner' not found."
        add_event(state, agent="lip_sync", level="error", message=err)
        return {"error": err, "status": "error"}

    out_mp4 = PHASE2_RAW_SCENES_DIR / f"scene_{scene_id:02d}.mp4"
    result = invoke_tool(
        "lip_sync_aligner",
        {
            "scene_id": scene_id,
            "wav_path": wav,
            "frames_dir": frames,
            "scene_video_path": scene_video,
            "character_image_path": ref or "",
            "output_mp4_path": str(out_mp4),
        },
        timeout=300,
    )
    video_path = result.get("video_path", str(out_mp4))
    mode = result.get("mode", "unknown")

    # Alignment metrics
    try:
        import wave
        with wave.open(wav, "rb") as wf:
            audio_dur = wf.getnframes() / float(wf.getframerate() or 22050)
    except Exception:
        audio_dur = 0.0

    alignment = {
        "audio_duration_sec": round(audio_dur, 3),
        "mode": mode,
    }

    # Add frame-level metrics if in slideshow mode
    if mode == "slideshow" and frames and Path(frames).is_dir():
        nframes = len(list(Path(frames).glob("*.png"))) + len(list(Path(frames).glob("*.jpg")))
        per_frame = result.get("per_frame_sec", 0.34)
        implied_video = nframes * per_frame
        alignment.update({
            "frame_count": nframes,
            "implied_slideshow_duration_sec": round(implied_video, 3),
            "drift_sec": round(abs(audio_dur - implied_video), 3),
        })

    add_event(
        state,
        agent="lip_sync",
        level="success",
        message=f"Wrote {video_path} (mode: {mode})",
        data={"alignment": alignment, "stub": result.get("stub")},
    )
    return {
        "raw_mp4_path": video_path,
        "alignment": alignment,
        "status": "complete",
    }
