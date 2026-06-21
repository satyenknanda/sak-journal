import streamlit as st
from datetime import date
from data.db import add_trade, exit_trade, get_strategies


def render_add_trade_modal():
    """Renders Add Trade form inside a st.dialog."""
    from data.db import get_mtf_margins
    strategies = get_strategies()

    # Ticker + Funding type must live OUTSIDE st.form — forms don't rerun on widget
    # change, only on submit, so the MTF margin% auto-fill lookup needs the ticker
    # value available before the form renders.
    st.markdown("### ＋ Add New Trade")
    fc0, fc1, fc2 = st.columns([2, 1, 2])
    with fc0:
        ticker = st.text_input("Ticker", placeholder="e.g. RELIANCE", key="add_trade_ticker").upper()
    with fc1:
        funding_type = st.selectbox("Funding", ["Cash", "MTF"], key="add_trade_funding",
                                     help="MTF = Zerodha Margin Trading Facility (leveraged/borrowed funds)")

    mtf_margin_pct = 50.0
    if funding_type == "MTF":
        # Auto-fill from saved lookup table if this ticker has a saved margin %
        lookup_default = 50.0
        if ticker:
            margins = get_mtf_margins()
            match = next((m for m in margins if m["ticker"] == ticker), None)
            if match:
                lookup_default = float(match.get("margin_pct") or 50.0)
        with fc2:
            mtf_margin_pct = st.number_input(
                "Your Margin % (MTF)", min_value=1.0, max_value=100.0, step=1.0, value=lookup_default,
                key=f"add_trade_margin_pct_{ticker}",
                help="Auto-filled from your MTF Margin Lookup (Fund Management page) if this ticker is saved there. "
                     "Still editable — check Kite's order screen at entry time for the exact figure."
            )
            if ticker and any(m["ticker"] == ticker for m in get_mtf_margins()):
                st.caption(f"📋 Auto-filled from saved lookup for {ticker}")

    with st.form("add_trade_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("Ticker", value=ticker, disabled=True, key="add_trade_ticker_display")
        with c2:
            strategy = st.selectbox("Strategy", strategies)
        with c3:
            side = st.selectbox("Side", ["Buy", "Sell"])

        c4, c5, c6 = st.columns(3)
        with c4:
            entry_date = st.date_input("Entry Date", value=date.today())
        with c5:
            qty = st.number_input("Quantity", min_value=1, step=1, value=100)
        with c6:
            entry_price = st.number_input("Entry Price ₹", min_value=0.01, step=0.05, format="%.2f")

        c7, c8, c9 = st.columns(3)
        with c7:
            stop_loss = st.number_input("Stop Loss ₹", min_value=0.01, step=0.05, format="%.2f")
        with c8:
            take_profit = st.number_input("Take Profit ₹", min_value=0.01, step=0.05, format="%.2f")
        with c9:
            tsl = st.number_input("TSL ₹ (optional)", min_value=0.0, step=0.05, format="%.2f", value=0.0)

        c10, c11 = st.columns(2)
        with c10:
            commission = st.number_input("Commission ₹", min_value=0.0, step=1.0, format="%.2f", value=0.0)
        with c11:
            notes = st.text_input("Notes (optional)")

        # Live 1R display
        if entry_price and stop_loss and qty:
            risk_per_share = abs(entry_price - stop_loss)
            one_r = risk_per_share * qty
            position_size = entry_price * qty
            extra = ""
            if funding_type == "MTF":
                own_amt = position_size * mtf_margin_pct / 100
                borrowed_amt = position_size - own_amt
                extra = f"  ⚡ MTF — Your capital ₹{own_amt:,.0f} ({mtf_margin_pct:.0f}%) · Borrowed ₹{borrowed_amt:,.0f}"
            st.info(f"📊  1R = ₹{one_r:,.0f}  |  Risk/share = ₹{risk_per_share:.2f}  |  Position size = ₹{position_size:,.0f}{extra}")

        submitted = st.form_submit_button("Add Trade", type="primary", use_container_width=True)
        if submitted:
            if not ticker:
                st.error("Ticker is required.")
            elif not entry_price or not stop_loss:
                st.error("Entry price and stop loss are required.")
            else:
                add_trade({
                    "status": "OPEN",
                    "entry_date": str(entry_date),
                    "side": side,
                    "qty": qty,
                    "ticker": ticker,
                    "strategy": strategy,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "commission_entry": commission,
                    "tsl": tsl if tsl > 0 else None,
                    "notes": notes,
                    "funding_type": funding_type.upper(),
                    "mtf_margin_pct": mtf_margin_pct if funding_type == "MTF" else None,
                })
                st.success(f"✅ Trade added: {ticker}")
                st.rerun()


def render_exit_trade_modal(trade: dict):
    """Renders Exit Trade form inside a st.dialog."""
    with st.form(f"exit_trade_form_{trade['id']}", clear_on_submit=True):
        st.markdown(f"### Exit Trade — **{trade['ticker']}** ({trade['strategy']})")
        funding_badge = " ⚡ MTF" if str(trade.get("funding_type","CASH")).upper() == "MTF" else ""
        st.caption(f"Entry: ₹{trade['entry_price']} × {trade['qty']} shares  |  SL: ₹{trade['stop_loss']}{funding_badge}")

        c1, c2 = st.columns(2)
        with c1:
            exit_date = st.date_input("Exit Date", value=date.today())
        with c2:
            exit_price = st.number_input("Exit Price ₹", min_value=0.01, step=0.05,
                                          value=float(trade.get("live_price") or trade["entry_price"]),
                                          format="%.2f")

        c3, c4 = st.columns(2)
        with c3:
            exit_qty = st.number_input("Exit Qty", min_value=1, step=1,
                                        value=int(trade.get("qty") or 1))
        with c4:
            commission_exit = st.number_input("Commission ₹", min_value=0.0, step=1.0,
                                               format="%.2f", value=0.0)

        risk_status = st.selectbox("Exit Reason", [
            "Manually Closed", "Target Hit", "SL Hit", "TSL Hit", "Breakeven"
        ])

        # P&L preview
        if exit_price and trade.get("entry_price") and exit_qty:
            ep = float(trade["entry_price"])
            comm_entry = float(trade.get("commission_entry") or 0)
            if trade.get("side") == "Sell":
                pnl_preview = (ep - exit_price) * exit_qty - comm_entry - commission_exit
            else:
                pnl_preview = (exit_price - ep) * exit_qty - comm_entry - commission_exit
            r_per_share = abs(ep - float(trade.get("stop_loss") or ep))
            r_mult = ((exit_price - ep) / r_per_share) if r_per_share else 0
            color = "🟢" if pnl_preview >= 0 else "🔴"
            st.info(f"{color}  P&L preview: ₹{pnl_preview:,.0f}  |  R-Multiple: {r_mult:.2f}R")

        submitted = st.form_submit_button("Confirm Exit", type="primary", use_container_width=True)
        if submitted:
            exit_trade(
                trade_id=trade["id"],
                exit_date=str(exit_date),
                exit_price=exit_price,
                exit_qty=exit_qty,
                commission_exit=commission_exit,
                risk_status=risk_status,
            )
            st.success(f"✅ {trade['ticker']} closed.")
            st.rerun()


def render_edit_trade_modal(trade: dict):
    """Renders Edit Trade form inside a st.dialog — pre-filled with existing values."""
    from data.db import update_trade, get_strategies
    strategies = get_strategies()
    from data.db import get_mtf_margins

    st.markdown(f"### ✏️ Edit Trade — **{trade.get('ticker','')}**")
    st.caption(f"Trade #{trade.get('trade_no','')}  ·  ID {trade.get('id','')}")

    cur_funding = str(trade.get("funding_type","CASH")).upper()
    funding_idx = 1 if cur_funding == "MTF" else 0
    fc1, fc2 = st.columns([1, 3])
    with fc1:
        funding_type = st.selectbox("Funding", ["Cash", "MTF"], index=funding_idx,
                                     key=f"edit_trade_funding_{trade['id']}",
                                     help="MTF = Zerodha Margin Trading Facility (leveraged/borrowed funds)")

    # Default priority: lookup table FIRST (it's your authoritative, deliberately-saved
    # value), then the trade's own stored margin% as fallback, then 50% generic default.
    # Previously this checked the trade's stored value first, which meant a stale/default
    # value already on the row (e.g. from briefly toggling MTF earlier) would silently
    # shadow your real saved lookup entry — this was the actual bug.
    trade_ticker = (trade.get("ticker") or "").upper().strip()
    margins = get_mtf_margins()
    match = next((m for m in margins if m["ticker"] == trade_ticker), None)
    existing_margin = trade.get("mtf_margin_pct")

    if match:
        mtf_margin_pct = float(match.get("margin_pct") or 50.0)
        lookup_note = f"📋 Auto-filled from saved lookup for {trade_ticker}"
    elif existing_margin:
        mtf_margin_pct = float(existing_margin)
        lookup_note = None
    else:
        mtf_margin_pct = 50.0
        lookup_note = None

    if funding_type == "MTF":
        with fc2:
            mtf_margin_pct = st.number_input(
                "Your Margin % (MTF)", min_value=1.0, max_value=100.0, step=1.0, value=mtf_margin_pct,
                key=f"edit_trade_margin_pct_{trade['id']}",
                help="Auto-filled from your MTF Margin Lookup (Fund Management page) if this ticker is saved there "
                     "and no margin% has been set on this trade yet. Still editable."
            )
            if lookup_note:
                st.caption(lookup_note)

    with st.form(f"edit_trade_form_{trade['id']}", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            ticker = st.text_input("Ticker", value=trade.get("ticker","")).upper()
        with c2:
            strat_list = strategies
            cur_strat = trade.get("strategy","")
            strat_idx = strat_list.index(cur_strat) if cur_strat in strat_list else 0
            strategy = st.selectbox("Strategy", strat_list, index=strat_idx)
        with c3:
            side = st.selectbox("Side", ["Buy","Sell"],
                index=0 if trade.get("side","Buy")=="Buy" else 1)

        c4, c5, c6 = st.columns(3)
        with c4:
            entry_date = st.date_input("Entry Date",
                value=date.fromisoformat(str(trade.get("entry_date") or date.today())))
        with c5:
            qty = st.number_input("Quantity", min_value=1, step=1,
                value=int(trade.get("qty") or 100))
        with c6:
            entry_price = st.number_input("Entry Price ₹", min_value=0.01, step=0.05,
                value=float(trade.get("entry_price") or 0.01), format="%.2f")

        c7, c8, c9 = st.columns(3)
        with c7:
            stop_loss = st.number_input("Stop Loss ₹", min_value=0.01, step=0.05,
                value=float(trade.get("stop_loss") or 0.01), format="%.2f")
        with c8:
            take_profit = st.number_input("Take Profit ₹", min_value=0.01, step=0.05,
                value=float(trade.get("take_profit") or 0.01), format="%.2f")
        with c9:
            tsl = st.number_input("TSL ₹", min_value=0.0, step=0.05,
                value=float(trade.get("tsl") or 0.0), format="%.2f")

        c10, c11 = st.columns(2)
        with c10:
            commission = st.number_input("Commission ₹", min_value=0.0, step=1.0,
                value=float(trade.get("commission_entry") or 0.0), format="%.2f")
        with c11:
            notes = st.text_input("Notes", value=trade.get("notes","") or "")

        # Live 1R
        if entry_price and stop_loss and qty:
            one_r = abs(entry_price - stop_loss) * qty
            st.info(f"📊  1R = ₹{one_r:,.0f}  |  Risk/share = ₹{abs(entry_price-stop_loss):.2f}")

        submitted = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
        if submitted:
            if not ticker:
                st.error("Ticker is required.")
            else:
                update_trade(trade["id"], {
                    "ticker":           ticker,
                    "strategy":         strategy,
                    "side":             side,
                    "entry_date":       str(entry_date),
                    "qty":              qty,
                    "entry_price":      entry_price,
                    "stop_loss":        stop_loss,
                    "take_profit":      take_profit,
                    "tsl":              tsl if tsl > 0 else None,
                    "commission_entry": commission,
                    "notes":            notes,
                    "funding_type":     funding_type.upper(),
                    "mtf_margin_pct":   mtf_margin_pct if funding_type == "MTF" else None,
                })
                st.success(f"✅ {ticker} updated!")
                st.rerun()
