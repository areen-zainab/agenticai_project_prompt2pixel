"""
agents/validator.py
────────────────────────────────────────────────────────────────────────────
Script Validator Agent — Manual mode only

Performs rule-based structural checks on a manually uploaded plain-text
script. If valid, parses it into a Script TypedDict and populates
state["script"]. If invalid, sets state["status"] = "error" with
detailed correction suggestions.
"""

import re

from phase1_writers_room.graph.state import AgentState, Script, ScriptScene
from shared.config.config import SCENE_MANIFEST_PATH
from phase1_writers_room.graph.state import add_event
import json


# ─────────────────────────────────────────────────────────────────────────────
# Validation rules
# ─────────────────────────────────────────────────────────────────────────────

# Matches: "INT. SPACESHIP - DAY", "EXT. ROOFTOP - NIGHT", "SCENE 1", "SCENE ONE"
SCENE_HEADING_RE = re.compile(
    r"^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s+.+|^SCENE\s+\d+",
    re.IGNORECASE | re.MULTILINE,
)

# Matches dialogue labels: "ALEX" or "ALEX (V.O.)" alone on a line
DIALOGUE_LABEL_RE = re.compile(
    r"^\s{0,4}([A-Z][A-Z\s']{1,30})(\s*\(.*?\))?\s*$",
    re.MULTILINE,
)

# An action line is any non-empty line that isn't a heading or dialogue label
ACTION_LINE_RE = re.compile(r"^\s{0,2}\S.*", re.MULTILINE)


def _check_scene_headings(text: str) -> list[str]:
    headings = SCENE_HEADING_RE.findall(text)
    if not headings:
        return [
            "No scene headings found. "
            "Each scene must start with INT., EXT., INT/EXT., or SCENE N."
        ]
    return []


def _check_dialogue(text: str) -> list[str]:
    labels = DIALOGUE_LABEL_RE.findall(text)
    if not labels:
        return [
            "No dialogue labels detected. "
            "Dialogue must be preceded by a character name on its own line (e.g., 'ALEX')."
        ]
    return []


def _check_action_lines(text: str) -> list[str]:
    # Split by scene headings and verify each scene has some action text
    scenes = SCENE_HEADING_RE.split(text)
    missing = []
    for i, chunk in enumerate(scenes[1:], start=1):  # skip text before first heading
        non_empty = [l for l in chunk.splitlines() if l.strip()]
        has_action = any(
            not DIALOGUE_LABEL_RE.match(l) and not SCENE_HEADING_RE.match(l)
            for l in non_empty
        )
        if not has_action:
            missing.append(f"Scene {i} has no action/description lines.")
    return missing


# ─────────────────────────────────────────────────────────────────────────────
# Script parser (best-effort conversion of plain text → Script TypedDict)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_script(text: str) -> Script:
    """
    Lightly parses a plain-text screenplay into the Script TypedDict.
    This is not a full screenplay parser — it extracts enough structure
    for downstream agents to work with.
    """
    scenes: list[ScriptScene] = []
    # Split on scene headings
    parts = re.split(r"(?m)^((?:INT\.|EXT\.|INT/EXT\.|I/E\.|SCENE\s+\d+)[^\n]*)", text)

    scene_id = 0
    i = 1
    while i < len(parts):
        heading = parts[i].strip()
        body    = parts[i + 1] if i + 1 < len(parts) else ""
        i += 2
        scene_id += 1

        dialogue: list[dict] = []
        characters_in_scene: set[str] = set()

        lines = body.splitlines()
        j = 0
        while j < len(lines):
            line = lines[j]
            label_match = DIALOGUE_LABEL_RE.match(line)
            if label_match:
                speaker = label_match.group(1).strip()
                characters_in_scene.add(speaker)
                # Next non-empty line(s) are the actual dialogue
                spoken = []
                visual_cue = ""
                j += 1
                while j < len(lines):
                    dl = lines[j].strip()
                    if not dl:
                        j += 1
                        break
                    # Parenthetical cue inside dialogue block
                    if dl.startswith("(") and dl.endswith(")"):
                        visual_cue = dl.strip("()")
                    else:
                        spoken.append(dl)
                    j += 1
                if spoken:
                    dialogue.append({
                        "speaker":    speaker,
                        "line":       " ".join(spoken),
                        "visual_cue": visual_cue or f"{speaker} speaks.",
                    })
                continue
            j += 1

        scenes.append(ScriptScene(
            scene_id=scene_id,
            location=heading,
            characters=sorted(characters_in_scene),
            dialogue=dialogue,
        ))

    return Script(scenes=scenes)


# ─────────────────────────────────────────────────────────────────────────────
# Agent entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(state: AgentState) -> AgentState:
    """
    Script Validator Agent entry point.

    Expects:
        state["raw_script"] — plain text content of the uploaded script
        state["input_mode"] == "manual"

    Produces (on success):
        state["script"]  — parsed Script TypedDict
        state["status"]  — "validating"

    Produces (on failure):
        state["status"]  — "error"
        state["error"]   — structured correction suggestions
    """
    raw = state.get("raw_script", "")
    if not raw or not raw.strip():
        state["status"] = "error"
        state["error"]  = "Uploaded script is empty."
        add_event(state, agent="validator", level="error", message=state["error"])
        return state

    state["status"] = "validating"
    add_event(state, agent="validator", message="Running structural checks on uploaded script…")

    errors: list[str] = []
    errors += _check_scene_headings(raw)
    errors += _check_dialogue(raw)
    errors += _check_action_lines(raw)

    if errors:
        add_event(
            state,
            agent="validator",
            level="warning",
            message="Validation failed. Fetching correction suggestions via MCP…",
            data={"errors": errors},
        )
        from shared.mcp_server.client import discover_tool, invoke_tool

        try:
            tool_schema = discover_tool("suggest_script_corrections")
            if tool_schema is None:
                raise RuntimeError("MCP tool 'suggest_script_corrections' not found in registry.")
            out = invoke_tool(
                "suggest_script_corrections",
                {"raw_script": raw, "detected_errors": errors},
                timeout=120,
            )
            suggestions = (out or {}).get("suggestions", "").strip()
            if suggestions:
                state["error"] = "Script validation failed.\n\nRequired corrections:\n" + suggestions
            else:
                state["error"] = "Script validation failed. Please fix scene headings and dialogue labels."
        except Exception as e:
            suggestions = "\n".join(f"  • {e}" for e in errors)
            state["error"] = "Script validation failed. Correction suggestions:\n" + suggestions
            add_event(
                state,
                agent="validator",
                level="warning",
                message="Could not fetch LLM suggestions (MCP). Falling back to rule errors.",
                data={"error": str(e)},
            )
            
        state["status"] = "error"
        add_event(state, agent="validator", level="error", message="Validation failed.")
        return state

    add_event(state, agent="validator", level="success", message="All checks passed. Parsing script…")
    state["script"] = _parse_script(raw)
    add_event(
        state,
        agent="validator",
        level="success",
        message=f"Parsed {len(state['script']['scenes'])} scene(s).",
    )

    # Persist standardized JSON to disk (deliverable parity with auto mode)
    SCENE_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCENE_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(state["script"], f, indent=2)
    add_event(
        state,
        agent="validator",
        level="success",
        message="scene_manifest.json written (manual mode).",
        data={"path": str(SCENE_MANIFEST_PATH)},
    )
    return state
