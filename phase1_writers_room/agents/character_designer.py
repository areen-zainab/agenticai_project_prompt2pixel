"""
agents/character_designer.py
────────────────────────────────────────────────────────────────────────────
Character Designer Agent

Parses the approved script, extracts all unique characters, and builds
full identity profiles via the LLM (called through MCP commit_memory tool).
Writes character_db.json and stores each character in ChromaDB.
"""

import json

from shared.config.config import CHARACTER_DB_PATH
from shared.mcp_server.client import discover_tool, invoke_tool
from phase1_writers_room.graph.state import AgentState, Character, add_event


# ─────────────────────────────────────────────────────────────────────────────
# Character extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_character_names(script: dict) -> list[str]:
    """Collect all unique character names from the script's dialogue entries."""
    names: set[str] = set()
    for scene in script.get("scenes", []):
        for entry in scene.get("dialogue", []):
            speaker = entry.get("speaker", "").strip()
            if speaker:
                names.add(speaker)
        # Also include characters listed in the scene's characters field
        for char in scene.get("characters", []):
            names.add(char.strip())
    return sorted(names)


def _build_character_profile(name: str, scenes_context: str) -> Character:
    """Generate a character profile via MCP tool (no direct LLM calls)."""
    tool_schema = discover_tool("generate_character_profile")
    if tool_schema is None:
        raise RuntimeError("MCP tool 'generate_character_profile' not found in registry.")

    data = invoke_tool(
        "generate_character_profile",
        {"name": name, "scenes_context": scenes_context},
        timeout=120,
    )

    return Character(
        name=data.get("name", name),
        personality_traits=data.get("personality_traits", []),
        appearance_description=data.get("appearance_description", ""),
        reference_style=data.get("reference_style", ""),
        image_path=None,
    )


def _scenes_for_character(name: str, script: dict) -> str:
    """Extract all dialogue lines by this character for LLM context."""
    lines = []
    for scene in script.get("scenes", []):
        if name in scene.get("characters", []):
            location = scene.get("location", "")
            lines.append(f"[{location}]")
            for entry in scene.get("dialogue", []):
                if entry.get("speaker") == name:
                    lines.append(f'  {name}: "{entry.get("line", "")}"')
                    if entry.get("visual_cue"):
                        lines.append(f'  ({entry["visual_cue"]})')
    return "\n".join(lines) if lines else f"{name} appears in the script."


# ─────────────────────────────────────────────────────────────────────────────
# Agent entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(state: AgentState) -> AgentState:
    """
    Character Designer Agent entry point.

    Expects:
        state["script"] — approved Script TypedDict

    Produces:
        state["characters"] — list of Character TypedDicts
        state["status"]     — "designing_characters"
    """
    script = state.get("script")
    if not script:
        state["status"] = "error"
        state["error"]  = "No script found for character extraction."
        add_event(state, agent="character_designer", level="error", message=state["error"])
        return state

    state["status"] = "designing_characters"
    names = _extract_character_names(script)
    add_event(
        state,
        agent="character_designer",
        message=f"Found {len(names)} character(s): {', '.join(names) if names else '(none)'}",
    )

    characters: list[Character] = []

    for name in names:
        add_event(state, agent="character_designer", message=f"Building profile: {name}")
        scenes_ctx = _scenes_for_character(name, script)

        try:
            profile = _build_character_profile(name, scenes_ctx)
        except Exception as e:
            add_event(
                state,
                agent="character_designer",
                level="warning",
                message=f"Profile generation failed for {name}. Using fallback.",
                data={"error": str(e)},
            )
            profile = Character(
                name=name,
                personality_traits=["mysterious", "determined"],
                appearance_description=f"{name} is a key character in the story.",
                reference_style="cinematic realism",
                image_path=None,
            )

        characters.append(profile)
        add_event(
            state,
            agent="character_designer",
            level="success",
            message=f"Profile ready: {profile['name']}",
            data={"traits": profile.get("personality_traits", [])},
        )

        # Commit character to vector memory via MCP
        try:
            tool_schema = discover_tool("commit_memory")
            if tool_schema is None:
                raise RuntimeError("MCP tool 'commit_memory' not found in registry.")

            memory_text = (
                f"Character: {profile['name']}. "
                f"Traits: {', '.join(profile['personality_traits'])}. "
                f"Appearance: {profile['appearance_description']}"
            )
            invoke_tool(
                "commit_memory",
                {
                    "text": memory_text,
                    "metadata": {"type": "character", "name": profile["name"]},
                    "doc_id": f"char_{name.lower().replace(' ', '_')}",
                },
                timeout=120,
            )
        except Exception as e:
            add_event(
                state,
                agent="character_designer",
                level="warning",
                message=f"Memory commit failed for {name}.",
                data={"error": str(e)},
            )

    state["characters"] = characters

    # Write character_db.json
    CHARACTER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHARACTER_DB_PATH, "w", encoding="utf-8") as f:
        json.dump({"characters": characters}, f, indent=2)
    add_event(
        state,
        agent="character_designer",
        level="success",
        message=f"character_db.json written ({len(characters)} character(s))",
        data={"path": str(CHARACTER_DB_PATH)},
    )

    return state
