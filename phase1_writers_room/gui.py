"""
phase1_writers_room/gui.py
──────────────────────────────────────────────────────────────────────────────
Reusable UI components for the Project Montage Streamlit app.

Important: ALL HTML passed to st.markdown must start at column-0 with no
leading whitespace.  In CommonMark (which Streamlit uses), lines indented by
4+ spaces are treated as fenced code blocks, causing raw HTML to print on
screen.  Use _render_html() everywhere instead of calling st.markdown directly
with HTML strings.
"""

import base64
import html as _html_lib
import os
import textwrap

import streamlit as st


# ── Helpers ───────────────────────────────────────────────────────────────────

def _render_html(markup: str) -> None:
    """
    Render raw HTML safely.
    Uses textwrap.dedent + strip so the first character is always '<',
    preventing the Markdown parser from interpreting indented HTML as a
    code block.
    """
    st.markdown(textwrap.dedent(markup).strip(), unsafe_allow_html=True)


def _esc(value) -> str:
    """HTML-escape a dynamic value before embedding it in an HTML template."""
    return _html_lib.escape(str(value) if value is not None else "")


def _img_b64(path: str) -> str | None:
    """Return a base64 data-URI for an image file, or None on failure."""
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        ext = os.path.splitext(path)[1].lstrip(".").lower() or "png"
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64,{data}"
    except Exception:
        return None


# ── Global styles ─────────────────────────────────────────────────────────────

def apply_styles() -> None:
    """Inject the shared CSS design system."""
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Inter:wght@300;400;500;600&display=swap');

:root {
    --bg:        #F5F2ED;
    --surface:   #FFFFFF;
    --surface2:  #FAF8F5;
    --border:    #DDD9D2;
    --border2:   #EBE7E1;
    --ink:       #18150F;
    --ink2:      #4A4540;
    --muted:     #837D76;
    --accent:    #B84A1E;
    --accent-lt: #F7EAE4;
    --blue:      #1E4476;
    --blue-lt:   #EBF0F9;
    --green:     #245C3E;
    --green-lt:  #E2F0E9;
    --red:       #8C1F1F;
    --red-lt:    #FAEAEA;
    --gold:      #9B7D3A;
    --gold-lt:   #FBF4E4;
    --r:         8px;
    --r-lg:      14px;
    --shadow-sm: 0 1px 4px rgba(24,21,15,.07);
    --shadow:    0 3px 16px rgba(24,21,15,.09);
    --ff-display: 'Cormorant Garamond', Georgia, serif;
    --ff-body:    'Inter', system-ui, sans-serif;
    --trans:      all .18s cubic-bezier(.4,0,.2,1);
}

*, *::before, *::after { box-sizing: border-box; }

/* ── App background & font ───────────────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main .block-container {
    background: var(--bg) !important;
    font-family: var(--ff-body) !important;
    color: var(--ink) !important;
}

/* Let Streamlit's centred layout control the width.
   Only override padding — no hard max-width that fights sidebar. */
.main .block-container {
    padding: 0 2rem 48px !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer { visibility: hidden !important; height: 0 !important; }
[data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--ink) !important; }
[data-testid="stSidebar"] code,
[data-testid="stSidebar"] pre {
    color: #E8E3DB !important;
    background: #2A2520 !important;
    border-radius: var(--r) !important;
}
[data-testid="stSidebar"] .stMarkdown p {
    font-size: .84rem !important;
    line-height: 1.65 !important;
    color: var(--ink2) !important;
}

/* ── Widget labels (fix "not visible" issue) ─────────────────────── */
.stTextArea label,
.stFileUploader label,
.stRadio > div > div > label,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {
    color: var(--ink) !important;
    font-weight: 500 !important;
    font-size: .88rem !important;
    opacity: 1 !important;
}

/* ── Textarea ────────────────────────────────────────────────────── */
div[data-testid="stTextArea"] textarea {
    background: var(--surface) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--ink) !important;
    font-size: .88rem !important;
    line-height: 1.65 !important;
}
div[data-testid="stTextArea"] textarea::placeholder {
    color: var(--muted) !important;
    opacity: 1 !important;
}
div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-lt) !important;
    outline: none !important;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
.stButton > button {
    font-family: var(--ff-body) !important;
    font-size: .86rem !important;
    font-weight: 500 !important;
    border-radius: var(--r) !important;
    height: 42px !important;
    transition: var(--trans) !important;
    letter-spacing: .01em !important;
}
/* Primary */
[data-testid="baseButton-primary"],
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    color: #ffffff !important;
    border: none !important;
}
[data-testid="baseButton-primary"]:hover,
.stButton > button[kind="primary"]:hover {
    background: #9e3e18 !important;
    color: #ffffff !important;
}
[data-testid="baseButton-primary"]:disabled,
.stButton > button[kind="primary"]:disabled {
    background: #c9836a !important;
    color: rgba(255,255,255,.75) !important;
    cursor: not-allowed !important;
}
/* Secondary */
[data-testid="baseButton-secondary"],
.stButton > button[kind="secondary"] {
    background: var(--surface) !important;
    color: var(--ink) !important;
    border: 1.5px solid var(--border) !important;
}
[data-testid="baseButton-secondary"]:hover,
.stButton > button[kind="secondary"]:hover {
    background: var(--surface2) !important;
    color: var(--ink) !important;
    border-color: var(--ink2) !important;
}

/* ── File uploader ───────────────────────────────────────────────── */
/* The "Browse files" button is NOT inside .stButton, so our button
   rules never touched it.  Target it explicitly here. */
[data-testid="stFileUploaderDropzone"] {
    background: var(--surface) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: var(--r) !important;
}
[data-testid="stFileUploaderDropzone"] * {
    color: var(--ink2) !important;
}
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stBaseButton-secondary"] {
    background: var(--surface) !important;
    color: var(--ink) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: var(--r) !important;
    font-family: var(--ff-body) !important;
    font-size: .84rem !important;
    font-weight: 500 !important;
    padding: 6px 14px !important;
}
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stBaseButton-secondary"]:hover {
    background: var(--surface2) !important;
    border-color: var(--ink2) !important;
    color: var(--ink) !important;
}

/* ── Alerts: force light-mode colours on ALL variants ───────────── */
/* Streamlit alert components carry their own dark-theme backgrounds
   which survive even when the rest of the app is forced to light mode.
   We must override bg AND text colour explicitly on every sub-element. */
div[data-testid="stAlert"] {
    border-radius: var(--r) !important;
    font-family: var(--ff-body) !important;
    font-size: .85rem !important;
    /* Light neutral base — the icon tints each variant enough */
    background-color: var(--surface) !important;
    color: var(--ink) !important;
    border: 1px solid var(--border) !important;
}
/* Every child element (icon wrapper, paragraphs, spans, SVG text) */
div[data-testid="stAlert"] *,
div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span,
div[data-testid="stAlert"] div {
    color: var(--ink) !important;
    background: transparent !important;
}
/* Keep the coloured left-border accent for each type */
div[data-testid="stAlert"][data-type="warning"],
div[data-testid="stAlert"] > div[data-testid*="warning"] {
    background-color: var(--gold-lt) !important;
    border-left: 4px solid #C9A96E !important;
    color: var(--ink) !important;
}
div[data-testid="stAlert"][data-type="error"],
div[data-testid="stAlert"] > div[data-testid*="error"] {
    background-color: var(--red-lt) !important;
    border-left: 4px solid #D08080 !important;
    color: var(--ink) !important;
}
div[data-testid="stAlert"][data-type="info"],
div[data-testid="stAlert"] > div[data-testid*="info"] {
    background-color: var(--blue-lt) !important;
    border-left: 4px solid #6A93C8 !important;
    color: var(--ink) !important;
}
div[data-testid="stAlert"][data-type="success"],
div[data-testid="stAlert"] > div[data-testid*="success"] {
    background-color: var(--green-lt) !important;
    border-left: 4px solid #6DB38A !important;
    color: var(--ink) !important;
}
/* Streamlit spinner text */
[data-testid="stSpinner"] p,
[data-testid="stSpinner"] span {
    color: var(--ink) !important;
}

/* ── Expanders ───────────────────────────────────────────────────── */
/* Lock the summary background to --surface2 at all times.
   This prevents Streamlit from applying its own dark-header-when-open
   style, so the dark ink text stays readable whether open or closed. */
details[data-testid="stExpander"] > summary,
details[data-testid="stExpander"][open] > summary {
    background: var(--surface2) !important;
    color: var(--ink) !important;
    font-weight: 500 !important;
    font-size: .88rem !important;
    border-radius: var(--r) !important;
}
details[data-testid="stExpander"][open] > summary {
    border-bottom-left-radius: 0 !important;
    border-bottom-right-radius: 0 !important;
}
details[data-testid="stExpander"] > summary *,
details[data-testid="stExpander"][open] > summary * {
    color: var(--ink) !important;
}

/* ── Radio button option labels (darker text) ────────────────────── */
.stRadio [data-testid="stMarkdownContainer"] p,
.stRadio label span,
.stRadio div[data-testid="stWidgetLabel"] p,
div[role="radiogroup"] label p,
div[role="radiogroup"] label span {
    color: var(--ink) !important;
    font-weight: 500 !important;
}

/* ── Sidebar toggle: always visible, always black ───────────────── */
/* The chevron/arrow icons are drawn with SVG stroke paths, not fill. */
[data-testid="collapsedControl"] {
    opacity: 1 !important;
    visibility: visible !important;
}
[data-testid="collapsedControl"] button {
    background: rgba(0,0,0,0.08) !important;
    border-radius: 6px !important;
    opacity: 1 !important;
    visibility: visible !important;
}
[data-testid="collapsedControl"] svg,
[data-testid="collapsedControl"] svg path,
[data-testid="collapsedControl"] svg polyline,
[data-testid="collapsedControl"] svg line {
    stroke: #000000 !important;
    fill: none !important;
    color: #000000 !important;
    opacity: 1 !important;
}
/* Collapse button inside open sidebar */
[data-testid="stSidebar"] button {
    opacity: 1 !important;
    visibility: visible !important;
}
[data-testid="stSidebar"] button svg,
[data-testid="stSidebar"] button svg path,
[data-testid="stSidebar"] button svg polyline,
[data-testid="stSidebar"] button svg line {
    stroke: #000000 !important;
    fill: none !important;
    opacity: 1 !important;
}

/* ── Dividers ────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1.5px solid var(--border2) !important;
    margin: 32px 0 !important;
}

/* ── Hero block ──────────────────────────────────────────────────── */
.pm-hero {
    padding: 4px 0 20px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 28px;
}
.pm-eyebrow {
    font-family: var(--ff-body);
    font-size: .68rem;
    font-weight: 600;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 10px;
}
.pm-hero-title {
    font-family: var(--ff-display);
    font-size: 2.6rem;
    font-weight: 700;
    color: var(--ink);
    line-height: 1.0;
    letter-spacing: -.5px;
    margin-bottom: 12px;
}
.pm-hero-sub {
    font-size: .88rem;
    color: var(--muted);
    line-height: 1.65;
    max-width: 480px;
}

/* ── Section labels ──────────────────────────────────────────────── */
.pm-section-label {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    margin-top: 28px;
}
.pm-section-label .num {
    width: 26px; height: 26px;
    background: var(--ink); color: #fff;
    font-family: var(--ff-body); font-size: .68rem; font-weight: 700;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.pm-section-label .lbl {
    font-family: var(--ff-display);
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--ink);
    line-height: 1;
}

/* ── Banners ─────────────────────────────────────────────────────── */
.pm-banner {
    display: flex; align-items: flex-start; gap: 14px;
    padding: 14px 18px;
    border-radius: var(--r); font-size: .87rem; line-height: 1.55;
    margin-bottom: 20px;
    border-left: 3px solid transparent;
}
.pm-banner .bicon { font-size: 1.1rem; flex-shrink: 0; margin-top: 1px; }
.pm-banner .btitle { font-weight: 600; margin-bottom: 3px; font-size: .9rem; }
.pm-banner .bbody  { opacity: .85; font-size: .84rem; }
.pm-banner.success { background: var(--green-lt); color: var(--green); border-color: #6DB38A; }
.pm-banner.error   { background: var(--red-lt);   color: var(--red);   border-color: #D08080; }
.pm-banner.warn    { background: var(--gold-lt);  color: var(--gold);  border-color: #C9A96E; }
.pm-banner.info    { background: var(--blue-lt);  color: var(--blue);  border-color: #6A93C8; }

/* ── Pipeline strip ──────────────────────────────────────────────── */
.pm-pipeline {
    display: flex; background: var(--surface);
    border: 1.5px solid var(--border); border-radius: var(--r);
    overflow: hidden; margin-bottom: 24px;
}
.pm-step {
    flex: 1; padding: 11px 6px; text-align: center;
    font-size: .7rem; font-weight: 500; color: var(--muted);
    border-right: 1px solid var(--border2); line-height: 1.45;
}
.pm-step:last-child { border-right: none; }
.pm-step.done   { color: var(--green); background: var(--green-lt); }
.pm-step.active { color: var(--accent); background: var(--accent-lt); font-weight: 600; }
.pm-step .sicon { display: block; font-size: .95rem; margin-bottom: 3px; }

/* ── Scene cards ─────────────────────────────────────────────────── */
.pm-scene {
    margin-bottom: 16px; border-radius: var(--r); overflow: hidden;
    border: 1.5px solid var(--border); box-shadow: var(--shadow-sm);
}
.pm-scene-head {
    background: var(--blue); padding: 10px 16px;
    display: flex; align-items: baseline; gap: 10px;
}
.pm-scene-id {
    font-size: .6rem; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: rgba(255,255,255,.6);
    flex-shrink: 0;
}
.pm-scene-loc {
    font-family: var(--ff-display); font-size: 1rem;
    font-weight: 600; color: #fff;
}
.pm-line {
    display: grid; grid-template-columns: 110px 1fr;
    border-bottom: 1px solid var(--border2);
}
.pm-line:last-child { border-bottom: none; }
.pm-line-spk {
    padding: 11px 12px; font-size: .7rem; font-weight: 700;
    letter-spacing: .6px; text-transform: uppercase;
    color: var(--blue); background: var(--blue-lt);
    border-right: 1px solid var(--border2);
    display: flex; align-items: flex-start;
}
.pm-line-body { padding: 11px 15px; background: var(--surface); }
.pm-line-txt { font-size: .87rem; color: var(--ink); line-height: 1.6; }
.pm-line-cue {
    margin-top: 5px; font-size: .74rem; color: var(--muted);
    font-style: italic; display: flex; align-items: center; gap: 4px;
}

/* ── Character cards ─────────────────────────────────────────────── */
.pm-char {
    background: var(--surface); border: 1.5px solid var(--border);
    border-radius: var(--r-lg); padding: 18px 20px;
    box-shadow: var(--shadow-sm); margin-bottom: 12px;
}
.pm-char-name {
    font-family: var(--ff-display); font-size: 1.35rem; font-weight: 700;
    color: var(--ink); margin-bottom: 5px;
}
.pm-char-desc {
    font-size: .84rem; color: var(--ink2); line-height: 1.6; margin-bottom: 8px;
}
.pm-char-style {
    font-size: .76rem; color: var(--muted); font-style: italic; margin-bottom: 8px;
}
.pm-tag {
    display: inline-block; background: var(--surface2); color: var(--ink2);
    border: 1px solid var(--border); font-size: .69rem; font-weight: 500;
    padding: 3px 9px; border-radius: 20px; margin: 2px 3px 2px 0;
}
.pm-char-img {
    width: 90px; height: 90px; border-radius: var(--r);
    border: 1.5px solid var(--border); object-fit: cover;
}
.pm-char-nopic {
    width: 90px; height: 90px; border-radius: var(--r);
    border: 1.5px solid var(--border); background: var(--surface2);
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; font-size: .68rem; color: var(--muted);
    gap: 4px;
}

/* ── Output chips ────────────────────────────────────────────────── */
.pm-outputs {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
    margin-bottom: 24px;
}
.pm-chip {
    background: var(--surface); border: 1.5px solid var(--border);
    border-radius: var(--r); padding: 14px 15px; box-shadow: var(--shadow-sm);
}
.pm-chip .cicon { font-size: 1.1rem; margin-bottom: 5px; display: block; }
.pm-chip .cname { font-weight: 600; font-size: .8rem; color: var(--ink); margin-bottom: 2px; }
.pm-chip .cdesc { font-size: .71rem; color: var(--muted); }

/* ── Event log ───────────────────────────────────────────────────── */
.pm-event { display: flex; gap: 10px; align-items: flex-start; padding: 6px 0; border-bottom: 1px solid var(--border2); }
.pm-event:last-child { border-bottom: none; }
.pm-event-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
.pm-event-dot.info    { background: var(--blue); }
.pm-event-dot.success { background: var(--green); }
.pm-event-dot.warning { background: var(--gold); }
.pm-event-dot.error   { background: var(--red); }
.pm-event-body { flex: 1; min-width: 0; }
.pm-event-agent { font-size: .69rem; font-weight: 600; letter-spacing: .5px; text-transform: uppercase; color: var(--muted); }
.pm-event-msg { font-size: .82rem; color: var(--ink2); line-height: 1.5; }
.pm-event-ts { font-size: .68rem; color: var(--muted); flex-shrink: 0; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        _render_html("""
<style>
.sb-section { margin-bottom: 20px; }
.sb-title {
    font-size: .62rem; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: var(--accent);
    margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border);
}
.sb-code {
    background: #2A2520; color: #E8E3DB !important;
    font-family: monospace; font-size: .72rem;
    padding: 8px 12px; border-radius: 6px;
    word-break: break-all;
}
.sb-agents { display: flex; flex-direction: column; gap: 6px; }
.sb-agent {
    display: flex; align-items: center; gap: 10px;
    padding: 7px 10px; border-radius: 6px;
    background: var(--surface2); border: 1px solid var(--border);
    font-size: .78rem; font-weight: 500; color: var(--ink);
}
.sb-agent .ag-icon { font-size: .95rem; }
.sb-agent .ag-name { flex: 1; }
.sb-agent .ag-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); }
.sb-mem {
    display: flex; align-items: center; gap: 8px; padding: 8px 10px;
    border-radius: 6px; background: var(--blue-lt); border: 1px solid #BDD0E8;
    font-size: .78rem; color: var(--blue);
}
.sb-footer {
    font-size: .68rem; color: var(--muted); text-align: center;
    padding-top: 12px; border-top: 1px solid var(--border);
}
</style>
<div class="sb-section">
<div class="sb-title">MCP Server</div>
<div class="sb-code">python -m shared.mcp_server</div>
</div>
<div class="sb-section">
<div class="sb-title">Streamlit App</div>
<div class="sb-code">streamlit run phase1_writers_room/main.py</div>
</div>
<div class="sb-section">
<div class="sb-title">Pipeline Agents</div>
<div class="sb-agents">
<div class="sb-agent"><span class="ag-icon">✍️</span><span class="ag-name">Scriptwriter</span><span class="ag-dot"></span></div>
<div class="sb-agent"><span class="ag-icon">✅</span><span class="ag-name">Validator</span><span class="ag-dot"></span></div>
<div class="sb-agent"><span class="ag-icon">👤</span><span class="ag-name">Human-in-the-Loop</span><span class="ag-dot"></span></div>
<div class="sb-agent"><span class="ag-icon">🎨</span><span class="ag-name">Character Designer</span><span class="ag-dot"></span></div>
<div class="sb-agent"><span class="ag-icon">🖼️</span><span class="ag-name">Image Synthesis</span><span class="ag-dot"></span></div>
</div>
</div>
<div class="sb-section">
<div class="sb-title">Memory Layer</div>
<div class="sb-mem">🗄️ &nbsp;ChromaDB vector store</div>
</div>
<div class="sb-footer">CS-4015 Agentic AI &nbsp;·&nbsp; FAST NUCES</div>
""")


# ── Presentation helpers ──────────────────────────────────────────────────────

def banner(kind: str, icon: str, title: str, body: str = "") -> None:
    body_part = f'<div class="bbody">{_esc(body)}</div>' if body else ""
    _render_html(f"""
<div class="pm-banner {kind}">
<div class="bicon">{icon}</div>
<div>
<div class="btitle">{_esc(title)}</div>
{body_part}
</div>
</div>
""")


def section_label(num: str, text: str) -> None:
    _render_html(f"""
<div class="pm-section-label">
<div class="num">{_esc(num)}</div>
<div class="lbl">{_esc(text)}</div>
</div>
""")


def pipeline_strip(active: int) -> None:
    steps = [
        ("✍️",  "Scriptwriter"),
        ("🎨",  "Character\nDesigner"),
        ("🖼️", "Image\nSynthesis"),
        ("✅",  "Validator"),
    ]
    parts = ['<div class="pm-pipeline">']
    for i, (icon, label) in enumerate(steps):
        idx = i + 1
        cls = "active" if idx == active else ("done" if idx < active else "")
        label_html = _esc(label).replace("\n", "<br>")
        parts.append(
            f'<div class="pm-step {cls}">'
            f'<span class="sicon">{icon}</span>{label_html}'
            f'</div>'
        )
    parts.append("</div>")
    _render_html("".join(parts))


def render_script(script: dict) -> None:
    scenes = script.get("scenes", [])
    if not scenes:
        _render_html('<p style="color:var(--muted);font-size:.86rem;">No scene data found.</p>')
        return

    for scene in scenes:
        lines_parts = []
        for entry in scene.get("dialogue", []):
            cue = entry.get("visual_cue", "")
            cue_html = (
                f'<div class="pm-line-cue">🎥 {_esc(cue)}</div>' if cue else ""
            )
            lines_parts.append(
                '<div class="pm-line">'
                f'<div class="pm-line-spk">{_esc(entry.get("speaker",""))}</div>'
                '<div class="pm-line-body">'
                f'<div class="pm-line-txt">{_esc(entry.get("line",""))}</div>'
                f'{cue_html}'
                '</div>'
                '</div>'
            )

        scene_html = (
            '<div class="pm-scene">'
            '<div class="pm-scene-head">'
            f'<span class="pm-scene-id">Scene {_esc(scene.get("scene_id","?"))}</span>'
            f'<span class="pm-scene-loc">{_esc(scene.get("location",""))}</span>'
            '</div>'
            + "".join(lines_parts) +
            '</div>'
        )
        _render_html(scene_html)


def render_characters(chars: list) -> None:
    if not chars:
        _render_html('<p style="color:var(--muted);font-size:.86rem;">No character data.</p>')
        return

    for char in chars:
        traits_html = "".join(
            f'<span class="pm-tag">{_esc(t)}</span>'
            for t in char.get("personality_traits", [])
        )
        style_ref = char.get("reference_style", "")
        style_html = (
            f'<div class="pm-char-style">Style: {_esc(style_ref)}</div>'
            if style_ref else ""
        )

        # Image: try base64 embed, else show placeholder
        img_path = char.get("image_path", "")
        if img_path and os.path.exists(img_path):
            b64_uri = _img_b64(img_path)
            img_slot = (
                f'<img class="pm-char-img" src="{b64_uri}" alt="{_esc(char.get("name",""))}">'
                if b64_uri
                else '<div class="pm-char-nopic">🎭<br>No image</div>'
            )
        else:
            img_slot = '<div class="pm-char-nopic">🎭<br>No image</div>'

        col_info, col_img = st.columns([4, 1])
        with col_info:
            _render_html(
                '<div class="pm-char">'
                f'<div class="pm-char-name">{_esc(char.get("name",""))}</div>'
                f'<div class="pm-char-desc">{_esc(char.get("appearance_description",""))}</div>'
                f'{style_html}'
                f'<div>{traits_html}</div>'
                '</div>'
            )
        with col_img:
            _render_html(img_slot)
