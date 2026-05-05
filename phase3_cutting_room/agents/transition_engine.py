"""
phase3_cutting_room/agents/transition_engine.py
───────────────────────────────────────────────
Applies crossfade / fade-to-black / wipe transitions between normalized
scene clips using the FFmpeg xfade filter.

Supported transition styles (configured via Phase3State.transition_style):
  "fade"       – crossfade (default)
  "fade_black" – fade to black then in
  "wipe_left"  – horizontal wipe
  "wipe_right" – horizontal wipe (right)
  "dissolve"   – dissolve (alias for fade in xfade)
  "cut"        – hard cut, no transition (fastest)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from phase3_cutting_room.graph.state import Phase3State, log_event
from shared.config.config import BASE_DIR

TRANSITIONS_DIR = BASE_DIR / "outputs_phase3" / "transitions"

# xfade transition name mapping
_XFADE_MAP = {
    "fade":       "fade",
    "fade_black": "fadeblack",
    "wipe_left":  "wipeleft",
    "wipe_right": "wiperight",
    "dissolve":   "dissolve",
    "cut":        "cut",   # handled specially — no xfade
}
DEFAULT_TRANSITION = "fade"
TRANSITION_DURATION = 0.5   # seconds of overlap


def _get_video_duration(path: Path, ff: str) -> float:
    """Probe video duration using ffprobe."""
    try:
        result = subprocess.run(
            [
                ff.replace("ffmpeg", "ffprobe"),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:
        return 5.0   # safe default


def _hard_cut_concat(clips: list[Path], output: Path, ff: str) -> bool:
    """Simple stream-copy concat — no transitions."""
    concat_list = output.parent / "_hardcut_concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in clips:
            f.write(f"file '{p.as_posix()}'\n")
    cmd = [
        ff, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    return result.returncode == 0 and output.is_file() and output.stat().st_size > 0


def _xfade_pair(
    clip_a: Path, clip_b: Path, output: Path,
    xfade_name: str, ff: str,
    duration_a: float | None = None,
) -> bool:
    """
    Merge clip_a and clip_b with an xfade transition, writing to output.
    duration_a is used to calculate the offset.
    """
    if duration_a is None:
        duration_a = _get_video_duration(clip_a, ff)

    offset = max(0.01, duration_a - TRANSITION_DURATION)

    # xfade requires re-encoding
    filter_complex = (
        f"[0:v][1:v]xfade=transition={xfade_name}:"
        f"duration={TRANSITION_DURATION}:offset={offset}[vout];"
        f"[0:a][1:a]acrossfade=d={TRANSITION_DURATION}[aout]"
    )
    cmd = [
        ff, "-y",
        "-i", str(clip_a),
        "-i", str(clip_b),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(output),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        return result.returncode == 0 and output.is_file() and output.stat().st_size > 0
    except Exception:
        return False


def _xfade_chain(clips: list[Path], output: Path, xfade_name: str, ff: str) -> bool:
    """
    Chain-apply xfade transitions across all clips sequentially.
    Each step merges the accumulated output with the next clip.
    """
    TRANSITIONS_DIR.mkdir(parents=True, exist_ok=True)
    current = clips[0]
    current_dur: float | None = None

    for i, next_clip in enumerate(clips[1:], 1):
        is_last = i == len(clips) - 1
        tmp_out = output if is_last else TRANSITIONS_DIR / f"_xfade_step_{i}.mp4"
        ok = _xfade_pair(current, next_clip, tmp_out, xfade_name, ff, current_dur)
        if not ok:
            return False
        current = tmp_out
        current_dur = None   # re-probe each step

    return output.is_file() and output.stat().st_size > 0


def run(state: Phase3State) -> dict[str, Any]:
    """
    Apply transitions between normalized clips.
    Returns:
        stitched_path – path to the stitched (pre-subtitle) video
    """
    clips_str: list[str] = state.get("normalized_paths", [])
    if not clips_str:
        err = "transition_engine: no normalized_paths"
        log_event(state, "transition_engine", err, "error")
        return {"error": err}

    ff: str = state.get("ffmpeg_exe", "ffmpeg")
    style: str = state.get("transition_style", DEFAULT_TRANSITION)
    xfade_name = _XFADE_MAP.get(style, "fade")

    clips = [Path(p) for p in clips_str]
    output_dir = BASE_DIR / "outputs_phase3"
    output_dir.mkdir(parents=True, exist_ok=True)
    stitched = output_dir / "stitched_raw.mp4"

    log_event(state, "transition_engine", f"Applying '{style}' transitions across {len(clips)} clip(s)…")

    if len(clips) == 1:
        shutil.copy2(clips[0], stitched)
        log_event(state, "transition_engine", "Single clip — copied directly", "success")
        return {"stitched_path": str(stitched)}

    if style == "cut":
        ok = _hard_cut_concat(clips, stitched, ff)
    else:
        ok = _xfade_chain(clips, stitched, xfade_name, ff)
        if not ok:
            # Graceful fallback to hard cut
            log_event(
                state, "transition_engine",
                f"xfade failed — falling back to hard cut", "warning",
            )
            ok = _hard_cut_concat(clips, stitched, ff)

    if not ok:
        err = "transition_engine: stitching failed"
        log_event(state, "transition_engine", err, "error")
        return {"error": err}

    log_event(
        state, "transition_engine",
        f"Stitched video: {stitched.name} ({stitched.stat().st_size // 1024} KB)", "success",
    )
    return {"stitched_path": str(stitched)}
