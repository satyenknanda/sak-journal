import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from collections import defaultdict
from data.db import get_journal_trades
from theme import *

STCG_RATE = 0.20      # 20% — Section 111A, FY 2026-27
LTCG_RATE = 0.125     # 12.5% — Section 112A, FY 2026-27
LTCG_EXEMPTION = 125_000  # ₹1.25L per FY, no carry-forward

def safe_float(v):
    try: return float(v or 0)
    except: return 0.0

def fmt_pnl(v):
    return f"{'+' if v>=0 else ''}₹{abs(v):,.0f}" if v>=0 else f"-₹{abs(v):,.0f}"

def fmt_inr(v):
    return f"₹{v:,.0f}"

def holding_days(t):
    try:
        ed = datetime.strptime(str(t.get("entry_date",""))[:10], "%Y-%m-%d")
        xd = datetime.strptime(str(t.get("exit_date",""))[:10], "%Y-%m-%d")
        return (xd - ed).days
    except Exception:
        return None

def fy_for_date(d_str):
    """Indian FY: Apr 1 – Mar 31. Returns e.g. 'FY 2026-27'."""
    try:
        d = datetime.strptime(str(d_str)[:10], "%Y-%m-%d")
    except Exception:
        return None
    if d.month >= 4:
        return f"FY {d.year}-{str(d.year+1)[2:]}"
    return f"FY {d.year-1}-{str(d.year)[2:]}"


def render():
    st.markdown("## Tax Analytics")
    st.caption("STCG/LTCG split for NSE equity — FY 2026-27 rates. Estimate only, not a substitute for a CA.")

    st.markdown(f"""<div style="background:{AMBER_BG};border:1px solid {AMBER_BORDER};border-radius:8px;
        padding:10px 14px;font-size:12px;color:{TEXT_BODY};margin-bottom:14px">
        ⚠️ Holding period ≤ 365 days = STCG, taxed at <b>20%</b> flat (Sec 111A). &nbsp;|&nbsp;
        Holding period &gt; 365 days = LTCG, taxed at <b>12.5%</b> on gains above the <b>₹1.25L</b> annual exemption (Sec 112A).
        This is an estimate computed from your journal data — verify against your actual contract notes / Form 26AS before filing.
    </div>""", unsafe_allow_html=True)

    trades = get_journal_trades()
    closed = [t for t in trades if t.get("status") == "CLOSED"]

    rows = []
    for t in closed:
        d = holding_days(t)
        if d is None: continue
        pnl = safe_float(t.get("pnl"))
        fy = fy_for_date(t.get("exit_date"))
        if fy is None: continue
        rows.append({
            "ticker": t.get("ticker",""),
            "strategy": t.get("strategy",""),
            "entry_date": str(t.get("entry_date",""))[:10],
            "exit_date": str(t.get("exit_date",""))[:10],
            "holding_days": d,
            "pnl": pnl,
            "term": "LTCG" if d > 365 else "STCG",
            "fy": fy,
        })

    if not rows:
        st.info("No closed trades with valid entry/exit dates found.")
        return

    df = pd.DataFrame(rows)

    fy_opts = ["All Years"] + sorted(df["fy"].unique(), reverse=True)
    c1, _ = st.columns([1,3])
    with c1:
        fy_sel = st.selectbox("Financial Year", fy_opts, key="tax_fy")
    if fy_sel != "All Years":
        df = df[df["fy"] == fy_sel]

    if df.empty:
        st.info("No trades in this period.")
        return

    stcg_df = df[df["term"] == "STCG"]
    ltcg_df = df[df["term"] == "LTCG"]

    stcg_gain = stcg_df["pnl"].sum()
    ltcg_gain = ltcg_df["pnl"].sum()

    # STCG: every rupee of net gain taxed at 20% (losses net against gains within STCG bucket)
    stcg_taxable = max(stcg_gain, 0)
    stcg_tax = stcg_taxable * STCG_RATE

    # LTCG: exemption of 1.25L applies to net LTCG gain, only if positive
    ltcg_taxable = max(ltcg_gain - LTCG_EXEMPTION, 0)
    ltcg_tax = ltcg_taxable * LTCG_RATE

    total_tax = stcg_tax + ltcg_tax

    # ── KPI strip ────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("STCG NET GAIN", fmt_pnl(stcg_gain), color=pnl_color(stcg_gain),
                          sub=f"{len(stcg_df)} trades · ≤365 days"), unsafe_allow_html=True)
    k2.markdown(kpi_card("LTCG NET GAIN", fmt_pnl(ltcg_gain), color=pnl_color(ltcg_gain),
                          sub=f"{len(ltcg_df)} trades · >365 days"), unsafe_allow_html=True)
    k3.markdown(kpi_card("EST. STCG TAX (20%)", fmt_inr(stcg_tax)), unsafe_allow_html=True)
    k4.markdown(kpi_card("EST. LTCG TAX (12.5%)", fmt_inr(ltcg_tax),
                          sub=f"after ₹1.25L exemption"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
        padding:18px 20px;box-shadow:{SHADOW_SM}">
        <div style="font-size:11px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;font-weight:500;margin-bottom:8px">
            Estimated Total Tax Liability — {fy_sel}
        </div>
        <div style="font-size:1.8rem;font-weight:700;color:{TEXT_H}">{fmt_inr(total_tax)}</div>
        <div style="font-size:12px;color:{TEXT_SUBTLE};margin-top:4px">
            STCG {fmt_inr(stcg_tax)} + LTCG {fmt_inr(ltcg_tax)} &nbsp;·&nbsp; excludes surcharge &amp; 4% cess, brokerage/STT already
            netted in P&amp;L
        </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── FY-wise breakdown chart (if All Years) ───────────────────────────
    if fy_sel == "All Years":
        st.markdown(section_label("FY-wise STCG vs LTCG"), unsafe_allow_html=True)
        by_fy = defaultdict(lambda: {"stcg":0.0, "ltcg":0.0})
        for _, r in df.iterrows():
            by_fy[r["fy"]][r["term"].lower()] += r["pnl"]
        fys = sorted(by_fy.keys())
        fig = go.Figure()
        fig.add_trace(go.Bar(x=fys, y=[by_fy[f]["stcg"] for f in fys], name="STCG",
                              marker=dict(color=BLUE, opacity=0.85)))
        fig.add_trace(go.Bar(x=fys, y=[by_fy[f]["ltcg"] for f in fys], name="LTCG",
                              marker=dict(color=TEAL, opacity=0.85)))
        l = chart_layout(height=280)
        l["barmode"] = "group"
        l["legend"] = dict(orientation="h", y=-0.18, x=0, font=dict(size=10, color=TEXT_MUTED))
        l["showlegend"] = True
        l["yaxis"]["tickprefix"] = "₹"
        fig.update_layout(**l)
        st.plotly_chart(fig, use_container_width=True)

    # ── Detail tables ─────────────────────────────────────────────────────
    tab1, tab2 = st.tabs(["STCG Trades", "LTCG Trades"])
    with tab1:
        if stcg_df.empty:
            st.caption("No STCG trades in this period.")
        else:
            out = stcg_df.copy()
            out["P&L"] = out["pnl"].map(fmt_pnl)
            out = out.rename(columns={"ticker":"Symbol","strategy":"Strategy",
                                       "entry_date":"Entry","exit_date":"Exit","holding_days":"Days Held"})
            st.dataframe(out[["Symbol","Strategy","Entry","Exit","Days Held","P&L"]],
                         use_container_width=True, hide_index=True)
    with tab2:
        if ltcg_df.empty:
            st.caption("No LTCG trades in this period.")
        else:
            out = ltcg_df.copy()
            out["P&L"] = out["pnl"].map(fmt_pnl)
            out = out.rename(columns={"ticker":"Symbol","strategy":"Strategy",
                                       "entry_date":"Entry","exit_date":"Exit","holding_days":"Days Held"})
            st.dataframe(out[["Symbol","Strategy","Entry","Exit","Days Held","P&L"]],
                         use_container_width=True, hide_index=True)

    st.caption("Rates per Finance (No. 2) Act 2024, unchanged for FY 2026-27 (Budget 2026). "
               "This estimate doesn't account for other income, surcharge slabs, STT already paid, or carry-forward of prior-year losses. Consult a CA before filing.")


def pnl_color(v):
    return TEAL if v >= 0 else RED
