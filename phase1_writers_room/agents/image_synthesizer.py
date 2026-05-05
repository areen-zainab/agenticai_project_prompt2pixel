"""
agents/image_synthesizer.py
────────────────────────────────────────────────────────────────────────────
Image Synthesizer Agent

For each character in state["characters"], calls the MCP tool
generate_character_image (which internally tries SD → Hugging Face → stub).
Updates character["image_path"] and populates state["images"].
"""

from shared.mcp_server.client import invoke_tool
from shared.mcp_server.client import discover_tool
from phase1_writers_room.graph.state import AgentState, add_event


# ─────────────────────────────────────────────────────────────────────────────
# Agent entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(state: AgentState) -> AgentState:
    """
    Image Synthesizer Agent entry point.

    Expects:
        state["characters"] — list of Character TypedDicts (with appearance_description)

    Produces:
        state["characters"] — updated with image_path per character
        state["images"]     — list of image file path strings
        state["status"]     — "generating_images"
    """
    characters = state.get("characters", [])
    if not characters:
        add_event(state, agent="image_synthesizer", level="warning", message="No characters found. Skipping image generation.")
        state["status"] = "generating_images"
        return state

    state["status"] = "generating_images"
    image_paths: list[str] = []

    tool_schema = discover_tool("generate_character_image")
    if tool_schema is None:
        state["status"] = "error"
        state["error"] = "MCP tool 'generate_character_image' not found in registry."
        add_event(state, agent="image_synthesizer", level="error", message=state["error"])
        return state

    for i, char in enumerate(characters):
        name        = char.get("name", f"character_{i}")
        description = char.get("appearance_description", "")
        style       = char.get("reference_style", "")
        full_desc   = f"{description} Style: {style}".strip()

        add_event(state, agent="image_synthesizer", message=f"Generating image: {name}")
        try:
            result = invoke_tool(
                "generate_character_image",
                {
                    "description": full_desc,
                    "character_name": name,
                },
                timeout=120,
            )
            img_path = result.get("image_path", "")
            is_stub  = result.get("stub", False)

            if img_path:
                char["image_path"] = img_path
                image_paths.append(img_path)
                add_event(
                    state,
                    agent="image_synthesizer",
                    level="success",
                    message=f"Image ready: {name}" + (" (stub)" if is_stub else ""),
                    data={"path": img_path},
                )
            else:
                add_event(state, agent="image_synthesizer", level="warning", message=f"No image path returned for {name}.")

        except Exception as e:
            add_event(
                state,
                agent="image_synthesizer",
                level="warning",
                message=f"Failed to generate image for {name}.",
                data={"error": str(e)},
            )

    state["characters"] = characters
    state["images"]     = image_paths
    add_event(
        state,
        agent="image_synthesizer",
        level="success",
        message=f"{len(image_paths)} image(s) generated.",
    )
    return state
