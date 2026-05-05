"""
phase3_cutting_room/agents/exporter.py
───────────────────────────────────────
Final export step.  Copies/renames the subtitled (or stitched) video to
the canonical output path:  outputs_phase3/final_output.mp4

Also writes a companion JSON manifest:  outputs_phase3/phase3_manifest.json
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phase3_cutting_room.graph.state import Phase3State, log_event
from shared.config.config import BASE_DIR

OUTPUTS_PHASE3_DIR = BASE_DIR / "outputs_phase3"
FINAL_OUTPUT_PATH  = OUTPUTS_PHASE3_DIR / "final_output.mp4"
MANIFEST_PATH      = OUTPUTS_PHASE3_DIR / "phase3_manifest.json"


def _video_duration(path: Path, ff: str) -> float:
    """Probe video duration with ffprobe."""
    import subprocess
    try:
        r = subprocess.run(
            [
                ff.replace("ffmpeg", "ffprobe"),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        return round(float(r.stdout.strip()), 3)
    except Exception:
        return 0.0


def run(state: Phase3State) -> dict[str, Any]:
    """
    Export final_output.mp4 and write phase3_manifest.json.
    """
    # Pick the best available video (subtitled > stitched > normalized[0])
    source_str: str = (
        state.get("subtitled_path")
        or state.get("stitched_path")
        or (state.get("normalized_paths") or [None])[0]
        or ""
    )
    if not source_str:
        err = "exporter: no video to export"
        log_event(state, "exporter", err, "error")
        return {"error": err}

    source = Path(source_str)
    if not source.is_file():
        err = f"exporter: source file not found: {source}"
        log_event(state, "exporter", err, "error")
        return {"error": err}

    OUTPUTS_PHASE3_DIR.mkdir(parents=True, exist_ok=True)

    # Copy to final canonical path
    shutil.copy2(source, FINAL_OUTPUT_PATH)
    log_event(
        state, "exporter",
        f"final_output.mp4 exported ({FINAL_OUTPUT_PATH.stat().st_size // 1024} KB)",
        "success",
    )

    # Write manifest
    ff: str = state.get("ffmpeg_exe", "ffmpeg")
    duration = _video_duration(FINAL_OUTPUT_PATH, ff)

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "final_output_path": str(FINAL_OUTPUT_PATH),
        "duration_seconds": duration,
        "scene_count": state.get("scene_count", 0),
        "transition_style": state.get("transition_style", "fade"),
        "subtitles_burned": bool(state.get("srt_path")),
        "srt_path": state.get("srt_path"),
        "source_scene_paths": state.get("scene_video_paths", []),
        "normalized_paths": state.get("normalized_paths", []),
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    log_event(state, "exporter", f"Phase 3 manifest written: {MANIFEST_PATH.name}", "info")

    return {
        "final_output_path": str(FINAL_OUTPUT_PATH),
        "duration_seconds": duration,
        "phase3_manifest": manifest,
        "status": "complete",
    }
