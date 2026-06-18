import yfinance as yf
import pandas as pd
from datetime import datetime
import threading
import time

_cache = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 300  # 5 minutes


def _nse_symbol(ticker: str) -> str:
    """Convert NSE ticker to yfinance format (append .NS)."""
    ticker = ticker.strip().upper()
    # Already has exchange suffix
    if "." in ticker:
        return ticker
    return f"{ticker}.NS"


def fetch_price(ticker: str) -> dict:
    """Fetch live price for a single NSE ticker. Returns dict with price and change_pct."""
    symbol = _nse_symbol(ticker)
    now = time.time()

    with _cache_lock:
        if symbol in _cache:
            cached_at, data = _cache[symbol]
            if now - cached_at < _CACHE_TTL:
                return data

    try:
        t = yf.Ticker(symbol)
        info = t.fast_info
        price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)

        if price is None:
            hist = t.history(period="2d", interval="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price

        change_pct = None
        if price and prev_close and prev_close != 0:
            change_pct = round(((price - prev_close) / prev_close) * 100, 2)

        result = {
            "ticker": ticker,
            "price": round(float(price), 2) if price else None,
            "change_pct": change_pct,
            "fetched_at": datetime.now().strftime("%H:%M:%S"),
            "error": None,
        }
    except Exception as e:
        result = {
            "ticker": ticker,
            "price": None,
            "change_pct": None,
            "fetched_at": datetime.now().strftime("%H:%M:%S"),
            "error": str(e),
        }

    with _cache_lock:
        _cache[symbol] = (time.time(), result)

    return result


def fetch_prices_bulk(tickers: list) -> dict:
    """Fetch prices for multiple tickers. Returns {ticker: {price, change_pct}}."""
    if not tickers:
        return {}

    symbols = [_nse_symbol(t) for t in tickers]
    now = time.time()
    results = {}
    to_fetch = []

    for ticker, symbol in zip(tickers, symbols):
        with _cache_lock:
            if symbol in _cache:
                cached_at, data = _cache[symbol]
                if now - cached_at < _CACHE_TTL:
                    results[ticker] = data
                    continue
        to_fetch.append((ticker, symbol))

    if to_fetch:
        try:
            syms_str = " ".join(s for _, s in to_fetch)
            data = yf.download(syms_str, period="2d", interval="1d", progress=False, auto_adjust=True)

            for ticker, symbol in to_fetch:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        close = data["Close"][symbol].dropna()
                    else:
                        close = data["Close"].dropna()

                    if len(close) >= 1:
                        price = round(float(close.iloc[-1]), 2)
                        prev = round(float(close.iloc[-2]), 2) if len(close) >= 2 else price
                        change_pct = round(((price - prev) / prev) * 100, 2) if prev else None
                    else:
                        price, change_pct = None, None

                    r = {
                        "ticker": ticker,
                        "price": price,
                        "change_pct": change_pct,
                        "fetched_at": datetime.now().strftime("%H:%M:%S"),
                        "error": None,
                    }
                except Exception as e:
                    r = {"ticker": ticker, "price": None, "change_pct": None,
                         "fetched_at": datetime.now().strftime("%H:%M:%S"), "error": str(e)}

                results[ticker] = r
                with _cache_lock:
                    _cache[symbol] = (time.time(), r)

        except Exception as e:
            for ticker, _ in to_fetch:
                results[ticker] = {"ticker": ticker, "price": None, "change_pct": None,
                                   "fetched_at": None, "error": str(e)}

    return results


def clear_cache():
    with _cache_lock:
        _cache.clear()
