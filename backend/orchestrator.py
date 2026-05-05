"""
backend/orchestrator.py
────────────────────────────────────────────────────────────────────────────
Orchestrates Phase 1 and Phase 2 execution, managing state and results.
"""

from __future__ import annotations

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Ensure imports work from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Phase 1 imports
from phase1_writers_room.graph.state import initial_state as phase1_initial_state
from phase1_writers_room.graph.workflow import build_graph as build_phase1_graph

# Phase 2 imports
from phase2_studio_floor.graph.state import initial_scene_state
from phase2_studio_floor.graph.workflow import build_scene_graph
from phase2_studio_floor.io import load_character_db, load_scene_manifest

# Shared imports
from shared.config.config import (
    BASE_DIR,
    CHARACTER_DB_PATH,
    SCENE_MANIFEST_PATH,
    USE_VIDEO_MODEL,
)

from backend.models import (
    Phase1Output, Phase2Output, Phase2SceneResult, PipelineStatus,
    Script, Scene, DialogueLine, Character
)


class PipelineOrchestrator:
    """
    Manages execution of Phase 1 and Phase 2, storing results and status.
    """
    
    def __init__(self):
        self.phase1_output: Optional[Phase1Output] = None
        self.phase2_output: Optional[Phase2Output] = None
        self.status = PipelineStatus()
        self._phase1_raw_state: Optional[dict] = None
        self._phase2_raw_state: Optional[dict] = None
        # Stores the intermediate state when pipeline pauses at HITL checkpoint
        self._phase1_interim_state: Optional[dict] = None
    
    def run_phase1(self, prompt: str, script_path: Optional[str] = None) -> Phase1Output:
        """
        Execute Phase 1 (Writer's Room) up to the HITL checkpoint.

        When gui_mode=True the graph pauses at the HITL node and returns
        state with status='awaiting_hitl'. The caller must then present the
        script to the user and call approve_hitl() to continue.

        Returns Phase1Output. If status=='awaiting_hitl', only the script
        field is populated; characters and images are empty until approved.
        """
        self.status.pipeline_running = True
        self.status.current_phase = "phase1"
        self.status.phase1_start_time = datetime.now().isoformat()
        self._phase1_interim_state = None

        try:
            if script_path:
                with open(script_path, "r", encoding="utf-8") as f:
                    raw_script = f.read()
                state = phase1_initial_state(script=raw_script)
            else:
                state = phase1_initial_state(prompt=prompt)

            # gui_mode=True means HITL node returns immediately instead of
            # blocking on stdin — the graph stops with status='awaiting_hitl'
            state["gui_mode"] = True

            graph = build_phase1_graph()
            final_state = graph.invoke(state)
            self._phase1_raw_state = final_state

            if final_state.get("status") == "awaiting_hitl":
                # Store intermediate state so approve_hitl() can resume it
                self._phase1_interim_state = final_state
                # Return a partial output — script present, characters/images empty
                return self._convert_phase1_state(final_state)

            # Pipeline completed without needing HITL (error or edge case)
            output = self._convert_phase1_state(final_state)
            if final_state.get("status") == "error":
                self.status.phase1_error = final_state.get("error")
            else:
                self.status.phase1_completed = True
            self.status.phase1_end_time = datetime.now().isoformat()
            self.phase1_output = output
            return output

        except Exception as e:
            error_msg = str(e)
            self.status.phase1_error = error_msg
            self.status.phase1_end_time = datetime.now().isoformat()
            self.status.pipeline_running = False
            self.status.current_phase = None
            raise RuntimeError(f"Phase 1 execution failed: {error_msg}") from e

    def approve_hitl(self, approved: bool) -> Phase1Output:
        """
        Resume Phase 1 after the user has reviewed the script.

        Args:
            approved: True to continue to character design, False to reject.

        Returns:
            Phase1Output with the complete results (or rejection status).
        """
        if not self._phase1_interim_state:
            raise RuntimeError("No HITL checkpoint is currently pending.")

        state = dict(self._phase1_interim_state)
        state["hitl_approved"] = approved
        state["status"] = "approved" if approved else "rejected"
        self._phase1_interim_state = None

        try:
            graph = build_phase1_graph()
            final_state = graph.invoke(state)
            self._phase1_raw_state = final_state

            output = self._convert_phase1_state(final_state)
            self.phase1_output = output

            if final_state.get("status") == "complete":
                self.status.phase1_completed = True
                self.status.phase1_error = None
            elif final_state.get("status") == "error":
                self.status.phase1_error = final_state.get("error")

            self.status.phase1_end_time = datetime.now().isoformat()
            self.status.pipeline_running = False
            self.status.current_phase = None
            return output

        except Exception as e:
            error_msg = str(e)
            self.status.phase1_error = error_msg
            self.status.phase1_end_time = datetime.now().isoformat()
            self.status.pipeline_running = False
            self.status.current_phase = None
            raise RuntimeError(f"Phase 1 HITL resume failed: {error_msg}") from e
    
    def run_phase2(self, scene_id: Optional[int] = None) -> Phase2Output:
        """
        Execute Phase 2 (Studio Floor) using Phase 1 outputs.
        
        Args:
            scene_id: If specified, process only this scene (1-based). If None, all scenes.
        
        Returns:
            Phase2Output: The structured output from Phase 2
        
        Raises:
            RuntimeError: If Phase 1 has not completed or Phase 2 execution fails
        """
        if not self.status.phase1_completed:
            raise RuntimeError("Phase 1 must be completed before running Phase 2")
        
        self.status.pipeline_running = True
        self.status.current_phase = "phase2"
        self.status.phase2_start_time = datetime.now().isoformat()
        
        try:
            # Load Phase 1 outputs (script and characters)
            manifest_path = BASE_DIR / SCENE_MANIFEST_PATH
            char_path = BASE_DIR / CHARACTER_DB_PATH
            
            if not manifest_path.is_file():
                raise FileNotFoundError(f"Missing scene manifest: {manifest_path}")
            if not char_path.is_file():
                raise FileNotFoundError(f"Missing character database: {char_path}")
            
            manifest = load_scene_manifest(manifest_path)
            character_db = load_character_db(char_path)
            
            scenes = manifest.get("scenes", [])
            if scene_id is not None:
                scenes = [s for s in scenes if int(s.get("scene_id", -1)) == scene_id]
                if not scenes:
                    raise ValueError(f"No scene with scene_id={scene_id}")
            
            # Build and run graph
            graph = build_scene_graph()
            results = []
            
            for scene in scenes:
                sid = int(scene.get("scene_id", 0))
                try:
                    state = initial_scene_state(scene, character_db)
                    
                    # Stream through graph updates
                    final_state = state
                    for update in graph.stream(state, stream_mode="updates"):
                        for node_name, node_update in update.items():
                            if node_update:
                                final_state.update(node_update)
                    
                    result = Phase2SceneResult(
                        scene_id=sid,
                        raw_mp4_path=final_state.get("raw_mp4_path"),
                        error=final_state.get("error")
                    )
                    results.append(result)
                    
                except Exception as e:
                    results.append(Phase2SceneResult(
                        scene_id=sid,
                        error=f"Scene processing failed: {str(e)}"
                    ))
            
            # Check if all scenes succeeded
            failed = [r for r in results if r.error]
            error_msg = None if not failed else f"{len(failed)} scenes failed"
            
            video_mode = "wan_i2v" if USE_VIDEO_MODEL else "pexels_stock"
            self.phase2_output = Phase2Output(
                scenes=results,
                error=error_msg,
                video_generation_mode=video_mode,
            )
            
            self.status.phase2_completed = not bool(failed)
            self.status.phase2_error = error_msg
            self.status.phase2_end_time = datetime.now().isoformat()
            
            return self.phase2_output
            
        except Exception as e:
            error_msg = str(e)
            self.status.phase2_error = error_msg
            self.status.phase2_end_time = datetime.now().isoformat()
            raise RuntimeError(f"Phase 2 execution failed: {error_msg}") from e
        
        finally:
            self.status.pipeline_running = False
            self.status.current_phase = None
    
    def run_full_pipeline(self, prompt: str) -> tuple[Phase1Output, Optional[Phase2Output]]:
        """
        Execute the full pipeline: Phase 1 followed by Phase 2.
        
        Args:
            prompt: Story idea for Phase 1
        
        Returns:
            Tuple of (Phase1Output, Phase2Output or None if Phase 2 fails)
        """
        # Run Phase 1
        phase1_result = self.run_phase1(prompt=prompt)
        
        if phase1_result.error:
            return phase1_result, None
        
        # Run Phase 2
        try:
            phase2_result = self.run_phase2()
            return phase1_result, phase2_result
        except Exception as e:
            self.status.phase2_error = str(e)
            return phase1_result, None
    
    def get_status(self) -> PipelineStatus:
        """Get current pipeline status."""
        return self.status
    
    def get_phase1_output(self) -> Optional[Phase1Output]:
        """Get Phase 1 results if available."""
        return self.phase1_output
    
    def get_phase2_output(self) -> Optional[Phase2Output]:
        """Get Phase 2 results if available."""
        return self.phase2_output
    
    def reset(self):
        """Reset orchestrator state for a new pipeline run."""
        self.phase1_output = None
        self.phase2_output = None
        self.status = PipelineStatus()
        self._phase1_raw_state = None
        self._phase2_raw_state = None
    
    @staticmethod
    def _convert_phase1_state(state: dict[str, Any]) -> Phase1Output:
        """
        Convert Phase 1 raw state to structured Phase1Output.
        
        Args:
            state: Raw state dict from Phase 1 workflow
        
        Returns:
            Phase1Output: Structured output
        """
        # Convert script to models
        script_data = state.get("script")
        script = None
        if script_data:
            scenes = []
            for scene_dict in script_data.get("scenes", []):
                dialogue = [
                    DialogueLine(
                        speaker=d.get("speaker", ""),
                        line=d.get("line", ""),
                        visual_cue=d.get("visual_cue")
                    )
                    for d in scene_dict.get("dialogue", [])
                ]
                scene = Scene(
                    scene_id=int(scene_dict.get("scene_id", 0)),
                    location=scene_dict.get("location", ""),
                    characters=scene_dict.get("characters", []),
                    dialogue=dialogue
                )
                scenes.append(scene)
            script = Script(scenes=scenes)
        
        # Convert characters to models
        characters = []
        for char_dict in state.get("characters", []):
            char = Character(
                name=char_dict.get("name", ""),
                personality_traits=char_dict.get("personality_traits", []),
                appearance_description=char_dict.get("appearance_description", ""),
                reference_style=char_dict.get("reference_style", ""),
                image_path=char_dict.get("image_path")
            )
            characters.append(char)
        
        # Images are paths; store as-is
        images = state.get("images", [])
        
        return Phase1Output(
            status=state.get("status", "unknown"),
            input_mode=state.get("input_mode", "unknown"),
            hitl_approved=state.get("hitl_approved", False),
            script=script,
            characters=characters,
            images=images,
            error=state.get("error")
        )


# Global orchestrator instance
_orchestrator = PipelineOrchestrator()


def get_orchestrator() -> PipelineOrchestrator:
    """Get the global orchestrator instance."""
    return _orchestrator
