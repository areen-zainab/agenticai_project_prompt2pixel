"""
phase3_cutting_room/agents/normalizer.py
────────────────────────────────────────
Re-encodes every scene clip to a common spec so FFmpeg concat never
chokes on mismatched codecs, resolutions, or frame-rates.

Target spec: 1280×720, 24 fps, yuv420p, libx264 / aac, stereo 44100 Hz.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from phase3_cutting_room.graph.state import Phase3State, log_event
from shared.config.config import BASE_DIR

NORMALIZED_DIR = BASE_DIR / "outputs_phase3" / "normalized"
TARGET_W, TARGET_H = 1280, 720
TARGET_FPS = 24
TARGET_AUDIO_RATE = 44100


def _resolve_ffmpeg() -> str:
    """Find ffmpeg executable (system PATH or imageio_ffmpeg fallback)."""
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise RuntimeError("ffmpeg not found. Install it or add it to PATH.")


def _normalize_clip(src: Path, dst: Path, ff: str) -> bool:
    """
    Re-encode *src* to the target spec and write to *dst*.
    Scale+pad preserves aspect ratio.  Audio is normalized to stereo aac.
    Returns True on success.
    """
    vf = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black"
    )
    cmd = [
        ff, "-y",
        "-i", str(src),
        # video stream
        "-vf", vf,
        "-r", str(TARGET_FPS),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        # audio stream (create silence if input has no audio)
        "-af", f"aresample={TARGET_AUDIO_RATE}",
        "-ar", str(TARGET_AUDIO_RATE),
        "-ac", "2",
        "-c:a", "aac",
        "-b:a", "128k",
        str(dst),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=180,
        )
        if result.returncode != 0:
            return False
        return dst.is_file() and dst.stat().st_size > 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def _normalize_clip_silent(src: Path, dst: Path, ff: str) -> bool:
    """
    Same as _normalize_clip but generates a silent audio track when the
    source has no audio (common for stock footage downloaded without sound).
    """
    # First try with existing audio
    if _normalize_clip(src, dst, ff):
        return True
    # Retry adding silent audio via lavfi
    vf = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black"
    )
    cmd = [
        ff, "-y",
        "-i", str(src),
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={TARGET_AUDIO_RATE}",
        "-vf", vf,
        "-r", str(TARGET_FPS),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(dst),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=180)
        return result.returncode == 0 and dst.is_file() and dst.stat().st_size > 0
    except Exception:
        return False


def run(state: Phase3State) -> dict[str, Any]:
    """
    Normalize every collected scene clip.
    Returns:
        normalized_paths – list of normalized MP4 path strings (same order)
        ffmpeg_exe       – resolved ffmpeg path for downstream agents
    """
    scene_paths: list[str] = state.get("scene_video_paths", [])
    if not scene_paths:
        err = "normalizer: no scene_video_paths to normalize"
        log_event(state, "normalizer", err, "error")
        return {"error": err, "normalized_paths": []}

    try:
        ff = _resolve_ffmpeg()
    except RuntimeError as e:
        log_event(state, "normalizer", str(e), "error")
        return {"error": str(e), "normalized_paths": []}

    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    normalized: list[str] = []

    for i, src_str in enumerate(scene_paths):
        src = Path(src_str)
        dst = NORMALIZED_DIR / f"norm_{i:02d}.mp4"

        log_event(state, "normalizer", f"  Normalizing {src.name} → {dst.name}")

        ok = _normalize_clip_silent(src, dst, ff)
        if ok:
            normalized.append(str(dst))
            log_event(state, "normalizer", f"  ✓ {dst.name} ({dst.stat().st_size // 1024} KB)", "success")
        else:
            log_event(state, "normalizer", f"  ✗ Failed to normalize {src.name} — skipping", "warning")

    if not normalized:
        err = "normalizer: all clips failed normalization"
        log_event(state, "normalizer", err, "error")
        return {"error": err, "normalized_paths": []}

    log_event(state, "normalizer", f"Normalized {len(normalized)}/{len(scene_paths)} clips", "success")
    return {"normalized_paths": normalized, "ffmpeg_exe": ff}
