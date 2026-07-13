def _calc_peak_size(ticker, all_trades_raw):
    """Compute the peak (maximum) position value this ticker has ever held,
    by replaying all OPEN/CLOSED entries chronologically and tracking running
    qty × entry_price as positions were added to and trimmed from."""
    events = []
    for t in all_trades_raw:
        if t.get("ticker") != ticker:
            continue
        qty = safe_float(t.get("qty"))
        ep = safe_float(t.get("entry_price"))
        entry_date = str(t.get("entry_date","") or "")
        exit_date = str(t.get("exit_date","") or "")
        exit_qty = safe_float(t.get("exit_qty")) or qty
        if entry_date:
            events.append((entry_date, qty * ep, "add"))
        if t.get("status") == "CLOSED" and exit_date:
            xp = safe_float(t.get("exit_price")) or ep
            events.append((exit_date, exit_qty * xp, "remove"))

    if not events:
        return 0.0

    events.sort(key=lambda e: e[0])
    running = 0.0
    peak = 0.0
    for _, val, kind in events:
        if kind == "add":
            running += val
        else:
            running = max(0.0, running - val)
        peak = max(peak, running)
    return peak


def safe_float(v):
    try: return float(v or 0)
    except: return 0.0


def render_portfolio_holdings(open_all, all_trades_raw, price_data):
    """Renders a card-grid Portfolio Holdings view, matching the Nexus-style
    AVG/LTP/ALLOC, AT RISK/R:R/SL, REM. SIZE/% of peak layout."""
    import streamlit as st
    from theme import TEAL, RED, AMBER, BLUE, TEXT_H, TEXT_MUTED, TEXT_SUBTLE, CARD_BG, BORDER, SHADOW_SM, BORDER_LIGHT

    from data.db import get_kpi_summary_extended as get_kpi
    kpi = get_kpi()
    acct_bal = safe_float(kpi.get("account_balance", 10_000_000))

    combined = {}
    for t in open_all:
        tk = t.get("ticker","")
        ep = safe_float(t.get("entry_price"))
        qty = safe_float(t.get("qty"))
        live = t.get("live_price")
        sl = safe_float(t.get("stop_loss"))
        if tk not in combined:
            combined[tk] = {"qty": 0.0, "cost": 0.0, "live": live, "sl_list": [], "strategy": set(), "side": t.get("side","")}
        combined[tk]["qty"] += qty
        combined[tk]["cost"] += qty * ep
        if live:
            combined[tk]["live"] = live
        if sl:
            combined[tk]["sl_list"].append(sl)
        if t.get("strategy"):
            combined[tk]["strategy"].add(t.get("strategy"))

    if not combined:
        st.info("No open positions.")
        return

    invested_total = sum(c["cost"] for c in combined.values())
    unrealized_total = 0.0
    for tk, c in combined.items():
        live = safe_float(c["live"])
        if live and c["qty"]:
            avg = c["cost"] / c["qty"]
            unrealized_total += (live - avg) * c["qty"]

    h1, h2 = st.columns([1, 1])
    h1.markdown(f"""<div style="font-size:13px;color:{TEXT_MUTED}">
        Portfolio Holdings <span style="background:{BLUE}1A;color:{BLUE};padding:1px 8px;border-radius:10px;font-size:11px;margin-left:6px">{len(combined)} Active</span>
    </div>""", unsafe_allow_html=True)
    h2.markdown(f"""<div style="text-align:right;font-size:13px">
        <span style="color:{TEXT_SUBTLE}">INVESTED</span> <b style="color:{TEXT_H}">₹{invested_total:,.2f}</b>
        &nbsp;&nbsp;<span style="color:{TEXT_SUBTLE}">UNREALIZED P&L</span>
        <b style="color:{TEAL if unrealized_total>=0 else RED}">{'+' if unrealized_total>=0 else ''}₹{unrealized_total:,.2f}
        ({unrealized_total/invested_total*100:+.2f}%)</b>
    </div>""", unsafe_allow_html=True) if invested_total else None

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    n_cols = 4
    tickers = list(combined.keys())
    for row_start in range(0, len(tickers), n_cols):
        cols = st.columns(n_cols)
        for j, tk in enumerate(tickers[row_start:row_start+n_cols]):
            c = combined[tk]
            qty = c["qty"]
            avg = c["cost"] / qty if qty else 0
            live = safe_float(c["live"]) or avg
            alloc = c["cost"] / acct_bal * 100 if acct_bal else 0
            unrealized = (live - avg) * qty
            unrealized_pct = (live - avg) / avg * 100 if avg else 0
            pnl_col = TEAL if unrealized >= 0 else RED

            sl_list = c["sl_list"]
            sl_display = f"₹{sl_list[0]:,.2f}" if sl_list else "—"
            at_risk = "Yes" if sl_list and live <= min(sl_list) else "No"
            risk_col = RED if at_risk == "Yes" else TEXT_MUTED

            if sl_list and avg != sl_list[0]:
                risk_per_share = abs(avg - sl_list[0])
                reward_per_share = abs(live - avg)
                rr = reward_per_share / risk_per_share if risk_per_share else 0
                rr_display = f"{rr:.2f}"
            else:
                rr_display = "—"

            peak_val = _calc_peak_size(tk, all_trades_raw)
            current_cost = c["cost"]
            rem_size = max(0, peak_val - current_cost) if peak_val else 0
            pct_of_peak = (current_cost / peak_val * 100) if peak_val else 100.0

            strat_display = ", ".join(sorted(c["strategy"])) or "—"
            # Entry Quality from agent
            import json as _json
            eq_data = c.get("entry_quality") or {}
            if not eq_data and all_trades_raw:
                # Get from first open trade for this ticker
                for _t in all_trades_raw:
                    if _t.get("ticker")==tk and _t.get("status")=="OPEN" and _t.get("entry_quality"):
                        eq_data = _t.get("entry_quality") or {}
                        break
            if isinstance(eq_data, str):
                try: eq_data = _json.loads(eq_data)
                except: eq_data = {}
            eq_grade = eq_data.get("grade","")
            eq_score = eq_data.get("score_pct",0)
            eq_checks = eq_data.get("checks",{})

            from data.db import calc_mtf_interest_total
            mtf_trades = [t for t in all_trades_raw
                         if t.get("ticker") == tk
                         and t.get("status") == "OPEN"
                         and str(t.get("funding_type","CASH") or "CASH").upper() == "MTF"]
            mtf_int_total = sum(calc_mtf_interest_total(t) for t in mtf_trades)
            # Margin bifurcation
            mtf_position_val = sum(float(t.get("qty") or 0) * float(t.get("entry_price") or 0) for t in mtf_trades)
            mtf_margin_pct = float(mtf_trades[0].get("mtf_margin_pct") or 50.0) if mtf_trades else 50.0
            mtf_your_margin = mtf_position_val * (mtf_margin_pct / 100)
            mtf_broker_loan = mtf_position_val * (1 - mtf_margin_pct / 100)

            with cols[j]:
                # Build entry quality HTML separately
                if eq_grade:
                    eq_grade_col = G if eq_grade in ("A","B") else AM if eq_grade=="C" else R
                    eq_rows = ""
                    for ck, cv in eq_checks.items():
                        status = cv.get("status","—")
                        label = cv.get("label","")
                        detail = cv.get("detail","")
                        s_col = G if status=="✅" else R if status=="❌" else TEXT_SUBTLE
                        eq_rows += f'<div style="display:flex;justify-content:space-between;align-items:center;font-size:9px;margin-bottom:3px"><span style="color:{TEXT_MUTED}">{label}</span><span style="color:{s_col};font-weight:600">{status}</span></div>'
                    eq_html = f'''<div style="border-top:1px solid {BORDER_LIGHT};padding-top:6px;margin-top:6px;font-size:10px">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                            <span style="color:{TEXT_MUTED};font-weight:600;font-size:10px">ENTRY QUALITY</span>
                            <span style="font-size:16px;font-weight:800;color:{eq_grade_col}">{eq_grade} <span style="font-size:9px;color:{TEXT_SUBTLE}">({eq_score:.0f}%)</span></span>
                        </div>{eq_rows}</div>'''
                else:
                    eq_html = ""

                st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:12px;
                    padding:14px 16px;margin-bottom:10px;box-shadow:{SHADOW_SM}">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
                        <div>
                            <div style="font-size:15px;font-weight:800;color:{TEXT_H}">{tk}</div>
                            <div style="font-size:11px;color:{TEXT_SUBTLE};font-weight:500">{strat_display}</div>
                        </div>
                        <div style="text-align:right">
                            <div style="font-size:15px;font-weight:800;color:{pnl_col}">{'+' if unrealized>=0 else ''}₹{unrealized:,.0f}</div>
                            <div style="font-size:11px;font-weight:600;color:{pnl_col}">{unrealized_pct:+.2f}%</div>
                        </div>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;font-size:11px;
                        border-top:1px solid {BORDER_LIGHT};padding-top:8px;margin-bottom:6px">
                        <div><div style="color:{TEXT_MUTED};font-weight:600;font-size:10px">AVG</div><div style="color:{TEXT_H};font-weight:700">₹{avg:,.2f}</div></div>
                        <div><div style="color:{TEXT_MUTED};font-weight:600;font-size:10px">LTP</div><div style="color:{TEXT_H};font-weight:700">₹{live:,.2f}</div></div>
                        <div><div style="color:{TEXT_MUTED};font-weight:600;font-size:10px">ALLOC</div><div style="color:{TEXT_H};font-weight:700">{alloc:.2f}%</div></div>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;font-size:11px;margin-bottom:6px">
                        <div><div style="color:{TEXT_MUTED};font-weight:600;font-size:10px">AT RISK</div><div style="color:{risk_col};font-weight:700">{at_risk}</div></div>
                        <div><div style="color:{TEXT_MUTED};font-weight:600;font-size:10px">R:R</div><div style="color:{TEXT_H};font-weight:700">{rr_display}</div></div>
                        <div><div style="color:{TEXT_MUTED};font-weight:600;font-size:10px">SL</div><div style="color:{RED};font-weight:700">{sl_display}</div></div>
                    </div>
                    <div style="border-top:1px solid {BORDER_LIGHT};padding-top:6px;font-size:11px">
                        <div style="color:{TEXT_MUTED};font-weight:600;font-size:10px">REM. SIZE</div>
                        <div style="color:{BLUE};font-weight:800">₹{rem_size:,.2f}</div>
                        <div style="color:{TEXT_MUTED};font-size:10px;font-weight:500;margin-top:1px">{pct_of_peak:.0f}% deployed of peak</div>
                    </div>{eq_html}{'<div style="border-top:1px solid '+BORDER_LIGHT+';padding-top:6px;margin-top:6px;font-size:10px"><div style="color:'+TEXT_SUBTLE+'">MTF INTEREST</div><div style="color:'+AMBER+';font-weight:700">₹'+f'{mtf_int_total:,.2f}'+'</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:4px"><div><div style="color:'+TEXT_SUBTLE+'">YOUR MARGIN ('+f'{mtf_margin_pct:.1f}'+'%)</div><div style="color:'+TEXT_H+';font-weight:600">₹'+f'{mtf_your_margin:,.0f}'+'</div></div><div><div style="color:'+TEXT_SUBTLE+'">BROKER LOAN</div><div style="color:'+RED+';font-weight:600">₹'+f'{mtf_broker_loan:,.0f}'+'</div></div></div></div>' if mtf_int_total>0 else ''}
                </div>""", unsafe_allow_html=True)
