# glass_theme.py — Apple-style frosted glass skin injector (v2: lighter, readable)
import streamlit as st

def inject_glass_css():
    st.markdown("""
<style>
/* ── Soft, pale animated gradient background (Apple-style, not saturated) ── */
html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #E8ECFB 0%, #F3E8FB 25%, #FCE8F3 50%, #E8F3FC 75%, #E8FBFA 100%) !important;
    background-size: 400% 400% !important;
    animation: glassGradientShift 30s ease infinite !important;
}
@keyframes glassGradientShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

[data-testid="stAppViewContainer"] > .main,
[data-testid="stHeader"] {
    background: transparent !important;
}

/* ── Glass cards: kpi_card() output and similar bordered divs ───────────── */
.glass-card, div[data-testid="stMarkdownContainer"] > div[style*="border-top:3px solid"],
div[data-testid="stMarkdownContainer"] > div[style*="border-top: 3px solid"] {
    background: rgba(255,255,255,0.65) !important;
    backdrop-filter: blur(20px) saturate(140%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(140%) !important;
    border: 1px solid rgba(255,255,255,0.8) !important;
    box-shadow: 0 4px 20px rgba(31,41,55,0.06), inset 0 1px 0 rgba(255,255,255,0.6) !important;
}

/* ── Sidebar: keep solid dark for readability/contrast ───────────────────── */
[data-testid="stSidebar"] {
    background: rgba(17,24,39,0.92) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}

/* ── Buttons ──────────────────────────────────────────────────────────── */
.stButton > button {
    background: rgba(255,255,255,0.7) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255,255,255,0.9) !important;
    color: #111827 !important;
}
.stButton > button[kind="primary"] {
    background: rgba(16,185,129,0.85) !important;
    border: 1px solid rgba(16,185,129,0.9) !important;
    color: #FFFFFF !important;
}

/* ── Expander ─────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.6) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(255,255,255,0.8) !important;
    border-radius: 14px !important;
}

/* ── Custom HTML tables (trade log, daily plan) — solid white for readability ── */
table {
    background: rgba(255,255,255,0.92) !important;
}
table thead th {
    background: rgba(249,250,251,0.95) !important;
    backdrop-filter: blur(8px) !important;
    color: #374151 !important;
}
table tbody td {
    color: #111827 !important;
}

/* ── Plotly/chart containers get a frosted card backing ─────────────────── */
[data-testid="stPlotlyChart"] {
    background: rgba(255,255,255,0.55) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border-radius: 14px !important;
    padding: 8px !important;
}
</style>
""", unsafe_allow_html=True)


GLASS_KPI_CSS = """
<style>
.glass-kpi {
    background: rgba(255,255,255,0.65);
    backdrop-filter: blur(20px) saturate(140%);
    -webkit-backdrop-filter: blur(20px) saturate(140%);
    border: 1px solid rgba(255,255,255,0.8);
    border-radius: 16px;
    padding: 16px 20px;
    box-shadow: 0 4px 20px rgba(31,41,55,0.06), inset 0 1px 0 rgba(255,255,255,0.6);
}
.glass-kpi .label {
    font-size: 11px; color: #4B5563; text-transform: uppercase;
    letter-spacing: 0.06em; font-weight: 600; margin-bottom: 8px;
}
.glass-kpi .value {
    font-size: 24px; font-weight: 700; letter-spacing: -0.5px; color: #111827;
}
.glass-kpi .value.green { color: #047857; }
.glass-kpi .value.red { color: #B91C1C; }
.glass-kpi .value.blue { color: #1D4ED8; }
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
