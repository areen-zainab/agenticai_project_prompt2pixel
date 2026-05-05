# Phase 2: Studio Floor — AI Video Pipeline

The Studio Floor consumes **Phase 1** outputs (`scene_manifest.json`, `character_db.json`, character portraits) and produces per-scene **video, audio, frames, and logs** under **`outputs_phase2/`**. Orchestration uses **LangGraph** with **`Send()`** so voice synthesis and video generation run **in parallel**, then converge through face swap and lip sync.

---

## Pipeline Architecture

```
SCENE MANIFEST (from Phase 1)
  scene_id, location, characters, dialogue[], visual_cues, emotions
         │
         ▼
  ┌─────────────────┐
  │  SCENE PARSER   │  ── get_task_graph MCP
  └────────┬────────┘
           │ LangGraph Send() — PARALLEL BRANCH
     ──────┴──────
    ╱              ╲
   ▼                ▼
┌──────────────┐  ┌───────────────┐
│ VIDEO GEN    │  │ VOICE SYNTH   │
│              │  │ edge-tts TTS  │
│ Mode A: AI   │  │ Per character │
│  Alibaba     │  │ Per emotion   │
│  DashScope   │  │               │
│  Wan2.1 I2V  │  │ Output: WAV   │
│              │  │               │
│ Mode B: Stock│  └───────┬───────┘
│  Pexels  +   │          │
│  Gender      │          │
│  Aware Query │          │
│              │          │
│  Output: MP4 │          │
└──────┬───────┘          │
       │                  │
       ▼                  │
┌──────────────┐          │
│  FACE SWAP   │          │
│  (stub)      │          │
└──────┬───────┘          │
       │                  │
       ▼                  ▼
┌──────────────────────────────┐
│         LIP SYNC             │
│                              │
│  Mode A: AI Animation        │
│   SadTalker / LivePortrait   │
│   via HuggingFace Space      │
│   (USE_AI_ANIMATION=true)    │
│                              │
│  Mode B: FFmpeg Audio Mux    │
│   Zero-drift alignment only  │
└──────────────┬───────────────┘
               │
               ▼
      ┌────────────────┐
      │ MEMORY COMMIT  │
      │  ChromaDB      │
      └────────┬───────┘
               │
               ▼
   outputs_phase2/raw_scenes/scene_XX.mp4
```

---

## Prerequisites

- **Python 3.11+** (match `requirements.txt`)
- **FFmpeg** on `PATH` (audio conversion, muxing, stock pipeline)
- **Phase 1 completed** so `outputs/scene_manifest.json`, `outputs/character_db.json`, and `outputs/image_assets/` exist
- **MCP server running** with Phase 2 tools registered (agents call tools over HTTP—see below)

---

## How to run Phase 2 (CLI)

From the **repository root** (recommended):

```bash
pip install -r requirements.txt
# Terminal 1 — MCP tool server (pick a port; see “MCP vs backend port” below)
uvicorn shared.mcp_server.server:app --host 127.0.0.1 --port 8001

# Optional: if MCP is not on 8000, set in .env:
# MCP_BASE_URL=http://localhost:8001

# Terminal 2 — Phase 2 pipeline
python -m phase2_studio_floor.run_phase2
```

Useful flags:

| Flag | Meaning |
|------|---------|
| `--scene-id N` | Process only scene `N` (matches `scene_id` in the manifest) |
| `--manifest PATH` | Override path to `scene_manifest.json` |
| `--characters PATH` | Override path to `character_db.json` |

Alternative: from inside `phase2_studio_floor/`, run `python run_phase2.py` (same code; ensure repo root is on `PYTHONPATH`—the package layout assumes running as `-m` from root or from this folder per the script’s `sys.path` setup).

---

## How to run via the central API + React UI

If you use the **FastAPI** app at the repo root and the **Vite** frontend:

1. Start **MCP** on a port that does **not** collide with the API (for example **8001**) and set **`MCP_BASE_URL`** accordingly in `.env`.
2. Start the backend: `python main.py` (default API: `http://localhost:8000`).
3. Start the frontend: `cd frontend && npm install && npm run dev` (default: `http://localhost:5173`).
4. Run Phase 1 from the UI or API, then trigger Phase 2 from the Phase 2 page or `POST /api/phase2/run`.

API documentation: `http://localhost:8000/docs`.

---

## MCP vs backend port

Both the **MCP server** (`shared/mcp_server/server.py`) and **`main.py`** use FastAPI. Default **`MCP_BASE_URL`** in `shared/config/config.py` is `http://localhost:8000`, which is the same host/port the React app uses for **`main.py`**. **Only one process can listen on a given port.**

**Typical fix:** run MCP on **8001**, add to `.env`:

```env
MCP_BASE_URL=http://localhost:8001
```

Keep **`python main.py`** on **8000** so the frontend’s API base URL stays valid.

---

## Configuration (`.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_BASE_URL` | `http://localhost:8000` | MCP HTTP base for tool discovery/invoke |
| `USE_VIDEO_MODEL` | `false` | `true`: cloud I2V path when keys set; `false`: Pexels stock pipeline |
| `ALIBABA_CLOUD_API` | — | Alibaba DashScope (when using cloud video) |
| `PEXELS_API_KEY` | — | Stock footage (when `USE_VIDEO_MODEL=false`) |
| `USE_AI_ANIMATION` | `true` | Optional HF Space talking-head path for lip sync |
| `LIP_SYNC_SPACE_ID` | *(see config)* | Hugging Face Space id for animation |
| `HF_TOKEN` | — | Hugging Face token (Phase 1 images / optional Spaces) |

See `shared/config/config.py` for the full list and defaults.

---

## Output layout

Artifacts are written under **`outputs_phase2/`** (paths defined in config), including:

- `raw_scenes/scene_XX.mp4` — final per-scene video  
- `audio/scene_XX.wav` — merged dialogue audio  
- `frames/scene_XX/` — frame sequences used by downstream steps  
- `task_graph_logs/` — JSON logs for debugging and submission evidence  

---

## Agents (summary)

| Agent | Role |
|-------|------|
| Scene parser | Builds/logs task graph via MCP; commits metadata |
| Voice synth | Dialogue → WAV via **edge-tts** (with fallback tone if TTS fails) |
| Video gen | Stock footage **or** I2V depending on env |
| Face swap | Wired; largely stub / identity passthrough |
| Lip sync | FFmpeg timeline + optional HF animation |

---

## Technologies

| Component | Stack |
|-----------|--------|
| Orchestration | LangGraph, `Send()` parallelism |
| Voice | edge-tts (Microsoft neural voices) |
| Video | Pexels + FFmpeg **or** DashScope / Wan-style I2V when configured |
| Lip sync | FFmpeg; optional Gradio HF Space |
| Memory | ChromaDB via MCP `commit_memory` |
