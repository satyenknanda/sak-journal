import streamlit as st
import pandas as pd
from datetime import datetime
from data.db import get_journal_trades
from theme import *

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def safe_float(v):
    try: return float(v or 0)
    except: return 0.0

def fmt_pnl(v):
    return f"{'+' if v>=0 else ''}₹{abs(v):,.0f}" if v>=0 else f"-₹{abs(v):,.0f}"

def fmt_inr(v):
    return f"₹{v:,.2f}"


def render():
    st.markdown("## Fund Management")
    st.caption("Track month-over-month capital flows and growth attribution. Enter Added/Withdrawn amounts as they occur — nothing is pre-filled.")

    from data.db import get_capital_flows, save_capital_flow

    trades = get_journal_trades()
    closed = [t for t in trades if t.get("status") == "CLOSED"]

    years = sorted({int(str(t.get("exit_date",""))[:4]) for t in closed if str(t.get("exit_date",""))[:4].isdigit()}, reverse=True)
    if not years:
        years = [datetime.now().year]
    year_sel = st.selectbox("Year", years, key="fund_year")

    flows = get_capital_flows(year_sel)  # {month_num: {"added": x, "withdrawn": y}}

    # ── monthly net P&L from journal ─────────────────────────────────────
    monthly_pnl = {m: 0.0 for m in range(1, 13)}
    for t in closed:
        d = str(t.get("exit_date",""))[:10]
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            continue
        if dt.year == year_sel:
            monthly_pnl[dt.month] += safe_float(t.get("pnl"))

    # ── compute starting capital roll-forward ───────────────────────────
    starting_capital = st.number_input(
        "Starting capital for Jan (or first traded month) of this year (₹)",
        min_value=0.0, value=safe_float(flows.get(0, {}).get("base_capital", 0.0)),
        step=10000.0, key=f"base_cap_{year_sel}",
        help="One-time anchor — only needed once per year you start tracking. Leave 0 if unknown."
    )

    rows = []
    running_capital = starting_capital
    total_added = total_withdrawn = total_pnl = 0.0

    for m in range(1, 13):
        f = flows.get(m, {"added": 0.0, "withdrawn": 0.0})
        added = f.get("added", 0.0)
        withdrawn = f.get("withdrawn", 0.0)
        pnl = monthly_pnl.get(m, 0.0)
        start_cap = running_capital
        running_capital = running_capital + added - withdrawn + pnl
        total_added += added
        total_withdrawn += withdrawn
        total_pnl += pnl
        rows.append({
            "month": MONTHS[m-1], "month_num": m,
            "added": added, "withdrawn": withdrawn,
            "starting_capital": start_cap, "net_pnl": pnl,
            "ending_capital": running_capital,
        })

    # ── KPI strip ────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("TOTAL ADDED", fmt_inr(total_added)), unsafe_allow_html=True)
    k2.markdown(kpi_card("TOTAL WITHDRAWN", fmt_inr(total_withdrawn)), unsafe_allow_html=True)
    k3.markdown(kpi_card("NET P&L (YEAR)", fmt_pnl(total_pnl), color=(TEAL if total_pnl>=0 else RED)), unsafe_allow_html=True)
    k4.markdown(kpi_card("CURRENT CAPITAL", fmt_inr(running_capital)), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── editable monthly table ──────────────────────────────────────────
    st.markdown(section_label(f"Monthly Flows — {year_sel}"))
    st.caption("Edit Added / Withdrawn inline below, then click Save. Starting Capital and Net P/L are computed automatically.")

    edit_df = pd.DataFrame([{
        "Month": r["month"],
        "Added (₹)": r["added"],
        "Withdrawn (₹)": r["withdrawn"],
        "Starting Capital (₹)": r["starting_capital"],
        "Net P/L (₹)": r["net_pnl"],
        "Ending Capital (₹)": r["ending_capital"],
    } for r in rows])

    edited = st.data_editor(
        edit_df,
        use_container_width=True, hide_index=True, key=f"fund_editor_{year_sel}",
        disabled=["Month", "Starting Capital (₹)", "Net P/L (₹)", "Ending Capital (₹)"],
        column_config={
            "Added (₹)": st.column_config.NumberColumn(format="₹%.0f", min_value=0.0),
            "Withdrawn (₹)": st.column_config.NumberColumn(format="₹%.0f", min_value=0.0),
            "Starting Capital (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Net P/L (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Ending Capital (₹)": st.column_config.NumberColumn(format="₹%.0f"),
        },
    )

    if st.button("💾 Save Changes", key=f"save_flows_{year_sel}"):
        for i, m in enumerate(range(1, 13)):
            added = safe_float(edited.iloc[i]["Added (₹)"])
            withdrawn = safe_float(edited.iloc[i]["Withdrawn (₹)"])
            save_capital_flow(year_sel, m, added, withdrawn)
        save_capital_flow(year_sel, 0, 0, 0, base_capital=starting_capital)  # month=0 stores the anchor
        st.success("Saved. Reload the page to see updated roll-forward.")
        st.rerun()

    # ── TOTAL (post-tax placeholder) row ─────────────────────────────────
    st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
        padding:14px 18px;margin-top:10px;display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:12px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;font-weight:600">
            TOTAL <span style="color:{TEAL}">POST-TAX</span>
        </span>
        <span style="font-size:13px;color:{TEXT_BODY}">
            Added {fmt_inr(total_added)} &nbsp;·&nbsp; Withdrawn {fmt_inr(total_withdrawn)} &nbsp;·&nbsp;
            Net P/L {fmt_pnl(total_pnl)} &nbsp;·&nbsp; <b style="color:{TEXT_H}">Ending {fmt_inr(running_capital)}</b>
        </span>
    </div>""", unsafe_allow_html=True)

    st.caption("Post-tax total is illustrative — wire to your Tax Analytics page output if you want an exact post-STCG/LTCG figure.")
