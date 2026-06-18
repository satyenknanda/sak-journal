#!/usr/bin/env python3
"""
SAK Journal — MAE/MFE Calculator
Calculates Maximum Adverse Excursion and Maximum Favorable Excursion
for all closed trades using yfinance price data.
Run: python3 calc_mae_mfe.py
"""
import sqlite3, os, time
from datetime import datetime, timedelta

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance..."); os.system("pip3 install yfinance --break-system-packages --quiet")
    import yfinance as yf

DB = os.path.expanduser("~/Desktop/sak_journal/journal.db")

def get_trades():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    trades = conn.execute("""
        SELECT id, ticker, side, entry_price, exit_price, qty, entry_date, exit_date
        FROM trades WHERE status='CLOSED' AND exit_price IS NOT NULL
        ORDER BY exit_date DESC
    """).fetchall()
    conn.close()
    return [dict(t) for t in trades]

def save_mae_mfe(trade_id, mae_price, mfe_price):
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE trades SET mae_price=?, mfe_price=? WHERE id=?",
                 (mae_price, mfe_price, trade_id))
    conn.commit(); conn.close()

def tv_to_yf(ticker):
    """Convert NSE/BSE ticker to yfinance format."""
    # Strip exchange prefix if present
    for prefix in ["BSE:", "NSE:", "NSE_EQ:"]:
        if ticker.startswith(prefix):
            ticker = ticker[len(prefix):]
    # Common indices
    index_map = {"NIFTY50": "^NSEI", "BANKNIFTY": "^NSEBANK",
                 "SENSEX": "^BSESN", "FINNIFTY": "NIFTY_FIN_SERVICE.NS"}
    if ticker in index_map:
        return index_map[ticker]
    # Try NSE first
    return f"{ticker}.NS"

def get_price_data(ticker, entry_date, exit_date):
    """Fetch intraday or daily OHLC for the trade period."""
    yf_ticker = tv_to_yf(ticker)
    try:
        d_entry = datetime.strptime(str(entry_date)[:10], "%Y-%m-%d")
        d_exit  = datetime.strptime(str(exit_date)[:10], "%Y-%m-%d")
        # Add buffer days
        start = (d_entry - timedelta(days=1)).strftime("%Y-%m-%d")
        end   = (d_exit  + timedelta(days=2)).strftime("%Y-%m-%d")

        days_held = (d_exit - d_entry).days

        # Use daily data for multi-day trades, hourly for intraday
        if days_held == 0:
            interval = "1h"
        elif days_held <= 5:
            interval = "1d"
        else:
            interval = "1d"

        df = yf.download(yf_ticker, start=start, end=end,
                        interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            # Try BSE
            yf_ticker_bse = ticker.replace(".NS", ".BO") if ".NS" in yf_ticker else f"{ticker}.BO"
            df = yf.download(yf_ticker_bse, start=start, end=end,
                           interval=interval, progress=False, auto_adjust=True)
        return df
    except Exception as e:
        print(f"  ⚠️  Price fetch error for {ticker}: {e}")
        return None

def calc_mae_mfe(trade, df):
    """
    MAE = worst price excursion against the trade (from entry price)
    MFE = best price excursion in favor of the trade (from entry price)
    Returns (mae_pnl, mfe_pnl) in ₹ P&L terms
    """
    if df is None or df.empty:
        return None, None

    entry_p = float(trade.get("entry_price") or 0)
    exit_p  = float(trade.get("exit_price") or 0)
    qty     = int(trade.get("qty") or 0)
    side    = str(trade.get("side") or "").upper()

    if not entry_p or not qty:
        return None, None

    # Filter to trade period
    try:
        d_entry = str(trade.get("entry_date",""))[:10]
        d_exit  = str(trade.get("exit_date",""))[:10]
        mask = (df.index.strftime("%Y-%m-%d") >= d_entry) & \
               (df.index.strftime("%Y-%m-%d") <= d_exit)
        period = df[mask]
        if period.empty:
            period = df  # fallback to all data
    except:
        period = df

    try:
        lows  = period["Low"].values.flatten()
        highs = period["High"].values.flatten()

        min_low  = float(min(lows))
        max_high = float(max(highs))

        if side in ("LONG", "BUY"):
            # MAE price = lowest low (worst case against long)
            # MFE price = highest high (best case for long)
            mae_val = round(min_low, 2)
            mfe_val = round(max_high, 2)
        else:
            # MAE price = highest high (worst case against short)
            # MFE price = lowest low (best case for short)
            mae_val = round(max_high, 2)
            mfe_val = round(min_low, 2)

        return mae_val, mfe_val
    except Exception as e:
        return None, None

def run(force=False, limit=None):
    """
    force=False: only calculate trades missing MAE/MFE
    force=True: recalculate all trades
    limit: max number of trades to process
    """
    trades = get_trades()
    if not force:
        conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
        missing = conn.execute("""
            SELECT id FROM trades WHERE status='CLOSED'
            AND (mae_price IS NULL OR mae_price=0)
            AND exit_price IS NOT NULL
        """).fetchall()
        conn.close()
        missing_ids = {r["id"] for r in missing}
        trades = [t for t in trades if t["id"] in missing_ids]

    if not trades:
        print("✅ All trades already have MAE/MFE data.")
        return

    if limit:
        trades = trades[:limit]

    print(f"📊 Calculating MAE/MFE for {len(trades)} trades...\n")
    success=0; failed=0; cache={}

    for i, trade in enumerate(trades):
        ticker = trade.get("ticker","")
        entry_d = str(trade.get("entry_date",""))[:10]
        exit_d  = str(trade.get("exit_date",""))[:10]

        print(f"[{i+1}/{len(trades)}] #{trade['id']} {ticker} {entry_d} → {exit_d}", end=" ")

        # Cache by ticker+period
        cache_key = f"{ticker}_{entry_d}_{exit_d}"
        if cache_key in cache:
            df = cache[cache_key]
        else:
            df = get_price_data(ticker, entry_d, exit_d)
            cache[cache_key] = df
            time.sleep(0.3)  # rate limit

        mae, mfe = calc_mae_mfe(trade, df)

        if mae is not None and mfe is not None:
            save_mae_mfe(trade["id"], mae, mfe)
            ep = float(trade.get("entry_price") or 0)
            qty = int(trade.get("qty") or 0)
            print(f"✅  MAE: ₹{mae:,.0f}  MFE: ₹{mfe:,.0f}")
            success += 1
        else:
            print(f"⚠️  No data")
            failed += 1

    print(f"\n{'='*50}")
    print(f"✅ Success: {success}  |  ⚠️ Failed: {failed}  |  Total: {len(trades)}")

if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
    if force:
        print("🔄 Force mode — recalculating all trades")
    run(force=force, limit=limit)
