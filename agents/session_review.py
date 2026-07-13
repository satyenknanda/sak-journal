"""
Agent 3 — Session Review
Runs at 4:15 PM IST via GitHub Actions.
Reviews all trades closed today vs morning plan, grades session, saves to daily_notes.
"""
import os, sys, json, requests
from datetime import date, datetime
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

def run_session_review(review_date=None):
    from data.db import _sb, _use_supabase
    if not _use_supabase():
        print("❌ Supabase not configured"); return

    sb = _sb()
    today = str(review_date or date.today())
    print(f"📋 Session Review for {today}")

    # Fetch today's closed trades
    trades = sb.table("trades").select("*").eq("exit_date", today).execute().data
    print(f"   Trades today: {len(trades)}")

    # Fetch morning brief / SA for today
    notes = sb.table("daily_notes").select("*").eq("date", today).execute().data
    morning_plan = ""
    for n in notes:
        if n.get("note_type") in ("morning_brief", "sa", "daily"):
            morning_plan += f"\n{n.get('content','')[:500]}"

    if not trades:
        print("   No trades today — skipping review")
        return

    # Build trade summary
    trade_summary = ""
    total_pnl = 0
    for t in trades:
        pnl = float(t.get("pnl") or 0)
        total_pnl += pnl
        r = float(t.get("r_multiple") or 0)
        tags = t.get("tags") or []
        trade_summary += f"\n- {t.get('ticker')} ({t.get('strategy')}): {r:+.2f}R ₹{pnl:+,.0f} | Tags: {tags} | Note: {t.get('auto_tag_notes','')}"

    api_key = get_api_key()
    if not api_key:
        print("❌ No API key"); return

    prompt = f"""You are a trading coach reviewing an NSE equity trader's session.
    
DATE: {today}

MORNING PLAN:
{morning_plan or "No morning plan recorded"}

TRADES TAKEN:
{trade_summary}

TOTAL P&L: ₹{total_pnl:+,.0f}
TRADES: {len(trades)} | WINNERS: {sum(1 for t in trades if float(t.get('r_multiple') or 0) > 0)} | LOSERS: {sum(1 for t in trades if float(t.get('r_multiple') or 0) < 0)}

Write a concise session review covering:
1. **Session Grade** (A/B/C/D/F) with one line reason
2. **What went well** (2-3 bullet points max)
3. **What to improve** (2-3 bullet points max)  
4. **Key lesson** for tomorrow (1 sentence)

Keep it under 200 words. Be direct, specific, and honest. Reference actual trade tickers and R-multiples.
Format as clean markdown."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01"},
            json={"model":"claude-sonnet-4-6","max_tokens":500,"messages":[{"role":"user","content":prompt}]},
            timeout=30
        )
        review_text = resp.json()["content"][0]["text"].strip()
        print(f"\n{review_text}\n")

        # Save to daily_notes
        sb.table("daily_notes").upsert({
            "date": today,
            "note_type": "session_review",
            "content": review_text,
            "created_at": datetime.now().isoformat()
        }, on_conflict="date,note_type").execute()
        print(f"✅ Session review saved for {today}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    review_date = sys.argv[1] if len(sys.argv) > 1 else None
    run_session_review(review_date)
