#!/usr/bin/env python3
"""
Run Phase 2 (Studio Floor) on Phase 1 outputs.

Does not import or execute Phase 1. Requires MCP server with Phase 2 tools registered.

  Terminal 1: python -m shared.mcp_server
  Terminal 2: python -m phase2_studio_floor.run_phase2
       (or from this directory: python run_phase2.py)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Project root (parent of `phase2_studio_floor`) so `python run_phase2.py` from this dir works
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from phase2_studio_floor.graph.state import initial_scene_state
from phase2_studio_floor.graph.workflow import build_scene_graph
from phase2_studio_floor.io import load_character_db, load_scene_manifest
from shared.config.config import BASE_DIR, CHARACTER_DB_PATH, SCENE_MANIFEST_PATH


def main() -> int:
    p = argparse.ArgumentParser(description="PROJECT MONTAGE — Phase 2 Studio Floor")
    p.add_argument(
        "--manifest",
        type=Path,
        default=SCENE_MANIFEST_PATH,
        help="Path to scene_manifest.json (default: outputs/scene_manifest.json)",
    )
    p.add_argument(
        "--characters",
        type=Path,
        default=CHARACTER_DB_PATH,
        help="Path to character_db.json",
    )
    p.add_argument(
        "--scene-id",
        type=int,
        default=None,
        help="Process only this scene_id (1-based). Default: all scenes.",
    )
    args = p.parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else BASE_DIR / args.manifest
    char_path = args.characters if args.characters.is_absolute() else BASE_DIR / args.characters

    if not manifest_path.is_file():
        print(f"Missing manifest: {manifest_path}", file=sys.stderr)
        return 1
    if not char_path.is_file():
        print(f"Missing character_db: {char_path}", file=sys.stderr)
        return 1

    manifest = load_scene_manifest(manifest_path)
    character_db = load_character_db(char_path)

    scenes = manifest["scenes"]
    if args.scene_id is not None:
        scenes = [s for s in scenes if int(s.get("scene_id", -1)) == args.scene_id]
        if not scenes:
            print(f"No scene with scene_id={args.scene_id}", file=sys.stderr)
            return 1

    graph = build_scene_graph()
    results = []
    
    total = len(scenes)
    for i, scene in enumerate(scenes):
        sid = int(scene.get("scene_id", 0))
        print(f"\n\033[95m{'='*80}\033[0m")
        print(f"\033[95mPROCESING SCENE {sid:02d} ({i+1}/{total})\033[0m")
        print(f"\033[95m{'='*80}\033[0m")
        
        state = initial_scene_state(scene, character_db)
        
        # Use streaming to track node completion
        final_state = state
        for update in graph.stream(state, stream_mode="updates"):
            for node_name, node_update in update.items():
                if node_update:
                    final_state.update(node_update)
        
        res = {
            "scene_id": sid, 
            "raw_mp4_path": final_state.get("raw_mp4_path"), 
            "error": final_state.get("error")
        }
        results.append(res)
        
        if res["error"]:
            print(f"\n\033[91m[Scene {sid:02d} Failed]: {res['error']}\033[0m")
        else:
            print(f"\n\033[92m[Scene {sid:02d} Complete]: {res['raw_mp4_path']}\033[0m")

    print(f"\n\033[95m{'='*80}\033[0m")
    success = [r for r in results if not r.get("error")]
    print(f"\033[95mFINISHED: {len(success)}/{total} scenes processed successfully.\033[0m")
    print(f"\033[95m{'='*80}\033[0m")
    
    return 1 if len(success) < total else 0


if __name__ == "__main__":
    raise SystemExit(main())
