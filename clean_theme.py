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
# NOTE: CSS lives in inject_clean_css() (called once globally), not repeated per-card,
# to avoid Streamlit markdown-escaping issues when called multiple times per page.

_ICON_BG = {
    "blue":   ("#EFF6FF", "#BFDBFE"),
    "green":  ("#F0FDF4", "#BBF7D0"),
    "amber":  ("#FFFBEB", "#FDE68A"),
    "red":    ("#FEF2F2", "#FECACA"),
    "neutral":("#F9FAFB", "#E5E7EB"),
}

def metric_row(label, value, sub="", icon="●", icon_color="neutral"):
    """One metric line: label + value + sub on the left, icon badge on the right."""
    bg, border = _ICON_BG.get(icon_color, _ICON_BG["neutral"])
    sub_html = f'<div style="font-size:12px;color:#9CA3AF;margin-top:2px">{sub}</div>' if sub else ""
    return (
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;'
        'margin-bottom:18px">'
        '<div>'
        f'<div style="font-size:16px;font-weight:700;font-style:italic;color:#111827;margin-bottom:4px">{label}</div>'
        f'<div style="font-size:22px;font-weight:800;color:#111827;'
        f'font-family:\'SF Mono\',\'Fira Code\',monospace">{value}</div>'
        f'{sub_html}'
        '</div>'
        f'<div style="width:34px;height:34px;border-radius:50%;background:{bg};border:1px solid {border};'
        'display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0">'
        f'{icon}</div>'
        '</div>'
    )

def metric_card_group(rows_html):
    """Wrap a list of metric_row() outputs in the white card container."""
    inner = "".join(rows_html)
    return (
        '<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:18px;'
        'padding:22px 24px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">'
        f'{inner}'
        '</div>'
    )


# ── Pill tab navigation matching reference (Position & P&L, Streaks, etc.) ──
def tab_pill_row(tabs, active):
    """tabs: list of (icon, label) tuples. active: label string currently selected."""
    pills = "".join(
        (
            f'<div style="padding:8px 16px;border-radius:10px;font-size:12.5px;font-weight:700;'
            f'white-space:nowrap;'
            f'{"background:#F3F4F6;color:#111827" if label==active else "color:#6B7280"}">'
            f'{icon} {label}</div>'
        )
        for icon, label in tabs
    )
    return (
        '<div style="display:flex;gap:6px;background:#FFFFFF;border:1px solid #E5E7EB;'
        f'border-radius:14px;padding:6px;margin:16px 0">{pills}</div>'
    )


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
