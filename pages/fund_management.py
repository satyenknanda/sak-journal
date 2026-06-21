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

    # ── MTF Margin Lookup (collapsible) ──────────────────────────────────
    from data.db import get_mtf_margins, save_mtf_margin, delete_mtf_margin

    with st.expander("⚡ MTF Margin Lookup — paste Zerodha margin % per ticker"):
        st.caption("Paste margin % from Zerodha's MTF page (zerodha.com/mtf-approved-securities) once per ticker. "
                   "Edit Trade will auto-fill from here instead of asking you to look it up every time. "
                   "Still editable per trade if Zerodha revises a stock's margin requirement.")

        margins = get_mtf_margins()

        if margins:
            mdf = pd.DataFrame([{
                "Symbol": m["ticker"],
                "Margin %": float(m.get("margin_pct") or 0),
                "Leverage": f"{float(m.get('leverage') or 0):.2f}x" if m.get("leverage") else "—",
                "Updated": str(m.get("updated_at",""))[:10],
            } for m in margins])
            st.dataframe(mdf, use_container_width=True, hide_index=True)
        else:
            st.caption("No tickers added yet.")

        st.markdown("<br>", unsafe_allow_html=True)
        ac1, ac2, ac3 = st.columns([2, 2, 1])
        with ac1:
            new_ticker = st.text_input("Ticker", key="mtf_lookup_ticker", placeholder="e.g. TATATECH").upper()
        with ac2:
            new_margin = st.number_input("Margin %", key="mtf_lookup_margin", min_value=1.0, max_value=100.0,
                                          step=0.01, value=50.0, format="%.2f")
        with ac3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("Save", key="mtf_lookup_save", use_container_width=True):
                if new_ticker:
                    save_mtf_margin(new_ticker, new_margin)
                    st.success(f"✅ Saved {new_ticker} at {new_margin:.2f}%")
                    st.rerun()
                else:
                    st.error("Enter a ticker first.")

        if margins:
            del_ticker = st.selectbox("Remove a ticker", ["—"] + [m["ticker"] for m in margins], key="mtf_lookup_del")
            if del_ticker != "—" and st.button(f"🗑️ Remove {del_ticker}", key="mtf_lookup_del_btn"):
                delete_mtf_margin(del_ticker)
                st.success(f"Removed {del_ticker}")
                st.rerun()

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

    # ════════════════════════════════════════════════════════════════════
    # MTF ANALYTICS — Interest Cost, MTF vs Cash P&L, Leverage Trend
    # ════════════════════════════════════════════════════════════════════
    import plotly.graph_objects as go

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown(section_label("MTF Analytics"), unsafe_allow_html=True)

    mtf_tab1, mtf_tab2, mtf_tab3 = st.tabs(["💸 Interest Cost", "⚖️ MTF vs Cash P&L", "📈 Leverage Trend"])

    # ── 1. MTF Interest Cost Over Time ───────────────────────────────────
    with mtf_tab1:
        st.caption(f"Monthly MTF interest paid in {year_sel}, from the flows table above.")
        interest_months = [r["month"] for r in rows]
        interest_vals = [r["mtf_interest"] for r in rows]

        if total_mtf_interest == 0:
            st.info("No MTF interest recorded yet. Enter monthly figures in the table above (from your Zerodha contract notes) to see this chart populate.")
        else:
            fig_int = go.Figure()
            fig_int.add_trace(go.Bar(
                x=interest_months, y=interest_vals,
                marker=dict(color=AMBER, opacity=0.85, line=dict(width=0)),
                hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>",
            ))
            l_int = chart_layout(height=260, title="")
            l_int["yaxis"]["tickprefix"] = "₹"
            fig_int.update_layout(**l_int)
            st.plotly_chart(fig_int, use_container_width=True, config={"displayModeBar": False})

            ic1, ic2, ic3 = st.columns(3)
            avg_monthly_interest = total_mtf_interest / max(1, sum(1 for v in interest_vals if v > 0))
            ic1.markdown(kpi_card("TOTAL MTF INTEREST", fmt_inr(total_mtf_interest), color=AMBER), unsafe_allow_html=True)
            ic2.markdown(kpi_card("AVG MONTHLY (active months)", fmt_inr(avg_monthly_interest)), unsafe_allow_html=True)
            interest_pct_of_gross = (total_mtf_interest / total_pnl * 100) if total_pnl else 0
            ic3.markdown(kpi_card("% OF GROSS P&L", f"{interest_pct_of_gross:.1f}%",
                                   color=(RED if interest_pct_of_gross > 15 else AMBER if interest_pct_of_gross > 5 else TEAL),
                                   sub="interest cost as a share of gross profit"), unsafe_allow_html=True)

    # ── 2. MTF vs Cash P&L Comparison ────────────────────────────────────
    with mtf_tab2:
        st.caption(f"Is leverage actually paying for itself? Gross P&L by funding type, {year_sel}, net of MTF interest where applicable.")

        cash_total = sum(monthly_pnl_cash.values())
        mtf_total_gross = sum(monthly_pnl_mtf.values())
        mtf_total_net = mtf_total_gross - total_mtf_interest

        cash_trades_n = sum(1 for t in closed if str(t.get("funding_type", "CASH") or "CASH").upper() != "MTF"
                             and str(t.get("exit_date", ""))[:4].isdigit() and int(str(t.get("exit_date", ""))[:4]) == year_sel)
        mtf_trades_n = sum(1 for t in closed if str(t.get("funding_type", "CASH") or "CASH").upper() == "MTF"
                            and str(t.get("exit_date", ""))[:4].isdigit() and int(str(t.get("exit_date", ""))[:4]) == year_sel)

        if cash_trades_n == 0 and mtf_trades_n == 0:
            st.info("No closed trades this year to compare.")
        else:
            mc1, mc2, mc3 = st.columns(3)
            mc1.markdown(kpi_card("CASH P&L", fmt_pnl(cash_total), color=pnl_color(cash_total),
                                   sub=f"{cash_trades_n} trade(s)"), unsafe_allow_html=True)
            mc2.markdown(kpi_card("MTF P&L (GROSS)", fmt_pnl(mtf_total_gross), color=pnl_color(mtf_total_gross),
                                   sub=f"{mtf_trades_n} trade(s)"), unsafe_allow_html=True)
            mc3.markdown(kpi_card("MTF P&L (NET OF INTEREST)", fmt_pnl(mtf_total_net), color=pnl_color(mtf_total_net),
                                   sub=f"after -{fmt_inr(total_mtf_interest)} interest"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            fig_cmp = go.Figure()
            cmp_months = [r["month"] for r in rows]
            fig_cmp.add_trace(go.Bar(
                x=cmp_months, y=[monthly_pnl_cash[i+1] for i in range(12)],
                name="Cash", marker=dict(color=BLUE, opacity=0.85),
                hovertemplate="%{x}<br>Cash: ₹%{y:,.0f}<extra></extra>",
            ))
            fig_cmp.add_trace(go.Bar(
                x=cmp_months, y=[monthly_pnl_mtf[i+1] for i in range(12)],
                name="MTF (gross)", marker=dict(color=AMBER, opacity=0.85),
                hovertemplate="%{x}<br>MTF: ₹%{y:,.0f}<extra></extra>",
            ))
            l_cmp = chart_layout(height=280, title="Monthly P&L — Cash vs MTF (gross)")
            l_cmp["yaxis"]["tickprefix"] = "₹"
            l_cmp["barmode"] = "group"
            l_cmp["legend"] = dict(orientation="h", y=-0.18, x=0, font=dict(size=10, color=TEXT_MUTED))
            l_cmp["showlegend"] = True
            fig_cmp.update_layout(**l_cmp)
            st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})

            if mtf_total_gross > 0:
                st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
                    padding:14px 18px;font-size:13px;color:{TEXT_BODY};line-height:1.6;margin-top:8px">
                    MTF interest consumed <b style="color:{TEXT_H}">{(total_mtf_interest/mtf_total_gross*100 if mtf_total_gross else 0):.1f}%</b>
                    of your gross MTF profit this year. {"Leverage is paying for itself." if mtf_total_net > 0 else "Net MTF result is negative after interest — worth reviewing whether the leverage is adding edge or just risk."}
                </div>""", unsafe_allow_html=True)

    # ── 3. Leverage Trend (approximate, reconstructed from trade entries) ──
    with mtf_tab3:
        st.caption(f"Approximate monthly leverage — % of newly-opened position value that was MTF-borrowed, by entry month, {year_sel}.")
        st.markdown(f"""<div style="background:{AMBER_BG};border:1px solid {AMBER_BORDER};border-radius:8px;
            padding:8px 12px;font-size:11px;color:{TEXT_BODY};margin-bottom:12px">
            ⚠️ This is reconstructed from trade entry dates, not a stored daily snapshot — it shows leverage at the
            point positions were <i>opened</i> each month, not your actual exposure on every day. Treat as directional, not exact.
        </div>""", unsafe_allow_html=True)

        all_trades_year = [t for t in trades if str(t.get("entry_date", ""))[:4].isdigit()
                            and int(str(t.get("entry_date", ""))[:4]) == year_sel]

        lev_by_month = {m: {"own": 0.0, "borrowed": 0.0} for m in range(1, 13)}
        for t in all_trades_year:
            try:
                month = datetime.strptime(str(t.get("entry_date", ""))[:10], "%Y-%m-%d").month
            except Exception:
                continue
            qty = safe_float(t.get("qty"))
            price = safe_float(t.get("entry_price"))
            value = qty * price
            funding = str(t.get("funding_type", "CASH") or "CASH").upper()
            if funding == "MTF":
                margin_pct = safe_float(t.get("mtf_margin_pct")) or 50.0
                lev_by_month[month]["own"] += value * margin_pct / 100
                lev_by_month[month]["borrowed"] += value * (1 - margin_pct / 100)
            else:
                lev_by_month[month]["own"] += value

        lev_pct_by_month = []
        for m in range(1, 13):
            own = lev_by_month[m]["own"]
            borrowed = lev_by_month[m]["borrowed"]
            total = own + borrowed
            lev_pct_by_month.append((borrowed / total * 100) if total > 0 else None)

        if all(v is None for v in lev_pct_by_month):
            st.info("No trade entries this year to reconstruct a leverage trend from.")
        else:
            lev_months_plot = [MONTHS[i] for i in range(12) if lev_pct_by_month[i] is not None]
            lev_vals_plot = [v for v in lev_pct_by_month if v is not None]

            fig_lev = go.Figure()
            fig_lev.add_trace(go.Scatter(
                x=lev_months_plot, y=lev_vals_plot, mode="lines+markers",
                line=dict(color=AMBER, width=2.5, shape="spline"),
                marker=dict(size=7, color=[RED if v > 30 else AMBER if v > 15 else TEAL for v in lev_vals_plot],
                            line=dict(color="white", width=1.5)),
                fill="tozeroy", fillcolor="rgba(245,158,11,0.15)",
                hovertemplate="%{x}<br>%{y:.1f}% leverage<extra></extra>",
            ))
            fig_lev.add_hline(y=30, line=dict(color=RED, width=1, dash="dot"),
                               annotation_text="30% — high leverage", annotation_font=dict(color=RED, size=9))
            fig_lev.add_hline(y=15, line=dict(color=AMBER, width=1, dash="dot"),
                               annotation_text="15% — moderate", annotation_font=dict(color=AMBER, size=9))
            l_lev = chart_layout(height=280, title="")
            l_lev["yaxis"]["ticksuffix"] = "%"
            l_lev["yaxis"]["range"] = [0, max(50, max(lev_vals_plot) * 1.2 if lev_vals_plot else 50)]
            fig_lev.update_layout(**l_lev)
            st.plotly_chart(fig_lev, use_container_width=True, config={"displayModeBar": False})

            avg_lev = sum(lev_vals_plot) / len(lev_vals_plot) if lev_vals_plot else 0
            peak_lev = max(lev_vals_plot) if lev_vals_plot else 0
            lc1, lc2 = st.columns(2)
            lc1.markdown(kpi_card("AVG MONTHLY LEVERAGE", f"{avg_lev:.1f}%",
                                   color=(RED if avg_lev > 30 else AMBER if avg_lev > 15 else TEAL)), unsafe_allow_html=True)
            lc2.markdown(kpi_card("PEAK MONTHLY LEVERAGE", f"{peak_lev:.1f}%",
                                   color=(RED if peak_lev > 30 else AMBER if peak_lev > 15 else TEAL)), unsafe_allow_html=True)

    st.caption("Post-tax total is illustrative — wire to your Tax Analytics page output if you want an exact post-STCG/LTCG figure. "
               "MTF interest is entered manually per month from your Zerodha contract notes / fund statement, since it isn't captured per-trade.")
