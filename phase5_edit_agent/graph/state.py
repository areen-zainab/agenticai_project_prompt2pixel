"""Typed state for the Phase 5 edit workflow."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

_LOCK = threading.Lock()


class EditAgentEvent(TypedDict):
    ts: str
    level: Literal["info", "success", "warning", "error"]
    agent: str
    message: str


class EditAgentState(TypedDict, total=False):
    query: str
    current_state: dict[str, Any]
    classified_intent: dict[str, Any]
    validation_status: Literal["ready", "low_confidence", "invalid"]
    execution_result: dict[str, Any]
    response: str
    history: list[dict[str, Any]]
    status: Literal["pending", "running", "complete", "error"]
    error: str
    events: list[EditAgentEvent]


def log_event(
    state: EditAgentState,
    agent: str,
    message: str,
    level: Literal["info", "success", "warning", "error"] = "info",
) -> None:
    color = {
        "info": "\033[94m",
        "success": "\033[92m",
        "warning": "\033[93m",
        "error": "\033[91m",
    }.get(level, "")
    reset = "\033[0m"
    tag = f"[{agent.replace('_', ' ').title()}]"
    print(f"{color}{tag:22} {message}{reset}")

    with _LOCK:
        if "events" not in state or state["events"] is None:
            state["events"] = []
        state["events"].append(
            EditAgentEvent(
                ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                level=level,
                agent=agent,
                message=message,
            )
        )


def initial_edit_state(query: str, current_state: dict[str, Any]) -> EditAgentState:
    return EditAgentState(
        query=query,
        current_state=current_state,
        status="pending",
        events=[],
    )
