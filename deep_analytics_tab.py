    # ════════════════════════════════════════════════════════════════════
    # DEEP ANALYTICS — Sharpe, Streaks, Risk, Weekday P&L, Symbol P&L, Stock Move %
    # ════════════════════════════════════════════════════════════════════
    with tab_deep:
        import numpy as np

        if not closed:
            st.info("No closed trades yet.")
        else:
            pnls_d = [safe_float(t.get("pnl")) for t in closed]
            wins_d = [p for p in pnls_d if p > 0]
            losses_d = [p for p in pnls_d if p < 0]

            # ── Daily P&L series for Sharpe ──────────────────────────────────
            by_date_d = defaultdict(float)
            for t in closed:
                d = str(t.get("exit_date","") or "")[:10]
                if d and d != "nan":
                    by_date_d[d] += safe_float(t.get("pnl"))
            daily_vals = list(by_date_d.values())

            # Sharpe Ratio (daily, annualized assumption not applied — raw daily Sharpe)
            if len(daily_vals) > 1 and np.std(daily_vals) > 0:
                sharpe = np.mean(daily_vals) / np.std(daily_vals)
            else:
                sharpe = 0.0

            avg_pnl_day = np.mean(daily_vals) if daily_vals else 0
            expectancy_inr = np.mean(pnls_d) if pnls_d else 0

            # ── Win/Loss Streaks with avg ₹ ──────────────────────────────────
            sorted_closed = sorted(closed, key=lambda x: str(x.get("exit_date","") or ""))
            win_streak = loss_streak = cur_w = cur_l = 0
            for t in sorted_closed:
                p = safe_float(t.get("pnl"))
                if p > 0: cur_w += 1; cur_l = 0; win_streak = max(win_streak, cur_w)
                else: cur_l += 1; cur_w = 0; loss_streak = max(loss_streak, cur_l)

            avg_win_inr = np.mean(wins_d) if wins_d else 0
            avg_loss_inr = np.mean(losses_d) if losses_d else 0

            # ── Avg Risk/Trade & Avg PF Risk/Trade ───────────────────────────
            risks = []
            for t in closed:
                ep = safe_float(t.get("entry_price"))
                sl = safe_float(t.get("stop_loss"))
                qty = safe_float(t.get("qty"))
                if ep and sl and qty:
                    risks.append(abs(ep - sl) * qty)
            avg_risk_inr = np.mean(risks) if risks else 0

            avg_pf_risk_pct = []
            for t in closed:
                ep = safe_float(t.get("entry_price"))
                sl = safe_float(t.get("stop_loss"))
                if ep and sl:
                    avg_pf_risk_pct.append(abs(ep - sl) / ep * 100)
            avg_pf_risk = np.mean(avg_pf_risk_pct) if avg_pf_risk_pct else 0

            best_trade = max(pnls_d) if pnls_d else 0
            worst_trade = min(pnls_d) if pnls_d else 0

            r_vals = [safe_float(t.get("r_multiple")) for t in closed if t.get("r_multiple")]
            highest_r = max(r_vals) if r_vals else 0
            lowest_r = min(r_vals) if r_vals else 0
            avg_r = np.mean(r_vals) if r_vals else 0

            # ── KPI cards ─────────────────────────────────────────────────────
            st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Key Performance Metrics</p>', unsafe_allow_html=True)
            d1, d2, d3, d4 = st.columns(4)
            d1.markdown(kpi_card("Avg PnL/Day", fmt_pnl(avg_pnl_day), color=pnl_color(avg_pnl_day),
                                  sub="Average daily profit/loss"), unsafe_allow_html=True)
            d2.markdown(kpi_card("Sharpe Ratio", f"{sharpe:.2f}", color=TEAL if sharpe >= 0 else RED,
                                  sub="Risk-adjusted return (daily)"), unsafe_allow_html=True)
            d3.markdown(kpi_card("Expectancy", fmt_pnl(expectancy_inr), color=pnl_color(expectancy_inr),
                                  sub="Expected profit per trade"), unsafe_allow_html=True)
            d4.markdown(kpi_card("Avg Risk/Trade", fmt_pnl(avg_risk_inr), sub="Average initial rupee risk"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            d5, d6, d7, d8 = st.columns(4)
            d5.markdown(kpi_card("Win Streak", str(win_streak), color=TEAL, sub=f"Avg Win: {fmt_pnl(avg_win_inr)}"), unsafe_allow_html=True)
            d6.markdown(kpi_card("Loss Streak", str(loss_streak), color=RED, sub=f"Avg Loss: {fmt_pnl(avg_loss_inr)}"), unsafe_allow_html=True)
            d7.markdown(kpi_card("Avg PF Risk/Trade", f"{avg_pf_risk:.2f}%", sub="Average risk vs entry price"), unsafe_allow_html=True)
            d8.markdown(kpi_card("Best / Worst Trade", f"{fmt_pnl(best_trade)} / {fmt_pnl(worst_trade)}",
                                  sub="Highest profit / Biggest loss"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            d9, d10, d11 = st.columns(3)
            d9.markdown(kpi_card("Highest R", f"{highest_r:.2f}R", color=TEAL, sub="Best risk:reward"), unsafe_allow_html=True)
            d10.markdown(kpi_card("Lowest R", f"{lowest_r:.2f}R", color=RED, sub="Worst risk:reward"), unsafe_allow_html=True)
            d11.markdown(kpi_card("Avg R", f"{avg_r:.2f}R", color=pnl_color(avg_r), sub="Average risk:reward"), unsafe_allow_html=True)

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            # ── Aggregate PnL vs Day (weekday distribution) ──────────────────
            st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Aggregate PnL vs Day — Weekday Distribution</p>', unsafe_allow_html=True)
            DOW_FULL = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            dow_pnl = defaultdict(float)
            dow_count = defaultdict(int)
            for t in closed:
                dow = _get_dow(t)
                if dow:
                    dow_pnl[dow] += safe_float(t.get("pnl"))
                    dow_count[dow] += 1
            dow_x = [d for d in DOW_FULL if d in dow_pnl]
            dow_y = [dow_pnl[d] for d in dow_x]
            if dow_x:
                fig_dow = go.Figure()
                fig_dow.add_trace(go.Bar(x=dow_x, y=dow_y,
                    marker=dict(color=[TEAL if v>=0 else RED for v in dow_y], opacity=0.85, line=dict(width=0)),
                    text=[f"{c} trades" for c in [dow_count[d] for d in dow_x]],
                    textposition="outside", textfont=dict(size=9, color=TEXT_MUTED),
                    hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"))
                l_dow = chart_layout(height=260, title="")
                l_dow["yaxis"]["tickprefix"] = "₹"
                fig_dow.update_layout(**l_dow)
                st.plotly_chart(fig_dow, use_container_width=True, config={"displayModeBar":False})
            else:
                st.info("No weekday data available.")

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            # ── Realized P&L Distribution / Aggregate PnL vs Symbol ──────────
            st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Aggregate PnL vs Symbol</p>', unsafe_allow_html=True)
            sym_pnl = defaultdict(float)
            sym_count = defaultdict(int)
            for t in closed:
                sym = t.get("ticker","")
                if sym:
                    sym_pnl[sym] += safe_float(t.get("pnl"))
                    sym_count[sym] += 1
            top_syms = sorted(sym_pnl.items(), key=lambda x: x[1], reverse=True)[:15]
            if top_syms:
                sym_x = [s for s,_ in top_syms]
                sym_y = [v for _,v in top_syms]
                fig_sym = go.Figure()
                fig_sym.add_trace(go.Bar(x=sym_x, y=sym_y,
                    marker=dict(color=[TEAL if v>=0 else RED for v in sym_y], opacity=0.85, line=dict(width=0)),
                    hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"))
                l_sym = chart_layout(height=280, title="Top 15 Symbols by Net P&L")
                l_sym["yaxis"]["tickprefix"] = "₹"
                l_sym["xaxis"]["tickangle"] = -40
                fig_sym.update_layout(**l_sym)
                st.plotly_chart(fig_sym, use_container_width=True, config={"displayModeBar":False})

            # Realized P&L distribution (frequency spread of trade P&L size)
            st.markdown(f'<p style="font-size:12px;color:{TEXT_MUTED};margin:12px 0 4px">Realized P&L Distribution — frequency spread of trade P&L size</p>', unsafe_allow_html=True)
            if pnls_d:
                fig_dist = go.Figure()
                fig_dist.add_trace(go.Histogram(x=pnls_d, nbinsx=25,
                    marker=dict(color=TEAL, opacity=0.7),
                    hovertemplate="₹%{x:,.0f}<br>%{y} trades<extra></extra>"))
                fig_dist.add_vline(x=0, line=dict(color=RED, width=1, dash="dash"))
                l_dist = chart_layout(height=240, title="")
                l_dist["xaxis"]["tickprefix"] = "₹"
                l_dist["xaxis"]["title"] = dict(text="Trade P&L (₹)", font=dict(size=10, color=TEXT_SUBTLE))
                fig_dist.update_layout(**l_dist)
                st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar":False})

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            # ── Stock Move % chart (Daily/Weekly/Monthly avg move) ───────────
            st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Stock Move % — Average Underlying Movement</p>', unsafe_allow_html=True)
            st.caption("% move of the underlying stock from entry to exit (not P&L% — the raw price move), bucketed by exit period.")

            move_period = st.radio("Period", ["Daily","Weekly","Monthly"], index=2, horizontal=True, key="deep_move_period")

            def stock_move_pct(t):
                ep = safe_float(t.get("entry_price"))
                xp = safe_float(t.get("exit_price"))
                if ep <= 0: return None
                side = str(t.get("side","") or "").upper()
                raw = (xp - ep) / ep * 100
                return raw if side not in ("SHORT","SELL") else -raw

            move_data = []
            for t in closed:
                m = stock_move_pct(t)
                ed = str(t.get("exit_date","") or "")[:10]
                if m is not None and ed and ed != "nan":
                    move_data.append({"date": ed, "move": m})

            if move_data:
                mdf = pd.DataFrame(move_data)
                mdf["date"] = pd.to_datetime(mdf["date"])
                if move_period == "Daily":
                    mdf["period"] = mdf["date"].dt.strftime("%Y-%m-%d")
                elif move_period == "Weekly":
                    mdf["period"] = mdf["date"].dt.to_period("W").astype(str)
                else:
                    mdf["period"] = mdf["date"].dt.strftime("%Y-%m")
                grp = mdf.groupby("period")["move"].mean().reset_index().sort_values("period")

                fig_move = go.Figure()
                fig_move.add_trace(go.Scatter(x=grp["period"], y=grp["move"], mode="lines+markers",
                    line=dict(color=BLUE, width=2.5, shape="spline"),
                    marker=dict(size=6, color=BLUE),
                    fill="tozeroy", fillcolor="rgba(59,130,246,0.15)",
                    hovertemplate="%{x}<br>%{y:+.2f}%<extra></extra>"))
                fig_move.add_hline(y=0, line=dict(color=BORDER_LIGHT, width=1))
                l_move = chart_layout(height=260, title="")
                l_move["yaxis"]["ticksuffix"] = "%"
                fig_move.update_layout(**l_move)
                st.plotly_chart(fig_move, use_container_width=True, config={"displayModeBar":False})
            else:
                st.info("No entry/exit price data available to compute stock move %.")
