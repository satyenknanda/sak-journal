    # ════════════════════════════════════════════════════════════════════
    # DEEP ANALYTICS — sub-tabbed: Position & P&L | Streaks | Risk & Expectancy
    # ════════════════════════════════════════════════════════════════════
    with tab_deep:
        import numpy as np

        if not closed:
            st.info("No closed trades yet.")
        else:
            da_sub1, da_sub2, da_sub3 = st.tabs(["📊 Position & P&L", "🔥 Streaks", "⚖️ Risk & Expectancy"])

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 1: POSITION & P&L (existing content)
            # ════════════════════════════════════════════════════════════
            with da_sub1:
                pnls_d = [safe_float(t.get("pnl")) for t in closed]
                wins_d = [p for p in pnls_d if p > 0]
                losses_d = [p for p in pnls_d if p < 0]

                by_date_d = defaultdict(float)
                for t in closed:
                    d = str(t.get("exit_date","") or "")[:10]
                    if d and d != "nan":
                        by_date_d[d] += safe_float(t.get("pnl"))
                daily_vals = list(by_date_d.values())

                if len(daily_vals) > 1 and np.std(daily_vals) > 0:
                    sharpe = np.mean(daily_vals) / np.std(daily_vals)
                else:
                    sharpe = 0.0

                avg_pnl_day = np.mean(daily_vals) if daily_vals else 0
                expectancy_inr = np.mean(pnls_d) if pnls_d else 0

                sorted_closed = sorted(closed, key=lambda x: str(x.get("exit_date","") or ""))
                win_streak = loss_streak = cur_w = cur_l = 0
                for t in sorted_closed:
                    p = safe_float(t.get("pnl"))
                    if p > 0: cur_w += 1; cur_l = 0; win_streak = max(win_streak, cur_w)
                    else: cur_l += 1; cur_w = 0; loss_streak = max(loss_streak, cur_l)

                avg_win_inr = np.mean(wins_d) if wins_d else 0
                avg_loss_inr = np.mean(losses_d) if losses_d else 0

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

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 2: STREAKS
            # ════════════════════════════════════════════════════════════
            with da_sub2:
                sorted_closed2 = sorted(closed, key=lambda x: str(x.get("exit_date","") or ""))

                cur_streak_n = 0
                cur_streak_type = None
                run_type = None
                run_pnl = 0.0
                run_n = 0
                run_syms = []

                best_streak_pnl = 0.0
                best_streak_label = ""
                worst_streak_pnl = 0.0
                worst_streak_label = ""

                streaks_list = []

                for t in sorted_closed2:
                    p = safe_float(t.get("pnl"))
                    ttype = "W" if p > 0 else "L"
                    sym = t.get("ticker","")
                    if ttype == run_type:
                        run_pnl += p
                        run_n += 1
                        run_syms.append(sym)
                    else:
                        if run_type is not None:
                            streaks_list.append((run_type, run_n, run_pnl, run_syms[0] if run_syms else "", run_syms[-1] if run_syms else ""))
                        run_type = ttype
                        run_pnl = p
                        run_n = 1
                        run_syms = [sym]
                if run_type is not None:
                    streaks_list.append((run_type, run_n, run_pnl, run_syms[0] if run_syms else "", run_syms[-1] if run_syms else ""))

                if streaks_list:
                    last_type, last_n, last_pnl, _, _ = streaks_list[-1]
                    cur_streak_type = "WINNING" if last_type == "W" else "LOSING"
                    cur_streak_n = last_n

                    win_streaks_pnl = [(n, pnl, s1, s2) for ty,n,pnl,s1,s2 in streaks_list if ty=="W"]
                    loss_streaks_pnl = [(n, pnl, s1, s2) for ty,n,pnl,s1,s2 in streaks_list if ty=="L"]

                    if win_streaks_pnl:
                        best = max(win_streaks_pnl, key=lambda x: x[1])
                        best_streak_pnl = best[1]
                        best_streak_label = f"RECORD: W{best[0]} · {best[2]}, {best[3]}"
                    if loss_streaks_pnl:
                        worst = min(loss_streaks_pnl, key=lambda x: x[1])
                        worst_streak_pnl = worst[1]
                        worst_streak_label = f"WORST: L{worst[0]}"

                cs_col = RED if cur_streak_type == "LOSING" else TEAL
                sc1, sc2, sc3 = st.columns(3)
                sc1.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
                    padding:16px;text-align:center">
                    <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Current</div>
                    <div style="font-size:24px;font-weight:800;color:{cs_col};margin:4px 0">{('L' if cur_streak_type=='LOSING' else 'W')}{cur_streak_n}</div>
                    <div style="font-size:10px;color:{TEXT_SUBTLE};text-transform:uppercase">{cur_streak_type or '—'}</div>
                </div>""", unsafe_allow_html=True)
                sc2.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
                    padding:16px;text-align:center">
                    <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Best Streak</div>
                    <div style="font-size:20px;font-weight:800;color:{TEAL};margin:4px 0">{fmt_pnl(best_streak_pnl)}</div>
                    <div style="font-size:9px;color:{TEXT_SUBTLE}">{best_streak_label}</div>
                </div>""", unsafe_allow_html=True)
                sc3.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
                    padding:16px;text-align:center">
                    <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Worst Streak</div>
                    <div style="font-size:20px;font-weight:800;color:{RED};margin:4px 0">{fmt_pnl(worst_streak_pnl)}</div>
                    <div style="font-size:9px;color:{TEXT_SUBTLE}">{worst_streak_label}</div>
                </div>""", unsafe_allow_html=True)

                st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

                st.markdown(f'<p style="font-size:12px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:8px">Trade-by-Trade Move %</p>', unsafe_allow_html=True)

                def stock_move_pct2(t):
                    ep = safe_float(t.get("entry_price"))
                    xp = safe_float(t.get("exit_price"))
                    if ep <= 0: return None
                    side = str(t.get("side","") or "").upper()
                    raw = (xp - ep) / ep * 100
                    return raw if side not in ("SHORT","SELL") else -raw

                grid_trades = sorted_closed2[-70:]
                n_grid_cols = 7
                for row_start in range(0, len(grid_trades), n_grid_cols):
                    row = grid_trades[row_start:row_start+n_grid_cols]
                    gcols = st.columns(n_grid_cols)
                    for gc, t in zip(gcols, row):
                        mv = stock_move_pct2(t)
                        sym = t.get("ticker","")
                        if mv is None:
                            continue
                        bg = TEAL_BG if mv >= 0 else RED_BG
                        fg = TEAL if mv >= 0 else RED
                        gc.markdown(f"""<div style="background:{bg};border-radius:6px;padding:6px 4px;
                            text-align:center;margin-bottom:4px">
                            <div style="font-size:9px;color:{fg};font-weight:700;white-space:nowrap;
                                overflow:hidden;text-overflow:ellipsis">{sym}</div>
                            <div style="font-size:11px;color:{fg};font-weight:700">{mv:+.1f}%</div>
                        </div>""", unsafe_allow_html=True)

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Trading Calendar Heatmap</p>', unsafe_allow_html=True)
                st.caption("Realized P&L spread mapped on a calendar view")

                cal_pnl = defaultdict(float)
                for t in closed:
                    d = str(t.get("exit_date","") or "")[:10]
                    if d and d != "nan":
                        cal_pnl[d] += safe_float(t.get("pnl"))

                if cal_pnl:
                    cal_df = pd.DataFrame([{"date": d, "pnl": v} for d, v in cal_pnl.items()])
                    cal_df["date"] = pd.to_datetime(cal_df["date"])
                    cal_df["year"] = cal_df["date"].dt.year
                    years_avail = sorted(cal_df["year"].unique(), reverse=True)
                    sel_year = st.selectbox("Year", years_avail, key="deep_streak_cal_year")
                    ydf = cal_df[cal_df["year"] == sel_year].copy()
                    ydf["week"] = ydf["date"].dt.isocalendar().week
                    ydf["dow"] = ydf["date"].dt.dayofweek

                    max_abs = ydf["pnl"].abs().max() if not ydf.empty else 1

                    def cal_color(v):
                        if v is None: return BORDER_LIGHT
                        intensity = min(abs(v) / max_abs, 1.0) if max_abs else 0
                        if v >= 0:
                            return f"rgba(16,185,129,{0.15 + intensity*0.6:.2f})"
                        return f"rgba(239,68,68,{0.15 + intensity*0.6:.2f})"

                    pivot = ydf.pivot_table(index="dow", columns="week", values="pnl", aggfunc="sum")
                    weeks_sorted = sorted(pivot.columns)
                    months_for_weeks = ydf.groupby("week")["date"].first().dt.strftime("%b")

                    html = '<div style="overflow-x:auto"><table style="border-collapse:separate;border-spacing:2px">'
                    html += "<tr><td></td>"
                    last_mo = ""
                    for wk in weeks_sorted:
                        mo = months_for_weeks.get(wk, "")
                        html += f'<td style="font-size:8px;color:{TEXT_MUTED};text-align:center">{"" if mo==last_mo else mo}</td>'
                        last_mo = mo
                    html += "</tr>"
                    DOW_LABELS = ["M","T","W","T","F","S","S"]
                    for dow in range(7):
                        html += f'<tr><td style="font-size:8px;color:{TEXT_MUTED};padding-right:3px">{DOW_LABELS[dow]}</td>'
                        for wk in weeks_sorted:
                            v = pivot.loc[dow, wk] if (dow in pivot.index and wk in pivot.columns and not pd.isna(pivot.loc[dow, wk])) else None
                            bg = cal_color(v)
                            tip = f"₹{v:,.0f}" if v is not None else "No trades"
                            html += f'<td title="{tip}" style="width:12px;height:12px;background:{bg};border-radius:2px"></td>'
                        html += "</tr>"
                    html += "</table></div>"
                    st.markdown(html, unsafe_allow_html=True)

                    total_for_year = ydf["pnl"].sum()
                    st.markdown(f"""<div style="display:flex;gap:14px;align-items:center;margin-top:8px;font-size:10px;color:{TEXT_SUBTLE}">
                        <span>⚪ No trades</span>
                        <span style="color:{RED}">🔴 Loss</span>
                        <span style="color:{TEAL}">🟢 Profit</span>
                        <span style="margin-left:auto;color:{TEXT_H};font-weight:700">Total: {fmt_pnl(total_for_year)}</span>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.info("No trade data for calendar heatmap.")

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 3: RISK & EXPECTANCY (Month-on-Month matrix)
            # ════════════════════════════════════════════════════════════
            with da_sub3:
                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Month-on-Month Risk & Expectancy Matrix</p>', unsafe_allow_html=True)

                by_month = defaultdict(list)
                for t in closed:
                    m = str(t.get("exit_date","") or "")[:7]
                    if m and m != "nan":
                        by_month[m].append(t)
                open_by_month = defaultdict(list)
                for t in trades:
                    if t.get("status") == "OPEN":
                        m = str(t.get("entry_date","") or "")[:7]
                        if m and m != "nan":
                            open_by_month[m].append(t)

                all_months_sorted = sorted(set(list(by_month.keys()) + list(open_by_month.keys())), reverse=True)[:6]

                if not all_months_sorted:
                    st.info("Not enough data for month-on-month matrix.")
                else:
                    def fmt_month_label(m):
                        try:
                            return pd.to_datetime(m + "-01").strftime("%b %Y").upper()
                        except Exception:
                            return m

                    month_stats = {}
                    for m in all_months_sorted:
                        ct = by_month.get(m, [])
                        ot = open_by_month.get(m, [])
                        pnls_m = [safe_float(t.get("pnl")) for t in ct]
                        wins_m = [p for p in pnls_m if p > 0]
                        losses_m = [p for p in pnls_m if p < 0]
                        be_m = [p for p in pnls_m if p == 0]
                        wr_m = len(wins_m) / len(pnls_m) * 100 if pnls_m else 0
                        avg_loss_m = np.mean(losses_m) if losses_m else 0
                        avg_gain_m = np.mean(wins_m) if wins_m else 0
                        r_vals_m = [safe_float(t.get("r_multiple")) for t in ct if t.get("r_multiple")]
                        r_wins_m = [r for r in r_vals_m if r > 0]
                        r_losses_m = [r for r in r_vals_m if r <= 0]
                        avg_r_loss = np.mean(r_losses_m) if r_losses_m else 0
                        avg_r_gain = np.mean(r_wins_m) if r_wins_m else 0
                        expectancy_r = (wr_m/100 * avg_r_gain) + ((1 - wr_m/100) * avg_r_loss) if r_vals_m else 0
                        total_r = sum(r_vals_m)
                        total_profit_entry = sum(safe_float(t.get("pnl")) for t in ct
                                                  if str(t.get("entry_date",""))[:7] == m)
                        total_profit_close = sum(pnls_m)

                        month_stats[m] = {
                            "entered": len(ct) + len(ot), "open": len(ot), "closed": len(ct),
                            "be": len(be_m), "winners": len(wins_m), "losers": len(losses_m),
                            "win_rate": wr_m, "avg_loss": avg_loss_m, "avg_gain": avg_gain_m,
                            "avg_r_loss": avg_r_loss, "avg_r_gain": avg_r_gain,
                            "arr": (avg_r_gain / abs(avg_r_loss)) if avg_r_loss else 0,
                            "expectancy_r": expectancy_r, "total_r": total_r,
                            "avg_risk_r": np.mean([abs(r) for r in r_vals_m]) if r_vals_m else 0,
                            "profit_entry": total_profit_entry, "profit_close": total_profit_close,
                        }

                    ROWS = [
                        ("1. TRADES", None, None),
                        ("Trades Entered", "entered", "int"),
                        ("Open Till Date", "open", "bracket"),
                        ("Trades Closed", "closed", "int"),
                        ("Breakeven", "be", "bracket"),
                        ("Winners", "winners", "int_green"),
                        ("Losers", "losers", "int_red"),
                        ("Win Rate", "win_rate", "pct"),
                        ("2. AVERAGES", None, None),
                        ("Avg Loss (Losers)", "avg_loss", "inr_red"),
                        ("Avg Gain (Winners)", "avg_gain", "inr_green"),
                        ("3. RISK/REWARD", None, None),
                        ("Avg R Loss (Losers)", "avg_r_loss", "r_red"),
                        ("Avg R Gain (Winners)", "avg_r_gain", "r_green"),
                        ("ARR", "arr", "num"),
                        ("4. EXPECTANCY", None, None),
                        ("Trade Expectancy (in R)", "expectancy_r", "r_signed"),
                        ("Trades Closed", "closed", "int"),
                        ("Total R Gained", "total_r", "r_signed"),
                        ("5. PROFITABILITY", None, None),
                        ("Avg Risk (R)", "avg_risk_r", "r"),
                        ("Total Profit (By Entry Date)", "profit_entry", "inr_signed"),
                        ("Total Profit (By Close Date)", "profit_close", "inr_signed"),
                    ]

                    def fmt_cell(val, kind):
                        if kind is None:
                            return ""
                        if kind == "int":
                            return str(int(val))
                        if kind == "int_green":
                            return f'<span style="color:{TEAL};font-weight:700">{int(val)}</span>'
                        if kind == "int_red":
                            return f'<span style="color:{RED};font-weight:700">{int(val)}</span>'
                        if kind == "bracket":
                            return f'<span style="color:{BLUE}">[{int(val)}]</span>'
                        if kind == "pct":
                            return f"{val:.0f}%"
                        if kind == "inr_red":
                            return f'<span style="color:{RED}">{fmt_pnl(val) if val else "₹0"}</span>'
                        if kind == "inr_green":
                            return f'<span style="color:{TEAL}">{fmt_pnl(val) if val else "₹0"}</span>'
                        if kind == "inr_signed":
                            return f'<span style="color:{pnl_color(val)};font-weight:700">{fmt_pnl(val)}</span>'
                        if kind == "r_red":
                            return f'<span style="color:{RED}">{val:.0f}R</span>'
                        if kind == "r_green":
                            return f'<span style="color:{TEAL}">+{val:.0f}R</span>'
                        if kind == "r":
                            return f"{val:.0f}R"
                        if kind == "r_signed":
                            return f'<span style="color:{pnl_color(val)}">{val:+.0f}R</span>'
                        if kind == "num":
                            return f"{val:.0f}"
                        return str(val)

                    th_style = f"padding:9px 14px;text-align:left;color:{TEXT_SUBTLE};font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;border-bottom:2px solid {BORDER};background:{CARD_BG};white-space:nowrap"
                    td_style = f"padding:8px 14px;font-size:13px;border-bottom:1px solid {BORDER_LIGHT};white-space:nowrap"
                    section_style = f"padding:10px 14px;font-size:11px;font-weight:700;font-style:italic;color:{TEXT_H};background:{PAGE_BG}"

                    rows_html = ""
                    for label, key, kind in ROWS:
                        if key is None:
                            rows_html += f'<tr><td colspan="{len(all_months_sorted)+1}" style="{section_style}">{label}</td></tr>'
                        else:
                            rows_html += f'<tr><td style="{td_style};color:{TEXT_MUTED}">{label}</td>'
                            for m in all_months_sorted:
                                val = month_stats[m].get(key, 0)
                                rows_html += f'<td style="{td_style};text-align:center">{fmt_cell(val, kind)}</td>'
                            rows_html += "</tr>"

                    header_html = f'<th style="{th_style}">Matrix Metrics</th>' + "".join(
                        f'<th style="{th_style};text-align:center">{fmt_month_label(m)}</th>' for m in all_months_sorted)

                    st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER};box-shadow:{SHADOW_SM}">
                        <table style="width:100%;border-collapse:collapse">
                        <thead><tr>{header_html}</tr></thead>
                        <tbody>{rows_html}</tbody>
                        </table>
                    </div>""", unsafe_allow_html=True)
