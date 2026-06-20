import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data.db import get_journal_trades
from theme import *

def safe_float(v):
    try: return float(v or 0)
    except: return 0.0

def fmt_pnl(v):
    return f"{'+' if v>=0 else ''}₹{abs(v):,.0f}" if v>=0 else f"-₹{abs(v):,.0f}"

def stock_move_pct(t):
    """% move of the underlying from entry to exit (not P&L%, the raw stock move)."""
    ep = safe_float(t.get("entry_price"))
    xp = safe_float(t.get("exit_price"))
    if ep <= 0:
        return 0.0
    side = str(t.get("side","") or "").upper()
    raw = (xp - ep) / ep * 100
    return raw if side != "SHORT" else -raw


def render():
    st.markdown("## Pareto / Asymmetry Analysis")
    st.caption("How concentrated is your profit? This is the structural-asymmetry lens on your MFE-capture problem.")

    trades = get_journal_trades()
    closed = [t for t in trades if t.get("status") == "CLOSED"]

    # ── filters ──────────────────────────────────────────────────────────
    c1, c2 = st.columns([1,3])
    with c1:
        strat_opts = ["All Strategies"] + sorted({t.get("strategy","") for t in closed if t.get("strategy")})
        strat_sel = st.selectbox("Strategy", strat_opts, key="pareto_strat")
    if strat_sel != "All Strategies":
        closed = [t for t in closed if t.get("strategy") == strat_sel]

    if not closed:
        st.info("No closed trades found for this filter.")
        return

    wins = [t for t in closed if safe_float(t.get("pnl")) > 0]
    total_gross_profit = sum(safe_float(t.get("pnl")) for t in wins)

    if not wins or total_gross_profit <= 0:
        st.info("No winning trades yet to analyze.")
        return

    # sort winners descending by P&L
    wins_sorted = sorted(wins, key=lambda t: safe_float(t.get("pnl")), reverse=True)

    cum_pct = []
    running = 0.0
    for t in wins_sorted:
        running += safe_float(t.get("pnl"))
        cum_pct.append(running / total_gross_profit * 100)

    n = len(wins_sorted)
    top1_pct  = cum_pct[0] if n >= 1 else 0
    top3_pct  = cum_pct[min(2, n-1)] if n >= 1 else 0
    top5_pct  = cum_pct[min(4, n-1)] if n >= 1 else 0

    # find smallest N such that cum_pct[N-1] >= 80 (Pareto threshold)
    pareto_n = next((i+1 for i, c in enumerate(cum_pct) if c >= 80), n)
    pareto_share = cum_pct[pareto_n-1] if pareto_n <= n else 100.0

    # ── narrative card ──────────────────────────────────────────────────
    left, right = st.columns([1, 2])
    with left:
        st.markdown(f"""<div style="background:{TEAL_BG};border:1px solid {TEAL_BORDER};border-radius:12px;padding:18px 20px;">
            <div style="display:inline-flex;align-items:center;gap:6px;background:{CARD_BG};border:1px solid {TEAL_BORDER};
                border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600;color:{TEAL_DARK};margin-bottom:10px">
                ⚡ ASYMMETRY {"FOUND" if pareto_share >= 70 else "MODERATE"}
            </div>
            <div style="font-size:11px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;font-weight:500;margin-bottom:6px">
                Statistical Narrative
            </div>
            <div style="font-size:14px;color:{TEXT_BODY};line-height:1.5">
                A significant <b style="color:{TEXT_H};font-size:16px">{pareto_share:.1f}%</b> of your gross profit comes
                from just <b style="color:{TEXT_H};font-size:16px">{pareto_n}</b> trades (out of {n} winners, {len(closed)} closed total).
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3)
        k1.markdown(kpi_card("TOP 1", f"{top1_pct:.0f}%"), unsafe_allow_html=True)
        k2.markdown(kpi_card("TOP 3", f"{top3_pct:.0f}%"), unsafe_allow_html=True)
        k3.markdown(kpi_card("TOP 5", f"{top5_pct:.0f}%"), unsafe_allow_html=True)

    with right:
        fig = go.Figure()
        x = list(range(1, n+1))
        fig.add_trace(go.Scatter(
            x=x, y=cum_pct, mode="lines+markers", fill="tozeroy",
            fillcolor="rgba(16,185,129,0.20)",
            line=dict(color=TEAL, width=2.5, shape="spline"),
            marker=dict(size=5, color=TEAL),
            hovertemplate="Top %{x} trades<br>%{y:.1f}% of profit<extra></extra>",
        ))
        fig.add_hline(y=80, line=dict(color=AMBER, width=1, dash="dash"),
                       annotation_text="80%", annotation_font=dict(color=AMBER, size=9))
        l = chart_layout(height=280, title="Cumulative Gross Profit Share — Top N Winners")
        l["yaxis"]["range"] = [0, 105]
        l["yaxis"]["ticksuffix"] = "%"
        l["xaxis"]["title"] = dict(text="N winning trades", font=dict(size=10, color=TEXT_SUBTLE))
        fig.update_layout(**l)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(section_label("Top Winners Breakdown"), unsafe_allow_html=True)

    rows = []
    for i, t in enumerate(wins_sorted[:15]):
        p = safe_float(t.get("pnl"))
        rows.append({
            "#": f"#{i+1}",
            "Symbol": t.get("ticker",""),
            "Strategy": t.get("strategy",""),
            "Stock Move %": f"{stock_move_pct(t):+.1f}%",
            "P&L": fmt_pnl(p),
            "PF Impact %": f"{p/total_gross_profit*100:+.1f}%",
            "Exit Date": str(t.get("exit_date",""))[:10],
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown(section_label("What this means"), unsafe_allow_html=True)
    st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 18px;font-size:13px;color:{TEXT_BODY};line-height:1.6">
        If a small number of trades drive most of your profit, your exit execution on the <i>rest</i> of your winners is likely
        cutting them short — i.e. an MFE-capture problem, not a stop-loss problem. The fix is usually trailing/scale-out discipline
        on trades that are already working, not finding more setups.
    </div>""", unsafe_allow_html=True)
