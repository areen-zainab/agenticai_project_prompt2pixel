# Project Montage - Central Backend

This is the central backend server for Project Montage, orchestrating Phase 1 (Writer's Room) and Phase 2 (Studio Floor) execution.

## Architecture Overview

```
main.py (FastAPI Server)
    ↓
backend/orchestrator.py (Execution Logic)
    ├── Phase 1: phase1_writers_room.run_phase1
    └── Phase 2: phase2_studio_floor workflows
```

## Structure

- **main.py**: FastAPI entry point; defines all API endpoints
- **backend/models.py**: Pydantic models for data serialization
- **backend/orchestrator.py**: Core orchestration logic; runs phases and manages state
- **backend/utils.py**: Utility functions
- **backend/__init__.py**: Package initialization

## Running the Backend

### Prerequisites

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

### MCP tool server (required for Phase 1 / Phase 2 workflows)

Phase graphs call tools via **`MCP_BASE_URL`** (`shared/config/config.py`). Start the MCP app on a port that matches `.env`:

```bash
uvicorn shared.mcp_server.server:app --host 127.0.0.1 --port 8001
```

If MCP listens on **8001**, set `MCP_BASE_URL=http://localhost:8001` in `.env`. **Do not run MCP and `main.py` both on port 8000**—the React UI expects this backend at `http://localhost:8000`.

### Start the Server

```bash
python main.py
```

The server will start on `http://localhost:8000`

#### API Documentation

Once running, visit:
- **Interactive docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

## API Endpoints

### Phase 1: Writer's Room

**POST /api/phase1/run**
- Trigger Phase 1 execution
- Body: `{ "prompt": "Your story idea" }`
- Returns: Full Phase 1 output (script, characters, images)

**GET /api/phase1/script**
- Retrieve generated script
- Returns: Scene and dialogue data

**GET /api/phase1/characters**
- Retrieve character profiles
- Returns: Array of characters with traits and descriptions

**GET /api/phase1/outputs**
- Retrieve all Phase 1 outputs
- Returns: Complete Phase 1 result object

### Phase 2: Studio Floor

**POST /api/phase2/run**
- Trigger Phase 2 execution
- Requires Phase 1 to be completed first
- Body: `{ "scene_id": null }` (optional; if null, all scenes are processed)
- Returns: Video generation results

**GET /api/phase2/videos**
- Retrieve video paths
- Returns: Array of scene results with MP4 paths

**GET /api/phase2/outputs**
- Retrieve all Phase 2 outputs
- Returns: Complete Phase 2 result object

### Pipeline

**GET /api/pipeline/status**
- Get overall pipeline status
- Returns: Completion flags, timestamps, errors

**POST /api/pipeline/run**
- Execute full pipeline (Phase 1 + Phase 2)
- Body: `{ "prompt": "Your story idea" }`
- Returns: Both Phase 1 and Phase 2 results

**POST /api/pipeline/reset**
- Reset pipeline state
- Clears all cached results

### Config

**GET /api/config**
- Get backend configuration
- Returns: Available phases, features

## Data Flow

### Phase 1 Execution

1. Frontend sends prompt to `/api/phase1/run`
2. Backend calls `orchestrator.run_phase1(prompt)`
3. Orchestrator imports and runs `phase1_writers_room.run_phase1()`
4. Results are structured into `Phase1Output` model
5. Frontend fetches results from `/api/phase1/script`, `/api/phase1/characters`, etc.

### Phase 2 Execution

1. Frontend sends request to `/api/phase2/run`
2. Backend verifies Phase 1 completion
3. Orchestrator loads Phase 1 outputs from disk (outputs/scene_manifest.json, outputs/character_db.json)
4. Orchestrator runs Phase 2 graph for each scene
5. Results are structured into `Phase2Output` model
6. Frontend fetches results from `/api/phase2/videos`

## Design Decisions

### Modularity

- Phase 1 and Phase 2 remain independent; run Phase 1 with `python phase1_writers_room/run_phase1.py`, Phase 2 with `python -m phase2_studio_floor.run_phase2` from the repo root (with MCP running)
- The orchestrator acts as a wrapper around existing workflows
- The central backend is a new abstraction layer; it doesn't modify existing phase code

### No Streamlit in Backend

- The central backend runs only the Phase 1 workflow (graph logic), not the Streamlit GUI
- The Streamlit app (`phase1_writers_room/main.py`) can still be run separately for interactive testing

### Async Support

- FastAPI enables future async execution (e.g., background jobs, WebSockets for real-time progress)
- Currently using sync execution; can be enhanced with async runners

### Data Persistence

- Phase outputs are automatically saved to disk by the workflows
- The backend reads from these files on API calls
- No separate database layer required for MVP

## Error Handling

- All endpoints return standard JSON responses with `success` flag
- Errors include descriptive messages
- HTTP status codes follow REST conventions (200, 400, 404, 500)

## Frontend Integration

The React frontend:
1. Calls `/api/phase1/run` with a prompt
2. Polls `/api/pipeline/status` to track progress
3. Fetches results from phase-specific endpoints
4. Navigates to Phase 2 page
5. Calls `/api/phase2/run` to generate videos
6. Displays results

## Debugging

Check orchestrator state:

```bash
curl http://localhost:8000/api/pipeline/status
```

View full Phase 1 output:

```bash
curl http://localhost:8000/api/phase1/outputs
```

## Next Steps

- Add background job runner for long-running phases (e.g., using Celery)
- Implement WebSocket for real-time progress updates
- Add request validation and rate limiting
- Integrate authentication for production deployment
- Add database layer for result persistence
