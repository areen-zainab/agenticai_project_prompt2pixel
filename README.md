# PROJECT MONTAGE

**Student:** Hafsa Imtiaz · 22i-0959  
**Section:** A  
**Course:** Agentic AI CS-4015 · FAST NUCES  
**Phase 1 Due:** 9th April 2026

---

## What is PROJECT MONTAGE?

PROJECT MONTAGE is an end-to-end **multi-agent multimedia pipeline**. A story prompt or script flows through **Phase 1 (Writer’s Room)** to produce a structured **scene manifest**, **character database**, and **portrait images**. **Phase 2 (Studio Floor)** turns those artifacts into **per-scene video and audio** using **LangGraph**, **parallel branches** (`Send()`), and an **MCP tool server** so agents discover and invoke tools at runtime.

You can run phases **from the command line**, or use the **FastAPI backend** (`main.py`) with the **React (Vite)** frontend for a guided UI.

---

## Repository layout (overview)

```
AgenticAI-Project/
├── main.py                    # FastAPI backend (REST API for Phase 1 / Phase 2 / pipeline)
├── backend/                   # Orchestrator + Pydantic models for the API
├── frontend/                  # React + Vite UI
├── phase1_writers_room/         # Phase 1 — LangGraph, Streamlit optional, run_phase1.py
├── phase2_studio_floor/        # Phase 2 — graph, agents, run_phase2
├── shared/                    # Config, LLM client, MCP server, ChromaDB memory
├── outputs/                   # Phase 1 runtime outputs (manifest, character_db, image_assets)
├── outputs_phase2/            # Phase 2 runtime outputs (video, audio, frames, logs)
├── requirements.txt
```

Detailed Phase 1 docs: [`phase1_writers_room/README.md`](phase1_writers_room/README.md).  
Detailed Phase 2 docs: [`phase2_studio_floor/README.md`](phase2_studio_floor/README.md).

---

## Prerequisites

- **Python 3.11+**
- **Node.js** (for the React frontend)
- **FFmpeg** on `PATH` (required for Phase 2 audio/video muxing and many media paths)
- API keys as needed: **Groq** (default LLM), optional **Gemini**, **Hugging Face**, **Pexels**, **Alibaba DashScope**, etc. (see `.env` below)

---

## Install

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

---

## Environment (`.env` in project root)

Create a `.env` file. Minimal example for Phase 1 + MCP + Groq:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...

# MCP: agents call this URL for tool discovery/invoke.
# If you run the MCP server on port 8001 (recommended when main.py uses 8000):
MCP_BASE_URL=http://localhost:8001

# Optional
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=...
# HF_TOKEN=hf_...
# PEXELS_API_KEY=...
# USE_VIDEO_MODEL=false
# USE_AI_ANIMATION=true
```

See [`shared/config/config.py`](shared/config/config.py) for all variables.

---

## Running the full stack (backend + frontend)

The **React app** talks to **`main.py`** at **`http://localhost:8000`**. The **MCP server** is a **separate** FastAPI app. **Do not bind MCP and `main.py` to the same port.**

1. **Terminal 1 — MCP tool server** (example port **8001**):

   ```bash
   uvicorn shared.mcp_server.server:app --host 127.0.0.1 --port 8001
   ```

   Set `MCP_BASE_URL=http://localhost:8001` in `.env`.

2. **Terminal 2 — Central backend**:

   ```bash
   python main.py
   ```

   Open **`http://localhost:8000/docs`** for interactive API docs.

3. **Terminal 3 — Frontend**:

   ```bash
   cd frontend
   npm run dev
   ```

   Open **`http://localhost:5173`**. Run Phase 1 from the UI, then Phase 2 when outputs exist.

---

## Running Phase 1 only (CLI, no UI)

Requires **MCP** running (same port note: use `MCP_BASE_URL` if MCP is not on 8000).

```bash
uvicorn shared.mcp_server.server:app --host 127.0.0.1 --port 8001
```

```bash
# Interactive prompt if you omit --prompt
python phase1_writers_room/run_phase1.py --prompt "A noir detective story set on Mars"
```

Optional: **Streamlit** GUI for Phase 1:

```bash
streamlit run phase1_writers_room/main.py
```

---

## Running Phase 2 only (CLI)

Requires Phase 1 outputs under `outputs/` and **MCP** running.

From the **repository root**:

```bash
python -m phase2_studio_floor.run_phase2
```

Optional: `python -m phase2_studio_floor.run_phase2 --scene-id 1`

See [`phase2_studio_floor/README.md`](phase2_studio_floor/README.md) for flags, `.env` knobs (`USE_VIDEO_MODEL`, `PEXELS_API_KEY`, etc.), and output paths under `outputs_phase2/`.

---

## Phase 1 pipeline (conceptual)

```
User input (prompt or script)
        │
        ▼
 mode_selector  ──── auto ────▶  scriptwriter  ──┐
        │                                         │
        └──── manual ──▶  validator  ─────────────┤
                              │ (fail → END)       │
                              └────────────────────┤
                                                   ▼
                                                 hitl
                                                   │
                                                   ▼
                                               character
                                                   │
                                                   ▼
                                                 image
                                                   │
                                                   ▼
                                           memory_commit
                                                   │
                                                   ▼
                                            outputs/
```

---

## Main outputs

| Location | Contents |
|----------|----------|
| `outputs/scene_manifest.json` | Structured screenplay |
| `outputs/character_db.json` | Character profiles |
| `outputs/image_assets/*.png` | Character portraits |
| `outputs_phase2/raw_scenes/scene_XX.mp4` | Phase 2 scene videos |
| `outputs_phase2/task_graph_logs/` | Task graph / tool evidence |

---

## Technology stack (summary)

| Concern | Technology |
|---------|------------|
| Orchestration | **LangGraph** `StateGraph`, `Send()` for Phase 2 parallelism |
| LLM (Phase 1) | **Groq** / **Gemini** via MCP and `shared/llm_client.py` |
| Tools | **MCP** server: `GET /tools`, `POST /invoke` |
| Memory | **ChromaDB** (`commit_memory`) |
| API UI | **FastAPI** (`main.py`) + **React** (`frontend/`) |
| Phase 1 optional UI | **Streamlit** |

---

## Configuration reference (selected)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq` or `gemini` |
| `GROQ_API_KEY` | — | Required for Groq |
| `MCP_BASE_URL` | `http://localhost:8000` | **Set to match** the MCP server port |
| `IMAGE_BACKEND` | `stub` | Image generation backend for Phase 1 portraits |
| `PEXELS_API_KEY` | — | Phase 2 stock footage (when not using cloud I2V) |
| `CHROMA_COLLECTION` | `montage_memory` | ChromaDB collection name |

---

## Documentation

- **Phase 1:** [`phase1_writers_room/README.md`](phase1_writers_room/README.md)  
- **Phase 2:** [`phase2_studio_floor/README.md`](phase2_studio_floor/README.md)  
- **Backend API:** [`backend/BACKEND_README.md`](backend/BACKEND_README.md)  
- **Frontend:** [`frontend/README.md`](frontend/README.md)

---

## Academic notice

This repository was created as part of an **academic course project** for **Agentic AI (CS-4015)** at **FAST NUCES**. It is intended for educational evaluation and demonstration purposes.
