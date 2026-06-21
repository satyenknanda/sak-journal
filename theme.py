# ── Exact Tradezella design tokens ─────────────────────────────────────────
# Extracted pixel-by-pixel from screenshots

# Core colours
TEAL        = "#10B981"   # primary accent, active nav, positive values
TEAL_DARK   = "#059669"   # hover teal
TEAL_BG     = "#ECFDF5"   # teal light background (win badges)
TEAL_BORDER = "#A7F3D0"   # teal border

RED         = "#EF4444"   # negative values, losses
RED_BG      = "#FEF2F2"   # red light bg (loss badges)
RED_BORDER  = "#FECACA"   # red border

AMBER       = "#F59E0B"   # warning, marginal
AMBER_BG    = "#FFFBEB"
AMBER_BORDER= "#FDE68A"

BLUE        = "#3B82F6"   # secondary, open badges, long
BLUE_BG     = "#EFF6FF"
BLUE_BORDER = "#BFDBFE"

PURPLE      = "#8B5CF6"

# Text hierarchy — exact Tradezella
TEXT_H      = "#0F172A"   # headings, ticker names, large values — slate-900
TEXT_BODY   = "#334155"   # body text, table cells — slate-700
TEXT_MUTED  = "#64748B"   # labels, secondary — slate-500
TEXT_SUBTLE = "#94A3B8"   # placeholders, hints — slate-400
TEXT_DIM    = "#CBD5E1"   # disabled, very muted — slate-300

# Backgrounds
PAGE_BG     = "#F8FAFC"   # page background — slate-50
CARD_BG     = "#FFFFFF"   # card, table background
SIDEBAR_BG  = "#0F172A"   # sidebar — slate-900
SIDEBAR_HOVER = "#1E293B" # sidebar hover — slate-800
TABLE_HEAD_BG = "#F8FAFC" # table header bg

# Borders & dividers
BORDER      = "#E2E8F0"   # card borders — slate-200
BORDER_LIGHT= "#F1F5F9"   # table row dividers — slate-100
BORDER_MED  = "#CBD5E1"   # stronger borders — slate-300

# Chart specific
CHART_GRID  = "#F1F5F9"   # almost invisible grid lines
CHART_AXIS  = "#CBD5E1"   # axis tick text

# Shadow
SHADOW_SM   = "0 1px 2px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.06)"
SHADOW_MD   = "0 2px 4px rgba(0,0,0,0.06), 0 4px 8px rgba(0,0,0,0.04)"

# Strategy colours
STRAT_COLORS = ["#10B981","#3B82F6","#8B5CF6","#F59E0B","#EC4899","#14B8A6","#F97316","#06B6D4"]


def chart_layout(height=240, title="", margin=None):
    """Exact Tradezella Plotly layout."""
    m = margin or dict(l=50, r=16, t=36 if title else 12, b=44)
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        font=dict(
            family="'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",
            color=TEXT_BODY, size=11,
        ),
        margin=m,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            linecolor=BORDER,
            linewidth=1,
            tickfont=dict(color=TEXT_SUBTLE, size=10, family="Inter"),
            ticklen=0,
            showline=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=CHART_GRID,
            gridwidth=1,
            zeroline=False,
            linecolor=BORDER,
            tickfont=dict(color=TEXT_SUBTLE, size=10, family="Inter"),
            ticklen=0,
            showline=False,
        ),
        legend=dict(
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor=BORDER,
            borderwidth=1,
            font=dict(color=TEXT_MUTED, size=10, family="Inter"),
            orientation="h",
            yanchor="bottom", y=-0.28,
            xanchor="center", x=0.5,
        ),
        hoverlabel=dict(
            bgcolor=CARD_BG,
            bordercolor=BORDER,
            font=dict(color=TEXT_BODY, size=11, family="Inter"),
            namelength=-1,
        ),
        hovermode="x unified",
        showlegend=False,
    )
    if title:
        layout["title"] = dict(
            text=title,
            font=dict(color=TEXT_MUTED, size=11, family="Inter", weight=500),
            x=0, xanchor="left", pad=dict(l=0, b=6),
        )
    return layout


def kpi_card(label, value, sub=None, color=None):
    """Exact Tradezella KPI card — white, subtle shadow, no border accent."""
    c = color or TEXT_H
    sub_html = f'<div style="font-size:11px;color:{TEXT_SUBTLE};margin-top:3px;font-family:Inter,sans-serif">{sub}</div>' if sub else ""
    return (f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;'
            f'padding:14px 16px;box-shadow:{SHADOW_SM};min-height:78px">'
            f'<div style="font-size:10.5px;color:{TEXT_SUBTLE};text-transform:uppercase;'
            f'letter-spacing:0.07em;font-weight:500;margin-bottom:6px;font-family:Inter,sans-serif">{label}</div>'
            f'<div style="font-size:1.35rem;font-weight:700;color:{c};letter-spacing:-0.02em;'
            f'font-family:Inter,sans-serif;font-variant-numeric:tabular-nums;line-height:1.2">{value}</div>'
            f'{sub_html}'
            f'</div>')


def section_label(text):
    """Small uppercase section label like Tradezella uses above chart groups."""
    return f'<p style="font-size:10.5px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.07em;margin:14px 0 8px;font-family:Inter,sans-serif">{text}</p>'


TABLE_STYLES = [
    {"selector": "table",
     "props": [("border-collapse","collapse"),("width","100%"),("font-family","Inter,sans-serif")]},
    {"selector": "thead th",
     "props": [("background-color", TABLE_HEAD_BG),
               ("color", TEXT_SUBTLE),
               ("font-size", "10px"),
               ("font-weight", "500"),
               ("text-transform", "uppercase"),
               ("letter-spacing", "0.07em"),
               ("border-bottom", f"1px solid {BORDER}"),
               ("padding", "9px 12px"),
               ("white-space", "nowrap")]},
    {"selector": "tbody td",
     "props": [("padding","9px 12px"),
               ("border-bottom", f"1px solid {BORDER_LIGHT}"),
               ("font-size","13px"),
               ("color", TEXT_BODY),
               ("font-family","Inter,sans-serif")]},
    {"selector": "tbody tr:hover td",
     "props": [("background-color", TABLE_HEAD_BG)]},
    {"selector": "tbody tr:last-child td",
     "props": [("font-weight","600"),
               ("background-color", TABLE_HEAD_BG),
               ("border-bottom","none")]},
]


def badge(label, style="open"):
    styles = {
        "open":     (BLUE_BG,   BLUE,   BLUE_BORDER),
        "win":      (TEAL_BG,   TEAL,   TEAL_BORDER),
        "loss":     (RED_BG,    RED,    RED_BORDER),
        "sl":       (AMBER_BG,  AMBER,  AMBER_BORDER),
        "positive": (TEAL_BG,   TEAL,   TEAL_BORDER),
        "marginal": (AMBER_BG,  AMBER,  AMBER_BORDER),
        "negative": (RED_BG,    RED,    RED_BORDER),
    }
    bg, fg, br = styles.get(style, (PAGE_BG, TEXT_MUTED, BORDER))
    return (f'<span style="display:inline-flex;align-items:center;padding:2px 9px;'
            f'border-radius:20px;font-size:10px;font-weight:600;white-space:nowrap;'
            f'background:{bg};color:{fg};border:1px solid {br};font-family:Inter,sans-serif">{label}</span>')

DNA_COLORS = ["#7C3AED","#EC4899","#10B981","#F59E0B","#3B82F6","#14B8A6",
              "#F97316","#06B6D4","#8B5CF6","#DC2626","#0D9488","#D97706"]
