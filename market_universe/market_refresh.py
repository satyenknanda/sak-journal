"""
market_refresh.py — Standalone script to refresh market_returns table.

Run this on your Mac (NOT inside Streamlit — it's too slow for a page load),
periodically (daily/weekly), e.g.:

    cd ~/Desktop/sak-journal
    python3 market_refresh.py

Requires: pip install yfinance supabase --break-system-packages
Requires environment variables SUPABASE_URL and SUPABASE_KEY to be set,
matching whatever your app's data/db.py already uses to connect.

This was NOT tested live — this sandbox's network egress blocks Yahoo
Finance hosts (query1/query2.finance.yahoo.com), so verify on your machine
before relying on it. If yfinance's API shape has changed, adjust the
.history() parsing below accordingly.
"""

import sys
import time
from datetime import datetime, date

import yfinance as yf
import pandas as pd

sys.path.insert(0, ".")
from data.db import _sb  # reuse the existing Supabase client your app already has

from market_universe.universe_seed import UNIVERSE  # the (ticker, sector, industry) list


def ensure_universe_seeded():
    """Upsert the static universe list into market_universe table (run once, or whenever you extend it)."""
    sb = _sb()
    rows = [{"ticker": t, "sector": s, "industry": i} for (t, s, i) in UNIVERSE]
    for r in rows:
        sb.table("market_universe").upsert(r, on_conflict="ticker").execute()
    print(f"✅ Seeded {len(rows)} tickers into market_universe")


def pct_change(hist, days_back):
    """% change from `days_back` trading days ago to latest close."""
    if len(hist) <= days_back:
        return None
    latest = hist["Close"].iloc[-1]
    past = hist["Close"].iloc[-1 - days_back]
    if past == 0 or pd.isna(past) or pd.isna(latest):
        return None
    return round((latest - past) / past * 100, 2)


def ytd_change(hist):
    """% change from first trading day of current calendar year to latest close."""
    this_year = hist[hist.index.year == datetime.now().year]
    if this_year.empty:
        return None
    first = this_year["Close"].iloc[0]
    latest = hist["Close"].iloc[-1]
    if first == 0 or pd.isna(first) or pd.isna(latest):
        return None
    return round((latest - first) / first * 100, 2)


def fetch_hist_for_ticker(ticker):
    """Pulls 1y daily history once. Returns the DataFrame or None on failure."""
    try:
        t = yf.Ticker(f"{ticker}.NS")
        hist = t.history(period="1y", interval="1d")
        if hist.empty or len(hist) < 2:
            print(f"  ⚠️ {ticker}: no data")
            return None
        return hist
    except Exception as e:
        print(f"  ❌ {ticker}: {e}")
        return None


def returns_row_from_hist(ticker, hist):
    return {
        "ticker": ticker,
        "as_of_date": str(date.today()),
        "ret_1d": pct_change(hist, 1),
        "ret_1w": pct_change(hist, 5),
        "ret_1m": pct_change(hist, 21),
        "ret_3m": pct_change(hist, 63),
        "ret_6m": pct_change(hist, 126),
        "ret_12m": pct_change(hist, 252) if len(hist) >= 253 else pct_change(hist, len(hist) - 1),
        "ret_ytd": ytd_change(hist),
    }


def price_rows_from_hist(ticker, hist):
    """One row per trading day: {ticker, trade_date, close}."""
    rows = []
    for idx, row in hist.iterrows():
        close = row.get("Close")
        if pd.isna(close):
            continue
        rows.append({"ticker": ticker, "trade_date": idx.strftime("%Y-%m-%d"), "close": round(float(close), 2)})
    return rows


def refresh_all():
    sb = _sb()
    tickers = [t for (t, s, i) in UNIVERSE]
    print(f"Refreshing returns + price history for {len(tickers)} tickers...")

    success, failed = 0, []
    for idx, ticker in enumerate(tickers, 1):
        print(f"[{idx}/{len(tickers)}] {ticker}...")
        hist = fetch_hist_for_ticker(ticker)
        if hist is None:
            failed.append(ticker)
            time.sleep(0.3)
            continue

        ok = True
        try:
            ret_row = returns_row_from_hist(ticker, hist)
            sb.table("market_returns").upsert(ret_row, on_conflict="ticker").execute()
        except Exception as e:
            print(f"  ❌ returns upsert failed for {ticker}: {e}")
            ok = False

        try:
            price_rows = price_rows_from_hist(ticker, hist)
            # batch upsert in chunks of 200 to stay well under request size limits
            for i in range(0, len(price_rows), 200):
                chunk = price_rows[i:i+200]
                sb.table("price_history").upsert(chunk, on_conflict="ticker,trade_date").execute()
        except Exception as e:
            print(f"  ❌ price_history upsert failed for {ticker}: {e}")
            ok = False

        if ok:
            success += 1
        else:
            failed.append(ticker)
        time.sleep(0.3)  # be polite to Yahoo's rate limits

    print(f"\n✅ Done. {success} succeeded, {len(failed)} failed.")
    if failed:
        print("Failed tickers:", ", ".join(failed))


if __name__ == "__main__":
    ensure_universe_seeded()
    refresh_all()
