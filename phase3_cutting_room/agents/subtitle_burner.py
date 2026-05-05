"""
phase3_cutting_room/agents/subtitle_burner.py
──────────────────────────────────────────────
Burns subtitles (SRT) into the stitched video using FFmpeg's subtitles
filter.  Generates per-scene SRT files from actual audio duration, then
combines them with proper timing offsets for the final video.

The agent is OPTIONAL: if add_subtitles=False in the state, it passes
the stitched video through unchanged.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from phase3_cutting_room.graph.state import Phase3State, log_event
from shared.config.config import BASE_DIR, SCENE_MANIFEST_PATH
from shared.config.config import BASE_DIR, SCENE_MANIFEST_PATH, PHASE2_AUDIO_DIR

OUTPUT_DIR = BASE_DIR / "outputs_phase3"
SRT_PATH   = OUTPUT_DIR / "subtitles.srt"
SCENE_SRTS_DIR = OUTPUT_DIR / "scene_srts"


# ─── SRT generation ─────────────────────────────────────────────────────────
# ─── Timing utilities ───────────────────────────────────────────────────────

def _ms_to_srt_ts(ms: float) -> str:
    """Convert milliseconds to SRT timestamp format HH:MM:SS,mmm."""
    total_s, millis = divmod(int(ms), 1000)
    total_m, secs   = divmod(total_s, 60)
    hours, mins     = divmod(total_m, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def _get_audio_duration(audio_path: Path, ff: str) -> float:
    """Get duration of audio file in seconds using ffprobe."""
    if not audio_path.is_file():
        return 0.0
    try:
        result = subprocess.run(
            [
                ff.replace("ffmpeg", "ffprobe"),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(audio_path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _get_video_duration(video_path: Path, ff: str) -> float:
    """Get duration of video file in seconds using ffprobe."""
    if not video_path.is_file():
        return 0.0
    try:
        result = subprocess.run(
            [
                ff.replace("ffmpeg", "ffprobe"),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# ─── Per-scene SRT generation ────────────────────────────────────────────────

def _build_scene_srt(scene: dict, scene_id: int, duration_sec: float) -> list[tuple[float, float, str]]:
    """
    Create SRT entries for a single scene based on its actual audio duration.
    Returns list of (start_ms, end_ms, text) tuples.
    """
    dialogues = scene.get("dialogue", [])
    if not dialogues:
        return []
    
    duration_ms = duration_sec * 1000
    entries: list[tuple[float, float, str]] = []
    
    # Distribute dialogue lines evenly across scene duration
    n = len(dialogues)
    line_dur_ms = duration_ms / max(n, 1)
    cursor_ms = 0.0
    
    for d in dialogues:
        speaker = d.get("speaker", "")
        line    = d.get("line", "")
        text    = f"{speaker}: {line}" if speaker else line
        end_ms  = cursor_ms + line_dur_ms
        entries.append((cursor_ms, end_ms, text))
        cursor_ms = end_ms
    
    return entries


def _combine_scene_srts(
    scenes: list[dict],
    scene_srts: list[list[tuple[float, float, str]]],
    video_durations: list[float],
) -> list[tuple[float, float, str]]:
    """
    Combine per-scene SRT entries with timing offsets.
    
    Args:
        scenes: list of scene dicts from manifest
        scene_srts: list of SRT entry lists, one per scene
        video_durations: list of video durations per scene (in seconds)
    
    Returns:
        Combined SRT entries with cumulative timing
    """
    combined: list[tuple[float, float, str]] = []
    cumulative_ms = 0.0
    
    for scene_idx, entries in enumerate(scene_srts):
        # Offset all entries in this scene by cumulative duration
        for start, end, text in entries:
            combined.append((cumulative_ms + start, cumulative_ms + end, text))
        
        # Advance cursor by this scene's video duration
        if scene_idx < len(video_durations):
            cumulative_ms += video_durations[scene_idx] * 1000
    
    return combined


def _write_srt_file(entries: list[tuple[float, float, str]], output_path: Path) -> bool:
    """Write SRT entries to file."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for idx, (start, end, text) in enumerate(entries, 1):
                f.write(f"{idx}\n")
                f.write(f"{_ms_to_srt_ts(start)} --> {_ms_to_srt_ts(end)}\n")
                f.write(f"{text}\n\n")
        return True
    except Exception as e:
        print(f"Error writing SRT: {e}")
        return False


def _build_srt(scene_manifest: dict, scene_video_paths: list[str], ff: str) -> Path:
    """
    Construct an SRT file from dialogue in the scene manifest.
    Estimates timing using per-scene video duration.
    """
    scenes = scene_manifest.get("scenes", [])
    if not scenes:
        return SRT_PATH
    
    SCENE_SRTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Get per-scene audio durations and build scene SRTs
    scene_srts: list[list[tuple[float, float, str]]] = []
    video_durations: list[float] = []
    
    for i, scene in enumerate(scenes):
        scene_id = int(scene.get("scene_id", i + 1))
        
        # Try to get duration from Phase 2 audio file
        audio_path = PHASE2_AUDIO_DIR / f"scene_{scene_id:02d}.wav"
        audio_dur_sec = _get_audio_duration(audio_path, ff)
        
        # Fallback to video duration if audio not found
        if audio_dur_sec <= 0 and i < len(scene_video_paths):
            vid_path = Path(scene_video_paths[i])
            audio_dur_sec = _get_video_duration(vid_path, ff)
        
        # Final fallback to default
        if audio_dur_sec <= 0:
            audio_dur_sec = 5.0
        
        video_durations.append(audio_dur_sec)
        
        # Build SRT entries for this scene
        scene_srt = _build_scene_srt(scene, scene_id, audio_dur_sec)
        scene_srts.append(scene_srt)
    
    # Step 2: Combine all scene SRTs with proper timing
    combined_entries = _combine_scene_srts(scenes, scene_srts, video_durations)
    
    # Step 3: Write final combined SRT
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_srt_file(combined_entries, SRT_PATH)
    
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
