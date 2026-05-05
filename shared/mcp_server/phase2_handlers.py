"""
Phase 2 MCP tool handlers (Studio Floor).
Kept separate from Phase 1 handlers so the registry stays maintainable.
Stubs are deterministic and write artifacts under shared.config PHASE2_* paths.
"""

from __future__ import annotations

import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any

from shared.config.config import (
    PHASE2_AUDIO_DIR,
    PHASE2_FACE_SWAPPED_DIR,
    PHASE2_RAW_SCENES_DIR,
    USE_AI_ANIMATION,
    LIP_SYNC_SPACE_ID,
)


def _scene_pad(scene_id: int) -> str:
    return f"{int(scene_id):02d}"


# ── get_task_graph ───────────────────────────────────────────────────────────


def handle_get_task_graph(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Build a small DAG description for one scene (parallel audio/video, then join).
    """
    scene_id = int(inp.get("scene_id", 1))
    return {
        "scene_id": scene_id,
        "tasks": [
            {"id": "voice", "deps": [], "parallel_group": "av"},
            {"id": "video", "deps": [], "parallel_group": "av"},
            {"id": "face_swap", "deps": ["voice", "video"]},
            {"id": "lip_sync", "deps": ["face_swap"]},
        ],
    }


# ── voice_cloning_synthesizer (real TTS via edge-tts) ────────────────────────

# ·· Fallback tone generator (used when edge-tts is unavailable) ··


def _write_tone_wav(path: Path, duration_sec: float, freq: float = 440.0) -> None:
    """Fallback: simple sine-wave WAV for pipeline continuity."""
    path.parent.mkdir(parents=True, exist_ok=True)
    framerate = 22050
    nframes = max(int(framerate * duration_sec), int(framerate * 0.5))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        for i in range(nframes):
            val = int(32767 * 0.12 * math.sin(2 * math.pi * freq * i / framerate))
            w.writeframes(struct.pack("<h", val))


# ·· Per-character voice assignment ··

# Elite Neural Voice Pools
_MALE_VOICES = [
    "en-US-ChristopherNeural", 
    "en-US-EricNeural", 
    "en-GB-RyanNeural", 
    "en-US-GuyNeural"
]
_FEMALE_VOICES = [
    "en-US-AvaNeural", 
    "en-US-EmmaNeural", 
    "en-GB-SoniaNeural", 
    "en-US-JennyNeural"
]
_NEUTRAL_VOICES = ["en-US-SteffanNeural", "en-US-MichelleNeural"]

# Full-Parameter Emotion Mapping
_EMOTION_SETTINGS: dict[str, dict[str, str]] = {
    "angry": {"rate": "+20%", "pitch": "+10Hz", "volume": "+15%"},
    "sad": {"rate": "-15%", "pitch": "-10Hz", "volume": "-20%"},
    "excited": {"rate": "+25%", "pitch": "+15Hz", "volume": "+10%"},
    "calm": {"rate": "-10%", "pitch": "-5Hz", "volume": "-10%"},
    "fearful": {"rate": "+30%", "pitch": "+20Hz", "volume": "+0%"},
    "happy": {"rate": "+15%", "pitch": "+12Hz", "volume": "+5%"},
    "neutral": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"},
}

_character_voices: dict[str, str] = {}


def _detect_gender(name: str, traits: str) -> str:
    """Enhanced gender detection using name overrides and weighted keyword scoring."""
    n = name.upper()
    t = traits.lower()
    
    # 1. Hardcoded Name Overrides (highest priority)
    if any(m in n for m in ["JACK", "VENDOR", "GUY", "MAN", "DETECTIVE", "MALE"]):
        return "male"
    if any(f in n for f in ["SARAH", "LADY", "WOMAN", "FEMALE", "GIRL"]):
        return "female"
        
    # 2. Weighted Keyword Scoring
    m_score = 0
    f_score = 0
    
    # High weight tokens (identities)
    for w in ["man", "male", "boy", "guy", "gentleman", "rugged", "beard"]:
        if w in t: m_score += 5
    for w in ["woman", "female", "girl", "lady", "auburn", "dress", "skirt"]:
        if w in t: f_score += 5
        
    # Low weight tokens (pronouns)
    for w in ["he", "him", "his"]:
        if f" {w} " in f" {t} ": m_score += 1
    for w in ["she", "her", "hers"]:
        if f" {w} " in f" {t} ": f_score += 1
        
    if m_score > f_score: return "male"
    if f_score > m_score: return "female"
    return "neutral"


def _assign_voice(character_name: str, traits: str | None = None) -> str:
    """Assign a persistent, gender-appropriate neural voice to each character."""
    key = character_name.strip().upper()
    if key not in _character_voices:
        gender = _detect_gender(key, traits or "")
        pool = {
            "male": _MALE_VOICES,
            "female": _FEMALE_VOICES,
        }.get(gender, _NEUTRAL_VOICES)
        
        # Consistent assignment using hash of name
        idx = zlib.adler32(key.encode()) % len(pool)
        _character_voices[key] = pool[idx]
        print(f"[Voice] Assigned '{_character_voices[key]}' ({gender}) to {character_name}")
    return _character_voices[key]


# ·· Async edge-tts helpers ··

import zlib

async def _edge_tts_synthesize(
    text: str, voice: str, mp3_path: str, settings: dict[str, str] | None = None
) -> None:
    """Generate speech MP3 via edge-tts with rate, pitch, and volume control."""
    import edge_tts
    s = settings or _EMOTION_SETTINGS["neutral"]
    communicate = edge_tts.Communicate(
        text, 
        voice, 
        rate=s.get("rate", "+0%"), 
        pitch=s.get("pitch", "+0Hz"), 
        volume=s.get("volume", "+0%")
    )
    await communicate.save(mp3_path)


def _run_tts(text: str, voice: str, mp3_path: str, settings: dict[str, str] | None = None) -> None:
    """Run edge-tts from synchronous context."""
    import asyncio as _aio
    try:
        _aio.run(_edge_tts_synthesize(text, voice, mp3_path, settings))
    except RuntimeError:
        loop = _aio.new_event_loop()
        _aio.set_event_loop(loop)
        try:
            loop.run_until_complete(_edge_tts_synthesize(text, voice, mp3_path, settings))
        finally:
            loop.close()


def _convert_mp3_to_wav(mp3_path: str, wav_path: str) -> None:
    """Convert MP3 -> mono 22 050 Hz PCM WAV via FFmpeg."""
    ff = _resolve_ffmpeg_exe()
    if not ff:
        raise RuntimeError("FFmpeg required for MP3 -> WAV conversion")
    subprocess.run(
        [ff, "-y", "-i", mp3_path, "-ar", "22050", "-ac", "1",
         "-acodec", "pcm_s16le", wav_path],
        capture_output=True, check=True, timeout=30,
    )


def _concatenate_wavs(wav_paths: list[str], output_path: str) -> None:
    """Concatenate WAVs with 0.4 s silence gaps via FFmpeg concat demuxer."""
    if not wav_paths:
        raise ValueError("No WAV files to concatenate")
    if len(wav_paths) == 1:
        shutil.copy2(wav_paths[0], output_path)
        return

    ff = _resolve_ffmpeg_exe()
    if not ff:
        raise RuntimeError("FFmpeg required for WAV concatenation")
    parent = str(Path(wav_paths[0]).parent)

    # Silence with matching format
    silence = str(Path(parent) / "_silence.wav")
    subprocess.run(
        [ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
         "-t", "0.4", "-acodec", "pcm_s16le", silence],
        capture_output=True, check=True, timeout=10,
    )

    concat_list = str(Path(parent) / "_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for i, wp in enumerate(wav_paths):
            f.write(f"file '{Path(wp).as_posix()}'\n")
            if i < len(wav_paths) - 1:
                f.write(f"file '{Path(silence).as_posix()}'\n")

    subprocess.run(
        [ff, "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c", "copy", output_path],
        capture_output=True, check=True, timeout=60,
    )


def handle_voice_cloning_synthesizer(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Generate real speech for scene dialogue via edge-tts.
    Assigns a unique neural voice per character, with emotion-aware rate adjustment.
    Falls back to sine-wave tone if edge-tts is unavailable.
    """
    import tempfile

    text = (inp.get("text") or "").strip()
    scene_id = int(inp.get("scene_id", 1))
    dialogue_entries = inp.get("dialogue_entries")  # [{speaker, line, emotion?}, ...]
    emotion = (inp.get("emotion") or "neutral").strip().lower()

    out_wav = PHASE2_AUDIO_DIR / f"scene_{_scene_pad(scene_id)}.wav"
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = tempfile.mkdtemp(prefix="montage_voice_")
    try:
        if dialogue_entries and isinstance(dialogue_entries, list):
            # ── Per-line synthesis — each character gets a distinct voice ──
            line_wavs: list[str] = []
            line_durations: list[float] = []  # duration of each individual line
            for i, entry in enumerate(dialogue_entries):
                speaker = entry.get("speaker", "NARRATOR")
                line = entry.get("line", "").strip()
                line_emotion = entry.get("emotion", emotion)
                traits = entry.get("traits", "")  # New: character metadata
                if not line:
                    continue

                voice = _assign_voice(speaker, traits)
                settings = _EMOTION_SETTINGS.get(line_emotion, _EMOTION_SETTINGS["neutral"])
                
                mp3 = str(Path(tmp_dir) / f"line_{i:03d}.mp3")
                wav = str(Path(tmp_dir) / f"line_{i:03d}.wav")

                _run_tts(line, voice, mp3, settings)
                _convert_mp3_to_wav(mp3, wav)
                line_wavs.append(wav)

                # Measure this individual line's exact duration + add the silence gap
                try:
                    with wave.open(wav, "rb") as wf:
                        dur = wf.getnframes() / float(wf.getframerate() or 22050)
                    # Add the 0.4s silence gap to the reported duration
                    line_durations.append(round(dur + 0.4, 3))
                except Exception:
                    line_durations.append(0.4)

            if line_wavs:
                _concatenate_wavs(line_wavs, str(out_wav))
            else:
                _write_tone_wav(out_wav, 1.0)
                line_durations = []
        elif text:
            # ── Single text, single voice ──
            character_name = inp.get("character_name", "NARRATOR")
            voice = _assign_voice(character_name)
            rate = _EMOTION_RATE.get(emotion, "+0%")
            mp3 = str(Path(tmp_dir) / "speech.mp3")
            _run_tts(text, voice, mp3, rate)
            _convert_mp3_to_wav(mp3, str(out_wav))
        else:
            raise ValueError("voice_cloning_synthesizer: no text or dialogue_entries")
    except Exception as e:
        # Fallback to tone so pipeline doesn't break
        print(f"[Voice] edge-tts failed ({e}), falling back to tone WAV")
        duration = float(inp.get("duration_sec") or 0.0)
        if duration <= 0:
            duration = min(12.0, max(1.5, len(text) * 0.06))
        _write_tone_wav(out_wav, duration)
        return {
            "wav_path": str(out_wav), "duration_sec": duration,
            "stub": True, "fallback_reason": str(e),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Measure actual WAV duration
    try:
        with wave.open(str(out_wav), "rb") as wf:
            duration = wf.getnframes() / float(wf.getframerate() or 22050)
    except Exception:
        duration = 0.0

    return {
        "wav_path": str(out_wav),
        "duration_sec": round(duration, 2),
        "line_durations": line_durations if dialogue_entries else [],
        "stub": False,
    }


# ── identity_validator (stub) ────────────────────────────────────────────────


def handle_identity_validator(inp: dict[str, Any]) -> dict[str, Any]:
    ref = (inp.get("reference_image_path") or "").strip()
    frame = (inp.get("frame_path") or "").strip()
    if ref and Path(ref).exists() and frame and Path(frame).exists():
        return {"valid": True, "confidence": 0.94, "stub": True}
    return {"valid": True, "confidence": 0.85, "stub": True, "note": "lenient_stub"}


# ── face_swapper (stub copy) ─────────────────────────────────────────────────


def handle_face_swapper(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Stub: copies frame PNGs into face_swapped/<scene_xx>/.
    """
    scene_id = int(inp.get("scene_id", 1))
    src = Path(inp.get("frames_dir", ""))
    if not src.is_dir():
        raise ValueError("face_swapper: frames_dir must be an existing directory")

    dst = PHASE2_FACE_SWAPPED_DIR / f"scene_{_scene_pad(scene_id)}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return {"frames_dir": str(dst), "stub": True}


# ── lip_sync_aligner (ffmpeg mux stub) ────────────────────────────────────────


def _resolve_ffmpeg_exe() -> str | None:
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


def handle_lip_sync_aligner(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Final stage: Mux audio + video or generate AI talking-head video.
    If USE_AI_ANIMATION=True, uses a public SadTalker/LivePortrait space.
    """
    import os
    from gradio_client import Client, handle_file
    
    wav = Path(inp.get("wav_path", ""))
    frames_dir = Path(inp.get("frames_dir", ""))
    scene_video = inp.get("scene_video_path", "")
    char_image = inp.get("character_image_path", "") # From phase1/agent
    scene_id = int(inp.get("scene_id", 1))
    
    out = Path(inp.get("output_mp4_path") or (PHASE2_RAW_SCENES_DIR / f"scene_{_scene_pad(scene_id)}.mp4"))
    out.parent.mkdir(parents=True, exist_ok=True)

    if not wav.is_file():
        raise ValueError("lip_sync_aligner: wav_path missing")

    # ── Path A: AI Animation (SadTalker / LivePortrait) ──
    if USE_AI_ANIMATION and LIP_SYNC_SPACE_ID:
        try:
            print(f"[Lip Sync] Calling AI Animation Space: {LIP_SYNC_SPACE_ID}")
            client = Client(LIP_SYNC_SPACE_ID)
            
            # Use the character portrait as the source
            source = char_image or str(PHASE2_FACE_SWAPPED_DIR / f"scene_{_scene_pad(scene_id)}" / "frame_000.png")
            if not Path(source).exists():
                # Fallback to any image in frames_dir
                imgs = sorted(frames_dir.glob("*.png")) + sorted(frames_dir.glob("*.jpg"))
                if imgs:
                    source = str(imgs[0])

            print(f"[Lip Sync] Animating character: {Path(source).name}")
            
            # Predict using the standard SadTalker API
            # result[0] is the video path
            res = client.predict(
                source_image=handle_file(source),
                driven_audio=handle_file(str(wav)),
                preprocess='full',
                is_still_mode=False,
                use_enhancer=False,
                batch_size=2,
                size=256,
                api_name="/predict"
            )
            
            # res is usually a tuple/list, the first item is the video temp path
            video_temp = res[0] if isinstance(res, (list, tuple)) else res
            
            if video_temp and os.path.exists(video_temp):
                shutil.copy2(video_temp, str(out))
                print(f"[Lip Sync] AI Animation complete: {out.name}")
                return {"video_path": str(out), "mode": "ai_animation", "stub": False}
        except Exception as e:
            print(f"[Lip Sync] AI Animation failed: {e}. Falling back to standard mux.")

    # ── Path B: Standard FFmpeg Muxing ──
    ff = _resolve_ffmpeg_exe()
    if not ff:
        raise RuntimeError(
            "lip_sync_aligner: no ffmpeg executable (install system ffmpeg or `pip install imageio-ffmpeg`)"
        )

    # ── Prefer real scene video (stock footage with motion) ──
    if scene_video and Path(scene_video).is_file():
        result = _ffmpeg_mux_video_audio(Path(scene_video), wav, out, ff)
        return {**result, "stub": False, "ffmpeg_exe": ff, "mode": "video_mux"}

    # ── Fallback: slideshow from frame images ──
    if not frames_dir.is_dir():
        raise ValueError("lip_sync_aligner: no scene_video_path and no frames_dir")

    frames = sorted(frames_dir.glob("*.png")) + sorted(frames_dir.glob("*.jpg"))
    if not frames:
        raise ValueError("lip_sync_aligner: no frames in frames_dir")

    concat = _ffmpeg_slideshow_from_list(frames, wav, out, ff)
    return {**concat, "stub": False, "ffmpeg_exe": ff, "mode": "slideshow"}


def _ffmpeg_mux_video_audio(video: Path, wav: Path, out: Path, ffmpeg_exe: str) -> dict[str, Any]:
    """Mux an existing video (stock footage) with audio. Trims to shorter of the two."""
    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(video),
        "-i", str(wav),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2",
        "-c:a", "aac",
        "-shortest",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=180)
    return {"video_path": str(out)}


def _ffmpeg_slideshow_from_list(frames: list[Path], wav: Path, out: Path, ffmpeg_exe: str) -> dict[str, Any]:
    """Concat demuxer slideshow + audio mux with audio-proportional frame timing."""
    # Calculate per-frame duration so video length matches audio length (zero drift)
    try:
        with wave.open(str(wav), "rb") as wf:
            audio_dur = wf.getnframes() / float(wf.getframerate() or 22050)
    except Exception:
        audio_dur = len(frames) * 0.34

    per_frame = max(0.1, audio_dur / len(frames)) if frames else 0.34

    concat_file = out.parent / f"_concat_{out.stem}.txt"
    lines = []
    for p in frames:
        lines.append(f"file '{p.as_posix()}'")
        lines.append(f"duration {per_frame:.4f}")
    lines.append(f"file '{frames[-1].as_posix()}'")
    concat_file.write_text("\n".join(lines), encoding="utf-8")
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-i", str(wav),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2",
        "-c:a", "aac",
        "-shortest",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=180)
    return {"video_path": str(out), "per_frame_sec": round(per_frame, 4)}


# ── generate_scene_video (Wan2.1 I2V via Alibaba Cloud DashScope) ─────────────────


def handle_generate_scene_video(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a video clip for one visual cue using Wan2.1 I2V via Alibaba Cloud DashScope.

    Priority order:
      1. Alibaba Cloud DashScope (ALIBABA_CLOUD_API set) → high quality Wan2.1 generation
      2. Returns stub if no API key is configured

    Takes:
      - prompt: Rich text description of the scene action
      - character_image_path: Local path to the character's reference PNG (from Phase 1)
      - scene_id / clip_index: Used to name the output file

    Returns:
      - downloaded_mp4: Absolute path to the saved video clip
      - mode: 'alibaba_wan_i2v' or 'stub'
    """
    import base64
    import requests
    import tempfile

    from shared.config.config import (
        PHASE2_STOCK_DIR, ALIBABA_CLOUD_API, ALIBABA_VIDEO_MODEL_ID
    )

    prompt = inp.get("prompt", "")
    char_image_path = inp.get("character_image_path", "")
    scene_id = int(inp.get("scene_id", 1))
    clip_index = int(inp.get("clip_index", 0))

    # Ensure clips go into scene-specific subfolders immediately
    scene_dir = PHASE2_STOCK_DIR / f"scene_{scene_id:02d}" / "full-clips"
    scene_dir.mkdir(parents=True, exist_ok=True)
    
    out_path = scene_dir / f"scene_{scene_id:02d}_clip_{clip_index:02d}.mp4"

    if not ALIBABA_CLOUD_API:
        print("[Wan2.1] ALIBABA_CLOUD_API not set — returning stub")
        return {"downloaded_mp4": None, "mode": "stub", "error": "ALIBABA_CLOUD_API not configured"}

    # ── Upload character image as base64 data URI ──
    img_url: str | None = None
    if char_image_path and Path(char_image_path).is_file():
        try:
            import cv2
            img = cv2.imread(str(char_image_path))
            if img is not None:
                # Resize to 720p-compatible dimensions for Wan2.1
                h, w = img.shape[:2]
                max_side = 720
                scale = max_side / max(h, w)
                if scale < 1:
                    img = cv2.resize(img, (int(w * scale), int(h * scale)))
                success, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if success:
                    b64 = base64.b64encode(buffer).decode("utf-8")
                    img_url = f"data:image/jpeg;base64,{b64}"
                    print(f"[Wan2.1] Character image prepared: {img.shape[1]}x{img.shape[0]}")
        except Exception as e:
            print(f"[Wan2.1] Image prep failed: {e}")

    try:
        import dashscope
        from dashscope import VideoSynthesis
        from http import HTTPStatus

        dashscope.api_key = ALIBABA_CLOUD_API
        # Use international endpoint
        dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

        print(f"[Wan2.1] Calling Alibaba Cloud DashScope: {ALIBABA_VIDEO_MODEL_ID}")

        call_kwargs: dict[str, Any] = {
            "model": ALIBABA_VIDEO_MODEL_ID,
            "prompt": prompt,
            "resolution": "720P",
        }
        if img_url:
            call_kwargs["img_url"] = img_url

        rsp = VideoSynthesis.call(**call_kwargs)

        if rsp.status_code == HTTPStatus.OK:
            video_url = rsp.output.video_url
            if not video_url:
                return {"downloaded_mp4": None, "mode": "stub", "error": "No video_url in response"}

            print(f"[Wan2.1] Downloading generated video from: {video_url[:60]}...")
            vid_resp = requests.get(video_url, timeout=120)
            vid_resp.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(vid_resp.content)
            print(f"[Wan2.1] Saved clip: {out_path.name} ({len(vid_resp.content) // 1024} KB)")
            return {"downloaded_mp4": str(out_path), "mode": "alibaba_wan_i2v"}
        else:
            err = f"{rsp.code}: {rsp.message}"
            print(f"[Wan2.1] DashScope API error: {err}")
            return {"downloaded_mp4": None, "mode": "stub", "error": err}

    except Exception as e:
        print(f"[Wan2.1] Generation failed: {e}")
        return {"downloaded_mp4": None, "mode": "stub", "error": str(e)}




PHASE2_TOOL_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "get_task_graph",
        "description": "Phase 2: return a task DAG for a single scene (parallel audio/video, then merge).",
        "input_schema": {
            "type": "object",
            "properties": {
                "scene_id": {"type": "integer", "description": "Scene index (1-based)"},
                "scene_summary": {"type": "string", "description": "Optional short summary for logging"},
            },
            "required": [],
        },
        "handler": handle_get_task_graph,
    },
    {
        "name": "voice_cloning_synthesizer",
        "description": "Phase 2: synthesize real speech for scene dialogue via edge-tts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Full dialogue text for the scene"},
                "scene_id": {"type": "integer"},
                "duration_sec": {"type": "number", "description": "Optional override duration"},
                "emotion": {"type": "string", "description": "Optional emotion hint"},
                "character_name": {"type": "string", "description": "Optional primary speaker"},
                "dialogue_entries": {
                    "type": "array",
                    "description": "Per-line dialogue [{speaker, line, emotion}] for multi-voice synthesis",
                    "items": {"type": "object"},
                },
            },
            "required": ["text", "scene_id"],
        },
        "handler": handle_voice_cloning_synthesizer,
    },
    {
        "name": "identity_validator",
        "description": "Phase 2: validate character identity before face mapping.",
        "input_schema": {
            "type": "object",
            "properties": {
                "character_name": {"type": "string"},
                "reference_image_path": {"type": "string"},
                "frame_path": {"type": "string"},
            },
            "required": ["character_name"],
        },
        "handler": handle_identity_validator,
    },
    {
        "name": "face_swapper",
        "description": "Phase 2: map character reference onto frames (stub: copy frames).",
        "input_schema": {
            "type": "object",
            "properties": {
                "scene_id": {"type": "integer"},
                "frames_dir": {"type": "string", "description": "Directory of source frames"},
                "reference_image_path": {"type": "string", "description": "Character reference image"},
            },
            "required": ["scene_id", "frames_dir"],
        },
        "handler": handle_face_swapper,
    },
    {
        "name": "lip_sync_aligner",
        "description": "Phase 2: align audio and video into final MP4. Uses scene video if available, otherwise builds slideshow from frames.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scene_id": {"type": "integer"},
                "wav_path": {"type": "string"},
                "frames_dir": {"type": "string"},
                "scene_video_path": {"type": "string", "description": "Path to scene video (stock footage). Preferred over frames."},
                "output_mp4_path": {"type": "string"},
            },
            "required": ["scene_id", "wav_path"],
        },
        "handler": handle_lip_sync_aligner,
    },
    {
        "name": "generate_scene_video",
        "description": "Generate a video clip from a character image + text prompt using Wan2.2-I2V via HuggingFace Inference API.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Rich scene description to generate video for"},
                "character_image_path": {"type": "string", "description": "Local path to character portrait PNG"},
                "scene_id": {"type": "integer"},
                "clip_index": {"type": "integer", "description": "Clip index within the scene (0-based)"},
            },
            "required": ["prompt", "scene_id"],
        },
        "handler": handle_generate_scene_video,
    },
]


__all__ = [
    "PHASE2_TOOL_REGISTRY",
    "handle_get_task_graph",
    "handle_voice_cloning_synthesizer",
    "handle_identity_validator",
    "handle_face_swapper",
    "handle_lip_sync_aligner",
    "handle_generate_scene_video",
]
