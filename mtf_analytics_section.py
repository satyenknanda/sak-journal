    # ════════════════════════════════════════════════════════════════════
    # MTF ANALYTICS — Interest Cost (auto-calculated), MTF vs Cash P&L, Leverage Trend
    # ════════════════════════════════════════════════════════════════════
    import plotly.graph_objects as go
    from datetime import date as _date, timedelta as _timedelta

    ZERODHA_MTF_DAILY_RATE = 0.0004  # 0.04% per day = ₹40 per lakh, per Zerodha's published MTF rate

    def calc_mtf_interest_for_trade(t, year_filter=None):
        """Auto-calculated MTF interest for one trade, per Zerodha's formula:
        0.04%/day on the BORROWED amount, from T+1 (entry+1 day) until exit
        (or today, for still-open positions). Returns {month: interest_amount}
        for the given year, splitting interest across months if the holding
        period spans multiple months."""
        if str(t.get("funding_type", "CASH") or "CASH").upper() != "MTF":
            return {}
        qty = safe_float(t.get("qty"))
        price = safe_float(t.get("entry_price"))
        margin_pct = safe_float(t.get("mtf_margin_pct")) or 50.0
        position_value = qty * price
        borrowed = position_value * (1 - margin_pct / 100)
        if borrowed <= 0:
            return {}

        try:
            entry_dt = datetime.strptime(str(t.get("entry_date", ""))[:10], "%Y-%m-%d").date()
        except Exception:
            return {}

        if t.get("status") == "CLOSED" and t.get("exit_date"):
            try:
                exit_dt = datetime.strptime(str(t.get("exit_date", ""))[:10], "%Y-%m-%d").date()
            except Exception:
                exit_dt = _date.today()
        else:
            exit_dt = _date.today()  # still open — interest accrued to date

        start = entry_dt + _timedelta(days=1)  # T+1
        if start > exit_dt:
            return {}  # held less than a day, no interest yet

        daily_interest = borrowed * ZERODHA_MTF_DAILY_RATE
        by_month = {}
        cur = start
        while cur <= exit_dt:
            if year_filter is None or cur.year == year_filter:
                by_month[cur.month] = by_month.get(cur.month, 0.0) + daily_interest
            cur += _timedelta(days=1)
        return by_month

    # Aggregate auto-calculated interest across all trades for the selected year
    auto_interest_by_month = {m: 0.0 for m in range(1, 13)}
    for t in trades:
        per_trade = calc_mtf_interest_for_trade(t, year_filter=year_sel)
        for m, amt in per_trade.items():
            auto_interest_by_month[m] += amt
    total_mtf_interest_auto = sum(auto_interest_by_month.values())

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown(section_label("MTF Analytics"), unsafe_allow_html=True)

    mtf_tab1, mtf_tab2, mtf_tab3 = st.tabs(["💸 Interest Cost", "⚖️ MTF vs Cash P&L", "📈 Leverage Trend"])

    # ── 1. MTF Interest Cost Over Time (auto-calculated) ─────────────────
    with mtf_tab1:
        st.caption("Auto-calculated per Zerodha's MTF rate: 0.04%/day (₹40 per lakh) on the borrowed amount, "
                   "from T+1 until exit (or today, for open positions). No manual entry needed.")

        interest_months_auto = MONTHS
        interest_vals_auto = [auto_interest_by_month[m] for m in range(1, 13)]

        if total_mtf_interest_auto == 0:
            st.info("No MTF interest accrued yet — either no MTF trades this year, or all MTF positions were entered today.")
        else:
            fig_int = go.Figure()
            fig_int.add_trace(go.Bar(
                x=interest_months_auto, y=interest_vals_auto,
                marker=dict(color=AMBER, opacity=0.85, line=dict(width=0)),
                hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>",
            ))
            l_int = chart_layout(height=260, title="")
            l_int["yaxis"]["tickprefix"] = "₹"
            fig_int.update_layout(**l_int)
            st.plotly_chart(fig_int, use_container_width=True, config={"displayModeBar": False})

            ic1, ic2, ic3 = st.columns(3)
            active_months_count = sum(1 for v in interest_vals_auto if v > 0)
            avg_monthly_interest = total_mtf_interest_auto / max(1, active_months_count)
            ic1.markdown(kpi_card("TOTAL MTF INTEREST (auto)", fmt_inr(total_mtf_interest_auto), color=AMBER), unsafe_allow_html=True)
            ic2.markdown(kpi_card("AVG MONTHLY (active months)", fmt_inr(avg_monthly_interest)), unsafe_allow_html=True)
            interest_pct_of_gross = (total_mtf_interest_auto / total_pnl * 100) if total_pnl else 0
            ic3.markdown(kpi_card("% OF GROSS P&L", f"{interest_pct_of_gross:.1f}%",
                                   color=(RED if interest_pct_of_gross > 15 else AMBER if interest_pct_of_gross > 5 else TEAL),
                                   sub="interest cost as a share of gross profit"), unsafe_allow_html=True)

        st.caption("⚠️ Excludes brokerage (0.3% or ₹20/order, whichever lower), pledge/unpledge charges (₹15+GST each), "
                   "and square-off charges (₹50+GST) — interest only. Check console.zerodha.com/funds/interest-statement "
                   "for the exact billed figure if you need precision for tax purposes.")

    # ── 2. MTF vs Cash P&L Comparison ────────────────────────────────────
    with mtf_tab2:
        st.caption(f"Is leverage actually paying for itself? Gross P&L by funding type, {year_sel}, net of auto-calculated MTF interest.")

        cash_total = sum(monthly_pnl_cash.values())
        mtf_total_gross = sum(monthly_pnl_mtf.values())
        mtf_total_net = mtf_total_gross - total_mtf_interest_auto

        cash_trades_n = sum(1 for t in closed if str(t.get("funding_type", "CASH") or "CASH").upper() != "MTF"
                             and str(t.get("exit_date", ""))[:4].isdigit() and int(str(t.get("exit_date", ""))[:4]) == year_sel)
        mtf_trades_n = sum(1 for t in closed if str(t.get("funding_type", "CASH") or "CASH").upper() == "MTF"
                            and str(t.get("exit_date", ""))[:4].isdigit() and int(str(t.get("exit_date", ""))[:4]) == year_sel)
        mtf_open_n = sum(1 for t in trades if t.get("status") == "OPEN"
                          and str(t.get("funding_type", "CASH") or "CASH").upper() == "MTF")

        if cash_trades_n == 0 and mtf_trades_n == 0:
            st.info("No closed trades this year to compare.")
        else:
            if mtf_trades_n == 0 and mtf_open_n > 0:
                st.markdown(f"""<div style="background:{AMBER_BG};border:1px solid {AMBER_BORDER};border-radius:8px;
                    padding:8px 12px;font-size:11px;color:{TEXT_BODY};margin-bottom:10px">
                    ℹ️ You have {mtf_open_n} open MTF position(s), but none closed yet this year — MTF P&L will show
                    ₹0 until at least one MTF trade is exited. Interest is still accruing (see Interest Cost tab).
                </div>""", unsafe_allow_html=True)

            mc1, mc2, mc3 = st.columns(3)
            mc1.markdown(kpi_card("CASH P&L", fmt_pnl(cash_total), color=pnl_color(cash_total),
                                   sub=f"{cash_trades_n} trade(s)"), unsafe_allow_html=True)
            mc2.markdown(kpi_card("MTF P&L (GROSS)", fmt_pnl(mtf_total_gross), color=pnl_color(mtf_total_gross),
                                   sub=f"{mtf_trades_n} closed trade(s)"), unsafe_allow_html=True)
            mc3.markdown(kpi_card("MTF P&L (NET OF INTEREST)", fmt_pnl(mtf_total_net), color=pnl_color(mtf_total_net),
                                   sub=f"after -{fmt_inr(total_mtf_interest_auto)} interest"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            fig_cmp = go.Figure()
            cmp_months = MONTHS
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
            l_cmp = chart_layout(height=280, title="Monthly P&L — Cash vs MTF (gross, closed trades only)")
            l_cmp["yaxis"]["tickprefix"] = "₹"
            l_cmp["barmode"] = "group"
            l_cmp["legend"] = dict(orientation="h", y=-0.18, x=0, font=dict(size=10, color=TEXT_MUTED))
            l_cmp["showlegend"] = True
            fig_cmp.update_layout(**l_cmp)
            st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})

            if mtf_total_gross > 0:
                st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
                    padding:14px 18px;font-size:13px;color:{TEXT_BODY};line-height:1.6;margin-top:8px">
                    MTF interest consumed <b style="color:{TEXT_H}">{(total_mtf_interest_auto/mtf_total_gross*100 if mtf_total_gross else 0):.1f}%</b>
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
