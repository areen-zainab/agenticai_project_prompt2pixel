# Phase 2 Studio Floor — Assignment alignment & roadmap

**Course:** Agentic AI CS-4015 · **Due:** 19 April 2026 Sunday  
**Official brief:** [`assignment4_text.txt`](assignment4_text.txt)

This document is the **single** Phase 2 engineering roadmap for this repository. It merges the former implementation plan and gap checklist into **one stack** and **one ordered backlog** — no alternate conflicting pipelines (e.g. pydub *and* FFmpeg for the same step, or three different “cloning” APIs).

---

## 1. What the assignment requires (compressed)

From [`assignment4_text.txt`](assignment4_text.txt):

| Theme | Brief asks for |
|------|----------------|
| **Outputs** | `scene_manifest.json` → audiovisual scenes; **`raw_scenes/*.mp4`**, **`.wav`**, **intermediate frames**, **task graph logs** |
| **Architecture** | Parallel **audio** ∥ **video** branches → converge at **lip sync**; **`get_task_graph`** per scene; scenes as **independent / parallelizable** units |
| **Memory** | **`commit_memory`** saves intermediates; **recovery** after failure/interruption |
| **Agents** | Parser, **voice** (TTS/cloning, emotion), **video** (refs + cues + env via **`query_stock_footage`**), **face swap** (+ **identity** validation first), **lip sync** (waveform + face motion, frame alignment, temporal consistency) |
| **Rubric (70)** | Parallel 10 · Audio 20 · Video 20 · Lip sync 10 · MCP 5 · Fault tolerance **5** |

---

## 2. Stack decisions for *this* repo (single approach)

These choices apply to **all** remaining work so implementations stay compatible.

| Layer | **Chosen approach** | Do **not** add parallel competing paths |
|-------|---------------------|----------------------------------------|
| **Orchestration** | Existing **LangGraph** graph + **`Send()`** + MCP **`discover_tool` / `invoke_tool`** | Duplicate direct API calls from agents |
| **Speech → WAV** | **`edge-tts`** (MP3) → **`ffmpeg`** PCM WAV (already in `phase2_handlers.py`) | **pydub** as a second conversion pipeline for the same job |
| **Voice ↔ character** | **`edge-tts` neural voices** with **deterministic assignment per character name** (see §4); optional **explicit override** via `character_db.json` (recommended next step) | Multiple cloning APIs (XTTS + ElevenLabs + …) at once |
| **“Cloning” wording in brief** | Treat **voice identity** as **stable neural voice per character** + emotion tags; **true speaker cloning from reference WAV** is **only** pursued if course staff require it → then **one** optional addon (see §6.2), not several |
| **Stock video** | **`query_stock_footage`** in **`shared/mcp_server/tools.py`** + **`video_gen.py`** (download + OpenCV frames) | New standalone downloader module **unless** refactoring reduces duplication |
| **Cloud I2V** | **`USE_VIDEO_MODEL`** + Alibaba **DashScope Wan** in **`handle_generate_scene_video`** (`phase2_handlers.py`) when `ALIBABA_CLOUD_API` is set | Treat HF SDXL stills + Alibaba + Pexels as three equal “primary” modes — **pick env-driven order already in code** |
| **Face identity / swap** | **InsightFace**-class **embedding similarity** + **`inswapper_128.onnx`** when you implement real swap; until then **stub** with **`stub: True`** in tool results | Multiple face libraries at once |
| **Lip sync** | Existing **ordered fallback**: (1) **HF Space** talking-head if `USE_AI_ANIMATION` + space id; (2) **mux** stock MP4 + WAV if `scene_video_path`; (3) **FFmpeg concat** slideshow with **per-frame duration = audio_length / n_frames** | A second unrelated lip-sync stack in parallel |
| **Resumability** | **`outputs_phase2/checkpoints/scene_XX.json`** **artifact manifest** + **`--resume`** + skip-if-valid-file in agents; **`commit_memory`** stays for **vector metadata / logs**, not as the only resume mechanism | Relying only on Chroma for “resume” without disk artifact checks |

---

## 3. Current implementation snapshot

### 3.1 Done (production path exists)

- **Graph:** `voice_synth` ∥ `video_gen` via **`Send()`** → `face_swap` → `lip_sync` (`phase2_studio_floor/graph/workflow.py`).
- **MCP:** Phase 2 tools + **`get_task_graph`**; logs under **`outputs_phase2/task_graph_logs/`**.
- **Voice:** **`handle_voice_cloning_synthesizer`** — per-line **`dialogue_entries`**, **`_assign_voice`**, **`_EMOTION_SETTINGS`**, FFmpeg WAV merge (`shared/mcp_server/phase2_handlers.py`). Agent passes traits (`voice_synth.py`).
- **Video:** Stock path via **`query_stock_footage`** (`tools.py`) + **`video_gen.py`**; optional **Wan** clips via **`generate_scene_video`** when Alibaba key present.
- **Lip sync:** HF animation branch; **mux** branch; **slideshow** with audio-length-based frame timing (`_ffmpeg_slideshow_from_list`).
- **Runner:** `python -m phase2_studio_floor.run_phase2` with correct imports.
- **Deps:** `edge-tts`, `opencv-python`, `imageio-ffmpeg` in **`requirements.txt`**.
- **Manifest:** Multi-scene **`outputs/scene_manifest.json`** for realistic runs.

### 3.2 Not done or stub (tied to rubric / brief)

| Area | Gap |
|------|-----|
| **Fault tolerance** | No **checkpoint JSON** + **`--resume`** + systematic skip-if-artifact-exists |
| **Face swap / identity** | **`identity_validator`** / **`face_swapper`** — stub / copy-tree |
| **Speaker “cloning” from audio** | Not implemented — only **consistent neural voices** |
| **Lip sync “models” phrasing** | Optional talking-head ≠ full composite lip model; **word-boundary** timing not passed from TTS |
| **Cross-scene parallelism** | Scenes run **sequentially** in `run_phase2.py` |
| **Tests** | No dedicated handler integration tests named in plan |

---

## 4. Voice consistency — same voice per character

**Today:** `_character_voices` in **`phase2_handlers.py`** maps **normalized character name → edge-tts voice**. New voices are chosen with **`zlib.adler32(name) % pool_size`**, which is **deterministic** for a given name and pool — so **JAX** gets the **same** neural voice across scenes **and** across process restarts **as long as** the code and pools stay unchanged.

**Remaining risks:**

1. **Heuristic drift:** First assignment wins; traits only affect **first** `_assign_voice` call for that key — acceptable, but document for graders.
2. **Name aliases:** `"Jax"` vs `"JAX"` both normalize to **`JAX`** — good.
3. **Transparency:** Submission should show **which voice** each character uses.

**Single remediation (recommended before any cloning API):**

- Extend **`character_db.json`** (and Phase 1 writer) with optional **`edge_voice_id`** (or **`tts_voice`**) per character — **authoritative override** when present.
- On startup or first synthesis, **persist** a small **`outputs_phase2/voice_assignments.json`** `{ "JAX": "en-US-ChristopherNeural", ... }** written once per project run for reproducibility and demo evidence.

This satisfies **“aligned with character identity”** without introducing a second TTS vendor.

---

## 5. Unified roadmap (priority order)

Work items below are **sequential priorities**. Later phases assume earlier ones when noted.

### Phase R — Resumability & robustness (**Fault tolerance 5**, brief §3.3)

**Goal:** recovery after failure/interruption with **deterministic** reruns.

1. Add **`PHASE2_CHECKPOINTS_DIR`** in **`shared/config/config.py`** → `outputs_phase2/checkpoints/`.
2. Implement **`phase2_studio_floor/checkpoint.py`**: load/save **`scene_XX.json`** with steps **`parser_done`**, **`voice_done`**, **`video_done`**, **`face_done`**, **`lip_done`** and **artifact paths + file sizes**.
3. At start of each agent **`run()`**: if **`--resume`** (or env **`PHASE2_RESUME=1`**) and expected outputs exist and valid → **skip** and load state from checkpoint.
4. Wire **`argparse`** in **`run_phase2.py`** for **`--resume`**; mirror in **`backend/orchestrator.py`** when calling Phase 2.
5. Log skip decisions to **`task_graph_logs`** for rubric evidence.

**Single resume model:** JSON checkpoints + file existence; **`commit_memory`** continues for narrative memory, **not** as sole resume store.

---

### Phase V — Voice quality & identity (**Audio 20**, brief §5.2)

**Goal:** natural multi-speech audio + stable identity — **without** splitting into rival TTS backends.

1. **`character_db` override:** optional **`edge_voice_id`** per character; handler uses override before hash (`§4`).
2. **Persist `voice_assignments.json`** after first assignment round.
3. **Reduce fallback tones:** preflight FFmpeg + edge-tts in deployment docs; narrow **`except`** paths.
4. **Emotion:** keep **`_EMOTION_SETTINGS`**; only extend if graders need stronger cues (SSML-like hints **within edge-tts** only).

**True reference-audio cloning:** **Out of default scope.** If instructors mandate cloning from samples, add **one** path only — e.g. **Coqui XTTS** or **OpenVoice** behind **`VOICE_BACKEND=clone`** — implemented **inside `voice_cloning_synthesizer`** with same MCP contract. **Do not** also add cloud cloning APIs in the same milestone.

---

### Phase F — Face mapping & identity (**Video 20**, brief §5.4)

**Goal:** validate identity, then map face — **one** CV stack.

1. Add **`insightface`**, **`onnxruntime`** to **`requirements.txt`** when implementing.
2. Add **`shared/mcp_server/face_utils.py`**: lazy **`FaceAnalysis`**, optional **`inswapper_128.onnx`**, cosine similarity helper.
3. Replace stubs in **`handle_identity_validator`** / **`handle_face_swapper`** with real paths; **fallback** to current copy behavior **only** if model missing, with **`fallback: true`** in output.

---

### Phase L — Lip sync evidence (**Lip sync 10**, brief multimodal §)

**Goal:** temporal alignment evidence + continuity — extend **existing** handler, no second lip engine.

1. **Logging:** always log **`audio_duration`**, **`video_duration`**, **`drift_sec`**, **`mode`** (`ai_animation` | `video_mux` | `slideshow`).
2. **Optional enhancement:** export **word boundaries** from edge-tts (**SubMaker**) in voice handler → pass **`line_timings`** into **`lip_sync_aligner`** input schema → drive **frame bucket boundaries** in slideshow mode **only** (same FFmpeg concat approach, smarter segment lengths).

---

### Phase P — Parallelism & polish (**Parallel 10**, brief “parallelizable workload”)

1. **Documentation / logs:** prove **`Send()`** in **`task_graph_logs`** (already); add explicit **branch_start / branch_join** events if missing.
2. **Optional code:** bounded **thread pool or asyncio** for **multiple scenes** — **only after** checkpointing works (avoid race on same `outputs_phase2` paths).

---

### Phase T — Testing & deliverables

1. **Integration test:** for each scene, assert **`raw_scenes/scene_XX.mp4`**, **`audio/scene_XX.wav`**, **`frames/scene_XX/`**, **`task_graph_logs/scene_XX.json`**.
2. **Handler tests:** WAV non-empty, stock path returns frames when key present.

---

## 6. Verification

**CLI end-to-end:**

```bash
python -m phase2_studio_floor.run_phase2
python -m phase2_studio_floor.run_phase2 --scene-id 1
```

**Expected tree (when checkpoint phase lands, add `checkpoints/`):**

```
outputs_phase2/
├── audio/scene_XX.wav
├── frames/scene_XX/*.png
├── face_swapped/scene_XX/
├── raw_scenes/scene_XX.mp4
├── stock/...
├── checkpoints/scene_XX.json    ← after Phase R
└── task_graph_logs/scene_XX.json
```

**Manual:** play WAV (multi-speaker), inspect frames (not only placeholders), play MP4, confirm logs; after Phase R, kill run mid-scene and rerun with **`--resume`**.

---

## 7. Full-stack operations

**MCP** and **`main.py`** both need HTTP ports. Default **`MCP_BASE_URL=http://localhost:8000`** conflicts with backend **8000**. Run MCP on **8001** and set **`MCP_BASE_URL=http://localhost:8001`** when using the React UI + **`python main.py`**.

---

## 8. Superseded / do-not-do (avoid churn)

| Idea | Reason |
|------|--------|
| Second MP3→WAV path via **pydub** | **FFmpeg** already used and consistent |
| Separate **`stock_downloader.py`** **without** refactor | Only if it **deduplicates** `tools.py` + **video_gen** — not a parallel download implementation |
| Multiple cloning APIs in one sprint | Conflicts with “single method” rule |
| Root **`run_phase2.py`** | Use **`python -m phase2_studio_floor.run_phase2`** only |

---

## 9. Rubric evidence checklist

| Criterion | What to capture |
|-----------|------------------|
| Parallel architecture | Graph log showing **`Send()`** and join before lip sync |
| Audio | WAV files; **`voice_assignments.json`** or override fields |
| Video | Stock MP4s / Wan clips + frames; face step non-stub if implemented |
| Lip sync | Logged durations/drift/mode |
| MCP | Tool discovery + invoke lines in logs |
| Fault tolerance | Checkpoint files + successful **resume** run log |

---

*This file supersedes scattered Phase 2 planning docs; update it as work lands.*
