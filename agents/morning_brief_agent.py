"""
Agent 1 — Morning Brief Auto-Generator
Runs at 8:30 AM IST via GitHub Actions.
Fetches market data, generates brief via Claude, saves to Supabase.
"""
import os, sys, json
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run():
    from data.db import _sb, _use_supabase
    if not _use_supabase():
        print("❌ Supabase not configured"); return

    today = str(date.today())
    print(f"📰 Generating Morning Brief for {today}")

    # Import fetch functions from morning_brief page
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pages"))
    from morning_brief import fetch_data, save_brief

    # Check if brief already exists
    sb = _sb()
    existing = sb.table("morning_brief").select("brief_date").eq("brief_date", today).execute().data
    if existing:
        print(f"✅ Brief already exists for {today} — skipping")
        return

    # Generate brief
    print("  Fetching market data + generating via Claude...")
    data, error = fetch_data()

    if error:
        print(f"❌ Error: {error}"); return
    if not data:
        print("❌ No data returned"); return

    # Save to morning_brief + daily_notes
    save_brief(today, data)
    print(f"✅ Morning brief saved for {today}")

    # Print summary
    print(f"   Day Type: {data.get('dayType','?')}")
    print(f"   Leading: {data.get('leadingSector','?')}")
    print(f"   Top Focus: {data.get('topFocus','?')[:100]}...")

if __name__ == "__main__":
    run()
