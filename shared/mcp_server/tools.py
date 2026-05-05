"""
mcp_server/tools.py
────────────────────────────────────────────────────────────────────────────
All MCP tool schemas and their handler implementations.

Each tool is registered in TOOL_REGISTRY as:
  {
    "name":        unique string id,
    "description": human-readable description,
    "input_schema": JSON-schema dict for the input payload,
    "handler":     callable(input_dict) -> dict
  }

Agents NEVER call LLM / image APIs directly — they go through MCP invoke.
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from shared.mcp_server.phase2_handlers import PHASE2_TOOL_REGISTRY

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

def _get_chroma_collection():
    import chromadb
    from shared.config.config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return client.get_or_create_collection(CHROMA_COLLECTION)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1: generate_script_segment
# ─────────────────────────────────────────────────────────────────────────────

_SCRIPT_SYSTEM_PROMPT = """You are a professional screenplay writer.
Given a story idea, generate a structured screenplay with the requested number of scenes.

Your output MUST be valid JSON matching this schema exactly:
{
  "scenes": [
    {
      "scene_id": 1,
      "location": "INT. SPACESHIP - DAY",
      "characters": ["ALEX", "MARIA"],
      "dialogue": [
        {
          "speaker": "ALEX",
          "line": "We need to move fast.",
          "visual_cue": "Alex glances nervously at the radar screen."
        }
      ]
    }
  ]
}

Rules:
- scene_id starts at 1 and is sequential
- location uses standard screenplay format (INT./EXT. PLACE - TIME)
- characters lists all characters appearing in the scene
- Each dialogue entry has speaker, line, and visual_cue
- Every scene must have at least 2 dialogue lines
- Return ONLY the JSON object, no markdown fences, no extra text
"""


def handle_generate_script_segment(inp: dict) -> dict:
    from shared.llm_client import chat_json

    prompt = inp.get("prompt", "")
    num_scenes = int(inp.get("num_scenes", 3))

    user_msg = f"Story idea: {prompt}\n\nGenerate exactly {num_scenes} scenes."
    script = chat_json(
        system=_SCRIPT_SYSTEM_PROMPT,
        user=user_msg,
        temperature=0.8,
    )
    return script   # {"scenes": [...]}

def handle_generate_character_profile(inp: dict) -> dict:
    """
    Generate a Character profile JSON from name + scene context.
    This is exposed as an MCP tool so agents don't call the LLM directly.
    """
    from shared.llm_client import chat_json

    name = inp.get("name", "").strip()
    scenes_context = inp.get("scenes_context", "")
    if not name:
        raise ValueError("Missing required field: name")

    system = """You are a character designer for a film production.
Given a character's name and the scenes they appear in, create a detailed character profile.

Output ONLY valid JSON matching this schema exactly:
{
  "name": "CHARACTER NAME",
  "personality_traits": ["trait1", "trait2", "trait3"],
  "appearance_description": "Detailed visual description... Include age, hair, eyes, clothing style, and a key distinguishing physical feature.",
  "reference_style": "e.g., neo-noir cyberpunk, 1920s Hollywood glamour"
}

Rules:
- personality_traits: list of 3–5 concise adjectives
- appearance_description: 3-4 sentences. Focus on consistent physical traits that define the character's 'identity' visually.
- reference_style: a short artistic style reference
- Return ONLY the JSON object, no markdown fences."""

    user = f"Character name: {name}\n\nScene context:\n{scenes_context}"
    return chat_json(system=system, user=user, temperature=0.7)


def handle_suggest_script_corrections(inp: dict) -> dict:
    """
    Provide concise, actionable corrections for a malformed screenplay.
    Exposed as an MCP tool so validator doesn't call the LLM directly.
    """
    from shared.llm_client import chat_text

    raw_script = inp.get("raw_script", "")
    detected_errors = inp.get("detected_errors", [])
    if not raw_script.strip():
        return {"suggestions": "Script is empty. Add scene headings and dialogue blocks."}

    system = (
        "You are a script format expert. A user uploaded a screenplay that failed basic structural checks. "
        "Provide a CONCISE list of specific corrections needed to make it standard Hollywood format "
        "(INT./EXT. headings, character names on their own line, dialogue below names, action lines). "
        "Output plain text only, no markdown headings."
    )
    user = (
        "Failed script content:\n\n"
        f"{raw_script}\n\n"
        "Errors detected by regex:\n"
        + "\n".join(str(e) for e in detected_errors)
    )
    suggestions = chat_text(system=system, user=user, temperature=0.2)
    return {"suggestions": suggestions}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2: commit_memory
# ─────────────────────────────────────────────────────────────────────────────

def handle_commit_memory(inp: dict) -> dict:
    text     = inp.get("text", "")
    metadata = inp.get("metadata", {})
    doc_id   = inp.get("doc_id") or str(uuid.uuid4())

    collection = _get_chroma_collection()
    collection.upsert(
        ids=[doc_id],
        documents=[text],
        metadatas=[metadata],
    )
    return {"status": "committed", "doc_id": doc_id}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3: query_stock_footage
# ─────────────────────────────────────────────────────────────────────────────

def handle_query_stock_footage(inp: dict) -> dict:
    """
    Search Pexels for stock video matching a description.
    When scene_id is provided, downloads the first result as an MP4 clip.
    clip_index differentiates multiple clips per scene (one per visual cue).
    """
    import requests
    description = inp.get("description", "")
    scene_id    = inp.get("scene_id")
    clip_index  = inp.get("clip_index", 0)  # which clip for this scene
    api_key     = os.getenv("PEXELS_API_KEY", "")

    if not api_key:
        print("[Pexels] No API key found. Returning mock results.")
        return {
            "results": [
                {"path": f"stock/footage_{i+1}.mp4", "relevance": round(0.9 - i * 0.1, 1)}
                for i in range(3)
            ],
            "query": description,
        }

    try:
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": api_key}
        params = {"query": description, "per_page": 5, "orientation": "landscape"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        results = []
        for video in data.get("videos", []):
            # Pick medium-quality file (not the tiniest, not the biggest)
            files = sorted(
                video.get("video_files", []),
                key=lambda x: (x.get("width") or 0) * (x.get("height") or 0),
            )
            # Pick the middle option for decent quality without huge downloads
            pick = files[len(files) // 2] if len(files) > 2 else (files[0] if files else None)
            if pick:
                results.append({
                    "id":    video["id"],
                    "url":   video["url"],
                    "path":  pick["link"],
                    "width": pick.get("width"),
                    "height": pick.get("height"),
                    "image": video.get("image"),
                })

        downloaded_mp4 = None

        # Download first matching video when scene_id is provided
        if results and scene_id is not None:
            from shared.config.config import PHASE2_STOCK_DIR
            scene_id = int(scene_id)
            clip_index = int(clip_index)

            # Ensure clips go into scene-specific subfolders immediately
            scene_dir = PHASE2_STOCK_DIR / f"scene_{scene_id:02d}" / "full-clips"
            scene_dir.mkdir(parents=True, exist_ok=True)
            
            download_url = results[0]["path"]
            mp4_path = scene_dir / f"scene_{scene_id:02d}_clip_{clip_index:02d}.mp4"

            try:
                print(f"[Pexels] Downloading clip {clip_index} for scene {scene_id}: '{description}'")
                vid_resp = requests.get(download_url, timeout=60, stream=True)
                vid_resp.raise_for_status()
                with open(mp4_path, "wb") as f:
                    for chunk in vid_resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded_mp4 = str(mp4_path)
                print(f"[Pexels] Downloaded: {mp4_path} ({mp4_path.stat().st_size // 1024} KB)")
            except Exception as e:
                print(f"[Pexels] Download failed: {e}")

        return {
            "results": results,
            "query": description,
            "downloaded_mp4": downloaded_mp4,
        }
    except Exception as e:
        print(f"[Pexels] Search failed: {e}")
        return {"results": [], "query": description, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4: generate_character_image
# ─────────────────────────────────────────────────────────────────────────────

_CHARACTER_SYSTEM_PROMPT = """You are a character concept artist.
Given a character description, produce a detailed visual prompt for Stable Diffusion.
Output ONLY the prompt string — no extra text, no quotes."""


def handle_generate_character_image(inp: dict) -> dict:
    """
    Generates a character image. Falls back gracefully through:
      stable_diffusion → huggingface → stub
    """
    from shared.config.config import IMAGE_BACKEND, IMAGE_ASSETS_DIR, SD_API_URL

    description  = inp.get("description", "a character")
    character_name = inp.get("character_name", "character")
    safe_name    = "".join(c if c.isalnum() else "_" for c in character_name)
    output_path  = IMAGE_ASSETS_DIR / f"{safe_name}.png"

    # ── Build a detailed SD prompt via LLM ───────────────────────────────────
    try:
        from shared.llm_client import chat_text

        sd_prompt = chat_text(
            system=_CHARACTER_SYSTEM_PROMPT,
            user=description,
            temperature=0.7,
        )
    except Exception:
        sd_prompt = f"concept art portrait of {description}, detailed, cinematic lighting"

    # ── Try image backends ────────────────────────────────────────────────────
    if IMAGE_BACKEND == "stable_diffusion":
        image_data = _call_stable_diffusion(sd_prompt, SD_API_URL)
        if image_data:
            _save_image_bytes(image_data, output_path)
            return {"image_path": str(output_path), "sd_prompt": sd_prompt}

    # Preferred free fallback: Hugging Face
    hf_token = os.getenv("HF_TOKEN", "")
    if hf_token:
        image_data = _call_huggingface(sd_prompt, hf_token)
        if image_data:
            _save_image_bytes(image_data, output_path)
            return {"image_path": str(output_path), "sd_prompt": sd_prompt, "backend": "huggingface"}

    # ── Stub fallback: create a labelled placeholder PNG ─────────────────────
    _create_stub_image(character_name, output_path)
    return {"image_path": str(output_path), "sd_prompt": sd_prompt, "stub": True}


def _call_stable_diffusion(prompt: str, api_url: str) -> bytes | None:
    try:
        import httpx
        payload = {
            "prompt": prompt,
            "negative_prompt": "blurry, low quality, deformed",
            "steps": 20,
            "width": 512,
            "height": 512,
        }
        r = httpx.post(f"{api_url}/sdapi/v1/txt2img", json=payload, timeout=60)
        r.raise_for_status()
        import base64
        return base64.b64decode(r.json()["images"][0])
    except Exception as e:
        print(f"[SD] Failed: {e}")
        return None


def _call_huggingface(prompt: str, token: str) -> bytes | None:
    try:
        from huggingface_hub import InferenceClient
        import io
        client = InferenceClient(token=token)
        # Using a reliable SDXL model
        image_data = client.text_to_image(
            prompt,
            model="stabilityai/stable-diffusion-xl-base-1.0",
        )
        # Converse to bytes if it's a PIL Image (older versions of huggingface_hub)
        if not isinstance(image_data, bytes):
            buf = io.BytesIO()
            image_data.save(buf, format="PNG")
            return buf.getvalue()
        return image_data
    except Exception as e:
        print(f"[Hugging Face] Failed: {e}")
        return None


def _save_image_bytes(data: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _create_stub_image(character_name: str, path: Path) -> None:
    """Creates a simple labelled placeholder PNG using Pillow."""
    from PIL import Image, ImageDraw, ImageFont
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (512, 512), color=(30, 30, 50))
    draw = ImageDraw.Draw(img)
    # Draw border
    draw.rectangle([10, 10, 501, 501], outline=(100, 100, 180), width=3)
    # Draw label
    text = f"[{character_name}]"
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((512 - w) // 2, (512 - h) // 2), text, fill=(200, 200, 255), font=font)
    draw.text(((512 - 200) // 2, 300), "stub image", fill=(120, 120, 120),
              font=ImageFont.load_default())
    img.save(path, "PNG")


# ─────────────────────────────────────────────────────────────────────────────
# Tool Registry
# ─────────────────────────────────────────────────────────────────────────────

TOOL_REGISTRY: list[dict] = [
    {
        "name": "generate_script_segment",
        "description": "Generate a structured multi-scene screenplay JSON from a story prompt.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt":     {"type": "string",  "description": "Story idea or premise"},
                "num_scenes": {"type": "integer", "description": "Number of scenes to generate", "default": 3},
            },
            "required": ["prompt"],
        },
        "handler": handle_generate_script_segment,
    },
    {
        "name": "generate_character_profile",
        "description": "Generate a structured character profile JSON from name + scene context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Character name"},
                "scenes_context": {"type": "string", "description": "Relevant scene context / lines"},
            },
            "required": ["name"],
        },
        "handler": handle_generate_character_profile,
    },
    {
        "name": "suggest_script_corrections",
        "description": "Suggest corrections for a malformed screenplay based on detected structural errors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_script": {"type": "string", "description": "Uploaded screenplay raw text"},
                "detected_errors": {"type": "array", "items": {"type": "string"}, "description": "List of structural errors detected"},
            },
            "required": ["raw_script"],
        },
        "handler": handle_suggest_script_corrections,
    },
    {
        "name": "commit_memory",
        "description": "Store a text document in the ChromaDB vector memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text":     {"type": "string", "description": "Text to store"},
                "metadata": {"type": "object", "description": "Optional metadata dict"},
                "doc_id":   {"type": "string", "description": "Optional unique ID; auto-generated if omitted"},
            },
            "required": ["text"],
        },
        "handler": handle_commit_memory,
    },
    {
        "name": "query_stock_footage",
        "description": "Search and download stock footage by description. Downloads one clip per call; use clip_index for multiple clips per scene.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Scene or visual description to search"},
                "scene_id": {"type": "integer", "description": "Scene ID — triggers video download"},
                "clip_index": {"type": "integer", "description": "Clip number within the scene (0-based, for per-visual-cue downloads)"},
            },
            "required": ["description"],
        },
        "handler": handle_query_stock_footage,
    },
    {
        "name": "generate_character_image",
        "description": "Generate a character reference image from an appearance description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description":    {"type": "string", "description": "Character appearance description"},
                "character_name": {"type": "string", "description": "Character's name (used for filename)"},
            },
            "required": ["description", "character_name"],
        },
        "handler": handle_generate_character_image,
    },
]

# Phase 2 tools (append — does not alter Phase 1 tool definitions above)
TOOL_REGISTRY.extend(PHASE2_TOOL_REGISTRY)

# Lookup map for O(1) dispatch
TOOL_MAP: dict[str, dict] = {t["name"]: t for t in TOOL_REGISTRY}
