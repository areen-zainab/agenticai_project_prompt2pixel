# Phase 1 — The Writer's Room

**Course:** Agentic AI CS-4015 · FAST NUCES  
**Project:** PROJECT MONTAGE  
**Due:** 9th April 2026

---

## Overview

Phase 1 implements the **autonomous story and image generation layer** of PROJECT MONTAGE. It accepts either a raw story idea (auto mode) or an uploaded screenplay (manual mode) and transforms it into three structured deliverables through a multi-agent pipeline.

**Deliverables produced:**

| File | Description |
|------|-------------|
| `outputs/scene_manifest.json` | Structured screenplay: scenes, dialogue, visual cues |
| `outputs/character_db.json` | Character identity store: name, traits, appearance, style |
| `outputs/image_assets/<name>.png` | AI-generated character reference images |

---

## Architecture

### High-Level Flow

```
User Input (prompt OR .txt script)
         │
         ▼
 ┌─────────────────┐
 │  mode_selector  │  ← entry node; routes by input_mode
 └────────┬────────┘
          │
    ┌─────┴──────┐
    ▼            ▼
validator    scriptwriter   ← mutual exclusive branches
    │            │
    └─────┬──────┘
          ▼
        hitl               ← human approval checkpoint (Streamlit UI)
          │
    ┌─────┴──── (rejected → END)
    ▼
  character                ← extract + profile all characters
          │
          ▼
        image              ← generate reference images per character
          │
          ▼
  memory_commit            ← persist everything to ChromaDB
          │
          ▼
        END
```

### Technology Stack

| Concern | Technology |
|---------|-----------|
| Agent orchestration | **LangGraph** `StateGraph` |
| LLM (primary) | **Groq** — `llama-3.3-70b-versatile` (via OpenAI-compatible API) |
| LLM (alternative) | **Google Gemini** — `gemini-1.5-flash` |
| Tool discovery / invocation | **MCP** — custom FastAPI server (`shared/mcp_server/`) |
| Vector memory | **ChromaDB** (persistent, cosine similarity) |
| Image generation | Stable Diffusion (local) → Hugging Face `stabilityai/stable-diffusion-xl-base-1.0` → Pillow stub fallback |
| Frontend | **Streamlit** |
| MCP HTTP client | **httpx** |
| Config | `python-dotenv` + `shared/config/config.py` |

---

## LangGraph Workflow

**File:** `phase1_writers_room/graph/workflow.py`

The workflow is a compiled `StateGraph[AgentState]` with **7 nodes** and **3 conditional edge routers**.

### Nodes

| Node | Function | Description |
|------|----------|-------------|
| `mode_selector` | `mode_selector_node` | Pure router; reads `input_mode` from state and branches accordingly |
| `validator` | `validator_node` | Validates a manually uploaded plain-text screenplay |
| `scriptwriter` | `scriptwriter_node` | Generates a structured screenplay from a user prompt via MCP |
| `hitl` | `hitl_node` | Human-in-the-loop approval checkpoint |
| `character` | `character_node` | Extracts characters and builds full identity profiles via MCP |
| `image` | `image_node` | Generates character reference images via MCP |
| `memory_commit` | `memory_commit_node` | Commits all outputs to ChromaDB vector memory via MCP |

### Conditional Routers

| Router | Source → Destinations |
|--------|-----------------------|
| `route_by_mode` | `mode_selector` → `validator` \| `scriptwriter` \| `hitl`* |
| `route_after_validator` | `validator` → `hitl` \| `END` |
| `route_by_hitl` | `hitl` → `character` \| `END` |

> \* The `hitl` shortcut from `mode_selector` handles Streamlit re-invocations after user approval — prevents re-running the generation/validation step.

### Shared State Schema

**File:** `phase1_writers_room/graph/state.py`

```python
class AgentState(TypedDict):
    input_mode:    Literal["auto", "manual"]
    raw_prompt:    Optional[str]       # auto mode
    raw_script:    Optional[str]       # manual mode
    gui_mode:      bool                # True = HITL via Streamlit, not stdin
    script:        Optional[Script]    # {scenes: [SceneDict, ...]}
    characters:    list[Character]     # [{name, traits, appearance, style, image_path}]
    images:        list[str]           # absolute file paths
    status:        Literal["pending", "validating", "generating_script",
                           "awaiting_hitl", "approved", "rejected",
                           "designing_characters", "generating_images",
                           "committing_memory", "complete", "error"]
    hitl_approved: Optional[bool]
    error:         Optional[str]
    events:        list[Event]         # UI-visible activity log
```

---

## MCP Server

**File:** `shared/mcp_server/server.py`  
**Start:** `python -m shared.mcp_server` (or `uvicorn shared.mcp_server.server:app --port 8000`)

The MCP server is a **FastAPI application** that exposes a tool registry. Agents **never call LLM APIs directly** — all LLM and image generation calls are routed through the MCP server.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check; returns tool count |
| `GET` | `/tools` | Returns all registered tool schemas (no handlers exposed) |
| `POST` | `/invoke` | Dispatches a tool call: `{"tool": "...", "input": {...}}` |

### MCP Client

**File:** `shared/mcp_server/client.py`

Agents use two functions:
- `discover_tool(name)` — `GET /tools`, returns the matching schema or `None`
- `invoke_tool(name, input, timeout)` — `POST /invoke`, returns the `output` dict

Both calls happen at **runtime** — no tool names or schemas are hardcoded in agent code.

### Registered MCP Tools

| Tool | Handler | Used By |
|------|---------|---------|
| `generate_script_segment` | `handle_generate_script_segment` | Scriptwriter |
| `generate_character_profile` | `handle_generate_character_profile` | Character Designer |
| `suggest_script_corrections` | `handle_suggest_script_corrections` | Validator (on failure) |
| `commit_memory` | `handle_commit_memory` | Character Designer, Memory Commit node |
| `query_stock_footage` | `handle_query_stock_footage` | Character Designer (downstream compatibility) |
| `generate_character_image` | `handle_generate_character_image` | Image Synthesizer |

#### Tool Details

**`generate_script_segment`**
```
Input:  { prompt: string, num_scenes: int = 3 }
Output: { scenes: [{ scene_id, location, characters[], dialogue[{speaker, line, visual_cue}] }] }
LLM:    chat_json(), temperature=0.8
```

**`generate_character_profile`**
```
Input:  { name: string, scenes_context: string }
Output: { name, personality_traits[], appearance_description, reference_style }
LLM:    chat_json(), temperature=0.7
```

**`suggest_script_corrections`**
```
Input:  { raw_script: string, detected_errors: string[] }
Output: { suggestions: string }
LLM:    chat_text(), temperature=0.2
```

**`commit_memory`**
```
Input:  { text: string, metadata: object, doc_id?: string }
Output: { status: "committed", doc_id: string }
Store:  ChromaDB PersistentClient — upserts into collection "montage_memory"
```

**`query_stock_footage`**
```
Input:  { description: string }
Output: { results: [{id, url, path, image}], query: string }
API:    Pexels Videos API (falls back to mock results if PEXELS_API_KEY absent)
```

**`generate_character_image`**
```
Input:  { description: string, character_name: string }
Output: { image_path: string, sd_prompt: string, stub?: bool }
Flow:   LLM → SD prompt → stable_diffusion | huggingface | stub
```

---

## Agents

### 1. Scriptwriter Agent
**File:** `phase1_writers_room/agents/scriptwriter.py`  
**Mode:** Auto only  
**Activated by:** `scriptwriter_node`

**Reasoning loop:**
1. Calls `discover_tool("generate_script_segment")` to verify tool availability
2. Invokes `generate_script_segment` with the user's prompt and `DEFAULT_NUM_SCENES`
3. Validates the returned JSON structure (`scenes` key must be a list)
4. Writes the result to `outputs/scene_manifest.json`
5. Emits events to the UI activity log at each step

**MCP Tools used:** `generate_script_segment`

---

### 2. Script Validator Agent
**File:** `phase1_writers_room/agents/validator.py`  
**Mode:** Manual only  
**Activated by:** `validator_node`

**Reasoning loop:**
1. Runs three regex-based structural checks:
   - **Scene headings** — must match `INT.`, `EXT.`, `INT/EXT.`, or `SCENE N`
   - **Dialogue labels** — character names must appear on their own line before dialogue
   - **Action lines** — each scene must contain at least one non-dialogue, non-heading line
2. On failure: calls `suggest_script_corrections` via MCP to get LLM-generated correction guidance
3. On success: parses the plain-text script into a `Script` TypedDict using a regex-based parser
4. Writes the standardised JSON to `outputs/scene_manifest.json` (parity with auto mode)

**MCP Tools used:** `suggest_script_corrections` (on validation failure)

---

### 3. Human-in-the-Loop (HITL) Agent
**File:** `phase1_writers_room/agents/hitl.py`  
**Activated by:** `hitl_node`

**Reasoning loop:**
1. If `gui_mode=True` (Streamlit): sets `status="awaiting_hitl"` and returns immediately — the Streamlit UI renders the script and Approve / Reject buttons
2. If `gui_mode=False` (CLI): reads from `stdin` in a loop until `y` or `n`
3. If the incoming state already has `hitl_approved` set (Streamlit re-invocation after button click): skips the wait and routes directly to `approved` or `rejected`

The `gui_mode` field is a first-class member of `AgentState` (not a side-channel), ensuring it survives serialisation through LangGraph's state machine.

---

### 4. Character Designer Agent
**File:** `phase1_writers_room/agents/character_designer.py`  
**Activated by:** `character_node`

**Reasoning loop:**
1. Extracts all unique character names from `script["scenes"]` — scans both `dialogue[].speaker` and `scene["characters"]` fields
2. For each character, assembles a `scenes_context` string (their lines + visual cues + locations)
3. Calls `generate_character_profile` via MCP to produce: name, personality traits (3–5), appearance description (3–4 sentences), reference style
4. Falls back to a minimal stub profile if the MCP call fails
5. Commits each profile to ChromaDB via `commit_memory` (MCP)
6. Writes `outputs/character_db.json`

**MCP Tools used:** `generate_character_profile`, `commit_memory`

---

### 5. Image Synthesizer Agent
**File:** `phase1_writers_room/agents/image_synthesizer.py`  
**Activated by:** `image_node`

**Reasoning loop:**
1. Verifies `generate_character_image` is registered by calling `discover_tool`
2. For each character: builds a description string = `appearance_description` + ` Style: ` + `reference_style`
3. Calls `generate_character_image` via MCP (120 s timeout)
4. Updates `character["image_path"]` and appends to `state["images"]`

**Image generation cascade (inside the MCP tool):**
| Priority | Backend | Condition |
|----------|---------|-----------|
| 1 | Stable Diffusion (local) | `IMAGE_BACKEND=stable_diffusion` and SD server reachable at `SD_API_URL` |
| 2 | Hugging Face Inference API | `HF_TOKEN` env var set; model: `stabilityai/stable-diffusion-xl-base-1.0` |
| 3 | Pillow stub | Always available as final fallback |

Before calling any image API, the tool uses the LLM (`chat_text`) to convert the appearance description into an optimised Stable Diffusion prompt.

**MCP Tools used:** `generate_character_image`

---

## LLM Integration

**File:** `shared/llm_client.py`

Two providers are supported, configured via `.env`:

### Groq (default)
- **Model:** `llama-3.3-70b-versatile` (default) or any model specified by `LLM_MODEL`
- **API:** OpenAI-compatible, base URL `https://api.groq.com/openai/v1`
- **Client:** `openai.OpenAI` with `GROQ_API_KEY`
- **JSON mode:** uses `response_format={"type": "json_object"}`

### Google Gemini
- **Model:** `gemini-1.5-flash` (default) or any model specified by `LLM_MODEL`
- **Client:** `google.generativeai.GenerativeModel`
- **JSON mode:** uses `response_mime_type="application/json"` in `GenerationConfig`

### Functions exposed

| Function | Returns | Temperature |
|----------|---------|-------------|
| `chat_json(system, user, temperature)` | `dict` (parsed JSON) | 0.7–0.8 |
| `chat_text(system, user, temperature)` | `str` | 0.2–0.7 |

---

## Vector Memory (ChromaDB)

**File:** `shared/memory/vector_store.py`  
**Persist path:** `shared/memory/chroma_store/`  
**Collection:** `montage_memory` (configurable via `CHROMA_COLLECTION`)  
**Distance metric:** cosine similarity

Data committed during a pipeline run:

| When | Content | `doc_id` |
|------|---------|---------|
| Character Designer (per character) | Name + traits + appearance summary | `char_<name>` |
| Memory Commit node (final, includes image path) | Full character summary | `char_<name>_final` |
| Memory Commit node | Full `scene_manifest` JSON | `scene_manifest_latest` |

All ChromaDB writes go through the `commit_memory` **MCP tool** — not called directly from agents.

---

## Streamlit UI

**File:** `phase1_writers_room/main.py`  
**Start:** `streamlit run phase1_writers_room/main.py`

### UI States

| State | What the user sees |
|-------|--------------------|
| **Idle** | Input form (prompt textarea or file uploader) + mode selector |
| **Processing** | Disabled "⏳ Running pipeline…" button + pipeline progress strip + spinner |
| **Awaiting HITL** | Generated script rendered in full + Approve / Reject buttons |
| **Rejected** | Error banner + Start Over button |
| **Complete** | Success banner + output file chips + full screenplay + character profiles with images |
| **Error** | Error banner with message + Start Over button |

### Activity Log

All agents emit structured `Event` entries (`agent`, `level`, `message`, `ts`, `data`) into `state["events"]` instead of printing to the terminal. The Streamlit UI renders these in a collapsible **"Agent activity log"** timeline after each run.

### HITL Flow (GUI Mode)

1. Pipeline runs until `hitl_node` sets `status="awaiting_hitl"` and returns
2. Streamlit renders the draft screenplay and the two action buttons
3. On **Approve**: sets `hitl_approved=True`, `status="approved"`, `processing=True`, calls `st.rerun()`
4. On re-run: `mode_selector` detects existing script + `status="approved"` and routes directly to `hitl_node` (skipping generation), which immediately continues to `character_node`

---

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq` or `gemini` |
| `GROQ_API_KEY` | — | Required if `LLM_PROVIDER=groq` |
| `GEMINI_API_KEY` | — | Required if `LLM_PROVIDER=gemini` |
| `LLM_MODEL` | _(auto)_ | Override model name (e.g. `llama-3.1-8b-instant`) |
| `MCP_BASE_URL` | `http://localhost:8000` | MCP server base URL |
| `IMAGE_BACKEND` | `stub` | `stub` \| `stable_diffusion` \| `huggingface` |
| `SD_API_URL` | `http://127.0.0.1:7860` | Local Stable Diffusion API URL |
| `HF_TOKEN` | — | Hugging Face token (enables SDXL inference) |
| `PEXELS_API_KEY` | — | Pexels API key for stock footage tool |
| `DEFAULT_NUM_SCENES` | `3` | Number of scenes generated in auto mode |
| `CHROMA_COLLECTION` | `montage_memory` | ChromaDB collection name |

---

## Running Phase 1

### Prerequisites

```
Python 3.11+
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure environment

```bash
# Create .env in the project root
GROQ_API_KEY=gsk_...
LLM_PROVIDER=groq
# Optional for image generation:
HF_TOKEN=hf_...
```

### Start the MCP server (terminal 1)

```bash
python -m shared.mcp_server
# or with auto-reload for development:
python -m shared.mcp_server --reload
```

### Start the Streamlit UI (terminal 2)

```bash
streamlit run phase1_writers_room/main.py
```

Open `http://localhost:8501` in your browser.

---

## Project Structure

```
phase1_writers_room/
├── main.py                        # Streamlit app entry point
├── gui.py                         # Reusable UI components + CSS design system
├── agents/
│   ├── scriptwriter.py            # Auto mode: prompt → screenplay via MCP
│   ├── validator.py               # Manual mode: regex checks + LLM corrections via MCP
│   ├── hitl.py                    # Human-in-the-loop approval checkpoint
│   ├── character_designer.py      # Character extraction + profiling via MCP
│   └── image_synthesizer.py       # Image generation via MCP
├── graph/
│   ├── state.py                   # AgentState TypedDict + add_event() helper
│   └── workflow.py                # LangGraph StateGraph: 7 nodes, 3 conditional routers
└── tests/
    ├── unit/test_validator.py
    └── integration/test_workflow.py

shared/
├── config/config.py               # All environment variables + output paths
├── llm_client.py                  # chat_json() / chat_text() for Groq + Gemini
├── mcp_server/
│   ├── server.py                  # FastAPI MCP server (GET /tools, POST /invoke)
│   ├── tools.py                   # All 6 MCP tool handlers + TOOL_REGISTRY
│   ├── client.py                  # discover_tool() + invoke_tool()
│   └── __main__.py                # python -m shared.mcp_server entrypoint
└── memory/
    └── vector_store.py            # ChromaDB store() / query() / count()

outputs/                           # Generated at runtime
├── scene_manifest.json
├── character_db.json
└── image_assets/
    └── <CharacterName>.png
```

---

## Design Constraints Enforced

### MCP Tool Discovery Constraint
Agents **never import or call LLM/image APIs directly**. Every external call goes through the pattern:
```python
schema = discover_tool("tool_name")          # GET /tools — verify at runtime
result = invoke_tool("tool_name", {input})   # POST /invoke — structured dispatch
```
This applies to: script generation, character profiling, script correction suggestions, memory commits, and image generation.

### Stateful Memory
All agent activity is captured in two layers:
1. **In-process** — `state["events"]` (UI activity log, reset per run)
2. **Persistent** — ChromaDB vector store (survives across runs; enables future retrieval by downstream agents)

### HITL as First-Class State
`gui_mode` and `hitl_approved` are declared fields of `AgentState` (not `st.session_state` hacks), ensuring they are serialised correctly through LangGraph's state machine and that the HITL agent behaves deterministically in both CLI and UI contexts.
