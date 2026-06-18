import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
try:
    import openpyxl
except ImportError:
    openpyxl = None
from theme import *

EXCEL_PATH = "Daily_P__FY26-27_.xlsx"

def load_bell_data():
    try:
        wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
        ws = wb['Bell']
        rows = list(ws.iter_rows(values_only=True))

        # Main distribution data (cols A-F)
        data = []
        for row in rows[1:]:
            if row[0] and isinstance(row[0], str) and row[3] is not None:
                try:
                    count = float(row[3]) if row[3] is not None else 0
                    bell  = float(row[4]) if row[4] is not None else 0
                    pnl   = float(row[5]) if row[5] is not None else 0
                    lower = float(row[1]) if row[1] is not None else 0
                    data.append({
                        'range': row[0],
                        'lower': lower,
                        'count': int(count),
                        'bell':  bell,
                        'pnl':   pnl,
                    })
                except: pass

        # Stats (cols G-H: value, label)
        stats = {}
        for row in rows[1:18]:
            if row[7] and row[6] is not None:
                try:
                    stats[str(row[7])] = row[6]
                except: pass

        wb.close()
        return data, stats
    except Exception as e:
        return [], {}


def render():
    st.markdown("## Bell Curve")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:18px;font-size:11px">FY 2026-27 · Trade % gain/loss distribution</p>', unsafe_allow_html=True)

    data, stats = load_bell_data()

    if not data:
        st.info("Bell curve Excel file not available on cloud. Generating from trade data...")
        # Generate from Supabase trades instead
        try:
            from data.db import get_trades
            trades = [t for t in get_trades() if t.get("status")=="CLOSED" and t.get("r_multiple")]
            if not trades:
                st.warning("No closed trades with R-multiple data found.")
                return
            import plotly.graph_objects as go
            import numpy as np
            rs = [float(t["r_multiple"]) for t in trades]
            mean_r = np.mean(rs); std_r = np.std(rs)
            # Clip outliers for display
            p5, p95 = np.percentile(rs, 5), np.percentile(rs, 95)
            x_range = [min(-3, p5-0.5), max(5, p95+0.5)]

            # Normal curve
            x_norm = np.linspace(x_range[0], x_range[1], 200)
            from scipy.stats import norm
            y_norm = norm.pdf(x_norm, mean_r, std_r) * len(rs) * (x_range[1]-x_range[0])/30

            fig = go.Figure()
            fig.add_trace(go.Histogram(x=rs, nbinsx=30, name="R Distribution",
                marker_color="#10B981", opacity=0.7,
                xbins=dict(start=x_range[0], end=x_range[1])))
            fig.add_trace(go.Scatter(x=x_norm, y=y_norm, mode="lines",
                name="Normal Curve", line=dict(color="#7C3AED", width=2)))
            fig.add_vline(x=0, line=dict(color="#EF4444", width=1, dash="dash"))
            fig.add_vline(x=mean_r, line=dict(color="#F59E0B", width=1, dash="dot"),
                annotation_text=f"Mean {mean_r:.2f}R", annotation_position="top right")
            fig.update_layout(title="R-Multiple Distribution",
                xaxis_title="R-Multiple", yaxis_title="Count",
                xaxis=dict(range=x_range),
                height=420, paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)

            # Stats strip
            wins = [r for r in rs if r>0]; losses = [r for r in rs if r<0]
            k1,k2,k3,k4,k5 = st.columns(5)
            k1.metric("Total Trades", len(rs))
            k2.metric("Win Rate", f"{len(wins)/len(rs)*100:.1f}%")
            k3.metric("Avg R", f"{mean_r:.2f}R")
            k4.metric("Avg Win R", f"{np.mean(wins):.2f}R" if wins else "—")
            k5.metric("Avg Loss R", f"{np.mean(losses):.2f}R" if losses else "—")
        except Exception as e:
            st.error(f"Error: {e}")
        return

    # Filter to rows with actual trades
    active = [d for d in data if d['count'] > 0]
    all_ranges = data  # use all for bell curve line

    # ── KPI strip from Excel stats ────────────────────────────────────────
    def pct(v):
        try: return f"{float(v)*100:.2f}%"
        except: return str(v)
    def fmt(v):
        try: return f"{float(v):,.0f}"
        except: return str(v)

    mean_val   = float(stats.get('Mean (Average)', 0)) * 100
    std_val    = float(stats.get('Standard Deviation', 0)) * 100
    wr_val     = float(stats.get('Win Rate', 0)) * 100
    avg_win    = float(stats.get('Avg Win', 0)) * 100
    avg_loss   = float(stats.get('Avg Loss', 0)) * 100
    wl_ratio   = float(stats.get('Win/Loss Ratio', 0))
    total_pnl  = float(stats.get('Total P&L', 0))
    total_tr   = int(float(stats.get('Total Trades', 0)))
    expectancy = float(stats.get('Expectancy (R)', 0))

    cols = st.columns(5)
    for col, (label, value, color) in zip(cols, [
        ("Total Trades",  str(total_tr),            TEXT_H),
        ("Win Rate",      f"{wr_val:.1f}%",          TEAL if wr_val>=40 else AMBER),
        ("Mean Return",   f"{mean_val:+.2f}%",       TEAL if mean_val>=0 else RED),
        ("Total P&L",     f"₹{total_pnl:,.0f}",     TEAL if total_pnl>=0 else RED),
        ("Expectancy",    f"{expectancy:+.2f}R",     TEAL if expectancy>=0 else RED),
    ]):
        col.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
            padding:14px 16px;box-shadow:{SHADOW_SM}">
            <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:6px">{label}</div>
            <div style="font-size:20px;font-weight:700;color:{color};letter-spacing:-0.02em">{value}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Main chart ───────────────────────────────────────────────────────
    # X axis: use lower bound of each bin
    xs     = [d['lower']*100 for d in data]
    bells  = [d['bell']      for d in data]
    counts = [d['count']     for d in data]
    labels = [d['range']     for d in data]

    fig = go.Figure()

    # Normalise bell curve to same scale as bar counts
    max_count = max(counts) if counts else 1
    max_bell  = max(bells)  if bells  else 1
    scale     = max_count / max_bell if max_bell else 1
    bells_scaled = [b * scale for b in bells]

    # Bars — count per bin, coloured green/red by sign of lower bound
    bar_colors = [TEAL if d['lower'] >= 0 else RED for d in data]
    fig.add_trace(go.Bar(
        x=xs, y=counts,
        name="Trade count",
        marker=dict(color=bar_colors, opacity=0.8, line=dict(width=0)),
        text=[str(c) if c > 0 else "" for c in counts],
        textposition="outside",
        textfont=dict(size=10, color=TEXT_MUTED, family="Inter"),
        hovertemplate="<b>%{customdata}</b><br>Trades: %{y}<extra></extra>",
        customdata=labels,
    ))

    # Bell curve line — scaled to same axis as bars
    fig.add_trace(go.Scatter(
        x=xs, y=bells_scaled,
        name="Bell curve",
        mode="lines",
        line=dict(color=BLUE, width=2.5, shape="spline", smoothing=0.3),
        hovertemplate="%{x:.1f}%<extra></extra>",
    ))

    # Mean line
    fig.add_vline(
        x=mean_val,
        line=dict(color=TEAL, width=1.5, dash="dash"),
        annotation_text=f"Mean {mean_val:+.2f}%",
        annotation_font=dict(color=TEAL, size=10),
        annotation_position="top right",
    )

    # Zero line
    fig.add_vline(x=0, line=dict(color=BORDER_LIGHT, width=1))

    l = chart_layout(height=420, title="")
    l["xaxis"]["title"] = dict(text="Trade Return %", font=dict(size=10, color=TEXT_SUBTLE))
    l["xaxis"]["ticksuffix"] = "%"
    l["xaxis"]["tickformat"] = ".0f"
    l["yaxis"]["title"] = dict(text="Number of trades", font=dict(size=10, color=TEXT_SUBTLE))

    l["showlegend"] = True
    l["legend"] = dict(
        orientation="h", y=-0.18, x=0.5, xanchor="center",
        bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=TEXT_MUTED)
    )
    # Clip x-axis to where data actually is
    active_xs = [d['lower']*100 for d in data if d['count'] > 0]
    if active_xs:
        x_min = min(active_xs) - 4
        x_max = max(active_xs) + 4
    else:
        x_min, x_max = -20, 40
    l["xaxis"]["range"] = [x_min, x_max]
    l["margin"] = dict(l=65, r=65, t=20, b=60)
    l["bargap"] = 0.05
    fig.update_layout(**l)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Stats cards ──────────────────────────────────────────────────────
    sc1, sc2, sc3, sc4 = st.columns(4)
    for col, (label, value, color) in zip([sc1,sc2,sc3,sc4], [
        ("Avg Win",       f"{avg_win:+.2f}%",   TEAL),
        ("Avg Loss",      f"{avg_loss:+.2f}%",  RED),
        ("Win/Loss Ratio",f"{wl_ratio:.2f}x",   TEAL if wl_ratio>=1 else RED),
        ("Std Deviation", f"{std_val:.2f}%",     TEXT_H),
    ]):
        col.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
            padding:14px 16px;box-shadow:{SHADOW_SM}">
            <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:6px">{label}</div>
            <div style="font-size:20px;font-weight:700;color:{color};letter-spacing:-0.02em">{value}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Distribution table ───────────────────────────────────────────────
    st.markdown(f'<p style="font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Distribution Detail</p>', unsafe_allow_html=True)

    rows_html = ""
    TH = f"padding:9px 14px;font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;background:{TABLE_HEAD_BG};border-bottom:1px solid {BORDER}"
    TD = f"padding:8px 14px;font-size:12.5px;border-bottom:1px solid {BORDER_LIGHT}"

    for d in active:
        pnl_c = TEAL if d['pnl'] >= 0 else RED
        bar_w = int(d['count'] / max(d['count'] for d in active) * 100) if active else 0
        bar_c = TEAL if d['lower'] >= 0 else RED
        rows_html += f"""<tr>
            <td style="{TD};font-weight:600;color:{TEXT_H}">{d['range']}</td>
            <td style="{TD};text-align:center;font-weight:700;color:{TEXT_H}">{d['count']}</td>
            <td style="{TD}">
                <div style="display:flex;align-items:center;gap:8px">
                    <div style="flex:1;height:6px;background:{BORDER_LIGHT};border-radius:3px;overflow:hidden">
                        <div style="width:{bar_w}%;height:100%;background:{bar_c};border-radius:3px"></div>
                    </div>
                    <span style="font-size:11px;color:{TEXT_MUTED};width:30px">{bar_w}%</span>
                </div>
            </td>
            <td style="{TD};text-align:right;font-weight:600;color:{pnl_c}">{"+" if d['pnl']>=0 else ""}₹{abs(d['pnl']):,.0f}</td>
        </tr>"""

    st.markdown(f"""<table style="width:100%;border-collapse:collapse">
        <thead><tr>
            <th style="{TH};text-align:left">Range</th>
            <th style="{TH};text-align:center">Trades</th>
            <th style="{TH};text-align:left">Distribution</th>
            <th style="{TH};text-align:right">Total P&amp;L</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>""", unsafe_allow_html=True)
