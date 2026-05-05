#!/usr/bin/env python3
"""
main.py
────────────────────────────────────────────────────────────────────────────
Central backend server for Project Montage.

This FastAPI server orchestrates Phase 1 (Writer's Room) and Phase 2 (Studio Floor),
providing REST APIs for the React frontend to fetch results and trigger execution.

Usage:
    python main.py
    
    The server will start on http://localhost:8000
    API docs available at http://localhost:8000/docs
"""

import os
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# Ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import get_orchestrator, Phase1Request, Phase2Request
from backend.models import ErrorResponse
from pydantic import BaseModel
from shared.config.config import IMAGE_ASSETS_DIR, USE_VIDEO_MODEL


# ── Lifespan Events ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    print("\n" + "="*80)
    print("PROJECT MONTAGE — Central Backend")
    print("="*80)
    print("\n✓ Backend server starting...")
    print("✓ Phase 1 (Writer's Room) available")
    print("✓ Phase 2 (Studio Floor) available")
    print("✓ API docs: http://localhost:8000/docs\n")
    
    yield
    
    print("\n✓ Backend server shutting down...\n")


# ── FastAPI App ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Project Montage Central Backend",
    description="Orchestrates Phase 1 (Writer's Room) and Phase 2 (Studio Floor)",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get global orchestrator
orchestrator = get_orchestrator()


# ── Health Check ────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    """Check if the backend is running."""
    return {"status": "ok", "service": "Project Montage Backend"}


# ── Phase 1: Writer's Room Endpoints ────────────────────────────────────────

@app.post("/api/phase1/run", tags=["Phase 1"])
def run_phase1(request: Phase1Request):
    """
    Trigger Phase 1 execution (Writer's Room).
    
    Generates a script and character profiles based on the provided prompt or script file.
    """
    try:
        output = orchestrator.run_phase1(
            prompt=request.prompt,
            script_path=request.script_path
        )
        return {
            "success": True,
            "data": output.model_dump(),
            "message": "Phase 1 completed successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class Phase1HITLRequest(BaseModel):
    approved: bool


@app.post("/api/phase1/hitl/approve", tags=["Phase 1"])
def approve_phase1_hitl(request: Phase1HITLRequest):
    """
    Resume Phase 1 after HITL review.
    Called by the frontend modal after the user reads and approves/rejects the script.
    """
    try:
        output = orchestrator.approve_hitl(approved=request.approved)
        msg = "Script approved — Phase 1 completed." if request.approved else "Script rejected — pipeline stopped."
        return {"success": True, "data": output.model_dump(), "message": msg}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/phase1/script", tags=["Phase 1"])
def get_phase1_script():
    """
    Retrieve the generated script from Phase 1.
    
    Returns the complete script with scenes and dialogue.
    """
    output = orchestrator.get_phase1_output()
    if output is None:
        raise HTTPException(status_code=404, detail="Phase 1 has not been run yet")
    
    if output.script is None:
        raise HTTPException(status_code=404, detail="No script available")
    
    return {
        "success": True,
        "data": output.script.model_dump(),
        "message": "Script retrieved successfully"
    }


@app.get("/api/phase1/character-image/{character_name}", tags=["Phase 1"])
def get_phase1_character_image(character_name: str):
    """
    Serve a Phase 1 character portrait from ``outputs/image_assets`` if present.
    Filenames follow the same sanitization as the Studio Floor pipeline.
    """
    from urllib.parse import unquote

    raw = unquote(character_name).strip()
    stem = "".join(c if c.isalnum() else "_" for c in raw)
    stem = stem.strip("_")
    if not stem:
        raise HTTPException(status_code=400, detail="Invalid character name")
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        path = Path(IMAGE_ASSETS_DIR) / f"{stem}{ext}"
        if path.is_file():
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="Character image not found")


@app.get("/api/phase1/characters", tags=["Phase 1"])
def get_phase1_characters():
    """
    Retrieve character profiles from Phase 1.
    
    Returns all generated characters with descriptions, traits, and reference styles.
    """
    output = orchestrator.get_phase1_output()
    if output is None:
        raise HTTPException(status_code=404, detail="Phase 1 has not been run yet")
    
    return {
        "success": True,
        "data": [c.model_dump() for c in output.characters],
        "message": "Characters retrieved successfully"
    }


@app.get("/api/phase1/outputs", tags=["Phase 1"])
def get_phase1_outputs():
    """
    Retrieve all outputs from Phase 1.
    
    Includes script, characters, images, and metadata.
    """
    output = orchestrator.get_phase1_output()
    if output is None:
        raise HTTPException(status_code=404, detail="Phase 1 has not been run yet")
    
    return {
        "success": True,
        "data": output.model_dump(),
        "message": "Phase 1 outputs retrieved successfully"
    }


# ── Phase 2: Studio Floor Endpoints ─────────────────────────────────────────

@app.post("/api/phase2/run", tags=["Phase 2"])
def run_phase2(request: Phase2Request):
    """
    Trigger Phase 2 execution (Studio Floor).
    
    Generates videos from the script and characters created in Phase 1.
    Requires Phase 1 to have completed successfully.
    """
    try:
        output = orchestrator.run_phase2(scene_id=request.scene_id)
        return {
            "success": True,
            "data": output.model_dump(),
            "message": "Phase 2 completed"
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/phase2/videos", tags=["Phase 2"])
def get_phase2_videos():
    """
    Retrieve video outputs from Phase 2.
    
    Returns paths to generated video files for each scene.
    """
    output = orchestrator.get_phase2_output()
    if output is None:
        raise HTTPException(status_code=404, detail="Phase 2 has not been run yet")
    
    videos = [
        {
            "scene_id": scene.scene_id,
            "path": scene.raw_mp4_path,
            "error": scene.error
        }
        for scene in output.scenes
    ]
    
    return {
        "success": True,
        "data": videos,
        "message": "Videos retrieved successfully"
    }


@app.get("/api/phase2/video/{scene_id}", tags=["Phase 2"])
def stream_scene_video(scene_id: int):
    """
    Stream the MP4 video for a specific scene so the browser can play it.
    Scans disk directly so it works even after a server restart.
    """
    from fastapi.responses import FileResponse
    import os

    base = os.path.dirname(os.path.abspath(__file__))

    # Candidate paths in priority order
    candidates = [
        os.path.join(base, "outputs_phase2", "raw_scenes", f"scene_{scene_id:02d}.mp4"),
        os.path.join(base, "outputs_phase2", "raw_scenes", f"scene_{scene_id}.mp4"),
        os.path.join(base, "outputs_phase2", "raw_scenes", "Pexel-Pipeline", f"scene_{scene_id:02d}.mp4"),
        os.path.join(base, "outputs_phase2", "raw_scenes", "WAN2.2", f"scene_{scene_id:02d}.mp4"),
    ]

    # Also check orchestrator state if available
    try:
        output = orchestrator.get_phase2_output()
        if output:
            match = next((s for s in output.scenes if s.scene_id == scene_id), None)
            if match and match.raw_mp4_path and not match.error:
                p = match.raw_mp4_path if os.path.isabs(match.raw_mp4_path) else os.path.join(base, match.raw_mp4_path)
                candidates.insert(0, p)
    except Exception:
        pass

    for path in candidates:
        if os.path.exists(path):
            return FileResponse(path, media_type="video/mp4", filename=f"scene_{scene_id}.mp4")

    raise HTTPException(
        status_code=404,
        detail=f"Video for scene {scene_id} not found. Checked: {candidates}"
    )


@app.get("/api/phase2/outputs", tags=["Phase 2"])
def get_phase2_outputs():
    """
    Retrieve all outputs from Phase 2.

    Falls back to scanning disk when orchestrator has no in-memory state.
    """
    import os, glob

    output = orchestrator.get_phase2_output()
    if output is not None:
        return {
            "success": True,
            "data": output.model_dump(),
            "message": "Phase 2 outputs retrieved successfully"
        }

    # Fallback: scan disk for generated scene files
    base = os.path.dirname(os.path.abspath(__file__))
    raw_dir = os.path.join(base, "outputs_phase2", "raw_scenes")
    if not os.path.isdir(raw_dir):
        raise HTTPException(status_code=404, detail="Phase 2 has not been run yet")

    scenes = []
    for mp4 in sorted(glob.glob(os.path.join(raw_dir, "scene_*.mp4"))):
        fname = os.path.basename(mp4)          # scene_01.mp4
        try:
            sid = int(fname.replace("scene_", "").replace(".mp4", ""))
        except ValueError:
            continue
        scenes.append({"scene_id": sid, "raw_mp4_path": mp4, "error": None})

    if not scenes:
        raise HTTPException(status_code=404, detail="Phase 2 has not been run yet")

    return {
        "success": True,
        "data": {"scenes": scenes, "video_generation_mode": "pexels_stock"},
        "message": "Phase 2 outputs retrieved from disk"
    }


# ── Pipeline Endpoints ──────────────────────────────────────────────────────

@app.get("/api/pipeline/status", tags=["Pipeline"])
def get_pipeline_status():
    """
    Get overall pipeline status.
    
    Returns completion status, timing, and error information for both phases.
    """
    status = orchestrator.get_status()
    return {
        "success": True,
        "data": status.model_dump(),
        "message": "Pipeline status retrieved"
    }


@app.post("/api/pipeline/run", tags=["Pipeline"])
def run_full_pipeline(request: Phase1Request):
    """
    Execute the full pipeline: Phase 1 followed by Phase 2.
    
    This is the complete workflow that generates a script, characters,
    and then produces videos from them.
    """
    try:
        orchestrator.reset()
        phase1_result, phase2_result = orchestrator.run_full_pipeline(
            prompt=request.prompt
        )
        
        return {
            "success": True,
            "data": {
                "phase1": phase1_result.model_dump(),
                "phase2": phase2_result.model_dump() if phase2_result else None
            },
            "message": "Full pipeline executed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pipeline/reset", tags=["Pipeline"])
def reset_pipeline():
    """
    Reset the pipeline state.
    
    Clears all results and status, allowing a fresh execution.
    """
    orchestrator.reset()
    return {
        "success": True,
        "message": "Pipeline reset successfully"
    }


# ── Config Endpoints ────────────────────────────────────────────────────────

@app.get("/api/config", tags=["Config"])
def get_config():
    """
    Get backend configuration for the frontend.
    
    Provides information about available phases and their status.
    """
    return {
        "success": True,
        "data": {
            "phases": ["phase1", "phase2"],
            "phase1_name": "Writer's Room",
            "phase2_name": "Studio Floor",
            "phase2_video_generation_mode": (
                "wan_i2v" if USE_VIDEO_MODEL else "pexels_stock"
            ),
            "features": [
                "script_generation",
                "character_design",
                "image_synthesis",
                "video_generation",
                "voice_synthesis",
                "face_swap",
                "lip_sync"
            ]
        }
    }


# ── MCP Endpoints (Integrated) ──────────────────────────────────────────────

from shared.mcp_server.server import list_tools, invoke_tool, InvokeRequest, ToolSchema

@app.get("/tools", response_model=list[ToolSchema], tags=["MCP"])
def get_mcp_tools():
    """List available MCP tools."""
    return list_tools()

@app.post("/invoke", tags=["MCP"])
def post_mcp_invoke(req: InvokeRequest):
    """Invoke an MCP tool."""
    return invoke_tool(req)


# ── Error Handlers ──────────────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
