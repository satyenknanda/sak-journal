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


# ── Cash Balance ──────────────────────────────────────────────────────────
# Shared by Dashboard, Fund Management, and Daily Plan so the number is
# always identical across the app. When a broker ledger has been imported
# (Fund Management → Upload Broker Ledger), available_cash uses that real
# figure directly. Otherwise it falls back to the estimated roll-forward
# (starting capital + deposits - withdrawals + realized P&L - MTF interest,
# minus capital currently deployed in open positions).
def get_cash_balance():
    """
    Returns dict:
        total_capital      -- current trading equity (ledger cash + deployed
                               capital, when ledger imported; else estimated)
        deployed_capital    -- your own money currently tied up in OPEN positions
                               (full value for CASH trades, margin-only for MTF trades)
        available_cash      -- free cash to deploy (real ledger balance if
                               imported, else the estimated roll-forward)
        source               -- "ledger" or "estimate"
        as_of                -- ledger as-of date string, or None
    """
    from datetime import datetime, date, timedelta
    from data.db import get_trades, get_capital_flows, get_ledger_balance

    def sf(v):
        try: return float(v or 0)
        except Exception: return 0.0

    trades = get_trades()
    open_trades = [t for t in trades if t.get("status") == "OPEN"]
    closed = [t for t in trades if t.get("status") == "CLOSED"]

    deployed_capital = 0.0
    for t in open_trades:
        qty = sf(t.get("qty")); price = sf(t.get("entry_price")) or sf(t.get("live_price"))
        value = qty * price
        if str(t.get("funding_type", "CASH") or "CASH").upper() == "MTF":
            margin_pct = sf(t.get("mtf_margin_pct")) or 50.0
            deployed_capital += value * margin_pct / 100
        else:
            deployed_capital += value

    ledger_balance, ledger_date = get_ledger_balance()
    if ledger_balance is not None:
        # ── Pending settlement: trades exited AFTER the ledger's as-of date
        # haven't hit the broker's actual cash balance yet (T+1 settlement in
        # India), so the ledger figure doesn't include them. Estimate what
        # each such trade returns to cash: capital originally locked
        # (full value for CASH, margin-only for MTF) plus its realized P&L.
        pending_settlement = 0.0
        try:
            ledger_dt = datetime.strptime(str(ledger_date)[:10], "%Y-%m-%d").date()
        except Exception:
            ledger_dt = None
        if ledger_dt is not None:
            for t in closed:
                exit_d = str(t.get("exit_date", ""))[:10]
                try:
                    exit_dt = datetime.strptime(exit_d, "%Y-%m-%d").date()
                except Exception:
                    continue
                if exit_dt <= ledger_dt:
                    continue  # already reflected in the ledger snapshot
                qty = sf(t.get("qty")); entry_price = sf(t.get("entry_price"))
                pnl = sf(t.get("pnl"))
                if str(t.get("funding_type", "CASH") or "CASH").upper() == "MTF":
                    margin_pct = sf(t.get("mtf_margin_pct")) or 50.0
                    locked_capital = qty * entry_price * margin_pct / 100
                else:
                    locked_capital = qty * entry_price
                pending_settlement += locked_capital + pnl

        available_cash = ledger_balance
        total_capital = ledger_balance + deployed_capital
        return {
            "total_capital": total_capital,
            "deployed_capital": deployed_capital,
            "available_cash": available_cash,
            "source": "ledger",
            "as_of": ledger_date,
            "pending_settlement": pending_settlement,
            "available_cash_projected": available_cash + pending_settlement,
        }

    today = date.today()
    year = today.year
    year_start, year_end = date(year, 1, 1), date(year, 12, 31)

    ZERODHA_MTF_DAILY_RATE = 0.0004  # 0.04%/day, matches Fund Management

    def mtf_interest_this_year(t):
        if str(t.get("funding_type", "CASH") or "CASH").upper() != "MTF":
            return 0.0
        qty = sf(t.get("qty")); price = sf(t.get("entry_price"))
        margin_pct = sf(t.get("mtf_margin_pct")) or 50.0
        position_value = qty * price
        borrowed = position_value * (1 - margin_pct / 100)
        if borrowed <= 0:
            return 0.0
        try:
            entry_dt = datetime.strptime(str(t.get("entry_date", ""))[:10], "%Y-%m-%d").date()
        except Exception:
            return 0.0
        if t.get("status") == "CLOSED" and t.get("exit_date"):
            try:
                exit_dt = datetime.strptime(str(t.get("exit_date", ""))[:10], "%Y-%m-%d").date()
            except Exception:
                exit_dt = today
        else:
            exit_dt = today
        start = max(entry_dt + timedelta(days=1), year_start)
        end = min(exit_dt, year_end)
        if start > end:
            return 0.0
        days = (end - start).days + 1
        return borrowed * ZERODHA_MTF_DAILY_RATE * days

    total_mtf_interest = sum(mtf_interest_this_year(t) for t in trades)

    realized_pnl_this_year = 0.0
    for t in closed:
        d = str(t.get("exit_date", ""))[:10]
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            continue
        if dt.year == year:
            realized_pnl_this_year += sf(t.get("pnl"))

    flows = get_capital_flows(year)
    saved_base = sf(flows.get(0, {}).get("base_capital", 0.0))
    if saved_base > 0:
        starting_capital = saved_base
    else:
        # same auto-calc fallback used in Fund Management / Dashboard
        cash_deployed_all = 0.0
        for t in open_trades:
            qty = sf(t.get("qty")); ep = sf(t.get("entry_price"))
            pos = qty * ep
            if str(t.get("funding_type", "") or "").upper() == "MTF":
                margin = sf(t.get("mtf_margin_pct") or 50) / 100
                cash_deployed_all += pos * margin
            else:
                cash_deployed_all += pos
        starting_capital = max(cash_deployed_all - sum(sf(t.get("pnl")) for t in closed), 0.0)

    total_added = sum(sf(flows.get(m, {}).get("added", 0.0)) for m in range(1, 13))
    total_withdrawn = sum(sf(flows.get(m, {}).get("withdrawn", 0.0)) for m in range(1, 13))

    total_capital = (starting_capital + total_added - total_withdrawn
                      + realized_pnl_this_year - total_mtf_interest)

    available_cash = total_capital - deployed_capital

    return {
        "total_capital": total_capital,
        "deployed_capital": deployed_capital,
        "available_cash": available_cash,
        "source": "estimate",
        "as_of": None,
        "pending_settlement": 0.0,
        "available_cash_projected": available_cash,
    }
