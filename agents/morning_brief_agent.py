"""
Agent 1 — Morning Brief Auto-Generator
Runs at 8:30 AM IST via GitHub Actions.
Fetches market data, generates brief via Claude, saves to Supabase.
"""
import os, sys, json
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def generate_sa(data, api_key):
    """Generate Situational Awareness (SA/TACO) from market data."""
    import requests, json

    nifty_change = data.get("niftyChange", "0")
    vix = data.get("vix", "?")
    sp500_change = data.get("sp500", "?")
    sector_bank = data.get("sector_bank", "→ Neutral")
    sector_it = data.get("sector_it", "→ Neutral")
    fii = data.get("fiiCash", "?")
    day_type = data.get("dayType", "SELECTIVE")
    leading = data.get("leadingSector", "")
    lagging = data.get("laggingSector", "")
    risk_note = data.get("riskNote", "")
    top_focus = data.get("topFocus", "")

    prompt = f"""You are an expert NSE momentum trader writing a Situational Awareness (SA) note.
Based on this market data, generate a concise SA in exactly this format:

MARKET DATA:
- Nifty change: {nifty_change}%
- VIX: {vix}
- SP500: {sp500_change}
- FII Cash: {fii}
- Leading sector: {leading}
- Lagging sector: {lagging}
- Day Type: {day_type}
- Bank sector: {sector_bank}
- IT sector: {sector_it}
- Risk note: {risk_note}
- Top focus: {top_focus}

Generate SA in this EXACT format (keep each section concise, 1-2 sentences):

1) LONG-TERM: [Choose one: Early Bull Market / Bull Market / Bull Market Under Doubt / Wait and Watch / Bear Market] — [one line reason]

2) SHORT-TERM: [Choose one: Positive bias / Cautiously positive / Reactive / Choppy / Neutral / Cautiously bearish / Bearish] — [one line reason based on Nifty + FII + VIX]

3) KEY EVENTS & CATALYSTS: [List 2-3 key events/catalysts active today]

4) STRATEGY FOR TODAY: 
   Stance: [Choose one: Aggressive / Positive bias / Trade-by-trade / Reactive / Selective / Wait and watch / Sit out]
   Priority: [Choose one: EP Day 1 + Momentum Burst / VCP Breakouts / SVRO / Reversal setups / All bread-and-butter setups / No specific priority]
   Note: [One sentence on approach for today]

Keep it tight. No fluff. NSE momentum trader perspective."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01"},
            json={"model":"claude-sonnet-4-6","max_tokens":400,"messages":[{"role":"user","content":prompt}]},
            timeout=30
        )
        return resp.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"SA generation error: {e}")
        return ""

def run():
    from data.db import _sb, _use_supabase
    if not _use_supabase():
        print("❌ Supabase not configured"); return

    today = str(date.today())
    print(f"📰 Generating Morning Brief for {today}")

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages"))
    from morning_brief import fetch_data, save_brief

    sb = _sb()
    existing = sb.table("morning_brief").select("brief_date").eq("brief_date", today).execute().data
    if existing:
        print(f"✅ Brief already exists for {today} — skipping")
        return

    print("  Fetching market data + generating via Claude...")
    data, error = fetch_data()

    if error:
        print(f"❌ Error: {error}"); return
    if not data:
        print("❌ No data returned"); return

    # Generate SA
    api_key = os.environ.get("ANTHROPIC_API_KEY","")
    if api_key:
        print("  Generating SA/TACO...")
        sa_text = generate_sa(data, api_key)
        if sa_text:
            data["sa"] = sa_text
            print(f"  SA generated: {sa_text[:100]}...")

    save_brief(today, data)
    print(f"✅ Morning brief + SA saved for {today}")
    print(f"   Day Type: {data.get('dayType','?')}")
    print(f"   Leading: {data.get('leadingSector','?')}")

if __name__ == "__main__":
    run()
