import streamlit as st
from theme import *
# ── backwards-compat aliases ──────────────────────────────────────────────
kcard   = kpi_card          # old name used in some pages
G       = TEAL
R       = RED
B       = BLUE
AM      = AMBER
MUTED   = TEXT_MUTED
TEXT    = TEXT_H
TEXT2   = TEXT_BODY
DIM     = BORDER_LIGHT
BG      = PAGE_BG
CARD    = CARD_BG
BORDER_C= BORDER
SHADOW  = SHADOW_SM
# ─────────────────────────────────────────────────────────────────────────

import json
from pathlib import Path
from data.db import get_setting, set_setting
from data.prices import fetch_price


def _safe(v, default=0.0):
    try: return float(v) if v else default
    except: return default


def _fmt(v, decimals=2):
    try: return f"₹{float(v):,.{decimals}f}"
    except: return "—"


def _save_history(entry):
    """Save calculation to session + persistent settings (last 10)."""
    hist = st.session_state.get("calc_history", [])
    hist.insert(0, entry)
    hist = hist[:10]
    st.session_state["calc_history"] = hist
    try:
        set_setting("calc_history", json.dumps(hist))
    except Exception:
        pass


def _load_history():
    if "calc_history" not in st.session_state:
        raw = get_setting("calc_history", "[]")
        try:
            st.session_state["calc_history"] = json.loads(raw)
        except Exception:
            st.session_state["calc_history"] = []
    return st.session_state.get("calc_history", [])


def result_card(label, value, color="primary"):
    color_map = {
        "primary": "var(--text-primary)",
        "green":   "#00C48C",
        "red":     "#FF5C5C",
        "blue":    "#4A9EFF",
        "amber":   "#FFB84A",
    }
    c = color_map.get(color, "var(--text-primary)")
    return f"""
    <div style="background:var(--card-bg);border:1px solid var(--border);
        border-radius:8px;padding:12px 14px;">
        <div style="font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;
            letter-spacing:0.06em;font-weight:600">{label}</div>
        <div style="font-size:1.2rem;font-weight:700;color:{c};
            margin-top:4px;font-family:'SF Mono',monospace">{value}</div>
    </div>"""


def render_position_sizing():
    st.markdown("#### Position Sizing")

    acct_bal  = _safe(get_setting("account_balance", "10000000"))
    risk_pct  = _safe(get_setting("risk_pct", "0.004"))
    one_r_val = acct_bal * risk_pct

    # ── Inputs ─────────────────────────────────────────────────────────────
    col_in, col_out = st.columns([1, 1], gap="large")

    with col_in:
        st.markdown(
            '<div style="background:var(--card-bg);border:1px solid var(--border);'
            'border-radius:10px;padding:20px">', unsafe_allow_html=True)

        st.markdown("**Account**")
        a1, a2 = st.columns(2)
        with a1:
            capital = st.number_input("Capital ₹", value=acct_bal, step=100000.0,
                                       format="%.0f", key="ps_capital")
        with a2:
            risk_pct_input = st.number_input("Risk % per trade", value=risk_pct * 100,
                                              min_value=0.01, max_value=5.0,
                                              step=0.01, format="%.2f", key="ps_riskpct")
            risk_pct_actual = risk_pct_input / 100
            one_r = capital * risk_pct_actual

        st.markdown(
            f'<div style="background:rgba(74,158,255,0.1);border-radius:6px;'
            f'padding:8px 12px;font-size:0.82rem;margin:4px 0 12px 0">'
            f'Base 1R = <strong style="color:#4A9EFF">₹{one_r:,.0f}</strong> '
            f'({risk_pct_input:.2f}% of ₹{capital:,.0f})</div>',
            unsafe_allow_html=True)

        st.markdown("**Trade Setup**")

        # Ticker + live fetch
        t1, t2 = st.columns([3, 1])
        with t1:
            ticker = st.text_input("Ticker", value=st.session_state.get("ps_ticker_val", ""),
                                    placeholder="e.g. RELIANCE", key="ps_ticker")
        with t2:
            st.markdown("<br>", unsafe_allow_html=True)
            fetch_clicked = st.button("⟳ Fetch", key="ps_fetch", use_container_width=True)

        live_price = st.session_state.get("ps_live_price", 0.0)
        if fetch_clicked and ticker:
            with st.spinner(f"Fetching {ticker}…"):
                result = fetch_price(ticker)
            if result.get("price"):
                live_price = result["price"]
                st.session_state["ps_live_price"] = live_price
                st.session_state["ps_ticker_val"] = ticker
                st.success(f"₹{live_price:,.2f}  ({result.get('change_pct',0):+.2f}%)")
            else:
                st.error(f"Could not fetch price for {ticker}")

        p1, p2 = st.columns(2)
        with p1:
            live_disp = st.number_input("Live Price ₹", value=float(live_price),
                                         min_value=0.0, step=0.05, format="%.2f",
                                         key="ps_live")
        with p2:
            entry = st.number_input("Entry Price ₹", value=float(live_price) or 0.0,
                                     min_value=0.0, step=0.05, format="%.2f",
                                     key="ps_entry")

        s1, s2 = st.columns(2)
        with s1:
            sl = st.number_input("Stop Loss ₹", min_value=0.0, step=0.05,
                                  format="%.2f", key="ps_sl")
        with s2:
            tp = st.number_input("Take Profit ₹", min_value=0.0, step=0.05,
                                  format="%.2f", key="ps_tp")

        market = st.selectbox("Market Regime", ["Normal Market", "Bull Market", "Bear Market"],
                               key="ps_regime")

        # Regime multiplier config
        regime_multipliers = {"Normal Market": 1.0, "Bull Market": 1.5, "Bear Market": 0.5}
        regime_colors      = {"Normal Market": "#4A9EFF", "Bull Market": "#00C48C", "Bear Market": "#FF5C5C"}
        regime_icons       = {"Normal Market": "⚖️", "Bull Market": "🐂", "Bear Market": "🐻"}
        multiplier = regime_multipliers[market]
        adjusted_1r = one_r * multiplier

        regime_color = regime_colors[market]
        regime_icon  = regime_icons[market]
        st.markdown(
            f'''<div style="background:rgba(74,158,255,0.08);border-left:3px solid {regime_color};
            border-radius:0 6px 6px 0;padding:10px 14px;margin:8px 0;font-size:0.82rem">
            {regime_icon} <strong style="color:{regime_color}">{market}</strong>
            &nbsp;·&nbsp; Multiplier <strong style="color:{regime_color}">{multiplier}×</strong>
            &nbsp;·&nbsp; Adjusted 1R = <strong style="color:{regime_color}">₹{adjusted_1r:,.0f}</strong>
            &nbsp;<span style="color:var(--text-muted);font-size:0.75rem">
            (base ₹{one_r:,.0f} × {multiplier})</span></div>''',
            unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Calculations using adjusted 1R ─────────────────────────────────────
    qty          = 0
    pos_size     = 0.0
    sl_value     = 0.0
    target_value = 0.0
    rr           = 0.0
    comm_entry   = 0.0
    comm_exit    = 0.0
    risk_per_share = 0.0

    if entry and sl and entry != sl:
        risk_per_share = abs(entry - sl)
        qty            = int(adjusted_1r / risk_per_share) if risk_per_share else 0
        pos_size       = entry * qty
        sl_value       = risk_per_share * qty
        if tp and tp != entry:
            reward      = abs(tp - entry) * qty
            rr          = abs(tp - entry) / risk_per_share if risk_per_share else 0
            target_value= tp * qty
        # Commission estimate (Zerodha-style: 0.03% or ₹20 whichever lower per leg)
        comm_entry = min(pos_size * 0.0003, 20.0) + pos_size * 0.00018  # brokerage + STT
        comm_exit  = min(pos_size * 0.0003, 20.0) + pos_size * 0.00018

    with col_out:
        # Result cards
        r1, r2 = st.columns(2)
        r1.markdown(result_card("Adjusted 1R", f"₹{adjusted_1r:,.0f}", "blue"), unsafe_allow_html=True)
        r2.markdown(result_card("Qty to Buy", f"{qty:,}" if qty else "—", "primary"), unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        r3, r4 = st.columns(2)
        r3.markdown(result_card("Position Size", f"₹{pos_size:,.0f}" if pos_size else "—", "primary"), unsafe_allow_html=True)
        r4.markdown(result_card("SL Value ₹", f"₹{sl_value:,.0f}" if sl_value else "—", "red"), unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        r5, r6 = st.columns(2)
        r5.markdown(result_card("Target Value", f"₹{target_value:,.0f}" if target_value else "—", "green"), unsafe_allow_html=True)
        r6.markdown(result_card("Max R:R", f"{rr:.2f}R" if rr else "—", "green" if rr >= 2 else "amber" if rr >= 1 else "red"), unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        r7, r8 = st.columns(2)
        r7.markdown(result_card("Risk/Share", f"₹{risk_per_share:.2f}" if risk_per_share else "—", "amber"), unsafe_allow_html=True)
        r8.markdown(result_card("Allocation %", f"{pos_size/capital*100:.1f}%" if capital and pos_size else "—", "primary"), unsafe_allow_html=True)

        # R:R visual bar
        if rr > 0:
            fill_pct = min(rr / 5 * 100, 100)
            bar_color = "#00C48C" if rr >= 2 else "#FFB84A" if rr >= 1 else "#FF5C5C"
            st.markdown(f"""
            <div style="margin:12px 0 4px 0">
                <div style="display:flex;justify-content:space-between;font-size:0.75rem;
                    color:var(--text-muted);margin-bottom:4px">
                    <span>Risk ₹{sl_value:,.0f}</span>
                    <span>R:R {rr:.2f}:1</span>
                    <span>Reward ₹{target_value - pos_size:,.0f}</span>
                </div>
                <div style="height:6px;background:var(--border);border-radius:3px;overflow:hidden">
                    <div style="height:100%;width:{fill_pct:.0f}%;background:{bar_color};border-radius:3px"></div>
                </div>
            </div>""", unsafe_allow_html=True)

        # Commission card
        if comm_entry:
            st.markdown(f"""
            <div style="background:var(--card-bg);border:1px solid var(--border);
                border-radius:8px;padding:14px;margin-top:8px">
                <div style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;
                    letter-spacing:0.06em;font-weight:600;margin-bottom:8px">Commission Estimate</div>
                <div style="display:flex;justify-content:space-between;font-size:0.82rem;
                    color:var(--text-muted);padding:4px 0">
                    <span>Entry</span>
                    <span style="font-family:'SF Mono',monospace;color:var(--text-primary)">₹{comm_entry:,.0f}</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.82rem;
                    color:var(--text-muted);padding:4px 0">
                    <span>Exit (est.)</span>
                    <span style="font-family:'SF Mono',monospace;color:var(--text-primary)">₹{comm_exit:,.0f}</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.85rem;
                    font-weight:700;color:var(--text-primary);padding:6px 0;
                    border-top:1px solid var(--border);margin-top:4px">
                    <span>Total Cost</span>
                    <span style="font-family:'SF Mono',monospace">₹{comm_entry+comm_exit:,.0f}</span>
                </div>
            </div>""", unsafe_allow_html=True)

        # Save button
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Save to History", type="primary", use_container_width=True, key="ps_save"):
            if qty and entry and sl:
                _save_history({
                    "ticker":    ticker or "—",
                    "entry":     entry,
                    "sl":        sl,
                    "tp":        tp,
                    "qty":       qty,
                    "pos_size":  pos_size,
                    "rr":        rr,
                    "one_r":     adjusted_1r,
                    "regime":    market,
                    "multiplier":multiplier,
                })
                st.success("Saved!")
            else:
                st.warning("Fill in Entry and Stop Loss first.")


def render_entry_finder(side="Long"):
    st.markdown(f"#### {side} Entry Finder")
    st.caption("Given your stop and target, find the minimum entry level that satisfies your R:R requirement.")

    one_r = _safe(get_setting("account_balance", "10000000")) * _safe(get_setting("risk_pct", "0.004"))

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(
            '<div style="background:var(--card-bg);border:1px solid var(--border);'
            'border-radius:10px;padding:20px">', unsafe_allow_html=True)
        st.markdown("**Parameters**")
        rr_req   = st.number_input("Required R:R", value=2.0, min_value=0.1, step=0.5,
                                    format="%.1f", key=f"{side}_rr")
        sl_level = st.number_input("Stop Loss Level ₹", min_value=0.0, step=0.05,
                                    format="%.2f", key=f"{side}_sl")
        tgt_level= st.number_input("Target Level ₹", min_value=0.0, step=0.05,
                                    format="%.2f", key=f"{side}_tp")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        min_entry = None
        min_shares = None

        if sl_level and tgt_level and rr_req:
            if side == "Long" and tgt_level > sl_level:
                # min_entry = (Target + RR × SL) / (1 + RR)
                # ensures (Target - Entry) / (Entry - SL) >= RR
                min_entry = (tgt_level + rr_req * sl_level) / (1 + rr_req)
                if sl_level < min_entry < tgt_level:
                    risk_per_share = min_entry - sl_level
                    reward_per_share = tgt_level - min_entry
                    actual_rr = reward_per_share / risk_per_share
                    min_shares = int(one_r / risk_per_share) if risk_per_share else 0
                else:
                    min_entry = None
            elif side == "Short" and sl_level > tgt_level:
                # max_entry = (Target + RR × SL) / (1 + RR)
                # ensures (Entry - Target) / (SL - Entry) >= RR
                max_entry = (tgt_level + rr_req * sl_level) / (1 + rr_req)
                min_entry = max_entry  # reuse variable for display
                if tgt_level < min_entry < sl_level:
                    risk_per_share = sl_level - min_entry
                    reward_per_share = min_entry - tgt_level
                    actual_rr = reward_per_share / risk_per_share
                    min_shares = int(one_r / risk_per_share) if risk_per_share else 0
                else:
                    min_entry = None

        label = "Min Long Entry" if side == "Long" else "Max Short Entry"
        st.markdown(result_card(label, f"₹{min_entry:,.2f}" if min_entry else "—", "blue"), unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        c2a, c2b = st.columns(2)
        c2a.markdown(result_card("Min Shares", f"{min_shares:,}" if min_shares else "—", "primary"), unsafe_allow_html=True)
        if min_entry:
            c2b.markdown(result_card("Actual R:R", f"{actual_rr:.2f}R", "green" if actual_rr >= rr_req else "red"), unsafe_allow_html=True)
        else:
            c2b.markdown(result_card("Actual R:R", "—", "neutral"), unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        c2c, c2d = st.columns(2)
        c2c.markdown(result_card("1R Value", f"₹{one_r:,.0f}", "amber"), unsafe_allow_html=True)
        if min_entry and min_shares:
            pos = min_entry * min_shares
            c2d.markdown(result_card("Position Size", f"₹{pos:,.0f}", "primary"), unsafe_allow_html=True)
        else:
            c2d.markdown(result_card("Position Size", "—", "neutral"), unsafe_allow_html=True)

        if not min_entry and sl_level and tgt_level:
            st.warning("Check inputs — Target must be above SL for Long, below for Short.")


def render_history():
    hist = _load_history()
    if not hist:
        st.caption("No calculations saved yet.")
        return

    st.markdown("#### Last 10 Calculations")
    rows = []
    for h in hist:
        rows.append({
            "Ticker":    h.get("ticker","—"),
            "Entry ₹":  f"₹{h['entry']:,.2f}" if h.get("entry") else "—",
            "SL ₹":     f"₹{h['sl']:,.2f}"    if h.get("sl")    else "—",
            "Target ₹": f"₹{h['tp']:,.2f}"    if h.get("tp")    else "—",
            "Qty":       f"{int(h.get('qty',0)):,}",
            "Pos Size":  f"₹{h.get('pos_size',0):,.0f}",
            "R:R":       f"{h.get('rr',0):.2f}R",
            "1R ₹":      f"₹{h.get('one_r',0):,.0f}",
            "Regime":    h.get("regime","—"),
        })

    import pandas as pd
    df = pd.DataFrame(rows)

    def style_hist(row):
        idx = df.columns.tolist()
        styles = [""] * len(row)
        rr_str = row.get("R:R","0R").replace("R","")
        try:
            rr = float(rr_str)
            if "R:R" in idx:
                styles[idx.index("R:R")] = "color:#00C48C;font-weight:600" if rr >= 2 else "color:#FFB84A;font-weight:600" if rr >= 1 else "color:#FF5C5C"
        except: pass
        return styles

    st.dataframe(
        df.style.apply(style_hist, axis=1)
        .set_properties(**{"font-size":"13px"})
        .set_table_styles([
            {"selector":"thead th","props":[
                ("background-color","#1A1F2E"),("color","#6B7489"),
                ("font-size","11px"),("text-transform","uppercase"),
                ("font-weight","600"),("border-bottom","2px solid #252B3B"),
                ("padding","8px 12px"),
            ]},
            {"selector":"td","props":[("padding","8px 12px"),("border-bottom","1px solid #252B3B")]},
        ]),
        use_container_width=True, hide_index=True
    )

    if st.button("🗑 Clear History", type="secondary"):
        st.session_state["calc_history"] = []
        set_setting("calc_history", "[]")
        st.rerun()


def render():
    st.markdown("## Position Sizing Calculator")
    st.markdown(
        '<p style="color:#6B7489;margin-top:-12px;margin-bottom:20px;font-size:0.9rem">'
        'FY 2026-27 · NSE Equity</p>',
        unsafe_allow_html=True
    )

    tab1, tab2, tab3 = st.tabs(["📐 Position Sizing", "📈 Long Entry Finder", "📉 Short Entry Finder"])

    with tab1:
        render_position_sizing()

    with tab2:
        render_entry_finder("Long")

    with tab3:
        render_entry_finder("Short")

    st.markdown("---")
    render_history()
