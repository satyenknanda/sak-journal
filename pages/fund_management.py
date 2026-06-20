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
    st.caption("Track month-over-month capital flows, growth attribution, and own-funds vs MTF (leverage) exposure.")

    from data.db import get_capital_flows, save_capital_flow

    trades = get_journal_trades()
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    open_trades = [t for t in trades if t.get("status") == "OPEN"]

    years = sorted({int(str(t.get("exit_date",""))[:4]) for t in closed if str(t.get("exit_date",""))[:4].isdigit()}, reverse=True)
    if not years:
        years = [datetime.now().year]
    year_sel = st.selectbox("Year", years, key="fund_year")

    flows = get_capital_flows(year_sel)  # {month_num: {"added": x, "withdrawn": y, "mtf_interest": z}}

    # ── Own Capital vs MTF Exposure (current open positions) ────────────
    st.markdown(section_label("Current Exposure — Own Capital vs MTF"), unsafe_allow_html=True)

    cash_value = 0.0
    mtf_own_value = 0.0
    mtf_borrowed_value = 0.0
    cash_count = mtf_count = 0
    for t in open_trades:
        qty = safe_float(t.get("qty"))
        price = safe_float(t.get("entry_price")) or safe_float(t.get("live_price"))
        value = qty * price
        funding = str(t.get("funding_type", "CASH") or "CASH").upper()
        if funding == "MTF":
            margin_pct = safe_float(t.get("mtf_margin_pct")) or 50.0
            mtf_own_value += value * margin_pct / 100
            mtf_borrowed_value += value * (1 - margin_pct / 100)
            mtf_count += 1
        else:
            cash_value += value
            cash_count += 1

    mtf_value = mtf_own_value + mtf_borrowed_value  # total MTF position value
    own_capital_total = cash_value + mtf_own_value   # your actual money across both
    total_exposure = cash_value + mtf_value
    leverage_pct = (mtf_borrowed_value / total_exposure * 100) if total_exposure > 0 else 0

    e1, e2, e3, e4 = st.columns(4)
    e1.markdown(kpi_card("YOUR CAPITAL DEPLOYED", fmt_inr(own_capital_total),
                          sub=f"Cash {fmt_inr(cash_value)} + MTF margin {fmt_inr(mtf_own_value)}"), unsafe_allow_html=True)
    e2.markdown(kpi_card("ZERODHA-BORROWED (MTF)", fmt_inr(mtf_borrowed_value), color=AMBER,
                          sub=f"{mtf_count} MTF position(s)"), unsafe_allow_html=True)
    e3.markdown(kpi_card("TOTAL EXPOSURE", fmt_inr(total_exposure), sub=f"{cash_count+mtf_count} open positions"), unsafe_allow_html=True)
    e4.markdown(kpi_card("LEVERAGE %", f"{leverage_pct:.1f}%",
                          color=(RED if leverage_pct > 30 else AMBER if leverage_pct > 15 else TEAL),
                          sub="borrowed ÷ total exposure"), unsafe_allow_html=True)

    if leverage_pct > 0:
        st.markdown(f"""<div style="background:{AMBER_BG};border:1px solid {AMBER_BORDER};border-radius:8px;
            padding:10px 14px;font-size:12px;color:{TEXT_BODY};margin:10px 0">
            ⚡ {leverage_pct:.1f}% of your total exposure is Zerodha-funded (borrowed) via MTF — based on the margin %
            you entered per trade. This amplifies both gains and losses, and accrues daily interest — tracked below as
            a monthly expense against P&L. Margin % per trade isn't pulled live from Zerodha; verify against Kite's
            order screen at entry time, since rates vary by stock and can change.
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── monthly net P&L from journal, split by funding type ──────────────
    monthly_pnl = {m: 0.0 for m in range(1, 13)}
    monthly_pnl_cash = {m: 0.0 for m in range(1, 13)}
    monthly_pnl_mtf = {m: 0.0 for m in range(1, 13)}
    for t in closed:
        d = str(t.get("exit_date",""))[:10]
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            continue
        if dt.year == year_sel:
            p = safe_float(t.get("pnl"))
            monthly_pnl[dt.month] += p
            if str(t.get("funding_type","CASH") or "CASH").upper() == "MTF":
                monthly_pnl_mtf[dt.month] += p
            else:
                monthly_pnl_cash[dt.month] += p

    # ── compute starting capital roll-forward ───────────────────────────
    starting_capital = st.number_input(
        "Starting capital for Jan (or first traded month) of this year (₹)",
        min_value=0.0, value=safe_float(flows.get(0, {}).get("base_capital", 0.0)),
        step=10000.0, key=f"base_cap_{year_sel}",
        help="One-time anchor — only needed once per year you start tracking. Leave 0 if unknown."
    )

    rows = []
    running_capital = starting_capital
    total_added = total_withdrawn = total_pnl = total_mtf_interest = 0.0

    for m in range(1, 13):
        f = flows.get(m, {"added": 0.0, "withdrawn": 0.0, "mtf_interest": 0.0})
        added = f.get("added", 0.0)
        withdrawn = f.get("withdrawn", 0.0)
        mtf_interest = f.get("mtf_interest", 0.0)
        pnl = monthly_pnl.get(m, 0.0)
        net_pnl = pnl - mtf_interest
        start_cap = running_capital
        running_capital = running_capital + added - withdrawn + net_pnl
        total_added += added
        total_withdrawn += withdrawn
        total_pnl += pnl
        total_mtf_interest += mtf_interest
        rows.append({
            "month": MONTHS[m-1], "month_num": m,
            "added": added, "withdrawn": withdrawn,
            "starting_capital": start_cap, "gross_pnl": pnl,
            "mtf_interest": mtf_interest, "net_pnl": net_pnl,
            "ending_capital": running_capital,
        })

    # ── KPI strip ────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("TOTAL ADDED", fmt_inr(total_added)), unsafe_allow_html=True)
    k2.markdown(kpi_card("TOTAL WITHDRAWN", fmt_inr(total_withdrawn)), unsafe_allow_html=True)
    k3.markdown(kpi_card("MTF INTEREST PAID", fmt_inr(total_mtf_interest), color=AMBER), unsafe_allow_html=True)
    k4.markdown(kpi_card("CURRENT CAPITAL", fmt_inr(running_capital)), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── editable monthly table ──────────────────────────────────────────
    st.markdown(section_label(f"Monthly Flows — {year_sel}"), unsafe_allow_html=True)
    st.caption("Edit Added / Withdrawn / MTF Interest inline below, then click Save. Starting Capital and Net P/L are computed automatically.")

    edit_df = pd.DataFrame([{
        "Month": r["month"],
        "Added (₹)": r["added"],
        "Withdrawn (₹)": r["withdrawn"],
        "MTF Interest (₹)": r["mtf_interest"],
        "Starting Capital (₹)": r["starting_capital"],
        "Gross P/L (₹)": r["gross_pnl"],
        "Net P/L (₹)": r["net_pnl"],
        "Ending Capital (₹)": r["ending_capital"],
    } for r in rows])

    edited = st.data_editor(
        edit_df,
        use_container_width=True, hide_index=True, key=f"fund_editor_{year_sel}",
        disabled=["Month", "Starting Capital (₹)", "Gross P/L (₹)", "Net P/L (₹)", "Ending Capital (₹)"],
        column_config={
            "Added (₹)": st.column_config.NumberColumn(format="₹%.0f", min_value=0.0),
            "Withdrawn (₹)": st.column_config.NumberColumn(format="₹%.0f", min_value=0.0),
            "MTF Interest (₹)": st.column_config.NumberColumn(format="₹%.0f", min_value=0.0,
                                                                help="Monthly MTF interest charged by Zerodha — reduces Net P/L"),
            "Starting Capital (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Gross P/L (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Net P/L (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Ending Capital (₹)": st.column_config.NumberColumn(format="₹%.0f"),
        },
    )

    if st.button("💾 Save Changes", key=f"save_flows_{year_sel}"):
        for i, m in enumerate(range(1, 13)):
            added = safe_float(edited.iloc[i]["Added (₹)"])
            withdrawn = safe_float(edited.iloc[i]["Withdrawn (₹)"])
            mtf_interest = safe_float(edited.iloc[i]["MTF Interest (₹)"])
            save_capital_flow(year_sel, m, added, withdrawn, mtf_interest=mtf_interest)
        save_capital_flow(year_sel, 0, 0, 0, base_capital=starting_capital)  # month=0 stores the anchor
        st.success("Saved. Reload the page to see updated roll-forward.")
        st.rerun()

    # ── TOTAL (post-tax placeholder) row ─────────────────────────────────
    st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
        padding:14px 18px;margin-top:10px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <span style="font-size:12px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;font-weight:600">
            TOTAL <span style="color:{TEAL}">POST-TAX</span>
        </span>
        <span style="font-size:13px;color:{TEXT_BODY}">
            Added {fmt_inr(total_added)} &nbsp;·&nbsp; Withdrawn {fmt_inr(total_withdrawn)} &nbsp;·&nbsp;
            Gross P/L {fmt_pnl(total_pnl)} &nbsp;·&nbsp; MTF Interest -{fmt_inr(total_mtf_interest)} &nbsp;·&nbsp;
            <b style="color:{TEXT_H}">Ending {fmt_inr(running_capital)}</b>
        </span>
    </div>""", unsafe_allow_html=True)

    st.caption("Post-tax total is illustrative — wire to your Tax Analytics page output if you want an exact post-STCG/LTCG figure. "
               "MTF interest is entered manually per month from your Zerodha contract notes / fund statement, since it isn't captured per-trade.")
