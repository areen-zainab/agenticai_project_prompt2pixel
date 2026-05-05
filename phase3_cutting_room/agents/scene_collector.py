"""
phase3_cutting_room/agents/scene_collector.py
─────────────────────────────────────────────
Scans the Phase 2 output directories for all finished scene MP4s and
returns them in scene_id order.  Checks every location the Phase 2
pipeline may have written to:

  Priority 1 – outputs_phase2/raw_scenes/scene_XX.mp4      (lip-sync output)
  Priority 2 – outputs_phase2/stock/scene_XX/scene_XX_merged.mp4  (Pexels)
  Priority 3 – outputs_phase2/stock/scene_XX/trimmed_*.mp4  (per-dialogue clips)
"""

from __future__ import annotations

import glob
import re
from pathlib import Path
from typing import Any

from phase3_cutting_room.graph.state import Phase3State, log_event
from shared.config.config import PHASE2_RAW_SCENES_DIR, PHASE2_STOCK_DIR, OUTPUTS_PHASE2_DIR


# ─── helpers ────────────────────────────────────────────────────────────────

def _scene_id_from_path(p: Path) -> int | None:
    """Extract scene integer from filenames like scene_01.mp4 or scene_1_merged.mp4."""
    m = re.search(r"scene[_\-](\d+)", p.stem, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _best_video_for_scene(scene_id: int) -> Path | None:
    """Return the highest-priority MP4 for a given scene_id."""
    sid = f"{scene_id:02d}"

    # 1) raw_scenes — lip-synced final output
    for ext in (f"scene_{sid}.mp4", f"scene_{scene_id}.mp4"):
        p = PHASE2_RAW_SCENES_DIR / ext
        if p.is_file() and p.stat().st_size > 0:
            return p

    # 2) stock sub-directory — merged clip
    stock_scene = PHASE2_STOCK_DIR / f"scene_{sid}"
    for pattern in (f"scene_{sid}_merged.mp4", f"scene_{scene_id}_merged.mp4"):
        p = stock_scene / pattern
        if p.is_file() and p.stat().st_size > 0:
            return p

    # 3) stock trimmed clips (take first one as representative)
    for trimmed in sorted(stock_scene.glob("trimmed_*.mp4")):
        if trimmed.stat().st_size > 0:
            return trimmed

    # 4) Recursive search anywhere under outputs_phase2
    for p in sorted(OUTPUTS_PHASE2_DIR.rglob(f"scene_{sid}*.mp4")):
        if p.stat().st_size > 0:
            return p

    return None


# ─── main agent ─────────────────────────────────────────────────────────────

def run(state: Phase3State) -> dict[str, Any]:
    """
    Discover all per-scene MP4 paths from Phase 2 outputs.
    Returns:
        scene_video_paths  – ordered list of (scene_id, path) tuples as strings
        scene_count        – number of scenes found
    """
    log_event(state, "scene_collector", "Scanning Phase 2 outputs for scene videos…")

    scene_manifest = state.get("scene_manifest", {})
    scenes = scene_manifest.get("scenes", [])

    if not scenes:
        log_event(state, "scene_collector", "No scenes in manifest — scanning disk", "warning")
        # Fallback: discover any scene_XX.mp4 under outputs_phase2
        found: dict[int, Path] = {}
        for mp4 in sorted(OUTPUTS_PHASE2_DIR.rglob("scene_*.mp4")):
            sid = _scene_id_from_path(mp4)
            if sid is not None and sid not in found and mp4.stat().st_size > 0:
                found[sid] = mp4
        ordered = [str(found[k]) for k in sorted(found)]
    else:
        ordered: list[str] = []
        for scene in scenes:
            sid = int(scene.get("scene_id", 0))
            p = _best_video_for_scene(sid)
            if p:
                ordered.append(str(p))
                log_event(state, "scene_collector", f"  Scene {sid}: {p.name}", "info")
            else:
                log_event(
                    state, "scene_collector",
                    f"  Scene {sid}: ⚠ no video found — will be skipped",
                    "warning",
                )

    if not ordered:
        err = "scene_collector: no scene videos found in Phase 2 outputs"
        log_event(state, "scene_collector", err, "error")
        return {"error": err, "scene_video_paths": []}

    log_event(
        state, "scene_collector",
        f"Collected {len(ordered)} scene video(s)", "success",
    )
    return {"scene_video_paths": ordered, "scene_count": len(ordered)}
