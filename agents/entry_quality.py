"""
Entry Quality Checker — runs on open trades
Fetches 5m intraday data for entry date and scores entry quality.
"""
import os, sys, json, requests
import pandas as pd
from datetime import datetime, date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_intraday_data(ticker, trade_date, interval="5m"):
    try:
        import yfinance as yf
        t = yf.Ticker(f"{ticker}.NS")
        df = t.history(period="60d", interval=interval, auto_adjust=False)
        if df.empty: return None
        df.index = pd.to_datetime(df.index)
        day_df = df[df.index.strftime("%Y-%m-%d") == str(trade_date)[:10]]
        return day_df if not day_df.empty else None
    except Exception as e:
        print(f"  Intraday error: {e}"); return None

def check_entry_quality(trade, intraday_df):
    """Score entry quality from intraday data."""
    results = {
        "ticker": trade.get("ticker"),
        "entry_date": str(trade.get("entry_date",""))[:10],
        "entry_price": float(trade.get("entry_price") or 0),
        "strategy": trade.get("strategy",""),
        "checks": {},
        "score": 0,
        "max_score": 0,
        "tags": [],
        "summary": ""
    }

    entry_p = results["entry_price"]
    side = str(trade.get("side","Buy") or "Buy").upper()

    if intraday_df is None or intraday_df.empty:
        results["summary"] = "No intraday data available (entry >60 days ago)"
        return results

    # ── Check 1: Day Open comparison ─────────────────────────────────────────
    day_open = float(intraday_df.iloc[0]["Open"])
    entry_vs_open = (entry_p - day_open) / day_open * 100
    results["max_score"] += 20
    if side == "BUY":
        if entry_vs_open <= 1.0:
            results["checks"]["vs_day_open"] = {"status": "✅", "label": "Early Entry", "detail": f"Entry only {entry_vs_open:+.1f}% from open ₹{day_open:.2f}", "score": 20}
            results["score"] += 20
            results["tags"].append("early_entry")
        elif entry_vs_open <= 2.5:
            results["checks"]["vs_day_open"] = {"status": "⚠️", "label": "Acceptable Entry", "detail": f"Entry {entry_vs_open:+.1f}% above open ₹{day_open:.2f}", "score": 10}
            results["score"] += 10
        else:
            results["checks"]["vs_day_open"] = {"status": "❌", "label": "Late Entry", "detail": f"Entry {entry_vs_open:+.1f}% above open — chasing", "score": 0}
            results["tags"].append("late_entry")

    # ── Check 2: VWAP ────────────────────────────────────────────────────────
    intraday_df = intraday_df.copy()
    intraday_df["TP"] = (intraday_df["High"] + intraday_df["Low"] + intraday_df["Close"]) / 3
    intraday_df["VWAP"] = (intraday_df["TP"] * intraday_df["Volume"]).cumsum() / intraday_df["Volume"].cumsum()
    entry_candles = intraday_df[
        (intraday_df["Low"] <= entry_p * 1.005) &
        (intraday_df["High"] >= entry_p * 0.995)
    ]
    results["max_score"] += 20
    if not entry_candles.empty:
        vwap = float(entry_candles.iloc[0]["VWAP"])
        if side == "BUY" and entry_p >= vwap:
            results["checks"]["vwap"] = {"status": "✅", "label": "Above VWAP", "detail": f"Entry ₹{entry_p:.2f} above VWAP ₹{vwap:.2f}", "score": 20}
            results["score"] += 20
            results["tags"].append("above_vwap")
        elif side == "BUY":
            results["checks"]["vwap"] = {"status": "❌", "label": "Below VWAP", "detail": f"Entry ₹{entry_p:.2f} below VWAP ₹{vwap:.2f}", "score": 0}
            results["tags"].append("below_vwap")
    else:
        results["checks"]["vwap"] = {"status": "—", "label": "VWAP N/A", "detail": "Entry candle not found in 5m data", "score": 0}

    # ── Check 3: Volume confirmation ─────────────────────────────────────────
    avg_vol = intraday_df["Volume"].mean()
    results["max_score"] += 20
    if not entry_candles.empty:
        entry_vol = float(entry_candles.iloc[0]["Volume"])
        vol_ratio = entry_vol / avg_vol if avg_vol > 0 else 0
        if vol_ratio >= 1.5:
            results["checks"]["volume"] = {"status": "✅", "label": "Volume Confirmed", "detail": f"Entry candle {vol_ratio:.1f}x avg volume", "score": 20}
            results["score"] += 20
            results["tags"].append("volume_confirmed")
        elif vol_ratio >= 1.0:
            results["checks"]["volume"] = {"status": "⚠️", "label": "Average Volume", "detail": f"Entry candle {vol_ratio:.1f}x avg volume", "score": 10}
            results["score"] += 10
        else:
            results["checks"]["volume"] = {"status": "❌", "label": "Low Volume", "detail": f"Entry candle only {vol_ratio:.1f}x avg volume", "score": 0}
            results["tags"].append("low_volume_entry")
    else:
        results["checks"]["volume"] = {"status": "—", "label": "Volume N/A", "detail": "Entry candle not found", "score": 0}

    # ── Check 4: Pre-entry tightness (TTT) ───────────────────────────────────
    results["max_score"] += 20
    if not entry_candles.empty:
        entry_idx = intraday_df.index.get_loc(entry_candles.index[0])
        if entry_idx >= 3:
            pre = intraday_df.iloc[max(0, entry_idx-5):entry_idx]
            pre_range = (pre["High"].max() - pre["Low"].min()) / entry_p * 100
            if pre_range < 1.0:
                results["checks"]["tightness"] = {"status": "✅", "label": "Tight Pre-Entry", "detail": f"5-candle range {pre_range:.1f}% — excellent TTT", "score": 20}
                results["score"] += 20
                results["tags"].append("tight_pre_entry")
            elif pre_range < 2.0:
                results["checks"]["tightness"] = {"status": "⚠️", "label": "Moderate Tightness", "detail": f"5-candle range {pre_range:.1f}%", "score": 10}
                results["score"] += 10
            else:
                results["checks"]["tightness"] = {"status": "❌", "label": "Wide Pre-Entry", "detail": f"5-candle range {pre_range:.1f}% — choppy before entry", "score": 0}
        else:
            results["checks"]["tightness"] = {"status": "—", "label": "Tightness N/A", "detail": "Not enough pre-entry candles", "score": 0}
    else:
        results["checks"]["tightness"] = {"status": "—", "label": "Tightness N/A", "detail": "Entry candle not found", "score": 0}

    # ── Check 5: Close near high (momentum) ──────────────────────────────────
    results["max_score"] += 20
    if not entry_candles.empty:
        c = float(entry_candles.iloc[0]["Close"])
        h = float(entry_candles.iloc[0]["High"])
        l = float(entry_candles.iloc[0]["Low"])
        close_pct = (c - l) / (h - l) * 100 if h != l else 50
        if close_pct >= 70:
            results["checks"]["close_strength"] = {"status": "✅", "label": "Strong Close", "detail": f"Entry candle closed at {close_pct:.0f}% of range", "score": 20}
            results["score"] += 20
            results["tags"].append("strong_close")
        elif close_pct >= 40:
            results["checks"]["close_strength"] = {"status": "⚠️", "label": "Mid Close", "detail": f"Entry candle closed at {close_pct:.0f}% of range", "score": 10}
            results["score"] += 10
        else:
            results["checks"]["close_strength"] = {"status": "❌", "label": "Weak Close", "detail": f"Entry candle closed at {close_pct:.0f}% of range — bearish", "score": 0}
    else:
        results["checks"]["close_strength"] = {"status": "—", "label": "Close N/A", "detail": "Entry candle not found", "score": 0}

    # ── Overall grade ─────────────────────────────────────────────────────────
    pct = results["score"] / results["max_score"] * 100 if results["max_score"] > 0 else 0
    if pct >= 80: results["grade"] = "A"
    elif pct >= 60: results["grade"] = "B"
    elif pct >= 40: results["grade"] = "C"
    elif pct >= 20: results["grade"] = "D"
    else: results["grade"] = "F"
    results["score_pct"] = pct
    results["summary"] = f"Entry score {results['score']}/{results['max_score']} ({pct:.0f}%) — Grade {results['grade']}"

    return results

def run_all_open_trades():
    """Check entry quality for all open trades."""
    from data.db import _sb
    trades = _sb().table("trades").select("*").eq("status","OPEN").execute().data
    print(f"Checking {len(trades)} open trades...\n")

    all_results = []
    import time
    for t in trades:
        ticker = t.get("ticker","")
        entry_date = str(t.get("entry_date",""))[:10]
        print(f"  {ticker} (entry {entry_date})...", end=" ", flush=True)
        df = get_intraday_data(ticker, entry_date)
        result = check_entry_quality(t, df)
        result["trade_id"] = t["id"]
        all_results.append(result)
        print(f"{result.get('grade','?')} — {result['summary']}")
        time.sleep(0.5)

    return all_results

if __name__ == "__main__":
    results = run_all_open_trades()
    print("\n\n=== ENTRY QUALITY SUMMARY ===")
    for r in sorted(results, key=lambda x: -(x.get("score_pct",0))):
        print(f"  {r.get('grade','—')} | {r.get('ticker','?'):12} | {r.get('summary','')}")
