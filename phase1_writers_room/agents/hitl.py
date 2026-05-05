"""
agents/hitl.py
────────────────────────────────────────────────────────────────────────────
Human-in-the-Loop (HITL) Agent

Pauses the pipeline, renders the draft script to the console in a readable
format, and waits for the user to approve or reject before continuing.
"""

import json

from phase1_writers_room.graph.state import AgentState
from phase1_writers_room.graph.state import add_event


# ─────────────────────────────────────────────────────────────────────────────
# Rendering helpers
# ─────────────────────────────────────────────────────────────────────────────

def _render_script(script: dict) -> str:
    """Pretty-print the script dict as a human-readable screenplay excerpt."""
    lines = []
    scenes = script.get("scenes", [])
    for scene in scenes:
        lines.append(f"\n{'─' * 60}")
        lines.append(f"  Scene {scene.get('scene_id', '?')} | {scene.get('location', '')}")
        lines.append(f"{'─' * 60}")
        chars = ", ".join(scene.get("characters", []))
        if chars:
            lines.append(f"  Characters: {chars}")
        for entry in scene.get("dialogue", []):
            lines.append(f"\n  {entry.get('speaker', 'UNKNOWN')}")
            lines.append(f"    \"{entry.get('line', '')}\"")
            cue = entry.get("visual_cue", "")
            if cue:
                lines.append(f"    ({cue})")
    lines.append(f"\n{'─' * 60}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Agent entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(state: AgentState) -> AgentState:
    """
    HITL Agent entry point.

    Expects:
        state["script"] — Script TypedDict to review

    Produces:
        state["hitl_approved"] — True or False
        state["status"]        — "approved" or "rejected"
    """
    add_event(state, agent="hitl", message="Human review checkpoint reached.")

    script = state.get("script")
    if not script or not script.get("scenes"):
        # Script generation failed upstream — propagate the error, do NOT auto-approve.
        error_msg = state.get("error") or "Script generation failed — no script available for review."
        add_event(state, agent="hitl", level="error", message=error_msg)
        state["status"] = "error"
        state["error"]  = error_msg
        return state

    # If the UI already set an approval decision, don't block / ask again.
    if state.get("hitl_approved") is True:
        state["status"] = "approved"
        add_event(state, agent="hitl", level="success", message="Script approved (UI). Continuing pipeline.")
        return state
    if state.get("hitl_approved") is False:
        state["status"] = "rejected"
        add_event(state, agent="hitl", level="error", message="Script rejected (UI). Stopping pipeline.")
        return state

    state["status"] = "awaiting_hitl"

    # Render draft script to console
    add_event(
        state,
        agent="hitl",
        message="Draft script ready for review.",
        data={"script_preview": _render_script(script)[:4000]},
    )

    # ── Approval loop ─────────────────────────────────────────────────────────
    # If in GUI mode, we just return the state as is (status = awaiting_hitl)
    # The GUI will handle the approval and re-invoke the graph.
    if state.get("gui_mode"):
        add_event(state, agent="hitl", message="Awaiting approval via Streamlit UI…")
        return state

    while True:
        try:
            answer = input("  Approve this script? [y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Non-interactive environment — auto-approve
            add_event(state, agent="hitl", level="warning", message="Non-interactive mode detected — auto-approving.")
            answer = "y"

        if answer in ("y", "yes"):
            state["hitl_approved"] = True
            state["status"]        = "approved"
            add_event(state, agent="hitl", level="success", message="Script approved. Continuing pipeline.")
            break

        elif answer in ("n", "no"):
            try:
                reason = input("  Rejection reason (optional): ").strip()
            except (EOFError, KeyboardInterrupt):
                reason = "No reason provided."
            state["hitl_approved"] = False
            state["status"]        = "rejected"
            add_event(
                state,
                agent="hitl",
                level="error",
                message="Script rejected. Pipeline will stop.",
                data={"reason": reason or "None given."},
            )
            break

        else:
            add_event(state, agent="hitl", level="warning", message="Invalid input. Please enter 'y' or 'n'.")

    return state
