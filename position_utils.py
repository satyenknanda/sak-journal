# position_utils.py — Shared helper to combine same-ticker OPEN positions
# for KPI/summary purposes across the app (Daily Plan, Dashboard, Terminal,
# Strategy Dashboard, etc.) WITHOUT altering individual trade rows in detail tables.

def _calc_trade_pnl(t):
    """Running (unrealized) P&L for a single OPEN trade using live_price vs entry_price."""
    live = t.get("live_price")
    ep = t.get("entry_price")
    if not (live and ep):
        return 0.0
    qty = float(t.get("qty") or 0)
    side = str(t.get("side", "")).upper()
    lp, epf = float(live), float(ep)
    if side in ("BUY", "LONG"):
        return (lp - epf) * qty
    return (epf - lp) * qty


def combine_open_positions(open_trades):
    """
    Group a list of OPEN trade dicts by ticker, returning one aggregated
    record per unique ticker:
        {
            ticker: {
                "qty": summed quantity,
                "pnl": summed running P&L,
                "avg_entry": weighted-average entry price,
                "strategies": set of strategy names involved,
                "live_price": most recent non-null live price seen,
                "at_risk": True if ANY underlying trade is flagged SL Breached / Open Risk,
                "in_profit": True if combined pnl > 0 or ANY underlying trade flagged In Profits,
                "trade_ids": list of underlying trade ids (for drill-down/debugging),
                "n_trades": number of individual trade rows combined,
            }, ...
        }
    """
    combined = {}
    for t in open_trades:
        tk = t.get("ticker", "")
        if not tk:
            continue
        if tk not in combined:
            combined[tk] = {
                "qty": 0.0, "pnl": 0.0, "cost": 0.0,
                "strategies": set(), "live_price": None,
                "at_risk": False, "in_profit": False,
                "trade_ids": [], "n_trades": 0,
            }
        agg = combined[tk]
        qty = float(t.get("qty") or 0)
        ep = float(t.get("entry_price") or 0)
        pnl = _calc_trade_pnl(t)
        rs = (t.get("risk_status") or "")

        agg["qty"] += qty
        agg["cost"] += ep * qty
        agg["pnl"] += pnl
        if t.get("strategy"):
            agg["strategies"].add(t.get("strategy"))
        if t.get("live_price"):
            agg["live_price"] = t.get("live_price")
        if "SL Breached" in rs or "Open Risk" in rs:
            agg["at_risk"] = True
        if "Profit" in rs:
            agg["in_profit"] = True
        if t.get("id") is not None:
            agg["trade_ids"].append(t.get("id"))
        agg["n_trades"] += 1

    # Finalize derived fields
    for tk, agg in combined.items():
        agg["avg_entry"] = agg["cost"] / agg["qty"] if agg["qty"] else 0.0
        if agg["pnl"] > 0:
            agg["in_profit"] = True
        del agg["cost"]

    return combined


def open_positions_summary(open_trades):
    """
    One-shot summary used by KPI cockpit strips across the app.
    Returns: (n_positions, unrealized_pnl, at_risk_count, in_profit_count, combined_dict)
    """
    combined = combine_open_positions(open_trades)
    n_positions = len(combined)
    unrealized_pnl = sum(a["pnl"] for a in combined.values())
    at_risk = sum(1 for a in combined.values() if a["at_risk"])
    in_profit = sum(1 for a in combined.values() if a["in_profit"] and not a["at_risk"])
    return n_positions, unrealized_pnl, at_risk, in_profit, combined
