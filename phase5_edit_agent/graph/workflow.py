"""LangGraph workflow for Phase 5 edit handling."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from phase5_edit_agent.agents.edit_executor import execute_edit, state_manager
from phase5_edit_agent.agents.intent_classifier import EditIntent, classify_intent
from phase5_edit_agent.graph.state import EditAgentState, log_event


def classify_node(state: EditAgentState) -> dict[str, Any]:
    query = state.get("query", "")
    log_event(state, "classify", f"Classifying edit request: {query}")
    intent = classify_intent(query)
    return {
        "classified_intent": intent.model_dump(),
        "status": "running",
    }


def validate_node(state: EditAgentState) -> dict[str, Any]:
    intent = EditIntent.model_validate(state.get("classified_intent", {}))
    if intent.confidence < 0.35:
        log_event(state, "validate", "Low confidence intent; returning clarification", "warning")
        return {"validation_status": "low_confidence"}
    log_event(state, "validate", f"Intent accepted: {intent.intent}", "success")
    return {"validation_status": "ready"}


def route_after_validate(state: EditAgentState) -> str:
    if state.get("validation_status") == "low_confidence":
        return "respond"
    return "execute"


def execute_node(state: EditAgentState) -> dict[str, Any]:
    intent = EditIntent.model_validate(state.get("classified_intent", {}))
    log_event(state, "execute", f"Executing {intent.target} edit: {intent.intent}")
    result = execute_edit(intent, state.get("current_state", {}), state_mgr=state_manager)
    return {
        "execution_result": result,
        "history": result.get("history", []),
    }


def snapshot_node(state: EditAgentState) -> dict[str, Any]:
    history = state_manager.history()
    log_event(state, "snapshot", f"Version history now has {len(history)} record(s)", "success")
    return {"history": history}


def respond_node(state: EditAgentState) -> dict[str, Any]:
    intent = state.get("classified_intent", {})
    validation = state.get("validation_status")
    if validation == "low_confidence":
        response = "The edit request was too ambiguous. Please rephrase it with a clearer target."
    else:
        response = f"Edit executed: {intent.get('intent', 'unknown')} ({intent.get('target', 'unknown')})"
    log_event(state, "respond", response, "success")
    return {"response": response, "status": "complete"}


def build_edit_graph():
    graph = StateGraph(EditAgentState)
    graph.add_node("classify", classify_node)
    graph.add_node("validate", validate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("snapshot", snapshot_node)
    graph.add_node("respond", respond_node)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "execute": "execute",
            "respond": "respond",
        },
    )
    graph.add_edge("execute", "snapshot")
    graph.add_edge("snapshot", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
