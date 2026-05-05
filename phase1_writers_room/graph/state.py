from typing import TypedDict, Optional, Literal, Any


class ScriptScene(TypedDict):
    scene_id: int
    location: str
    characters: list[str]
    dialogue: list[dict]          # [{speaker, line, visual_cue}]


class Script(TypedDict):
    scenes: list[ScriptScene]


class Character(TypedDict):
    name: str
    personality_traits: list[str]
    appearance_description: str
    reference_style: str
    image_path: Optional[str]     # filled in by image_synthesizer


class Event(TypedDict):
    ts: str
    level: Literal["info", "success", "warning", "error"]
    agent: str
    message: str
    data: dict[str, Any]


class AgentState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────────────
    input_mode: Literal["auto", "manual"]   # set by mode_selector_node
    raw_prompt: Optional[str]               # used in auto mode
    raw_script: Optional[str]               # used in manual mode
    gui_mode: bool                          # if True, HITL happens in Streamlit UI

    # ── Pipeline data ────────────────────────────────────────────────────────
    script: Optional[Script]               # populated by scriptwriter / validator
    characters: list[Character]            # populated by character_designer
    images: list[str]                      # file paths, populated by image_synthesizer

    # ── Control flow ─────────────────────────────────────────────────────────
    status: Literal[
        "pending",
        "validating",
        "generating_script",
        "awaiting_hitl",
        "approved",
        "rejected",
        "designing_characters",
        "generating_images",
        "committing_memory",
        "complete",
        "error",
    ]
    hitl_approved: Optional[bool]          # set by hitl_node
    error: Optional[str]                   # set on any failure
    events: list[Event]                    # UI-visible agent updates


def initial_state(
    prompt: str | None = None,
    script: str | None = None,
) -> AgentState:
    """
    Returns a clean starting state.
    Pass either prompt (auto mode) or script (manual mode), not both.
    """
    if prompt and script:
        raise ValueError("Provide either prompt or script, not both.")
    if not prompt and not script:
        raise ValueError("Provide at least one of: prompt, script.")

    return AgentState(
        input_mode="auto" if prompt else "manual",
        raw_prompt=prompt,
        raw_script=script,
        gui_mode=False,
        script=None,
        characters=[],
        images=[],
        status="pending",
        hitl_approved=None,
        error=None,
        events=[],
    )


def add_event(
    state: AgentState,
    *,
    agent: str,
    message: str,
    level: Literal["info", "success", "warning", "error"] = "info",
    data: dict[str, Any] | None = None,
) -> None:
    """
    Append a UI-visible event entry into state["events"].
    Agents should prefer this over print() so Streamlit can render progress.
    """
    from datetime import datetime, timezone

    if "events" not in state or state["events"] is None:
        state["events"] = []
    state["events"].append(
        Event(
            ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            level=level,
            agent=agent,
            message=message,
            data=data or {},
        )
    )