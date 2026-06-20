# clean_theme.py — Neutral white-card skin matching the reference design.
# Replaces glass_theme.py. Import and call inject_clean_css() once after st.set_page_config().

import streamlit as st

def inject_clean_css():
    st.markdown("""
<style>
/* ── Plain light background, no gradient ─────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: #FAFAFA !important;
}
[data-testid="stAppViewContainer"] > .main,
[data-testid="stHeader"] {
    background: transparent !important;
}

/* ── Sidebar: solid dark, clean ──────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #111827 !important;
    border-right: 1px solid #1F2937 !important;
}

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.stButton > button {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    color: #111827 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"] {
    background: #10B981 !important;
    border: 1px solid #10B981 !important;
    color: #FFFFFF !important;
}

/* ── Expander ─────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}

/* ── Tables ───────────────────────────────────────────────────────────────── */
table {
    background: #FFFFFF !important;
}
table thead th {
    background: #F9FAFB !important;
    color: #6B7280 !important;
}
table tbody td {
    color: #111827 !important;
}

/* ── Plotly chart containers ─────────────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 14px !important;
    padding: 8px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Clean metric card matching the reference design ─────────────────────────
METRIC_CARD_CSS = """
<style>
.metric-card-group {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 18px;
    padding: 22px 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.metric-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 18px;
}
.metric-row:last-child { margin-bottom: 0; }
.metric-label {
    font-size: 16px;
    font-weight: 700;
    font-style: italic;
    color: #111827;
    margin-bottom: 4px;
}
.metric-value {
    font-size: 22px;
    font-weight: 800;
    color: #111827;
    font-family: 'SF Mono','Fira Code',monospace;
}
.metric-sub {
    font-size: 12px;
    color: #9CA3AF;
    margin-top: 2px;
}
.metric-icon {
    width: 34px; height: 34px;
    border-radius: 50%;
    background: #F9FAFB;
    border: 1px solid #E5E7EB;
    display: flex; align-items: center; justify-content: center;
    font-size: 15px;
    flex-shrink: 0;
}
.metric-icon.blue { background: #EFF6FF; border-color: #BFDBFE; }
.metric-icon.green { background: #F0FDF4; border-color: #BBF7D0; }
.metric-icon.amber { background: #FFFBEB; border-color: #FDE68A; }
.metric-icon.red { background: #FEF2F2; border-color: #FECACA; }
</style>
"""

def metric_row(label, value, sub="", icon="●", icon_color="neutral"):
    """One metric line inside a metric-card-group: icon top-right, label + value + sub below."""
    return f'''<div class="metric-row">
        <div>
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {f'<div class="metric-sub">{sub}</div>' if sub else ''}
        </div>
        <div class="metric-icon {icon_color}">{icon}</div>
    </div>'''

def metric_card_group(rows_html):
    """Wrap a list of metric_row() outputs in the card container."""
    return f'{METRIC_CARD_CSS}<div class="metric-card-group">{"".join(rows_html)}</div>'


# ── Pill tab navigation matching reference (Position & P&L, Streaks, etc.) ──
TAB_PILL_CSS = """
<style>
.tab-pill-row {
    display: flex; gap: 6px; background: #FFFFFF; border: 1px solid #E5E7EB;
    border-radius: 14px; padding: 6px; margin: 16px 0;
}
.tab-pill {
    padding: 8px 16px; border-radius: 10px; font-size: 12.5px; font-weight: 700;
    color: #6B7280; cursor: pointer; white-space: nowrap;
}
.tab-pill.active { background: #F3F4F6; color: #111827; }
</style>
"""

def tab_pill_row(tabs, active):
    """tabs: list of (icon, label) tuples. active: label string currently selected."""
    pills = "".join(
        f'<div class="tab-pill{" active" if label==active else ""}">{icon} {label}</div>'
        for icon, label in tabs
    )
    return f'{TAB_PILL_CSS}<div class="tab-pill-row">{pills}</div>'


# ── Insight callout card (e.g. "Asymmetry Found") ────────────────────────────
def insight_card(badge_text, badge_color, title, body_html, side_content_html=""):
    bg = {"green":"#F0FDF4","blue":"#EFF6FF","amber":"#FFFBEB"}.get(badge_color,"#F3F4F6")
    fg = {"green":"#047857","blue":"#1D4ED8","amber":"#B45309"}.get(badge_color,"#374151")
    return f'''<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:18px;
        padding:24px;display:flex;gap:32px;align-items:flex-start;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
        <div style="flex:1;min-width:240px">
            <span style="background:{bg};color:{fg};padding:4px 12px;border-radius:20px;
                font-size:11px;font-weight:700;letter-spacing:0.05em">⚡ {badge_text}</span>
            <div style="font-size:17px;font-weight:800;font-style:italic;color:#111827;margin-top:14px">{title}</div>
            <div style="font-size:14px;color:#6B7280;margin-top:8px;line-height:1.5">{body_html}</div>
        </div>
        <div style="flex:2">{side_content_html}</div>
    </div>'''
