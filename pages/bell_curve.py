import streamlit as st
import plotly.graph_objects as go
import numpy as np
from scipy.stats import norm
from collections import defaultdict
from theme import *

def _bell_chart(returns, pnls, title_suffix=""):
    if len(returns) == 0:
        st.info("No trades in this period.")
        return

    returns = np.array(returns)
    pnls    = np.array(pnls)
    wins    = returns[returns > 0]
    losses  = returns[returns < 0]
    mean_r  = float(np.mean(returns))
    std_r   = float(np.std(returns)) if len(returns) > 1 else 0
    wr      = len(wins) / len(returns) * 100
    avg_win  = float(np.mean(wins))   if len(wins)   else 0
    avg_loss = float(np.mean(losses)) if len(losses) else 0
    wl_ratio = abs(avg_win / avg_loss) if avg_loss else 0
    total_pnl = float(np.sum(pnls))

    # KPI strip
    cols = st.columns(5)
    for col, (label, value, color) in zip(cols, [
        ("Trades",      str(len(returns)),          TEXT_H),
        ("Win Rate",    f"{wr:.1f}%",               TEAL if wr>=40 else AMBER),
        ("Mean Return", f"{mean_r:+.2f}%",          TEAL if mean_r>=0 else RED),
        ("Total P&L",   f"₹{total_pnl:,.0f}",      TEAL if total_pnl>=0 else RED),
        ("Std Dev",     f"{std_r:.2f}%",             TEXT_H),
    ]):
        col.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 16px;box-shadow:{SHADOW_SM}">
            <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:6px">{label}</div>
            <div style="font-size:20px;font-weight:700;color:{color};letter-spacing:-0.02em">{value}</div>
        </div>''', unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Bins
    bin_edges = list(np.arange(-0.42, 0.60, 0.02))
    bin_labels, bin_lower, bin_counts, bin_pnls = [], [], [], []
    for i in range(len(bin_edges)-1):
        lo, hi = bin_edges[i]*100, bin_edges[i+1]*100
        if i == 0: label = f"< {hi:.0f}%"
        elif i == len(bin_edges)-2: label = f"> {lo:.0f}%"
        else: label = f"{lo:.0f}% to {hi:.0f}%"
        mask = (returns >= lo) & (returns < hi)
        bin_labels.append(label); bin_lower.append(lo)
        bin_counts.append(int(np.sum(mask)))
        bin_pnls.append(float(np.sum(pnls[mask])))

    # Bell curve
    x_bell = np.array(bin_lower)
    y_bell = norm.pdf(x_bell, mean_r, std_r) if std_r > 0 else np.zeros_like(x_bell)
    max_count = max(bin_counts) if max(bin_counts) > 0 else 1
    max_bell  = max(y_bell) if max(y_bell) > 0 else 1
    y_bell_scaled = y_bell * (max_count / max_bell)

    fig = go.Figure()
    bar_colors = [TEAL if lo >= 0 else RED for lo in bin_lower]
    fig.add_trace(go.Bar(x=bin_lower, y=bin_counts, name="Trade count",
        marker=dict(color=bar_colors, opacity=0.8, line=dict(width=0)),
        text=[str(c) if c > 0 else "" for c in bin_counts],
        textposition="outside", textfont=dict(size=10, color=TEXT_MUTED),
        hovertemplate="<b>%{customdata}</b><br>Trades: %{y}<extra></extra>",
        customdata=bin_labels))
    if std_r > 0:
        fig.add_trace(go.Scatter(x=bin_lower, y=y_bell_scaled, name="Bell curve",
            mode="lines", line=dict(color=BLUE, width=2.5, shape="spline", smoothing=0.3),
            hovertemplate="%{x:.1f}%<extra></extra>"))
    fig.add_vline(x=mean_r, line=dict(color=TEAL, width=1.5, dash="dash"),
        annotation_text=f"Mean {mean_r:+.2f}%",
        annotation_font=dict(color=TEAL, size=10), annotation_position="top right")
    fig.add_vline(x=0, line=dict(color=BORDER_LIGHT, width=1))

    active_lowers = [lo for lo, c in zip(bin_lower, bin_counts) if c > 0]
    x_min = (min(active_lowers) - 4) if active_lowers else -20
    x_max = (max(active_lowers) + 4) if active_lowers else 40

    l = chart_layout(height=380, title="")
    l["xaxis"]["title"] = dict(text="Trade Return %", font=dict(size=10, color=TEXT_SUBTLE))
    l["xaxis"]["ticksuffix"] = "%"; l["xaxis"]["tickformat"] = ".0f"
    l["xaxis"]["range"] = [x_min, x_max]
    l["yaxis"]["title"] = dict(text="Number of trades", font=dict(size=10, color=TEXT_SUBTLE))
    l["showlegend"] = True
    l["legend"] = dict(orientation="h", y=-0.18, x=0.5, xanchor="center",
        bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=TEXT_MUTED))
    l["margin"] = dict(l=65, r=65, t=20, b=60); l["bargap"] = 0.05
    fig.update_layout(**l)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"bell_chart_{id(returns)}_{len(returns)}")

    # Stats cards
    sc1, sc2, sc3, sc4 = st.columns(4)
    for col, (label, value, color) in zip([sc1,sc2,sc3,sc4], [
        ("Avg Win",        f"{avg_win:+.2f}%",   TEAL),
        ("Avg Loss",       f"{avg_loss:+.2f}%",  RED),
        ("Win/Loss Ratio", f"{wl_ratio:.2f}x",   TEAL if wl_ratio>=1 else RED),
        ("Std Deviation",  f"{std_r:.2f}%",       TEXT_H),
    ]):
        col.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 16px;box-shadow:{SHADOW_SM}">
            <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:6px">{label}</div>
            <div style="font-size:20px;font-weight:700;color:{color};letter-spacing:-0.02em">{value}</div>
        </div>''', unsafe_allow_html=True)


def render():
    st.markdown("## Bell Curve")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:18px;font-size:11px">Trade % return distribution</p>', unsafe_allow_html=True)

    try:
        from data.db import get_trades
        trades = [t for t in get_trades() if t.get("status")=="CLOSED"
                  and t.get("entry_price") and t.get("exit_price")]
    except Exception as e:
        st.error(f"Error loading trades: {e}"); return

    if not trades:
        st.info("No closed trades found."); return

    all_returns, all_pnls = [], []
    for t in trades:
        ep = float(t.get("entry_price") or 0)
        xp = float(t.get("exit_price")  or 0)
        if ep <= 0: continue
        side = str(t.get("side","")).upper()
        raw = (xp - ep) / ep * 100
        all_returns.append(raw if side not in ("SHORT","SELL") else -raw)
        all_pnls.append(float(t.get("pnl") or 0))

    # Group by month and year
    monthly = defaultdict(lambda: {"returns": [], "pnls": []})
    yearly  = defaultdict(lambda: {"returns": [], "pnls": []})
    for t, ret, pnl in zip(trades, all_returns, all_pnls):
        ed = str(t.get("exit_date",""))[:10]
        if ed and ed != "nan":
            monthly[ed[:7]]["returns"].append(ret)
            monthly[ed[:7]]["pnls"].append(pnl)
            yearly[ed[:4]]["returns"].append(ret)
            yearly[ed[:4]]["pnls"].append(pnl)

    tab_all, tab_monthly, tab_yearly = st.tabs(["📊 Overall", "📅 Monthly", "📆 Yearly"])

    with tab_all:
        _bell_chart(all_returns, all_pnls)

    with tab_monthly:
        months = sorted(monthly.keys(), reverse=True)
        if months:
            sel_month = st.selectbox("Select Month", months, key="bell_month_sel")
            _bell_chart(monthly[sel_month]["returns"], monthly[sel_month]["pnls"])

    with tab_yearly:
        years = sorted(yearly.keys(), reverse=True)
        if years:
            sel_year = st.selectbox("Select Year", years, key="bell_year_sel")
            _bell_chart(yearly[sel_year]["returns"], yearly[sel_year]["pnls"])
