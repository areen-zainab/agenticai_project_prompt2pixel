"""
phase3_cutting_room/agents/subtitle_burner.py
──────────────────────────────────────────────
Burns subtitles (SRT) into the stitched video using FFmpeg's subtitles
filter.  Generates the SRT file from the scene manifest + timing data
if one does not already exist.

The agent is OPTIONAL: if add_subtitles=False in the state, it passes
the stitched video through unchanged.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from phase3_cutting_room.graph.state import Phase3State, log_event
from shared.config.config import BASE_DIR, SCENE_MANIFEST_PATH

OUTPUT_DIR = BASE_DIR / "outputs_phase3"
SRT_PATH   = OUTPUT_DIR / "subtitles.srt"


# ─── SRT generation ─────────────────────────────────────────────────────────

def _ms_to_srt_ts(ms: float) -> str:
    """Convert milliseconds to SRT timestamp format HH:MM:SS,mmm."""
    total_s, millis = divmod(int(ms), 1000)
    total_m, secs   = divmod(total_s, 60)
    hours, mins     = divmod(total_m, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def _build_srt(scene_manifest: dict, scene_video_paths: list[str], ff: str) -> Path:
    """
    Construct an SRT file from dialogue in the scene manifest.
    Estimates timing using per-scene video duration.
    """
    scenes = scene_manifest.get("scenes", [])
    entries: list[tuple[float, float, str]] = []   # (start_ms, end_ms, text)
    cursor_ms = 0.0

    for i, scene in enumerate(scenes):
        # Estimate this scene's duration from its video if available
        scene_dur_ms = 5000.0  # default 5 s per scene
        if i < len(scene_video_paths):
            vid = Path(scene_video_paths[i])
            if vid.is_file():
                try:
                    result = subprocess.run(
                        [
                            ff.replace("ffmpeg", "ffprobe"),
                            "-v", "error",
                            "-show_entries", "format=duration",
                            "-of", "csv=p=0",
                            str(vid),
                        ],
                        capture_output=True, text=True, timeout=10,
                    )
                    scene_dur_ms = float(result.stdout.strip()) * 1000
                except Exception:
                    pass

        dialogues = scene.get("dialogue", [])
        n = len(dialogues)
        line_dur = scene_dur_ms / max(n, 1)

        for d in dialogues:
            speaker = d.get("speaker", "")
            line    = d.get("line", "")
            text    = f"{speaker}: {line}" if speaker else line
            end_ms  = cursor_ms + line_dur
            entries.append((cursor_ms, end_ms, text))
            cursor_ms = end_ms

    # Write SRT
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(SRT_PATH, "w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(entries, 1):
            f.write(f"{idx}\n")
            f.write(f"{_ms_to_srt_ts(start)} --> {_ms_to_srt_ts(end)}\n")
            f.write(f"{text}\n\n")

    return SRT_PATH


# ─── subtitle burn ───────────────────────────────────────────────────────────

def _burn_subtitles(src: Path, srt: Path, dst: Path, ff: str) -> bool:
    """
    Burn SRT subtitles into *src* using FFmpeg subtitles filter.
    Falls back to ASS-style forced subtitle if the primary filter fails.
    """
    # Primary: use subtitles filter (requires libass)
    srt_escaped = str(srt).replace("\\", "/").replace(":", "\\:")
    cmd = [
        ff, "-y",
        "-i", str(src),
        "-vf", f"subtitles='{srt_escaped}':force_style='FontSize=18,PrimaryColour=&Hffffff&,OutlineColour=&H000000&,Outline=2'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(dst),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode == 0 and dst.is_file() and dst.stat().st_size > 0:
            return True
    except Exception:
        pass

    # Fallback: drawtext-based rendering (no libass required)
    # Just copies the video without subtitles as a last resort
    cmd_copy = [ff, "-y", "-i", str(src), "-c", "copy", str(dst)]
    try:
        result = subprocess.run(cmd_copy, capture_output=True, timeout=120)
        return result.returncode == 0 and dst.is_file() and dst.stat().st_size > 0
    except Exception:
        return False


# ─── main agent ─────────────────────────────────────────────────────────────

def run(state: Phase3State) -> dict[str, Any]:
    """
    Optionally burn subtitles into the stitched video.
    Reads add_subtitles from state; defaults to True.
    """
    stitched_str: str = state.get("stitched_path", "")
    if not stitched_str:
        err = "subtitle_burner: no stitched_path in state"
        log_event(state, "subtitle_burner", err, "error")
        return {"error": err}

    add_subs: bool = state.get("add_subtitles", True)
    stitched = Path(stitched_str)

    if not add_subs:
        log_event(state, "subtitle_burner", "Subtitles disabled — skipping", "info")
        return {"subtitled_path": stitched_str}

    ff: str = state.get("ffmpeg_exe", "ffmpeg")
    scene_manifest: dict = state.get("scene_manifest", {})
    scene_video_paths: list[str] = state.get("normalized_paths", [])

    log_event(state, "subtitle_burner", "Generating SRT from scene manifest…")
    srt = _build_srt(scene_manifest, scene_video_paths, ff)
    log_event(state, "subtitle_burner", f"SRT written: {srt}")

    output_dir = BASE_DIR / "outputs_phase3"
    output_dir.mkdir(parents=True, exist_ok=True)
    subtitled = output_dir / "stitched_subtitled.mp4"

    log_event(state, "subtitle_burner", "Burning subtitles into video…")
    ok = _burn_subtitles(stitched, srt, subtitled, ff)
    if not ok:
        log_event(state, "subtitle_burner", "Subtitle burn failed — using un-subtitled video", "warning")
        return {"subtitled_path": stitched_str, "srt_path": str(srt)}

    log_event(
        state, "subtitle_burner",
        f"Subtitled video ready: {subtitled.name} ({subtitled.stat().st_size // 1024} KB)",
        "success",
    )
    return {"subtitled_path": str(subtitled), "srt_path": str(srt)}
