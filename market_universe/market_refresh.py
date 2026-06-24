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
    refresh_bonde_signals()


def bonde_signals_from_hist(ticker, hist, sector="", industry=""):
    """Calculate Pradeep Bonde scanner signals from price history."""
    import numpy as np
    if hist is None or len(hist) < 10:
        return None

    closes = hist["Close"].values
    volumes = hist["Volume"].values
    highs = hist["High"].values
    lows = hist["Low"].values

    last_close = float(closes[-1])
    last_vol = int(volumes[-1])
    prev_close = float(closes[-2])
    prev_vol = int(volumes[-2])

    # Volume ratio vs 50-day avg
    avg_vol_50 = int(np.mean(volumes[-50:])) if len(volumes) >= 50 else int(np.mean(volumes))
    vol_ratio = round(last_vol / avg_vol_50, 2) if avg_vol_50 > 0 else 0

    # Returns
    ret_1d = round((last_close - prev_close) / prev_close * 100, 2) if prev_close else 0
    ret_5d = round((last_close - closes[-6]) / closes[-6] * 100, 2) if len(closes) >= 6 else 0
    ret_2m = round((last_close - closes[-42]) / closes[-42] * 100, 2) if len(closes) >= 42 else 0

    # 52W high/low
    high_52w = round(float(np.max(highs[-252:])), 2) if len(highs) >= 252 else round(float(np.max(highs)), 2)
    low_52w  = round(float(np.min(lows[-252:])),  2) if len(lows)  >= 252 else round(float(np.min(lows)), 2)
    pct_from_52w_high = round((last_close - high_52w) / high_52w * 100, 2) if high_52w else 0

    # Momentum Burst — +4% day with volume > previous day
    momentum_burst = bool(ret_1d >= 4.0 and last_vol > prev_vol)

    # TTT — Tight Tight Tight (3 bar range <= 1.5%, today <= 0.3%)
    if len(closes) >= 3:
        range_3d = (max(closes[-3:]) - min(closes[-3:])) / closes[-4] * 100 if len(closes) >= 4 else 0
        range_1d = (float(highs[-1]) - float(lows[-1])) / prev_close * 100 if prev_close else 0
        ttt = bool(range_3d <= 1.5 and range_1d <= 0.8)
        range_3d_pct = round(range_3d, 2)
    else:
        ttt = False
        range_3d_pct = 0

    # 20% in 5 days
    ret_20pct_5d = bool(ret_5d >= 20.0)

    # 50% in 2 months
    ret_50pct_2m = bool(ret_2m >= 50.0)

    # TI65 — Trend Intensity: % of last 65 days closing above their prior close
    if len(closes) >= 65:
        up_days = sum(1 for i in range(-65, 0) if closes[i] > closes[i-1])
        ti65 = round(up_days / 65 * 100, 1)
    else:
        ti65 = None

    # ATR 20-day
    if len(closes) >= 21:
        trs = [max(highs[i] - lows[i],
                   abs(highs[i] - closes[i-1]),
                   abs(lows[i] - closes[i-1])) for i in range(-20, 0)]
        atr_20d = round(float(np.mean(trs)), 2)
    else:
        atr_20d = None

    return {
        "ticker": ticker,
        "as_of_date": str(date.today()),
        "close": round(last_close, 2),
        "volume": last_vol,
        "avg_volume_50d": avg_vol_50,
        "volume_ratio": vol_ratio,
        "ret_1d": ret_1d,
        "ret_5d": ret_5d,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "pct_from_52w_high": pct_from_52w_high,
        "momentum_burst": momentum_burst,
        "ttt": ttt,
        "ret_20pct_5d": ret_20pct_5d,
        "ret_50pct_2m": ret_50pct_2m,
        "ti65": ti65,
        "atr_20d": atr_20d,
        "range_3d_pct": range_3d_pct,
        "sector": sector,
        "industry": industry,
    }


def refresh_bonde_signals():
    """Calculate and store Bonde signals for all tickers."""
    sb = _sb()
    universe = sb.table("market_universe").select("ticker,sector,industry").execute().data
    print(f"\nCalculating Bonde signals for {len(universe)} tickers...")

    success = 0
    for idx, row in enumerate(universe, 1):
        ticker = row["ticker"]
        sector = row.get("sector", "")
        industry = row.get("industry", "")
        print(f"[{idx}/{len(universe)}] {ticker}...")
        hist = fetch_hist_for_ticker(ticker)
        if hist is None:
            continue
        sig = bonde_signals_from_hist(ticker, hist, sector, industry)
        if sig:
            try:
                sb.table("bonde_signals").upsert(sig, on_conflict="ticker").execute()
                success += 1
            except Exception as e:
                print(f"  ❌ {ticker}: {e}")
        time.sleep(0.2)

    print(f"✅ Bonde signals: {success} tickers updated.")
