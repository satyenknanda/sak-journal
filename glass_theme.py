# glass_theme.py — Apple-style frosted glass skin injector
# Import and call inject_glass_css() once near the top of app.py, after st.set_page_config()

import streamlit as st

def inject_glass_css():
    st.markdown("""
<style>
/* ── Animated gradient background ─────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #4facfe 75%, #00f2fe 100%) !important;
    background-size: 400% 400% !important;
    animation: glassGradientShift 22s ease infinite !important;
}
@keyframes glassGradientShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* Make the main content area transparent so the gradient shows through */
[data-testid="stAppViewContainer"] > .main,
[data-testid="stHeader"] {
    background: transparent !important;
}

/* ── Glass cards: kpi_card() output and similar bordered divs ───────────── */
.glass-card, div[data-testid="stMarkdownContainer"] > div[style*="border-top:3px solid"],
div[data-testid="stMarkdownContainer"] > div[style*="border-top: 3px solid"] {
    background: rgba(255,255,255,0.22) !important;
    backdrop-filter: blur(20px) saturate(160%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(160%) !important;
    border: 1px solid rgba(255,255,255,0.35) !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.4) !important;
}

/* ── Sidebar glass ────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: rgba(20,20,35,0.55) !important;
    backdrop-filter: blur(28px) saturate(150%) !important;
    -webkit-backdrop-filter: blur(28px) saturate(150%) !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
}

/* ── Buttons get a subtle glass treatment ────────────────────────────── */
.stButton > button {
    background: rgba(255,255,255,0.15) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255,255,255,0.3) !important;
}
.stButton > button[kind="primary"] {
    background: rgba(16,185,129,0.55) !important;
    border: 1px solid rgba(16,185,129,0.7) !important;
}

/* ── Expander, dataframe, and table containers ───────────────────────── */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.15) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    border-radius: 14px !important;
}

/* Tables rendered via raw HTML (our custom trade tables) */
table {
    background: transparent !important;
}
table thead th {
    background: rgba(255,255,255,0.18) !important;
    backdrop-filter: blur(10px) !important;
}
</style>
""", unsafe_allow_html=True)


GLASS_KPI_CSS = """
<style>
.glass-kpi {
    background: rgba(255,255,255,0.22);
    backdrop-filter: blur(20px) saturate(160%);
    -webkit-backdrop-filter: blur(20px) saturate(160%);
    border: 1px solid rgba(255,255,255,0.35);
    border-radius: 16px;
    padding: 16px 20px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.4);
}
.glass-kpi .label {
    font-size: 11px; color: rgba(20,20,35,0.6); text-transform: uppercase;
    letter-spacing: 0.06em; font-weight: 600; margin-bottom: 8px;
}
.glass-kpi .value {
    font-size: 24px; font-weight: 700; letter-spacing: -0.5px; color: #1a1a2e;
}
.glass-kpi .value.green { color: #0a7a4a; }
.glass-kpi .value.red { color: #b8293f; }
.glass-kpi .value.blue { color: #1a5fb8; }
</style>
"""

def glass_kpi_card(label, value, color="neutral"):
    """Drop-in replacement for kpi_card() with frosted glass styling."""
    color_class = {"green":"green","red":"red","blue":"blue"}.get(color, "")
    return f'''{GLASS_KPI_CSS}
<div class="glass-kpi">
    <div class="label">{label}</div>
    <div class="value {color_class}">{value}</div>
</div>'''
