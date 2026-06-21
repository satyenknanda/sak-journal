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
            rem_size = c["cost"]
            pct_of_peak = (rem_size / peak_val * 100) if peak_val else 100.0

            strat_display = ", ".join(sorted(c["strategy"])) or "—"

            with cols[j]:
                st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:12px;
                    padding:14px 16px;margin-bottom:10px;box-shadow:{SHADOW_SM}">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
                        <div>
                            <div style="font-size:14px;font-weight:700;color:{TEXT_H}">{tk}</div>
                            <div style="font-size:10px;color:{TEXT_SUBTLE}">{strat_display}</div>
                        </div>
                        <div style="text-align:right">
                            <div style="font-size:14px;font-weight:700;color:{pnl_col}">{'+' if unrealized>=0 else ''}₹{unrealized:,.0f}</div>
                            <div style="font-size:10px;color:{pnl_col}">{unrealized_pct:+.2f}%</div>
                        </div>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;font-size:10px;
                        border-top:1px solid {BORDER_LIGHT};padding-top:8px;margin-bottom:6px">
                        <div><div style="color:{TEXT_SUBTLE}">AVG</div><div style="color:{TEXT_H};font-weight:600">₹{avg:,.2f}</div></div>
                        <div><div style="color:{TEXT_SUBTLE}">LTP</div><div style="color:{TEXT_H};font-weight:600">₹{live:,.2f}</div></div>
                        <div><div style="color:{TEXT_SUBTLE}">ALLOC</div><div style="color:{TEXT_H};font-weight:600">{alloc:.2f}%</div></div>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;font-size:10px;margin-bottom:6px">
                        <div><div style="color:{TEXT_SUBTLE}">AT RISK</div><div style="color:{risk_col};font-weight:600">{at_risk}</div></div>
                        <div><div style="color:{TEXT_SUBTLE}">R:R</div><div style="color:{TEXT_H};font-weight:600">{rr_display}</div></div>
                        <div><div style="color:{TEXT_SUBTLE}">SL</div><div style="color:{RED};font-weight:600">{sl_display}</div></div>
                    </div>
                    <div style="border-top:1px solid {BORDER_LIGHT};padding-top:6px;font-size:10px">
                        <div style="color:{TEXT_SUBTLE}">REM. SIZE</div>
                        <div style="color:{BLUE};font-weight:700">₹{rem_size:,.2f}</div>
                        <div style="color:{TEXT_SUBTLE};font-size:9px;margin-top:1px">{pct_of_peak:.0f}% of peak</div>
                    </div>
                </div>""", unsafe_allow_html=True)
