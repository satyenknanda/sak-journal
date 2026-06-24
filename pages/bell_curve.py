import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from scipy.stats import norm
from theme import *

def render():
    st.markdown("## Bell Curve")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:18px;font-size:11px">Trade % return distribution — FY 2026-27</p>', unsafe_allow_html=True)

    try:
        from data.db import get_trades
        trades = [t for t in get_trades() if t.get("status")=="CLOSED"
                  and t.get("entry_price") and t.get("exit_price")]
    except Exception as e:
        st.error(f"Error loading trades: {e}"); return

    if not trades:
        st.info("No closed trades found."); return

    # ── Calculate % returns ───────────────────────────────────────────────
    returns = []
    pnls    = []
    for t in trades:
        ep = float(t.get("entry_price") or 0)
        xp = float(t.get("exit_price")  or 0)
        if ep <= 0: continue
        side = str(t.get("side","")).upper()
        raw = (xp - ep) / ep * 100
        ret = raw if side not in ("SHORT","SELL") else -raw
        returns.append(ret)
        pnls.append(float(t.get("pnl") or 0))

    returns = np.array(returns)
    pnls    = np.array(pnls)

    # ── Stats ─────────────────────────────────────────────────────────────
    wins      = returns[returns > 0]
    losses    = returns[returns < 0]
    mean_r    = float(np.mean(returns))
    std_r     = float(np.std(returns))
    wr        = len(wins) / len(returns) * 100
    avg_win   = float(np.mean(wins))   if len(wins)   else 0
    avg_loss  = float(np.mean(losses)) if len(losses) else 0
    wl_ratio  = abs(avg_win / avg_loss) if avg_loss else 0
    total_pnl = float(np.sum(pnls))
    exp_r     = float(np.mean([float(t.get("r_multiple") or 0) for t in trades]))

    # ── KPI strip ─────────────────────────────────────────────────────────
    cols = st.columns(5)
    for col, (label, value, color) in zip(cols, [
        ("Total Trades",  str(len(returns)),          TEXT_H),
        ("Win Rate",      f"{wr:.1f}%",               TEAL if wr>=40 else AMBER),
        ("Mean Return",   f"{mean_r:+.2f}%",          TEAL if mean_r>=0 else RED),
        ("Total P&L",     f"₹{total_pnl:,.0f}",      TEAL if total_pnl>=0 else RED),
        ("Expectancy",    f"{exp_r:+.2f}R",           TEAL if exp_r>=0 else RED),
    ]):
        col.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
            padding:14px 16px;box-shadow:{SHADOW_SM}">
            <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:6px">{label}</div>
            <div style="font-size:20px;font-weight:700;color:{color};letter-spacing:-0.02em">{value}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Bins: 2% width from -42% to +58% (matching Excel) ────────────────
    bin_edges = list(np.arange(-0.42, 0.60, 0.02))
    bin_labels = []
    bin_lower  = []
    bin_counts = []
    bin_pnls   = []

    for i in range(len(bin_edges)-1):
        lo = bin_edges[i]
        hi = bin_edges[i+1]
        lo_pct = lo * 100
        hi_pct = hi * 100
        if i == 0:
            label = f"< {hi_pct:.0f}%"
        elif i == len(bin_edges)-2:
            label = f"> {lo_pct:.0f}%"
        else:
            label = f"{lo_pct:.0f}% to {hi_pct:.0f}%"
        mask = (returns >= lo_pct) & (returns < hi_pct)
        bin_labels.append(label)
        bin_lower.append(lo_pct)
        bin_counts.append(int(np.sum(mask)))
        bin_pnls.append(float(np.sum(pnls[mask])))

    # ── Bell curve (normal distribution) ─────────────────────────────────
    x_bell = np.array(bin_lower)
    y_bell = norm.pdf(x_bell, mean_r, std_r)
    max_count = max(bin_counts) if max(bin_counts) > 0 else 1
    max_bell  = max(y_bell) if max(y_bell) > 0 else 1
    y_bell_scaled = y_bell * (max_count / max_bell)

    # ── Chart ─────────────────────────────────────────────────────────────
    fig = go.Figure()

    bar_colors = [TEAL if lo >= 0 else RED for lo in bin_lower]
    fig.add_trace(go.Bar(
        x=bin_lower, y=bin_counts,
        name="Trade count",
        marker=dict(color=bar_colors, opacity=0.8, line=dict(width=0)),
        text=[str(c) if c > 0 else "" for c in bin_counts],
        textposition="outside",
        textfont=dict(size=10, color=TEXT_MUTED),
        hovertemplate="<b>%{customdata}</b><br>Trades: %{y}<extra></extra>",
        customdata=bin_labels,
    ))

    fig.add_trace(go.Scatter(
        x=bin_lower, y=y_bell_scaled,
        name="Bell curve",
        mode="lines",
        line=dict(color=BLUE, width=2.5, shape="spline", smoothing=0.3),
        hovertemplate="%{x:.1f}%<extra></extra>",
    ))

    fig.add_vline(x=mean_r, line=dict(color=TEAL, width=1.5, dash="dash"),
        annotation_text=f"Mean {mean_r:+.2f}%",
        annotation_font=dict(color=TEAL, size=10),
        annotation_position="top right")
    fig.add_vline(x=0, line=dict(color=BORDER_LIGHT, width=1))

    # Clip x-axis to active bins
    active_lowers = [lo for lo, c in zip(bin_lower, bin_counts) if c > 0]
    x_min = (min(active_lowers) - 4) if active_lowers else -20
    x_max = (max(active_lowers) + 4) if active_lowers else 40

    l = chart_layout(height=420, title="")
    l["xaxis"]["title"]     = dict(text="Trade Return %", font=dict(size=10, color=TEXT_SUBTLE))
    l["xaxis"]["ticksuffix"] = "%"
    l["xaxis"]["tickformat"] = ".0f"
    l["xaxis"]["range"]      = [x_min, x_max]
    l["yaxis"]["title"]      = dict(text="Number of trades", font=dict(size=10, color=TEXT_SUBTLE))
    l["showlegend"] = True
    l["legend"] = dict(orientation="h", y=-0.18, x=0.5, xanchor="center",
        bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=TEXT_MUTED))
    l["margin"]  = dict(l=65, r=65, t=20, b=60)
    l["bargap"]  = 0.05
    fig.update_layout(**l)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Stats cards ───────────────────────────────────────────────────────
    sc1, sc2, sc3, sc4 = st.columns(4)
    for col, (label, value, color) in zip([sc1,sc2,sc3,sc4], [
        ("Avg Win",        f"{avg_win:+.2f}%",   TEAL),
        ("Avg Loss",       f"{avg_loss:+.2f}%",  RED),
        ("Win/Loss Ratio", f"{wl_ratio:.2f}x",   TEAL if wl_ratio>=1 else RED),
        ("Std Deviation",  f"{std_r:.2f}%",       TEXT_H),
    ]):
        col.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
            padding:14px 16px;box-shadow:{SHADOW_SM}">
            <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:6px">{label}</div>
            <div style="font-size:20px;font-weight:700;color:{color};letter-spacing:-0.02em">{value}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Distribution table ────────────────────────────────────────────────
    st.markdown(f'<p style="font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Distribution Detail</p>', unsafe_allow_html=True)

    active_bins = [(l, c, p) for l, lo, c, p in zip(bin_labels, bin_lower, bin_counts, bin_pnls) if c > 0]
    max_c = max(c for _, c, _ in active_bins) if active_bins else 1

    TH = f"padding:9px 14px;font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;background:{TABLE_HEAD_BG};border-bottom:1px solid {BORDER}"
    TD = f"padding:8px 14px;font-size:12.5px;border-bottom:1px solid {BORDER_LIGHT}"

    rows_html = ""
    for label, count, pnl in active_bins:
        pnl_c = TEAL if pnl >= 0 else RED
        bar_w = int(count / max_c * 100)
        bar_c = TEAL if pnl >= 0 else RED
        rows_html += f"""<tr>
            <td style="{TD};font-weight:600;color:{TEXT_H}">{label}</td>
            <td style="{TD};text-align:center;font-weight:700;color:{TEXT_H}">{count}</td>
            <td style="{TD}">
                <div style="display:flex;align-items:center;gap:8px">
                    <div style="flex:1;height:6px;background:{BORDER_LIGHT};border-radius:3px;overflow:hidden">
                        <div style="width:{bar_w}%;height:100%;background:{bar_c};border-radius:3px"></div>
                    </div>
                    <span style="font-size:11px;color:{TEXT_MUTED};width:30px">{bar_w}%</span>
                </div>
            </td>
            <td style="{TD};text-align:right;font-weight:600;color:{pnl_c}">{"+" if pnl>=0 else ""}₹{abs(pnl):,.0f}</td>
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
