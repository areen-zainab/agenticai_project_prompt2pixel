"""
phase1_writers_room/main.py
──────────────────────────────────────────────────────────────────────────────
Streamlit entry-point for Project Montage Phase 1 — The Writer's Room.

Run:
    streamlit run phase1_writers_room/main.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

from phase1_writers_room.graph.state import initial_state, Event
from phase1_writers_room.graph.workflow import build_graph
from phase1_writers_room.gui import (
    _render_html, _esc,
    apply_styles, render_sidebar, banner, section_label,
    pipeline_strip, render_script, render_characters,
)

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Project Montage — Writer's Room",
    layout="centered",
    initial_sidebar_state="collapsed",
)

apply_styles()
render_sidebar()

# ── Session state defaults ────────────────────────────────────────────────────
defaults = {
    "state": None,
    "processing": False,
    "mode": "Auto (Prompt)",
    "prompt_value": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reset():
    st.session_state.state = None
    st.session_state.processing = False
    st.rerun()


def render_events(events: list[Event]) -> None:
    """Render agent activity as a compact timeline."""
    if not events:
        return

    level_color = {
        "info":    "var(--blue)",
        "success": "var(--green)",
        "warning": "var(--gold)",
        "error":   "var(--red)",
    }

    rows_html = []
    for e in events[-60:]:  # show last 60 entries
        lvl   = e.get("level", "info")
        color = level_color.get(lvl, "var(--muted)")
        ts    = e.get("ts", "")[-8:]   # HH:MM:SS portion only
        agent = e.get("agent", "")
        msg   = _esc(e.get("message", ""))
        rows_html.append(
            '<div class="pm-event">'
            f'<div class="pm-event-dot {lvl}" style="background:{color}"></div>'
            '<div class="pm-event-body">'
            f'<div class="pm-event-agent">{_esc(agent)}</div>'
            f'<div class="pm-event-msg">{msg}</div>'
            '</div>'
            f'<div class="pm-event-ts">{_esc(ts)}</div>'
            '</div>'
        )

    with st.expander("🧾  Agent activity log", expanded=False):
        _render_html(
            '<div style="padding:4px 0;">'
            + "".join(rows_html) +
            '</div>'
        )


# ── Hero ──────────────────────────────────────────────────────────────────────
_render_html("""
<div class="pm-hero">
<div class="pm-eyebrow">Project Montage &nbsp;·&nbsp; Phase 1</div>
<div class="pm-hero-title">The Writer's Room</div>
<div class="pm-hero-sub">
Transform a story idea into a fully structured screenplay, character profiles,
and AI-generated visuals — orchestrated by a multi-agent LangGraph pipeline.
</div>
</div>
""")

# ── Mode selector ─────────────────────────────────────────────────────────────
with st.expander("⚙️  Input mode", expanded=not st.session_state.processing):
    mode = st.radio(
        "How should the pipeline receive source material?",
        options=["Auto (Prompt)", "Manual (Upload)"],
        index=0 if st.session_state.mode == "Auto (Prompt)" else 1,
        horizontal=True,
        help="Auto: AI generates a screenplay from your idea.  Manual: upload an existing .txt script.",
    )
    st.session_state.mode = mode

# ── Input form (only shown when not processing) ───────────────────────────────
if not st.session_state.processing and st.session_state.state is None:
    section_label("1", "Story Input")

    if st.session_state.mode == "Auto (Prompt)":
        prompt = st.text_area(
            "Describe your story idea",
            value=st.session_state.prompt_value,
            placeholder=(
                "A sci-fi noir about a detective investigating a robot's disappearance "
                "in a rain-soaked, neon-lit city where machines are fighting for civil rights…"
            ),
            height=130,
            help="The Scriptwriter agent will craft a multi-scene screenplay from your concept.",
            key="prompt_input",
        )
        col_btn, col_hint = st.columns([1, 2], gap="medium")
        with col_btn:
            clicked = st.button(
                "Generate Script →",
                type="primary",
                use_container_width=True,
                key="go_btn",
            )
        with col_hint:
            _render_html(
                '<p style="font-size:.75rem;color:var(--muted);padding-top:13px;margin:0;">'
                'Agents collaborate to produce screenplay + character assets.'
                '</p>'
            )

        if clicked:
            if prompt and prompt.strip():
                st.session_state.prompt_value = prompt
                new_state = initial_state(prompt=prompt.strip())
                new_state["gui_mode"] = True
                st.session_state.state = new_state
                st.session_state.processing = True
                st.rerun()
            else:
                st.warning("Please describe your story idea before generating.")

    else:
        uploaded = st.file_uploader(
            "Upload your screenplay (.txt)",
            type=["txt"],
            help="Plain-text screenplay — the pipeline will validate, parse, and enrich it.",
        )
        col_btn, col_hint = st.columns([1, 2], gap="medium")
        with col_btn:
            clicked = st.button(
                "Validate & Run →",
                type="primary",
                use_container_width=True,
                key="go_btn_manual",
            )
        with col_hint:
            _render_html(
                '<p style="font-size:.75rem;color:var(--muted);padding-top:13px;margin:0;">'
                'Script will be validated, characters extracted, and images generated.'
                '</p>'
            )

        if clicked:
            if uploaded:
                raw_script = uploaded.read().decode("utf-8")
                new_state = initial_state(script=raw_script)
                new_state["gui_mode"] = True
                st.session_state.state = new_state
                st.session_state.processing = True
                st.rerun()
            else:
                st.warning("Please upload a .txt screenplay file.")


# ── Pipeline execution (when processing=True) ─────────────────────────────────
if st.session_state.processing and st.session_state.state:

    # Show disabled button so user sees the click was registered
    section_label("1", "Story Input")
    col_btn, col_hint = st.columns([1, 2], gap="medium")
    with col_btn:
        st.button(
            "⏳  Running pipeline…",
            disabled=True,
            type="primary",
            use_container_width=True,
        )
    with col_hint:
        _render_html(
            '<p style="font-size:.75rem;color:var(--muted);padding-top:13px;margin:0;">'
            'The pipeline is running. This usually takes 15–60 seconds.'
            '</p>'
        )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Pipeline progress strip (always visible — no scrolling needed)
    pipeline_strip(active=1)

    # Run the graph
    with st.spinner("Agents collaborating — please wait…"):
        graph = build_graph()
        result = graph.invoke(st.session_state.state)

    st.session_state.state = result
    st.session_state.processing = False
    st.rerun()


# ── Results ───────────────────────────────────────────────────────────────────
if st.session_state.state and not st.session_state.processing:
    state = st.session_state.state

    _render_html('<hr>')

    # Activity log (collapsed by default — available for inspection)
    render_events(state.get("events", []))

    # ── A: Error ──
    if state["status"] == "error":
        banner("error", "⚠️", "Pipeline Error",
               state.get("error", "An unknown error occurred."))
        if st.button("← Start Over", type="secondary", key="restart_err"):
            _reset()

    # ── B: HITL ──
    elif state["status"] == "awaiting_hitl":
        pipeline_strip(active=4)
        banner(
            "warn", "👤",
            "Your Review is Required",
            "The script has been generated. Read it carefully below — approve to "
            "continue to character design, or reject to start over with a new idea.",
        )

        section_label("2", "Generated Script")
        render_script(state.get("script", {}))

        _render_html('<div style="height:8px"></div>')
        col_a, col_r = st.columns(2, gap="medium")
        with col_a:
            if st.button("✅  Approve & Continue", type="primary",
                         use_container_width=True, key="hitl_approve"):
                state["hitl_approved"] = True
                state["status"] = "approved"
                st.session_state.processing = True
                st.rerun()
        with col_r:
            if st.button("✕  Reject — Start Over", type="secondary",
                         use_container_width=True, key="hitl_reject"):
                state["hitl_approved"] = False
                state["status"] = "rejected"
                st.rerun()

    # ── C: Rejected ──
    elif state["status"] == "rejected":
        banner("error", "✕", "Script Rejected",
               "The script did not meet your requirements. Adjust your prompt and try again.")
        if st.button("← Start Over", type="primary", key="restart_rej"):
            _reset()

    # ── D: Complete ──
    elif state["status"] == "complete":
        pipeline_strip(active=5)
        banner(
            "success", "✓", "Phase 1 Complete",
            "All agents finished. Your screenplay, character database, and image assets are ready.",
        )

        # Output file chips
        _render_html("""
<div class="pm-outputs">
<div class="pm-chip">
<span class="cicon">📄</span>
<div class="cname">scene_manifest.json</div>
<div class="cdesc">Structured screenplay</div>
</div>
<div class="pm-chip">
<span class="cicon">🗂️</span>
<div class="cname">character_db.json</div>
<div class="cdesc">Character identity store</div>
</div>
<div class="pm-chip">
<span class="cicon">🖼️</span>
<div class="cname">image_assets/</div>
<div class="cdesc">AI-generated visuals</div>
</div>
</div>
""")

        section_label("3", "Final Screenplay")
        render_script(state.get("script", {}))

        section_label("4", "Character Profiles")
        render_characters(state.get("characters", []))

        _render_html('<div style="height:16px"></div>')
        if st.button("← Reset Pipeline", type="secondary", key="reset_complete"):
            st.session_state.prompt_value = ""
            _reset()
