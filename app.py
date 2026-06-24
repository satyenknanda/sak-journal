import streamlit as st
from clean_theme import inject_clean_css
from pathlib import Path
import sys
import traceback

# Cloud error logging
def _log_error():
    exc = traceback.format_exc()
    st.error(f"App Error:\n```\n{exc}\n```")
    st.stop()
sys.path.insert(0, str(Path(__file__).parent))

from data.db import init_db, import_from_excel, last_sync_time
from theme import (TEAL, TEAL_DARK, CARD_BG, PAGE_BG, BORDER, BORDER_LIGHT,
                   SHADOW_SM, SIDEBAR_BG, TEXT_H, TEXT_BODY, TEXT_MUTED, TEXT_SUBTLE,
                   TEXT_DIM, TABLE_HEAD_BG)

st.set_page_config(
    page_title="SAK Trading Journal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


init_db()

if "page" not in st.session_state:
    st.session_state.page = "dashboard"

st.markdown(f"""
<style>

*,*::before,*::after{{box-sizing:border-box}}

/* Page background */
html,body,[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"]>section,.main{{
    background:{PAGE_BG}!important;
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important;
    color:{TEXT_BODY}!important;
}}

/* Hide keyboard shortcut tooltip "keyb" */
[data-testid="stMainMenuPopover"],
.st-emotion-cache-pkbazv,
[data-testid="stKeyboardShortcutPanel"],
iframe[title="keyboard shortcut"],
div[data-testid="stKeyboardShortcuts"],
.shortcut,
[aria-label="keyboard shortcuts"] {{
    display: none !important;
    visibility: hidden !important;
}}

/* Force sidebar always visible */
[data-testid="stSidebar"]{{
    transform:none!important;
    visibility:visible!important;
    display:block!important;
}}
.main .block-container{{
    padding:1.5rem 2rem 3rem!important;
    max-width:1560px!important;
}}

/* Sidebar */
[data-testid="stSidebar"]{{
    background:{SIDEBAR_BG}!important;
    border-right:none!important;
    box-shadow:1px 0 0 rgba(255,255,255,0.05)!important;
}}
[data-testid="stSidebar"]>div{{background:{SIDEBAR_BG}!important}}
[data-testid="stSidebar"] *{{font-family:'Inter',sans-serif!important}}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span:not(.nav-active-text){{color:#94A3B8!important}}

/* Sidebar nav buttons - remove ALL default styling */
[data-testid="stSidebar"] [data-testid="stButton"] > button,
[data-testid="stSidebar"] [data-testid="stButton"] > button:focus,
[data-testid="stSidebar"] [data-testid="stButton"] > button:active {{
    all: unset !important;
    box-sizing: border-box !important;
    display: flex !important;
    align-items: center !important;
    gap: 9px !important;
    width: 100% !important;
    padding: 8px 10px !important;
    border-radius: 7px !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    color: #64748B !important;
    cursor: pointer !important;
    transition: background 0.12s, color 0.12s !important;
    font-family: 'Inter', sans-serif !important;
    margin-bottom: 1px !important;
    white-space: nowrap !important;
    background: transparent !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {{
    background: rgba(255,255,255,0.06) !important;
    color: #94A3B8 !important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] > button > div {{
    display: flex !important;
    align-items: center !important;
    gap: 9px !important;
    width: 100% !important;
    background: transparent !important;
    color: inherit !important;
}}
/* Kill the white card background Streamlit adds */
[data-testid="stSidebar"] [data-testid="stButton"] {{
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 0 1px 0 !important;
}}

/* Form inputs */
[data-testid="stSelectbox"]>div>div,
[data-testid="stTextInput"]>div>div>input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input{{
    background:{CARD_BG}!important;
    border:1px solid {BORDER}!important;
    border-radius:8px!important;
    color:{TEXT_H}!important;
    font-family:'Inter',sans-serif!important;
    font-size:13px!important;
    box-shadow:none!important;
}}
[data-testid="stSelectbox"]>div>div:focus-within,
[data-testid="stTextInput"]>div>div:focus-within{{
    border-color:{TEAL}!important;
    box-shadow:0 0 0 2px rgba(16,185,129,0.12)!important;
}}
/* Input labels */
[data-testid="stSelectbox"] label,
[data-testid="stTextInput"] label,
[data-testid="stDateInput"] label,
[data-testid="stNumberInput"] label{{
    color:{TEXT_MUTED}!important;
    font-size:11.5px!important;
    font-weight:500!important;
    font-family:'Inter',sans-serif!important;
}}

/* Primary button */
[data-testid="stButton"]>button[kind="primary"]{{
    background:{TEAL}!important;
    border:none!important;
    border-radius:8px!important;
    color:#fff!important;
    font-family:'Inter',sans-serif!important;
    font-size:13px!important;
    font-weight:600!important;
    padding:0.45rem 1.1rem!important;
    box-shadow:none!important;
    letter-spacing:0!important;
}}
[data-testid="stButton"]>button[kind="primary"]:hover{{background:{TEAL_DARK}!important}}

/* Sidebar Add Trade button — purple gradient */
[data-testid="stSidebar"] [data-testid="stButton"] [data-testid="stBaseButton-primary"]{{
    background:linear-gradient(135deg,#7C3AED,#6D28D9)!important;
    border-radius:8px!important;
    font-size:13px!important;
    font-weight:600!important;
    padding:10px 0!important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] [data-testid="stBaseButton-primary"]:hover{{
    background:linear-gradient(135deg,#6D28D9,#5B21B6)!important;
}}

/* Secondary button */
[data-testid="stButton"]>button[kind="secondary"]{{
    background:{CARD_BG}!important;
    border:1px solid {BORDER}!important;
    border-radius:8px!important;
    color:{TEXT_BODY}!important;
    font-size:13px!important;
    font-weight:500!important;
    font-family:'Inter',sans-serif!important;
}}
[data-testid="stButton"]>button[kind="secondary"]:hover{{
    background:{TABLE_HEAD_BG}!important;
    border-color:#CBD5E1!important;
}}

/* Expanders */
[data-testid="stExpander"]{{
    background:{CARD_BG}!important;
    border:1px solid {BORDER}!important;
    border-radius:10px!important;
    box-shadow:{SHADOW_SM}!important;
    overflow:hidden!important;
    margin-bottom:10px!important;
}}
[data-testid="stExpander"] summary{{
    padding:12px 16px!important;
    font-size:13.5px!important;
    font-weight:600!important;
    color:{TEXT_H}!important;
    background:{CARD_BG}!important;
    font-family:'Inter',sans-serif!important;
}}
[data-testid="stExpander"] summary:hover{{background:{TABLE_HEAD_BG}!important}}
[data-testid="stExpander"] summary svg{{color:{TEXT_MUTED}!important}}

/* Tabs — plain underline style, no pill */
[data-testid="stTabs"] [data-baseweb="tab-list"]{{
    background:transparent!important;
    border:none!important;
    border-bottom:1px solid {BORDER}!important;
    border-radius:0!important;
    padding:0!important;
    gap:0!important;
}}
[data-testid="stTabs"] [data-baseweb="tab"]{{
    background:transparent!important;
    border-radius:0!important;
    color:{TEXT_MUTED}!important;
    font-size:12.5px!important;
    font-weight:500!important;
    padding:8px 16px!important;
    border:none!important;
    border-bottom:2px solid transparent!important;
    font-family:'Inter',sans-serif!important;
}}
[data-testid="stTabs"] [aria-selected="true"]{{
    background:transparent!important;
    color:{TEXT_H}!important;
    font-weight:600!important;
    border-bottom:2px solid {TEAL}!important;
}}
[data-testid="stTabs"] [data-baseweb="tab-highlight"]{{
    background:{TEAL}!important;
    height:2px!important;
}}

/* Dataframe */
[data-testid="stDataFrame"]{{
    border:1px solid {BORDER}!important;
    border-radius:10px!important;
    overflow:hidden!important;
    box-shadow:{SHADOW_SM}!important;
}}
.stDataFrame th{{
    background:{TABLE_HEAD_BG}!important;
    color:{TEXT_SUBTLE}!important;
    font-size:10px!important;
    font-weight:500!important;
    text-transform:uppercase!important;
    letter-spacing:0.07em!important;
    font-family:'Inter',sans-serif!important;
}}
.stDataFrame td{{
    font-size:13px!important;
    color:{TEXT_BODY}!important;
    font-family:'Inter',sans-serif!important;
}}

/* Typography */
h1{{font-size:1.55rem!important;font-weight:700!important;color:{TEXT_H}!important;letter-spacing:-0.025em!important;margin-bottom:2px!important}}
h2{{font-size:1.25rem!important;font-weight:700!important;color:{TEXT_H}!important;letter-spacing:-0.015em!important}}
h3,h4{{font-weight:600!important;color:{TEXT_H}!important}}
p{{color:{TEXT_BODY}!important;font-size:13.5px!important}}

/* Caption */
[data-testid="stCaptionContainer"] p{{color:{TEXT_SUBTLE}!important;font-size:11.5px!important}}

/* Alerts */
[data-testid="stSuccess"]{{background:#ECFDF5!important;border-color:#A7F3D0!important;color:#065F46!important;border-radius:8px!important}}
[data-testid="stError"]{{background:#FEF2F2!important;border-color:#FECACA!important;color:#991B1B!important;border-radius:8px!important}}
[data-testid="stInfo"]{{background:#EFF6FF!important;border-color:#BFDBFE!important;color:#1E40AF!important;border-radius:8px!important}}

/* Plotly toolbar — hide */
.js-plotly-plot .modebar{{display:none!important}}
.js-plotly-plot .plotly .modebar-container{{display:none!important}}

/* Hide keyboard_double_arrow sidebar icon */
[data-testid="stSidebarCollapseButton"] span[class*="material"] {{ display:none!important }}
[data-testid="stSidebarCollapseButton"] .material-symbols-rounded {{ display:none!important }}
button[data-testid="stBaseButton-headerNoPadding"] span {{ display:none!important }}
/* Hide keyboard shortcut label */
[data-testid="stKeyboardShortcuts"] {{ display:none!important }}
span:contains("keyboard_double") {{ display:none!important }}

/* Hide Streamlit branding + keyboard tooltip */
#MainMenu, footer, header {{ display:none!important }}
[data-testid="stToolbar"] {{ display:none!important }}
[data-testid="stDecoration"] {{ display:none!important }}
[data-testid="stKeyboardShortcuts"] {{ display:none!important }}
[data-testid="stStatusWidget"] {{ display:none!important }}
/* The "keyb" label */
[class*="keyboard"] {{ display:none!important }}
span[class*="shortcut"] {{ display:none!important }}
/* Remove gap between column rows */
[data-testid="stHorizontalBlock"] {{
    gap: 12px !important;
    align-items: stretch !important;
}}
/* Remove excess vertical padding from column blocks */
[data-testid="stVerticalBlockBorderWrapper"] {{
    padding: 0 !important;
}}

/* Hide Streamlit auto page nav list at top of sidebar */
[data-testid="stSidebarNav"] {{ display:none!important }}
[data-testid="stSidebarNavItems"] {{ display:none!important }}
[data-testid="stSidebarNavSeparator"] {{ display:none!important }}
section[data-testid="stSidebar"] > div > div > div > ul {{ display:none!important }}
nav[data-testid="stSidebarNav"] {{ display:none!important }}

/* Sidebar nav buttons - styled like Tradezella */
[data-testid="stSidebar"] [data-testid="stButton"] > button {{
    all:unset!important;
    display:flex!important;
    align-items:center!important;
    gap:9px!important;
    width:100%!important;
    padding:8px 10px!important;
    border-radius:7px!important;
    font-size:12.5px!important;
    font-weight:500!important;
    color:#64748B!important;
    cursor:pointer!important;
    font-family:'Inter',sans-serif!important;
    margin-bottom:1px!important;
    background:transparent!important;
    border:none!important;
    box-sizing:border-box!important;
    transition:background 0.12s,color 0.12s!important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {{
    background:rgba(255,255,255,0.08)!important;
    color:#94A3B8!important;
}}
[data-testid="stSidebar"] [data-testid="stButton"] {{
    margin:0 0 1px 0!important;
    padding:0!important;
}}

/* Sidebar collapse button — keep visible, style it */
[data-testid="stSidebarCollapseButton"] {{
    display:flex!important;
    visibility:visible!important;
}}
[data-testid="stSidebarCollapseButton"] button {{
    background:rgba(255,255,255,0.08)!important;
    border:1px solid rgba(255,255,255,0.1)!important;
    border-radius:6px!important;
    color:#94A3B8!important;
    width:28px!important;
    height:28px!important;
    padding:0!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
}}
[data-testid="stSidebarCollapseButton"] button:hover {{
    background:rgba(255,255,255,0.15)!important;
    color:#fff!important;
}}
/* Also target the collapsed state toggle */
[data-testid="collapsedControl"] {{
    display:flex!important;
    visibility:visible!important;
    background:{SIDEBAR_BG}!important;
}}
[data-testid="collapsedControl"] button {{
    background:rgba(16,185,129,0.15)!important;
    border:1px solid rgba(16,185,129,0.3)!important;
    color:{TEAL}!important;
    border-radius:0 6px 6px 0!important;
}}

/* Sidebar toggle button — keep visible */
[data-testid="collapsedControl"],
button[kind="header"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] {{
    display:flex!important;
    visibility:visible!important;
    opacity:1!important;
}}
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapsedControl"] button {{
    background:rgba(255,255,255,0.08)!important;
    border:1px solid rgba(255,255,255,0.12)!important;
    border-radius:6px!important;
    color:#94A3B8!important;
}}
[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="stSidebarCollapsedControl"] button:hover {{
    background:rgba(255,255,255,0.15)!important;
    color:#fff!important;
}}

/* Scrollbar */
::-webkit-scrollbar{{width:4px;height:4px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:{BORDER};border-radius:4px}}
::-webkit-scrollbar-thumb:hover{{background:#CBD5E1}}
</style>
""", unsafe_allow_html=True)

inject_clean_css()  # Apply clean neutral skin

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="padding:18px 14px 14px;border-bottom:1px solid rgba(255,255,255,0.07);margin-bottom:4px">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:10px">
          <div style="width:30px;height:30px;background:{TEAL};border-radius:7px;
            display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0">📈</div>
          <div>
            <div style="font-size:13px;font-weight:700;color:#F1F5F9;letter-spacing:-0.01em">SAK Journal</div>
            <div style="font-size:10px;color:#475569">FY 2026-27</div>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    page = st.session_state.get("page", "dashboard")

    # SVG icons matching Tradezella
    NAV_ICONS = {
        "dashboard": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
        "dayview":   '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
        "journal":   '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>',
        "daily":     '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
        "chart":     '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/><polyline points="15,3 15,9"/></svg>',
        "notebook":  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>',
        "calendar":  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
        "reports":   '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
        "calc":      '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="10" y2="10"/><line x1="14" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="10" y2="14"/><line x1="14" y1="14" x2="16" y2="14"/></svg>',
        "strategy":  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
        "playbook":  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
        "progress":  '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
        "morning":   '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/></svg>',
        "tax_analytics":   '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1v22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
        "portfolio_dna":   '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>',
        "fund_management": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v16"/></svg>',
        "thematic_heatmap": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
        "tracker": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
        "comparison_engine": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "stock_niche_mapper": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
        "domain_vector": '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><line x1="10" y1="6.5" x2="14" y2="6.5"/><line x1="6.5" y1="10" x2="6.5" y2="14"/></svg>',
    }

    # Add Trade button - functional
    st.markdown('<div style="padding:8px 8px 4px">', unsafe_allow_html=True)
    if st.button("＋  Add Trade", key="sidebar_add_trade", use_container_width=True, type="primary"):
        st.session_state["show_add_trade"] = True
        st.session_state.page = "daily"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    nav = [
        ("dashboard","Dashboard"),
        ("dayview",  "Daily Journal"),
        ("journal",  "Trade Log"),
        ("daily",    "Daily Plan"),
        ("calendar", "Calendar"),
        ("notebook", "Notebook"),
        ("chart",    "Chart"),
        None,
        ("reports",  "Reports"),
        ("calc",     "Calculator"),
        ("strategy", "Strategy"),
        ("progress", "Progress Tracker"),
        ("playbook", "Playbook"),
        ("morning", "Morning Brief"),
        None,
        ("tax_analytics",   "Tax Analytics"),
        ("portfolio_dna",   "Portfolio DNA"),
        ("fund_management", "Fund Management"),
        None,
        ("thematic_heatmap", "Thematic Heatmap"),
        ("tracker", "Tracker"),
        ("comparison_engine", "Comparison Engine"),
        ("stock_niche_mapper", "Stock Niche Mapper"),
        ("domain_vector", "Domain Vector"),
        ("import",   "Import Excel"),
        ("terminal", "Terminal"),
    ]

    # Nav — use st.button with CSS override to look like Tradezella nav items
    page = st.session_state.get("page","dashboard")

    for item in nav:
        if item is None:
            st.markdown(f'<div style="height:1px;background:rgba(255,255,255,0.07);margin:5px 4px"></div>', unsafe_allow_html=True)
            continue
        if isinstance(item, str):
            st.markdown(f'<div style="font-size:9px;font-weight:600;color:rgba(255,255,255,0.3);letter-spacing:0.1em;padding:10px 12px 4px">{item}</div>', unsafe_allow_html=True)
            continue
        key, label = item
        icon_svg = NAV_ICONS.get(key,"")
        if page == key:
            # Active item — render as HTML (no click needed)
            st.markdown(f"""<div style="display:flex;align-items:center;gap:9px;padding:8px 10px;
                border-radius:7px;background:rgba(124,58,237,0.2);margin-bottom:1px">
                <span style="color:#A78BFA;flex-shrink:0;display:flex">{icon_svg}</span>
                <span style="font-size:12.5px;font-weight:600;color:#A78BFA">{label}</span>
            </div>""", unsafe_allow_html=True)
        else:
            # Inactive — real st.button that works, styled via CSS
            if st.button(f"{label}", key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()

    st.markdown(f'<div style="height:1px;background:rgba(255,255,255,0.07);margin:8px 2px 6px"></div>', unsafe_allow_html=True)

    pass  # Re-sync Excel removed — use Import Excel page instead

# ── First-run import ───────────────────────────────────────────────────────
if not last_sync_time():
    with st.spinner("First run — importing…"):
        try:
            from data.db import import_trading_journal
        except Exception:
            import_trading_journal = lambda: None
        n, msg = import_from_excel()
        import_trading_journal()
    if msg == "OK" and n > 0:
        st.success(f"✅ Imported {n} trades!")

# ── Route ──────────────────────────────────────────────────────────────────
p = st.session_state.get("page","dashboard")
try:
    if   p=="dashboard": from pages.dashboard         import render; render()
    elif p=="daily":     from pages.journal            import render; render()
    elif p=="journal":   from pages.trade_log          import render; render()
    elif p=="tradedetail": from pages.trade_detail       import render; render()
    elif p=="calendar":  from pages.calendar_view      import render; render()
    elif p=="dayview":   from pages.daily_journal      import render; render()
    elif p=="chart":     from pages.chart_view      import render; render()
    elif p=="notebook":  from pages.notebook            import render; render()
    elif p=="calc":      from pages.calculator         import render; render()
    elif p=="reports":   from pages.reports            import render; render()
    elif p=="strategy":  from pages.strategy_dashboard import render; render()
    elif p=="playbook": from pages.playbook         import render; render()
    elif p=="progress": from pages.progress_tracker import render; render()
    elif p=="morning":   from pages.morning_brief      import render; render()
    elif p=="terminal":  from pages.terminal           import render; render()
    elif p=="import":    from pages.import_excel      import render; render()
    elif p=="tax_analytics":   from pages.tax_analytics     import render; render()
    elif p=="tracker": from pages.tracker import render; render()
    elif p=="portfolio_dna":   from pages.portfolio_dna     import render; render()
    elif p=="fund_management": from pages.fund_management   import render; render()
    elif p=="thematic_heatmap": from pages.thematic_heatmap import render; render()
    elif p=="comparison_engine": from pages.comparison_engine import render; render()
    elif p=="stock_niche_mapper": from pages.stock_niche_mapper import render; render()
    elif p=="domain_vector": from pages.domain_vector import render; render()
    else:                from pages.dashboard          import render; render()
except Exception as _err:
    import traceback
    st.error(f"Page error: {_err}")
    st.code(traceback.format_exc())
