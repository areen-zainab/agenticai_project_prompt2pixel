# Project Montage — Remaining Work & Implementation Guide

## Current State Summary

| Phase | Status | What Exists |
|---|---|---|
| **Phase 1 — Story & Script** | ✅ Complete | `phase1_writers_room/` — LangGraph graph, scriptwriter, character_designer, image_synthesizer, HITL, validator agents |
| **Phase 2 — Audio + Video (Studio Floor)** | ✅ Complete | `phase2_studio_floor/` — voice_synth, video_gen (Pexels + Wan2.2), face_swap, lip_sync agents |
| **Phase 3 — Video Composition** | ❌ Missing | **No Phase 3 exists** — the final MP4 compositing/merging of all scenes is absent |
| **Phase 4 — Web Interface** | 🟡 Partial | Only Phase1 and Phase2 pages exist; no Phase3/Edit page, no SSE/WebSocket progress, no download button |
| **Phase 5 — Edit Agent + Undo** | ❌ Missing | **Completely absent** — no edit agent, no intent classifier, no state snapshot system, no version history UI |
| **Tests** | 🟡 Minimal | Only `test_validator.py` (Phase 1) and `test_graph_compile.py` (Phase 2) exist |
| **Submission Docs** | 🟡 Partial | README exists; no project report, no demo video guide, no presentation |

---

## WHAT IS LEFT — Master Checklist

### 🔴 Phase 3: Final Video Composition (Missing Entirely)

The PROJECT.md defines Phase 3 as:
- Take all per-scene MP4s from Phase 2 + timing manifest
- Stitch scenes with transitions (fade, cut, wipe)
- Overlay subtitles (optional)
- Export a single `final_output.mp4`

**Files to create:**

```
phase3_cutting_room/
├── __init__.py
├── agents/
│   ├── __init__.py
│   ├── scene_stitcher.py      # Concatenate all scene MP4s with FFmpeg
│   ├── transition_engine.py   # Fade/dissolve transitions between scenes
│   └── subtitle_burner.py     # Optional subtitle overlay via FFmpeg
├── graph/
│   ├── __init__.py
│   ├── state.py               # Phase3State TypedDict
│   └── workflow.py            # LangGraph graph: stitch → transition → subtitle → export
├── run_phase3.py              # CLI entry point
└── README.md
```

#### Step-by-step: `scene_stitcher.py`

```python
"""
Collects all scene MP4s from outputs_phase2/raw_scenes/ (or stock/),
normalizes them to the same resolution/fps, and concatenates them.
"""
import subprocess, glob, os
from pathlib import Path

RAW_SCENES_DIR = Path("outputs_phase2/raw_scenes")
OUTPUT_DIR = Path("outputs_phase3")
FINAL_OUTPUT = OUTPUT_DIR / "final_output.mp4"

def collect_scene_videos() -> list[Path]:
    """Return sorted list of all scene_XX.mp4 files."""
    files = sorted(RAW_SCENES_DIR.glob("scene_*.mp4"))
    # Also check sub-directories (stock pipeline nests videos)
    for subdir in RAW_SCENES_DIR.iterdir():
        if subdir.is_dir():
            files += sorted(subdir.glob("*_merged.mp4"))
    return sorted(set(files))

def normalize_clip(src: Path, dst: Path, ff: str = "ffmpeg") -> bool:
    """Force 1280x720, 24fps, yuv420p, strip audio (audio is added later)."""
    cmd = [
        ff, "-y", "-i", str(src),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
        "-r", "24", "-pix_fmt", "yuv420p", "-an", str(dst)
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    return dst.exists() and dst.stat().st_size > 0

def stitch_scenes(scene_paths: list[Path], output: Path, ff: str = "ffmpeg") -> Path:
    norm_dir = output.parent / "normalized"
    norm_dir.mkdir(parents=True, exist_ok=True)
    
    normalized = []
    for i, p in enumerate(scene_paths):
        dst = norm_dir / f"norm_{i:02d}.mp4"
        if normalize_clip(p, dst, ff):
            normalized.append(dst)
    
    concat_list = output.parent / "_concat.txt"
    with open(concat_list, "w") as f:
        for p in normalized:
            f.write(f"file '{p.as_posix()}'\n")
    
    cmd = [ff, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
           "-c", "copy", str(output)]
    subprocess.run(cmd, capture_output=True, check=True, timeout=300)
    return output
```

#### Step-by-step: `transition_engine.py`

```python
"""
Adds crossfade / fade-to-black transitions between scenes using FFmpeg xfade filter.
"""
import subprocess
from pathlib import Path

TRANSITION_DURATION = 0.5  # seconds

def apply_transitions(scene_clips: list[Path], output: Path, ff="ffmpeg") -> Path:
    """
    Chain scenes with xfade crossfade transitions.
    Works by chaining pairs: clip1 xfade clip2, result xfade clip3, etc.
    """
    if len(scene_clips) == 1:
        import shutil
        shutil.copy(scene_clips[0], output)
        return output
    
    current = scene_clips[0]
    for i, next_clip in enumerate(scene_clips[1:], 1):
        is_last = (i == len(scene_clips) - 1)
        tmp = output.parent / f"_xfade_{i}.mp4"
        dst = output if is_last else tmp
        
        # Get duration of current clip for offset calculation
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(current)],
            capture_output=True, text=True
        )
        try:
            duration = float(probe.stdout.strip())
        except ValueError:
            duration = 5.0
        
        offset = max(0, duration - TRANSITION_DURATION)
        
        cmd = [
            ff, "-y", "-i", str(current), "-i", str(next_clip),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={TRANSITION_DURATION}:offset={offset}[v]",
            "-map", "[v]", "-pix_fmt", "yuv420p", str(dst)
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=180)
        current = dst
    
    return output
```

#### Step-by-step: `graph/workflow.py` (Phase 3 LangGraph)

```python
from langgraph.graph import StateGraph, START, END
from phase3_cutting_room.graph.state import Phase3State

def build_phase3_graph():
    graph = StateGraph(Phase3State)
    graph.add_node("collect_scenes", collect_scenes_node)
    graph.add_node("stitch",         stitch_node)
    graph.add_node("transitions",    transitions_node)
    graph.add_node("subtitle_burn",  subtitle_node)   # optional, skips if no subtitles
    graph.add_node("export",         export_node)
    
    graph.add_edge(START, "collect_scenes")
    graph.add_edge("collect_scenes", "stitch")
    graph.add_edge("stitch", "transitions")
    graph.add_conditional_edges("transitions", route_subtitles,
        {"subtitle_burn": "subtitle_burn", "export": "export"})
    graph.add_edge("subtitle_burn", "export")
    graph.add_edge("export", END)
    return graph.compile()
```

#### Backend API endpoints to add in `main.py`

```python
@app.post("/api/phase3/run")
def run_phase3():
    """Stitch all Phase 2 scene videos into final_output.mp4"""
    ...

@app.get("/api/phase3/video")
def get_final_video():
    """Stream the final composited MP4"""
    return FileResponse("outputs_phase3/final_output.mp4", media_type="video/mp4")

@app.get("/api/phase3/outputs")
def get_phase3_outputs():
    """Return metadata about the final video"""
    ...
```

---

### 🔴 Phase 5: Edit Agent + Undo System (Missing Entirely)

This is worth **20% of the grade**. It consists of four sub-systems:

#### 5.1 Intent Classification Agent

**File:** `phase5_edit_agent/agents/intent_classifier.py`

```python
"""
LangGraph node that receives a free-text edit command and outputs a
structured EditIntent object.
"""
from pydantic import BaseModel
from typing import Literal
from shared.llm_client import chat_text
import json

class EditIntent(BaseModel):
    intent: str           # e.g. "change_voice_tone"
    target: Literal["audio", "video_frame", "video", "script"]
    scope: str            # e.g. "character:Narrator" or "scene:2"
    parameters: dict      # e.g. {"tone": "whispered"}
    confidence: float

SYSTEM_PROMPT = """
You are an edit intent classifier for an AI video generation pipeline.
Given a natural language edit command, output a JSON object with:
- intent: snake_case action name
- target: one of "audio", "video_frame", "video", "script"
- scope: what is targeted (e.g. "character:NAME", "scene:ID", "all")
- parameters: dict of specific change parameters
- confidence: 0.0–1.0

Target rules:
- "audio" → voice tone, background music, silence, audio speed
- "video_frame" → visual look, character design, scene darkness/color, scene style
- "video" → subtitles, speed, transitions, full recomposition
- "script" → regenerate dialogue, story, add/remove scenes

Output ONLY valid JSON, no markdown.
"""

def classify_intent(edit_query: str) -> EditIntent:
    response = chat_text(system=SYSTEM_PROMPT, user=edit_query, temperature=0.2)
    data = json.loads(response)
    return EditIntent(**data)
```

#### 5.2 State Snapshot System (Versioning + Undo)

**File:** `phase5_edit_agent/state_manager.py`

```python
"""
Append-only SQLite-based state snapshot system.
Each pipeline run or edit creates a new version.
"""
import sqlite3, json, shutil, os
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

DB_PATH = Path("outputs/state_versions.db")
SNAPSHOTS_DIR = Path("outputs/snapshots")

@dataclass
class VersionRecord:
    version: int
    timestamp: str
    description: str
    state_json: dict
    asset_paths: list[str]

class StateManager:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS versions (
                    version     INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    description TEXT NOT NULL,
                    state_json  TEXT NOT NULL,
                    asset_paths TEXT NOT NULL
                )
            """)
    
    def snapshot(self, state_json: dict, description: str, asset_paths: list[str]) -> int:
        """Save a new version. Returns the new version number."""
        ts = datetime.now().isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "INSERT INTO versions (timestamp, description, state_json, asset_paths) VALUES (?,?,?,?)",
                (ts, description, json.dumps(state_json), json.dumps(asset_paths))
            )
            version = cur.lastrowid
        
        # Copy assets into snapshot directory
        snap_dir = SNAPSHOTS_DIR / f"v{version}"
        snap_dir.mkdir(parents=True, exist_ok=True)
        for src in asset_paths:
            p = Path(src)
            if p.exists():
                shutil.copy2(p, snap_dir / p.name)
        
        return version
    
    def revert(self, version: int) -> VersionRecord:
        """Restore assets and state from a previous version."""
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT * FROM versions WHERE version=?", (version,)
            ).fetchone()
        if not row:
            raise ValueError(f"Version {version} not found")
        
        record = VersionRecord(
            version=row[0], timestamp=row[1], description=row[2],
            state_json=json.loads(row[3]), asset_paths=json.loads(row[4])
        )
        
        # Restore assets from snapshot
        snap_dir = SNAPSHOTS_DIR / f"v{version}"
        for asset_path in record.asset_paths:
            p = Path(asset_path)
            snap_file = snap_dir / p.name
            if snap_file.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(snap_file, p)
        
        return record
    
    def history(self) -> list[dict]:
        """Return all versions as list of dicts for the UI."""
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT version, timestamp, description FROM versions ORDER BY version DESC"
            ).fetchall()
        return [{"version": r[0], "timestamp": r[1], "description": r[2]} for r in rows]
```

#### 5.3 Edit Execution Router

**File:** `phase5_edit_agent/agents/edit_executor.py`

```python
"""
Routes the classified EditIntent to the correct pipeline re-run.
"""
from phase5_edit_agent.agents.intent_classifier import EditIntent
from phase5_edit_agent.state_manager import StateManager

state_manager = StateManager()

def execute_edit(intent: EditIntent, current_state: dict) -> dict:
    """
    Dispatch edit to the correct handler based on intent.target.
    Returns updated state after re-run.
    """
    # Snapshot BEFORE making changes (enables undo)
    state_manager.snapshot(
        state_json=current_state,
        description=f"Before edit: {intent.intent}",
        asset_paths=_collect_current_assets()
    )
    
    if intent.target == "script":
        return _rerun_phase1(intent, current_state)
    elif intent.target == "audio":
        return _rerun_voice_synth(intent, current_state)
    elif intent.target == "video_frame":
        return _rerun_image_gen(intent, current_state)
    elif intent.target == "video":
        return _rerun_composition(intent, current_state)
    else:
        raise ValueError(f"Unknown target: {intent.target}")

def _rerun_phase1(intent: EditIntent, state: dict) -> dict:
    """Re-invoke Phase 1 with modified prompt or parameters."""
    from backend.orchestrator import get_orchestrator
    orch = get_orchestrator()
    prompt = state.get("original_prompt", "") + f" ({intent.parameters})"
    result = orch.run_phase1(prompt=prompt)
    return {**state, "phase1_output": result.model_dump()}

def _rerun_voice_synth(intent: EditIntent, state: dict) -> dict:
    """Re-synthesize TTS for the targeted character/scene."""
    # Extract scene_id and character from scope
    # e.g. scope = "character:Narrator" or "scene:2"
    # Then re-invoke phase2 voice_synth node for those scenes only
    from backend.orchestrator import get_orchestrator
    orch = get_orchestrator()
    scene_id = _parse_scope_scene(intent.scope)
    result = orch.run_phase2(scene_id=scene_id)
    return {**state, "phase2_output": result.model_dump()}

def _rerun_image_gen(intent: EditIntent, state: dict) -> dict:
    """Re-generate images for specified character/scene."""
    # Modify the image generation parameters and re-run
    # For "make the scene darker" → modify visual_cue/prompt
    from phase1_writers_room.agents.image_synthesizer import run as synth_run
    # ... targeted re-synthesis
    return state

def _rerun_composition(intent: EditIntent, state: dict) -> dict:
    """Recompose final video with updated parameters."""
    from phase3_cutting_room.graph.workflow import build_phase3_graph
    graph = build_phase3_graph()
    # Pass intent.parameters (e.g. {"speed": 1.5, "subtitles": False})
    result = graph.invoke({**state, "edit_params": intent.parameters})
    return result

def _parse_scope_scene(scope: str) -> int | None:
    if scope.startswith("scene:"):
        try:
            return int(scope.split(":")[1])
        except Exception:
            pass
    return None

def _collect_current_assets() -> list[str]:
    import glob
    assets = []
    assets += glob.glob("outputs_phase2/raw_scenes/**/*.mp4", recursive=True)
    assets += glob.glob("outputs_phase3/*.mp4")
    assets += glob.glob("outputs/image_assets/*.png")
    return assets
```

#### 5.4 LangGraph Edit Agent

**File:** `phase5_edit_agent/graph/workflow.py`

```python
"""
LangGraph workflow for the Edit Agent.
Nodes: classify → validate → execute → snapshot → respond
Uses SqliteSaver checkpointer for multi-turn memory.
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from phase5_edit_agent.graph.state import EditAgentState

def build_edit_graph():
    graph = StateGraph(EditAgentState)
    graph.add_node("classify",  classify_node)
    graph.add_node("validate",  validate_node)   # sanity-check intent
    graph.add_node("execute",   execute_node)    # run the edit
    graph.add_node("snapshot",  snapshot_node)   # save new version
    graph.add_node("respond",   respond_node)    # format response for UI
    
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "validate")
    graph.add_conditional_edges("validate", route_after_validate,
        {"execute": "execute", "respond": "respond"})  # respond on low confidence
    graph.add_edge("execute", "snapshot")
    graph.add_edge("snapshot", "respond")
    graph.add_edge("respond", END)
    
    checkpointer = SqliteSaver.from_conn_string("outputs/edit_agent_memory.db")
    return graph.compile(checkpointer=checkpointer)
```

#### 5.5 Backend API for Edit Agent

Add to `main.py`:

```python
from phase5_edit_agent.graph.workflow import build_edit_graph
from phase5_edit_agent.state_manager import StateManager

edit_graph = build_edit_graph()
state_mgr = StateManager()

@app.post("/api/edit/run")
def run_edit(request: EditRequest):
    """Accept a natural language edit command and execute it."""
    result = edit_graph.invoke(
        {"query": request.query, "current_state": orchestrator.get_status().model_dump()},
        config={"configurable": {"thread_id": "main_session"}}
    )
    return {"success": True, "data": result, "intent": result.get("classified_intent")}

@app.get("/api/edit/history")
def get_version_history():
    """Return all saved versions for the undo UI panel."""
    return {"success": True, "data": state_mgr.history()}

@app.post("/api/edit/undo/{version}")
def undo_to_version(version: int):
    """Revert pipeline state and assets to a previous version."""
    record = state_mgr.revert(version)
    return {"success": True, "data": {"version": record.version, "description": record.description}}
```

---

### 🟡 Phase 4: Missing Frontend Pages

The frontend only has Phase1 and Phase2 pages. You need to add:

#### 5.6 Phase 3 Page — `frontend/src/pages/Phase3.tsx`

```tsx
// Key features to implement:
// 1. "Run Phase 3" button → POST /api/phase3/run
// 2. Progress indicator (same spinner style as Phase1/Phase2)
// 3. Video player for final_output.mp4 from /api/phase3/video
// 4. Download button: <a href="/api/phase3/video" download="final_output.mp4">
// 5. "Proceed to Edit Agent →" button linking to /phase4-edit
```

#### 5.7 Edit Agent Page — `frontend/src/pages/EditAgent.tsx`

```tsx
// Key features to implement:
// 1. Free-text input: "Describe your edit..."
// 2. Intent display card: shows classified intent, target, parameters
// 3. Execution progress + result preview
// 4. VERSION HISTORY PANEL:
//    - Scrollable list of versions (v1, v2, v3...)
//    - Each shows: version number, timestamp, description
//    - "Revert to this version" button → POST /api/edit/undo/{version}
// 5. Undo button (reverts to previous version instantly)
```

#### 5.8 Update `App.tsx` to add new routes

```tsx
import Phase3 from './pages/Phase3';
import EditAgent from './pages/EditAgent';

// Add to Routes:
<Route path="/phase3" element={<Phase3 />} />
<Route path="/edit" element={<EditAgent />} />
```

Also update Phase2.tsx CTA button to navigate to `/phase3` instead of ending.

---

### 🟡 Missing Unit Tests

The PROJECT.md requires unit tests for each phase. Currently only one test file exists for Phase 1 and one for Phase 2.

#### Tests to add:

**`phase1_writers_room/tests/unit/test_scriptwriter.py`**
```python
def test_scriptwriter_output_has_scenes(): ...
def test_scriptwriter_output_has_dialogue(): ...
def test_character_designer_output_schema(): ...
def test_validator_catches_missing_fields(): ...
```

**`phase2_studio_floor/tests/test_voice_synth.py`**
```python
def test_voice_synth_runs_without_crashing(): ...
def test_face_swap_skips_gracefully_on_missing_frames(): ...
def test_video_gen_fallback_placeholder(): ...
```

**`phase5_edit_agent/tests/test_intent_classifier.py`** (10+ test cases required by PROJECT.md)
```python
# These are explicitly required by the spec
queries_and_expected = [
    ("Change voice tone", "audio"),
    ("Make the scene darker", "video_frame"),
    ("Add background music", "audio"),
    ("Remove the subtitle", "video"),
    ("Change character design", "video_frame"),
    ("Speed up this scene", "video"),
    ("Regenerate the script", "script"),
    ("Make the narrator sound sad", "audio"),
    ("Add fade transitions between scenes", "video"),
    ("Rewrite scene 2 dialogue", "script"),
]
def test_intent_classification_accuracy():
    for query, expected_target in queries_and_expected:
        intent = classify_intent(query)
        assert intent.target == expected_target
```

---

### 📁 Full Directory Structure to Create

```
phase3_cutting_room/
├── __init__.py
├── agents/
│   ├── __init__.py
│   ├── scene_stitcher.py
│   ├── transition_engine.py
│   └── subtitle_burner.py
├── graph/
│   ├── __init__.py
│   ├── state.py
│   └── workflow.py
├── run_phase3.py
└── README.md

phase5_edit_agent/
├── __init__.py
├── agents/
│   ├── __init__.py
│   ├── intent_classifier.py
│   └── edit_executor.py
├── graph/
│   ├── __init__.py
│   ├── state.py
│   └── workflow.py
├── state_manager.py
├── tests/
│   ├── __init__.py
│   └── test_intent_classifier.py
└── README.md

frontend/src/pages/
├── Phase1.tsx       ✅ exists
├── Phase2.tsx       ✅ exists
├── Phase3.tsx       ❌ create
├── EditAgent.tsx    ❌ create
└── HITLModal.tsx    ✅ exists
```

---

## Implementation Priority Order

Given the deadline, tackle in this order:

| # | Task | Effort | Grade Impact |
|---|---|---|---|
| 1 | **Phase 5 State Manager** (`state_manager.py`) | ~1hr | 20% |
| 2 | **Phase 5 Intent Classifier** (`intent_classifier.py`) | ~2hr | 20% |
| 3 | **Phase 5 Backend APIs** (`/api/edit/*`) | ~1hr | 20% |
| 4 | **Phase 3 Scene Stitcher** (`scene_stitcher.py` + graph) | ~2hr | 20% |
| 5 | **Frontend: EditAgent.tsx** (with version history) | ~2hr | 10% |
| 6 | **Frontend: Phase3.tsx** (with video player + download) | ~1hr | 10% |
| 7 | **Unit Tests** (10 intent classifier tests) | ~1hr | embedded |
| 8 | **Demo Video** (initial gen → 3 edits → 2 reverts) | ~30min | 10% |

---

## Integration Notes

### Shared JSON Schema Compliance

Phase 3 must consume the outputs of Phase 2. The scene video paths live in:
- `outputs_phase2/raw_scenes/scene_XX.mp4` (Pexels pipeline)
- `outputs_phase2/stock/scene_XX/scene_XX_merged.mp4` (Wan2.2 pipeline)

Phase 3's `collect_scenes_node` must scan both locations.

### LangGraph Checkpointer for Edit Agent

The Edit Agent must use `SqliteSaver` so multi-turn edit conversations retain context. Install if missing:
```bash
pip install langgraph-checkpoint-sqlite
```

### State Manager Integration Points

Call `state_manager.snapshot()` at:
1. After Phase 1 completes → version "v1: Initial script generation"
2. After Phase 2 completes → version "v2: Studio floor complete"  
3. After Phase 3 completes → version "v3: Final video composed"
4. Before every edit → version "vN: Before edit: {query}"
5. After every edit → version "vN+1: After edit: {intent.intent}"

---

## Submission Checklist

- [ ] Phase 3 pipeline runs and produces `final_output.mp4`
- [ ] Edit Agent classifies at least 10 edit query types correctly
- [ ] Undo reverts both assets and state to a previous version
- [ ] Version history UI panel shows all versions with timestamps
- [ ] Frontend has Phase3 page with working video player and download
- [ ] Frontend has Edit Agent page with intent display and version panel
- [ ] 10+ unit tests for intent classifier pass
- [ ] `requirements.txt` updated with any new dependencies
- [ ] Root `README.md` updated with Phase 3 and Phase 5 run instructions
- [ ] Demo video recorded: initial generation → 3 edits → 2 reverts (3–7 min)
