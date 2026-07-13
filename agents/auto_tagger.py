"""
Agent 2 — Trade Auto Tagger (v2 with yfinance intraday)
Triggered after exit_trade() — analyzes trade data and tags automatically.
"""
import os, sys, json, requests
import pandas as pd
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.strip().split("=", 1)[1].strip().strip('"\'')
    return key

def get_intraday_data(ticker, trade_date, interval="5m"):
    """Fetch intraday data for the trade date."""
    try:
        import yfinance as yf
        sym = f"{ticker}.NS"
        # Fetch 5 days around trade date to ensure we get the right day
        t = yf.Ticker(sym)
        df = t.history(period="5d", interval=interval, auto_adjust=False)
        if df.empty:
            return None
        # Filter to trade date only
        trade_dt = str(trade_date)[:10]
        df.index = pd.to_datetime(df.index)
        day_df = df[df.index.strftime("%Y-%m-%d") == trade_dt]
        return day_df if not day_df.empty else None
    except Exception as e:
        print(f"  Intraday fetch error: {e}")
        return None

def calculate_objective_tags(trade, intraday_df=None):
    """Calculate data-driven tags from trade fields + intraday data."""
    tags = []
    notes = []

    r_mult   = float(trade.get("r_multiple") or 0)
    mae      = float(trade.get("mae_price") or 0)
    mfe      = float(trade.get("mfe_price") or 0)
    entry_p  = float(trade.get("entry_price") or 0)
    exit_p   = float(trade.get("exit_price") or 0)
    stop     = float(trade.get("stop_loss") or 0)
    side     = str(trade.get("side", "Buy") or "Buy").upper()
    strategy = str(trade.get("strategy", "") or "")
    entry_date = str(trade.get("entry_date", ""))[:10]
    exit_date  = str(trade.get("exit_date", ""))[:10]

    # ── Intraday-based tags ───────────────────────────────────────────────────
    if intraday_df is not None and not intraday_df.empty:

        # Day open price (9:15 AM first candle)
        day_open = float(intraday_df.iloc[0]["Open"])

        # Late Entry — entry >2% above day open for longs
        if entry_p > 0 and day_open > 0:
            entry_vs_open = (entry_p - day_open) / day_open * 100
            if side == "BUY" and entry_vs_open > 2.0:
                tags.append("late_entry")
                notes.append(f"Entry {entry_vs_open:.1f}% above day open ₹{day_open:.2f}")
            elif side == "SELL" and entry_vs_open < -2.0:
                tags.append("late_entry")
                notes.append(f"Entry {abs(entry_vs_open):.1f}% below day open for short")

        # Volume confirmation at entry — find candle nearest entry price
        if entry_p > 0:
            avg_vol = intraday_df["Volume"].mean()
            # Find candles where price was near entry
            entry_candles = intraday_df[
                (intraday_df["Low"] <= entry_p * 1.005) &
                (intraday_df["High"] >= entry_p * 0.995)
            ]
            if not entry_candles.empty:
                entry_vol = float(entry_candles.iloc[0]["Volume"])
                if entry_vol >= avg_vol * 1.5:
                    tags.append("volume_confirmed")
                    notes.append(f"Entry candle volume {entry_vol/avg_vol:.1f}x average")
                elif entry_vol < avg_vol * 0.7:
                    tags.append("low_volume_entry")
                    notes.append(f"Entry candle volume only {entry_vol/avg_vol:.1f}x average")

        # Pre-breakout tightness — check 5 candles before entry (TTT)
        if entry_p > 0 and len(intraday_df) > 5:
            entry_candles = intraday_df[intraday_df["High"] >= entry_p * 0.995]
            if not entry_candles.empty:
                entry_idx = intraday_df.index.get_loc(entry_candles.index[0])
                if entry_idx >= 5:
                    pre_candles = intraday_df.iloc[max(0, entry_idx-5):entry_idx]
                    if not pre_candles.empty:
                        pre_range = (pre_candles["High"].max() - pre_candles["Low"].min()) / entry_p * 100
                        if pre_range < 1.5:
                            tags.append("tight_pre_entry")
                            notes.append(f"Pre-entry range only {pre_range:.1f}% — good VCP/TTT setup")

        # VWAP position at entry
        if "Volume" in intraday_df.columns:
            intraday_df = intraday_df.copy()
            intraday_df["TP"] = (intraday_df["High"] + intraday_df["Low"] + intraday_df["Close"]) / 3
            intraday_df["cumVol"] = intraday_df["Volume"].cumsum()
            intraday_df["cumTPVol"] = (intraday_df["TP"] * intraday_df["Volume"]).cumsum()
            intraday_df["VWAP"] = intraday_df["cumTPVol"] / intraday_df["cumVol"]
            # Find VWAP at entry time
            entry_candles2 = intraday_df[intraday_df["High"] >= entry_p * 0.995]
            if not entry_candles2.empty:
                vwap_at_entry = float(entry_candles2.iloc[0]["VWAP"])
                if side == "BUY":
                    if entry_p > vwap_at_entry:
                        tags.append("above_vwap_entry")
                        notes.append(f"Entry ₹{entry_p:.2f} above VWAP ₹{vwap_at_entry:.2f}")
                    else:
                        tags.append("below_vwap_entry")
                        notes.append(f"Entry ₹{entry_p:.2f} below VWAP ₹{vwap_at_entry:.2f}")

    # ── MAE/MFE based tags ────────────────────────────────────────────────────
    if mfe > 0 and entry_p > 0 and exit_p > 0:
        if side == "BUY":
            actual_gain = exit_p - entry_p
            max_gain    = mfe - entry_p
        else:
            actual_gain = entry_p - exit_p
            max_gain    = entry_p - mfe
        if max_gain > 0 and actual_gain > 0 and actual_gain < max_gain * 0.4:
            tags.append("early_exit")
            notes.append(f"Captured only {actual_gain/max_gain*100:.0f}% of max move")

    if mae > 0 and stop > 0 and entry_p > 0:
        if side == "BUY":
            stop_dist = entry_p - stop
            mae_dist  = entry_p - mae
        else:
            stop_dist = stop - entry_p
            mae_dist  = mae - entry_p
        if stop_dist > 0 and mae_dist > stop_dist * 1.3:
            tags.append("held_drawdown")
            notes.append(f"MAE extended {mae_dist/stop_dist:.1f}x beyond stop distance")

    # ── R-multiple tags ───────────────────────────────────────────────────────
    if r_mult >= 3.0:
        tags.append("big_winner")
        notes.append(f"+{r_mult:.1f}R trade")
    elif r_mult <= -0.9:
        tags.append("stopped_out")
    elif -0.8 <= r_mult <= -0.1:
        tags.append("clean_stop")
    elif -0.1 <= r_mult <= 0.1:
        tags.append("breakeven")

    if r_mult < -0.8 and r_mult > -1.3 and stop > 0:
        notes.append("Stopped out near planned level")

    # ── Strategy tags ─────────────────────────────────────────────────────────
    strategy_map = {
        "VCP": "vcp_setup", "REVERSAL": "reversal_setup",
        "EP": "ep_setup", "SVRO": "svro_setup",
        "NR 1HR": "nr1hr_setup", "1M ORB": "orb_setup"
    }
    if strategy in strategy_map:
        tags.append(strategy_map[strategy])

    return tags, notes

def ai_tag_trade(trade, obj_tags, obj_notes):
    """Use Claude to add qualitative tags based on trade context."""
    api_key = get_api_key()
    if not api_key:
        return [], "", ""

    prompt = f"""You are a trading coach analyzing a closed NSE equity trade.
Analyze this trade and return a JSON object with tags and a brief coaching note.

TRADE DATA:
- Ticker: {trade.get('ticker')}
- Strategy: {trade.get('strategy')}
- Side: {trade.get('side')}
- Entry: ₹{trade.get('entry_price')} on {trade.get('entry_date')}
- Exit: ₹{trade.get('exit_price')} on {trade.get('exit_date')}
- Stop Loss: ₹{trade.get('stop_loss')}
- R-Multiple: {trade.get('r_multiple')}
- MAE Price: ₹{trade.get('mae_price')} (worst price reached)
- MFE Price: ₹{trade.get('mfe_price')} (best price reached)
- Objective tags calculated: {obj_tags}
- System notes: {obj_notes}

Return ONLY valid JSON (no other text):
{{
    "ai_tags": ["tag1", "tag2"],
    "coaching_note": "One sentence coaching insight under 15 words",
    "grade": "A/B/C/D/F"
}}

Available AI tags (pick relevant ones only):
- "followed_plan": entry/exit matched strategy rules
- "deviated_plan": exit too early or late vs strategy rules
- "good_entry": entered at optimal location
- "poor_entry": entry timing was suboptimal
- "patient": held trade according to plan
- "impulsive": entry or exit appeared rushed
- "textbook": near-perfect execution of strategy rules
- "revenge_trade": appears to be emotional re-entry after loss"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01"},
            json={"model":"claude-sonnet-4-6","max_tokens":300,"messages":[{"role":"user","content":prompt}]},
            timeout=30
        )
        text = resp.json()["content"][0]["text"].strip()
        if "```" in text:
            text = text.split("```")[1].replace("json","").strip()
        result = json.loads(text)
        return result.get("ai_tags",[]), result.get("coaching_note",""), result.get("grade","")
    except Exception as e:
        print(f"  AI tag error: {e}")
        return [], "", ""

def tag_trade(trade_id, trade_data):
    """Main entry point — fetch intraday, calculate + AI tag, save to Supabase."""
    from data.db import update_trade

    ticker     = trade_data.get("ticker","")
    entry_date = str(trade_data.get("entry_date",""))[:10]

    # Fetch intraday data
    print(f"  Fetching 5m intraday for {ticker} on {entry_date}...")
    intraday_df = get_intraday_data(ticker, entry_date, interval="5m")
    if intraday_df is not None:
        print(f"  Got {len(intraday_df)} 5m candles")
    else:
        print(f"  No intraday data — using daily data only")

    obj_tags, obj_notes = calculate_objective_tags(trade_data, intraday_df)
    ai_tags, coaching_note, grade = ai_tag_trade(trade_data, obj_tags, obj_notes)

    all_tags = list(set(obj_tags + ai_tags))
    print(f"🏷️  {ticker} — Tags: {all_tags}")
    print(f"   Grade: {grade} | Note: {coaching_note}")

    update_trade(trade_id, {
        "tags": all_tags,
        "session_grade": grade,
        "auto_tag_notes": coaching_note
    })
    return all_tags, grade, coaching_note

if __name__ == "__main__":
    from data.db import _sb
    trade_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if trade_id:
        res = _sb().table("trades").select("*").eq("id", trade_id).execute()
        if res.data:
            tag_trade(trade_id, res.data[0])
