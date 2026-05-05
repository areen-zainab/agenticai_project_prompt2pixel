"""
Video Generation Agent — branches on USE_VIDEO_MODEL config flag.

  USE_VIDEO_MODEL = True:
    Calls Wan2.2-I2V via HuggingFace Inference API (generate_scene_video MCP tool).
    For each dialogue entry's visual cue, builds a rich prompt that includes the
    character's appearance description and the visual cue text, then sends the
    character's Phase 1 portrait image + prompt to the model to generate a real
    video clip of that character performing the action.

  USE_VIDEO_MODEL = False:
    Uses the Pexels stock footage pipeline (query_stock_footage MCP tool).
    Downloads one stock video clip per visual cue, trims and concatenates them.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from phase2_studio_floor.graph.state import Phase2SceneState, add_event
from shared.config.config import (
    PHASE2_FRAMES_ROOT,
    PHASE2_STOCK_DIR,
    IMAGE_ASSETS_DIR,
    USE_VIDEO_MODEL,
)
from shared.mcp_server.client import discover_tool, invoke_tool


# ── Shared helpers ───────────────────────────────────────────────────────────


def _resolve_ffmpeg() -> str | None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=5)
        return "ffmpeg"
    except Exception:
        pass
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _count_frames(frames_dir: str) -> int:
    p = Path(frames_dir)
    return len(list(p.glob("*.png"))) + len(list(p.glob("*.jpg")))


def _add_character_frames(scene: dict[str, Any], frames_dir: str) -> None:
    """Copy Phase 1 character portrait images into the frame sequence."""
    characters = scene.get("characters", []) or []
    next_idx = _count_frames(frames_dir) + 1
    for char_name in characters:
        safe = "".join(c if c.isalnum() else "_" for c in str(char_name))
        for ext in (".png", ".jpg"):
            img_path = IMAGE_ASSETS_DIR / f"{safe}{ext}"
            if img_path.exists():
                dest = Path(frames_dir) / f"frame_{next_idx:03d}.png"
                try:
                    import cv2
                    img = cv2.imread(str(img_path))
                    if img is not None:
                        resized = cv2.resize(img, (640, 360))
                        cv2.imwrite(str(dest), resized)
                        next_idx += 1
                except Exception:
                    shutil.copy2(img_path, dest)
                    next_idx += 1
                break


def _write_placeholder_frames(frames_dir: str, scene_id: int, caption: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    for i in range(1, 5):
        path = Path(frames_dir) / f"frame_{i:03d}.png"
        img = Image.new("RGB", (640, 360), color=(20, 24, 40))
        draw = ImageDraw.Draw(img)
        draw.rectangle([4, 4, 635, 355], outline=(80, 120, 200), width=2)
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            font = ImageFont.load_default()
        draw.text((16, 16), f"Scene {scene_id} · frame {i}", fill=(220, 220, 240), font=font)
        for j, line in enumerate(caption[:80].splitlines()[:3]):
            draw.text((16, 52 + j * 26), line[:70], fill=(160, 170, 200), font=font)
        img.save(path, "PNG")


def _resolve_character_image(char_name: str) -> str | None:
    """Find the character's Phase 1 portrait image."""
    safe = "".join(c if c.isalnum() else "_" for c in str(char_name))
    for ext in (".png", ".jpg"):
        p = IMAGE_ASSETS_DIR / f"{safe}{ext}"
        if p.exists():
            return str(p)
    return None


# ── VIDEO MODEL path (Wan2.2-I2V via HuggingFace) ───────────────────────────


def _build_wan_prompt(
    visual_cue: str,
    location: str,
    character_name: str,
    character_db: dict[str, Any],
) -> str:
    """Build a rich image-to-video prompt from visual cue + character description."""
    # Find character appearance
    appearance = ""
    for ch in (character_db.get("characters") or []):
        if str(ch.get("name", "")).upper() == character_name.upper():
            appearance = ch.get("appearance_description", "")
            style = ch.get("reference_style", "")
            break

    # Strip character name from cue (LTX/Wan doesn't know "JACK")
    cue = visual_cue
    for variant in [character_name, character_name.lower(), character_name.title()]:
        cue = cue.replace(variant, "").strip(" ,.")

    # Parse location
    loc = re.sub(r"^(INT\.|EXT\.)\s*", "", location)
    loc = re.sub(r"\s*-\s*(NIGHT|DAY|DAWN|DUSK).*$", "", loc, flags=re.IGNORECASE).strip()

    parts = []
    # Core Framing - Upper body shot is essential for high-fidelity lip sync
    parts.append("cinematic medium close-up, upper body shot, character facing camera")
    
    if cue:
        parts.append(cue)
    if appearance:
        parts.append(appearance)
    if loc:
        parts.append(f"background: realistic cinematic {loc} environment, blurred bokeh")
    
    # Performance & Quality Hints
    parts.append("speaking clearly, natural lip movement, dynamic facial expressions")
    parts.append("highly detailed, realistic skin texture, 4k, cinematic lighting, realistic motion, 24fps")

    return ", ".join(p.strip(" ,") for p in parts if p.strip())


def _run_video_model_path(
    state: Phase2SceneState,
    scene: dict[str, Any],
    scene_id: int,
    frames_dir: str,
) -> str | None:
    """Per-visual-cue video generation via Wan2.2-I2V on HuggingFace."""
    character_db = state.get("character_db", {})
    characters = [str(c) for c in (scene.get("characters") or [])]
    location = scene.get("location", "")
    dialogues = scene.get("dialogue") or []

    if discover_tool("generate_scene_video") is None:
        add_event(state, agent="video_gen", level="error",
                  message="MCP tool 'generate_scene_video' not found")
        return None

    clip_paths: list[str] = []

    for idx, d in enumerate(dialogues):
        cue = d.get("visual_cue", "").strip()
        speaker = (d.get("speaker") or (characters[0] if characters else "CHARACTER")).upper()

        if not cue:
            cue = location or "character speaking in a cinematic scene"

        # Build rich prompt
        prompt = _build_wan_prompt(cue, location, speaker, character_db)

        # Find character image
        char_image = _resolve_character_image(speaker)

        add_event(
            state, agent="video_gen", level="info",
            message=f"Generating clip {idx + 1}/{len(dialogues)} via Wan2.2-I2V",
            data={"speaker": speaker, "prompt": prompt[:120]},
        )

        result = invoke_tool(
            "generate_scene_video",
            {
                "prompt": prompt,
                "character_image_path": char_image or "",
                "scene_id": scene_id,
                "clip_index": idx,
            },
            timeout=360,
        )

        clip = result.get("downloaded_mp4")
        mode = result.get("mode", "stub")

        if clip and Path(clip).is_file():
            clip_paths.append(clip)
            add_event(
                state, agent="video_gen", level="success",
                message=f"Clip {idx + 1} generated ({mode}): {Path(clip).name}",
            )
        else:
            add_event(
                state, agent="video_gen", level="warning",
                message=f"Clip {idx + 1} failed ({result.get('error', 'unknown')})",
            )

    # Concatenate all clips with precision timing
    ff = _resolve_ffmpeg()
    if clip_paths and ff:
        durations = state.get("line_durations")
        scene_video = _concat_clips(clip_paths, scene_id, ff, durations=durations)
        if scene_video:
            _extract_key_frames(scene_video, frames_dir, ff)
            return scene_video

    # Fallback: use extracted frames from individual clips
    for clip in clip_paths:
        ff2 = _resolve_ffmpeg()
        if ff2:
            _extract_key_frames(clip, frames_dir, ff2)

    return None


# ── STOCK FOOTAGE path (Pexels) ──────────────────────────────────────────────


def _get_speaker_traits(character_name: str, character_db: dict[str, Any]) -> str:
    """Extract primary subject type (man/woman/person) from character description."""
    name = character_name.strip().upper()
    for ch in (character_db.get("characters") or []):
        if str(ch.get("name", "")).strip().upper() == name:
            desc = str(ch.get("appearance_description", "")).lower()
            if "woman" in desc or "female" in desc or "girl" in desc:
                return "woman"
            if "man" in desc or "male" in desc or "boy" in desc:
                return "man"
    return "person"


def _get_llm_stock_query(
    visual_cue: str, 
    location: str, 
    speaker_name: str, 
    character_db: dict[str, Any]
) -> str | None:
    """Use an LLM (Groq/Gemini) to generate a high-relevance Pexels search query."""
    from shared.llm_client import chat_text
    
    # Resolve speaker traits for context
    traits = _get_speaker_traits(speaker_name, character_db)
    
    system_prompt = (
        "You are a cinematic research assistant for a video production pipeline. "
        "Your task is to generate a SINGLE, concise Pexels search query (5-8 words) for a stock video clip. "
        "Rules:\n"
        "1. Do NOT include character names (e.g. 'Jax'). Use generic subjects like 'man', 'woman', or 'person'.\n"
        "2. Focus on the action and environment from the visual cue.\n"
        "3. Ensure the lighting/time matches the location description.\n"
        "4. Output ONLY the search query string, no quotes or explanations."
    )
    
    user_prompt = (
        f"Location: {location}\n"
        f"Subject: {traits}\n"
        f"Action/Visual Cue: {visual_cue}\n\n"
        "Generate the best Pexels search query:"
    )
    
    try:
        query = chat_text(system=system_prompt, user=user_prompt, temperature=0.5)
        return query.strip().strip('"')
    except Exception as e:
        print(f"[VideoGen] LLM stock query failed: {e}")
        return None


def _build_stock_query(
    visual_cue: str, location: str, speaker_traits: str
) -> str:
    """Fallback: Build a character-centric Pexels search query using rules."""
    # Start with the human subject, specifying a single person for clarity
    query = f"one {speaker_traits}"
    
    # Add location context
    loc = location
    for prefix in ["INT.", "EXT.", "INT ", "EXT ", " - ", " – "]:
        loc = loc.replace(prefix, " ")
    loc_clean = re.sub(r"\s*-\s*(NIGHT|DAY|DAWN|DUSK).*$", "", loc, flags=re.IGNORECASE).strip()
    
    # Keywords to replace 'Agency' with 'Office' which has more human stock footage
    if "agency" in loc_clean.lower():
        loc_clean = loc_clean.lower().replace("agency", "office").strip()
    
    query += f" in {loc_clean}"

    # Add descriptive elements from cue
    cue = visual_cue
    _strip = [
        "slams", "pulls", "checks", "slides", "narrows", "leans", "paces",
        "stands", "walks", "sits", "looks", "turns", "speaks", "says",
        "grabs", "opens", "closes", "reaches", "holds", "pointing",
        "visible", "expression", "resting", "behind", "near", "against",
    ]
    for word in _strip:
        cue = re.sub(rf"\b{word}\b", "", cue, flags=re.IGNORECASE)
    
    cue_words = [w for w in re.sub(r"[^\w\s]", "", cue).split() if len(w) > 2][:3]
    if cue_words:
        query += " " + " ".join(cue_words)

    # Final polish
    query = re.sub(r"\s+", " ", query).strip()
    return query


def _run_stock_footage_path(
    state: Phase2SceneState,
    scene: dict[str, Any],
    scene_id: int,
    frames_dir: str,
) -> str | None:
    """Per-character 'Consistent Subject' stock footage download via Pexels."""
    from shared.config.config import IMAGE_ASSETS_DIR
    character_db = state.get("character_db", {})
    location = scene.get("location", "")
    dialogues = scene.get("dialogue") or []

    if discover_tool("query_stock_footage") is None:
        add_event(state, agent="video_gen", level="error",
                  message="MCP tool 'query_stock_footage' not found")
        return None

    # Group dialogues by speaker to find a consistent clip for each segment
    # For now, we take one primary clip for the scene or per major speaker change
    clip_paths: list[str] = []
    processed_speakers = set()
    
    for idx, d in enumerate(dialogues):
        speaker = str(d.get("speaker") or "CHARACTER").strip().upper()
        cue = d.get("visual_cue", "").strip()
        
        # Attempt LLM-optimized query first (Groq/Gemini)
        query = _get_llm_stock_query(cue, location, speaker, character_db)
        
        if not query:
            # Fallback to rule-based query
            traits = _get_speaker_traits(speaker, character_db)
            query = _build_stock_query(cue, location, traits)
            add_event(
                state, agent="video_gen", level="info",
                message=f"Pexels rule-based search: '{query}' for {speaker}",
            )
        else:
            add_event(
                state, agent="video_gen", level="info",
                message=f"Pexels LLM-optimized search: '{query}' for {speaker}",
            )
        
        stock = invoke_tool(
            "query_stock_footage",
            {"description": query, "scene_id": scene_id, "clip_index": idx},
            timeout=120,
        )
        clip = stock.get("downloaded_mp4")
        if clip and Path(clip).is_file():
            clip_paths.append(clip)
        
        # If we have multiple dialogues for the same person, we might want to skip downloading 
        # identical queries, but Pexels search results vary, so multiple results is fine.

    # Concatenate all clips with precision timing
    ff = _resolve_ffmpeg()
    if clip_paths and ff:
        durations = state.get("line_durations")
        scene_video = _concat_clips(clip_paths, scene_id, ff, durations=durations)
        if scene_video:
            _extract_key_frames(scene_video, frames_dir, ff)
            return scene_video

    return None


# ── Shared clip processing ───────────────────────────────────────────────────


def _concat_clips(
    clip_paths: list[str], scene_id: int, ff: str, durations: list[float] | None = None
) -> str | None:
    """
    Concatenate video clips with optional precision trimming.
    Saves everything in outputs_phase2/stock/scene_XX/
    """
    # New Structured Folder: stock/scene_01/
    scene_dir = PHASE2_STOCK_DIR / f"scene_{scene_id:02d}"
    full_clips_dir = scene_dir / "full-clips"
    
    scene_dir.mkdir(parents=True, exist_ok=True)
    full_clips_dir.mkdir(parents=True, exist_ok=True)

    trimmed: list[Path] = []
    for i, raw_path_str in enumerate(clip_paths):
        raw_path = Path(raw_path_str)
        # Move raw download to structured 'full-clips' folder
        structured_raw = full_clips_dir / raw_path.name
        if raw_path.exists() and not structured_raw.exists():
            shutil.move(str(raw_path), str(structured_raw))
        
        target_raw = structured_raw if structured_raw.exists() else raw_path
        out = scene_dir / f"trimmed_{i:02d}.mp4"
        
        # Determine duration: use precision timing if available, else default to 5s
        dur = 5.0
        if durations and i < len(durations):
            dur = durations[i]
            # Add a tiny buffer (0.1s) to prevent sharp cuts often seen in stock-to-stock
            dur = max(0.5, dur + 0.1)

        try:
            cmd = [
                ff, "-y", "-i", str(target_raw),
                "-t", str(dur),
                "-c:v", "libx264",
                "-vf", "scale=640:360:force_original_aspect_ratio=decrease,"
                       "pad=640:360:(ow-iw)/2:(oh-ih)/2",
                "-r", "24", "-pix_fmt", "yuv420p", "-an", str(out),
            ]
            subprocess.run(cmd, capture_output=True, check=True, timeout=60)
            if out.exists() and out.stat().st_size > 0:
                trimmed.append(out)
        except Exception as e:
            print(f"[VideoGen] Trim failed for clip {i}: {e}")

    if not trimmed:
        return None

    # Merge video now lives inside the scene directory
    scene_video = scene_dir / f"scene_{scene_id:02d}_merged.mp4"
    concat_list = scene_dir / "_concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in trimmed:
            f.write(f"file '{p.as_posix()}'\n")
    try:
        cmd = [ff, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(scene_video)]
        subprocess.run(cmd, capture_output=True, check=True, timeout=60)
        if scene_video.exists() and scene_video.stat().st_size > 0:
            return str(scene_video)
    except Exception as e:
        print(f"[VideoGen] Concat failed: {e}")
    return None


def _extract_key_frames(video_path: str, frames_dir: str, ff: str) -> None:
    """
    Extract frames from video for face swapping and lip syncing.
    Increased FPS from 1 to 12 to preserve 'movement' as requested.
    """
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 24
        
        # User requested more frames to improve movement aspect.
        # We'll target 12 FPS (half-rate for efficiency but fluid enough for AI).
        target_fps = 12 
        step = max(1, int(fps / target_fps))
        
        existing = _count_frames(frames_dir)
        saved = 0
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % step == 0:
                out = Path(frames_dir) / f"frame_{existing + saved + 1:04d}.png"
                import cv2 as _cv2
                _cv2.imwrite(str(out), frame)
                saved += 1
            idx += 1
        cap.release()
        print(f"[VideoGen] Extracted {saved} frames at index step {step} (target ~12 FPS)")
    except Exception as e:
        print(f"[VideoGen] Frame extraction failed: {e}")


# ── Main agent entry point ───────────────────────────────────────────────────


def run(state: Phase2SceneState) -> dict[str, Any]:
    scene = state["scene"]
    scene_id = int(scene.get("scene_id", 1))
    location = scene.get("location", "")

    add_event(
        state, agent="video_gen", level="info",
        message=f"Starting video generation for scene {scene_id}...",
    )

    frames_dir = str(PHASE2_FRAMES_ROOT / f"scene_{scene_id:02d}")
    f_path = Path(frames_dir)
    if f_path.exists():
        shutil.rmtree(f_path)
    f_path.mkdir(parents=True, exist_ok=True)

    add_event(
        state, agent="video_gen", level="info",
        message=f"Video gen started (mode: {'wan_i2v' if USE_VIDEO_MODEL else 'pexels_stock'})",
    )

    scene_video_path: str | None = None

    if USE_VIDEO_MODEL:
        # ── Path A: AI video generation via Wan2.2-I2V ──
        scene_video_path = _run_video_model_path(state, scene, scene_id, frames_dir)
    else:
        # ── Path B: Pexels stock footage ──
        scene_video_path = _run_stock_footage_path(state, scene, scene_id, frames_dir)

    # Always add Phase 1 character images as supplementary frames
    _add_character_frames(scene, frames_dir)

    # Last resort: placeholder frames if nothing worked
    if not scene_video_path and _count_frames(frames_dir) == 0:
        _write_placeholder_frames(frames_dir, scene_id, location)
        add_event(
            state, agent="video_gen", level="warning",
            message="All video sources failed — using placeholder frames",
        )

    return {
        "video_frames_dir": frames_dir,
        "scene_video_path": scene_video_path or "",
    }
