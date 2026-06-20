import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from data.db import get_journal_trades
from theme import *

def safe_float(v):
    try: return float(v or 0)
    except: return 0.0

def fmt_pnl(v):
    return f"{'+' if v>=0 else ''}₹{abs(v):,.0f}" if v>=0 else f"-₹{abs(v):,.0f}"

BUCKETS = ["Intraday", "1-3 Days", "4-7 Days", "1-2 Weeks", "2-4 Weeks", "1-2 Months", "2+ Months"]

def holding_days(t):
    try:
        ed = datetime.strptime(str(t.get("entry_date",""))[:10], "%Y-%m-%d")
        xd = datetime.strptime(str(t.get("exit_date",""))[:10], "%Y-%m-%d")
        return (xd - ed).days
    except Exception:
        return None

def bucket_for(days):
    if days is None: return None
    if days <= 0: return "Intraday"
    if days <= 3: return "1-3 Days"
    if days <= 7: return "4-7 Days"
    if days <= 14: return "1-2 Weeks"
    if days <= 28: return "2-4 Weeks"
    if days <= 60: return "1-2 Months"
    return "2+ Months"


def render():
    st.markdown("## Duration Performance Matrix")
    st.caption("Correlation between holding period and profitability — sharpens stop/exit timing across strategies.")

    trades = get_journal_trades()
    closed = [t for t in trades if t.get("status") == "CLOSED"]

    c1, c2 = st.columns([1,3])
    with c1:
        strat_opts = ["All Strategies"] + sorted({t.get("strategy","") for t in closed if t.get("strategy")})
        strat_sel = st.selectbox("Strategy", strat_opts, key="dur_strat")
    if strat_sel != "All Strategies":
        closed = [t for t in closed if t.get("strategy") == strat_sel]

    data = []
    for t in closed:
        d = holding_days(t)
        b = bucket_for(d)
        if b is None: continue
        data.append({"bucket": b, "pnl": safe_float(t.get("pnl")), "days": d})

    if not data:
        st.info("No closed trades with valid entry/exit dates found.")
        return

    df = pd.DataFrame(data)
    df["bucket"] = pd.Categorical(df["bucket"], categories=BUCKETS, ordered=True)
    grp = df.groupby("bucket", observed=True).agg(
        trades=("pnl","count"),
        avg_pnl=("pnl","mean"),
        total_pnl=("pnl","sum"),
        win_rate=("pnl", lambda s: (s>0).mean()*100),
    ).reindex(BUCKETS).fillna(0)

    # ── KPI strip ────────────────────────────────────────────────────────
    best_bucket = grp["avg_pnl"].idxmax() if grp["trades"].sum() > 0 else "—"
    worst_bucket = grp["avg_pnl"].idxmin() if grp["trades"].sum() > 0 else "—"
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("TOTAL CLOSED TRADES", f"{int(grp['trades'].sum())}"), unsafe_allow_html=True)
    k2.markdown(kpi_card("BEST AVG P/L BUCKET", best_bucket, color=TEAL), unsafe_allow_html=True)
    k3.markdown(kpi_card("WORST AVG P/L BUCKET", worst_bucket, color=RED), unsafe_allow_html=True)
    k4.markdown(kpi_card("MEDIAN HOLDING DAYS", f"{df['days'].median():.0f}d"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Volume by duration / Returns by duration ───────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(section_label("Volume by Duration"), unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=BUCKETS, y=grp["trades"], marker=dict(color=BLUE, opacity=0.85),
                              hovertemplate="%{x}<br>%{y} trades<extra></extra>"))
        l = chart_layout(height=260)
        l["yaxis"]["title"] = dict(text="Trades", font=dict(size=10, color=TEXT_SUBTLE))
        fig.update_layout(**l)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown(section_label("Returns by Duration"), unsafe_allow_html=True)
        fig = go.Figure()
        colors = [TEAL if v>=0 else RED for v in grp["avg_pnl"]]
        fig.add_trace(go.Bar(x=BUCKETS, y=grp["avg_pnl"], marker=dict(color=colors, opacity=0.9),
                              hovertemplate="%{x}<br>₹%{y:,.0f} avg<extra></extra>"))
        l = chart_layout(height=260)
        l["yaxis"]["title"] = dict(text="Avg P/L (₹)", font=dict(size=10, color=TEXT_SUBTLE))
        l["yaxis"]["tickprefix"] = "₹"
        fig.update_layout(**l)
        st.plotly_chart(fig, use_container_width=True)

    # ── Combined correlation matrix (dual axis) ─────────────────────────
    st.markdown(section_label("Duration Performance Matrix — Correlation Between Frequency & Profitability"), unsafe_allow_html=True)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=BUCKETS, y=grp["trades"], name="# Trades",
                          marker=dict(color=BLUE, opacity=0.55),
                          hovertemplate="%{x}<br>%{y} trades<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(x=BUCKETS, y=grp["avg_pnl"], name="Avg P/L", mode="lines+markers",
                              line=dict(color=TEAL, width=2.5, shape="spline"),
                              marker=dict(size=7, color=TEAL, line=dict(color="white", width=1.5)),
                              hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"), secondary_y=True)
    l = chart_layout(height=320, title="")
    l["legend"] = dict(orientation="h", y=-0.18, x=0, font=dict(size=10, color=TEXT_MUTED))
    l["showlegend"] = True
    fig.update_layout(**l)
    fig.update_yaxes(title_text="# Trades", secondary_y=False, gridcolor=CHART_GRID,
                      tickfont=dict(size=10, color=TEXT_SUBTLE))
    fig.update_yaxes(title_text="Avg P/L (₹)", secondary_y=True, showgrid=False,
                      tickfont=dict(size=10, color=TEAL), tickprefix="₹")
    st.plotly_chart(fig, use_container_width=True)

    # ── Detail table ─────────────────────────────────────────────────────
    st.markdown(section_label("Bucket Detail"), unsafe_allow_html=True)
    out = grp.reset_index().rename(columns={"bucket": "Duration"})
    out["Trades"] = out["trades"].astype(int)
    out["Win Rate"] = out["win_rate"].map(lambda v: f"{v:.1f}%")
    out["Avg P/L"] = out["avg_pnl"].map(fmt_pnl)
    out["Total P/L"] = out["total_pnl"].map(fmt_pnl)
    st.dataframe(out[["Duration","Trades","Win Rate","Avg P/L","Total P/L"]],
                 use_container_width=True, hide_index=True)

    # ── Strategy-specific note (VCP/REVERSAL stop optimization) ─────────
    if strat_sel in ("VCP", "REVERSAL", "All Strategies"):
        st.markdown(section_label("Notes"), unsafe_allow_html=True)
        st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 18px;font-size:13px;color:{TEXT_BODY};line-height:1.6">
            Use this to sanity-check your strategy-specific stop levels: VCP at 2.5–3% and REVERSAL at technical stop with a 2.5% floor
            should show their best Avg P/L in the 4-7 Day to 2-4 Week buckets if exits are working as designed. If the Intraday or 1-3 Day
            buckets are dragging the average down, that's premature stop-outs rather than the setup failing.
        </div>""", unsafe_allow_html=True)
