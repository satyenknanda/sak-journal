"""
Agent 2 — Trade Auto Tagger
Triggered after exit_trade() — analyzes trade data and tags automatically.
"""
import os, sys, json, requests
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

def calculate_objective_tags(trade):
    """Calculate data-driven tags from trade fields."""
    tags = []
    notes = []

    r_mult = float(trade.get("r_multiple") or 0)
    mae = float(trade.get("mae_price") or 0)
    mfe = float(trade.get("mfe_price") or 0)
    entry_p = float(trade.get("entry_price") or 0)
    exit_p = float(trade.get("exit_price") or 0)
    stop = float(trade.get("stop_loss") or 0)
    side = str(trade.get("side", "Buy") or "Buy").upper()
    strategy = str(trade.get("strategy", "") or "")

    # Early Exit — MFE was much better than actual exit
    if mfe > 0 and entry_p > 0 and exit_p > 0:
        if side == "BUY":
            actual_gain = exit_p - entry_p
            max_gain = mfe - entry_p
        else:
            actual_gain = entry_p - exit_p
            max_gain = entry_p - mfe
        if max_gain > 0 and actual_gain > 0 and actual_gain < max_gain * 0.4:
            tags.append("early_exit")
            notes.append(f"Captured only {actual_gain/max_gain*100:.0f}% of max move")

    # Held Through Drawdown — MAE was deep
    if mae > 0 and stop > 0 and entry_p > 0:
        if side == "BUY":
            stop_dist = entry_p - stop
            mae_dist = entry_p - mae
        else:
            stop_dist = stop - entry_p
            mae_dist = mae - entry_p
        if stop_dist > 0 and mae_dist > stop_dist * 1.3:
            tags.append("held_drawdown")
            notes.append(f"MAE extended {mae_dist/stop_dist:.1f}x beyond stop distance")

    # Good Risk Management — stopped out cleanly near stop
    if r_mult < -0.8 and r_mult > -1.3 and stop > 0:
        tags.append("clean_stop")
        notes.append("Stopped out near planned level")

    # Big Winner
    if r_mult >= 3.0:
        tags.append("big_winner")
        notes.append(f"+{r_mult:.1f}R trade")

    # Stopped Out
    if r_mult <= -0.9:
        tags.append("stopped_out")

    # Breakeven
    if -0.1 <= r_mult <= 0.1:
        tags.append("breakeven")

    # Strategy-specific
    if strategy == "VCP":
        tags.append("vcp_setup")
    elif strategy == "REVERSAL":
        tags.append("reversal_setup")
    elif strategy == "EP":
        tags.append("ep_setup")

    return tags, notes

def ai_tag_trade(trade, obj_tags, obj_notes):
    """Use Claude to add qualitative tags based on trade context."""
    api_key = get_api_key()
    if not api_key:
        return [], "No API key"

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
- Already tagged: {obj_tags}
- System notes: {obj_notes}

Return ONLY a JSON object like this (no other text):
{{
    "ai_tags": ["tag1", "tag2"],
    "coaching_note": "One sentence coaching insight",
    "grade": "A/B/C/D/F"
}}

Available AI tags (pick relevant ones only):
- "followed_plan": entry/exit matched strategy rules
- "deviated_plan": exit too early or late vs strategy rules  
- "good_entry": entered at optimal location
- "poor_entry": entry timing was suboptimal
- "patient": held trade according to plan
- "impulsive": entry or exit appeared rushed
- "size_appropriate": position size matched risk rules
- "oversize": position appears too large for setup

Keep coaching_note under 15 words. Be direct and specific."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01"},
            json={"model":"claude-sonnet-4-6","max_tokens":300,"messages":[{"role":"user","content":prompt}]},
            timeout=30
        )
        data = resp.json()
        text = data["content"][0]["text"].strip()
        # Clean JSON
        if "```" in text:
            text = text.split("```")[1].replace("json","").strip()
        result = json.loads(text)
        return result.get("ai_tags",[]), result.get("coaching_note",""), result.get("grade","")
    except Exception as e:
        print(f"AI tag error: {e}")
        return [], "", ""

def tag_trade(trade_id, trade_data):
    """Main entry point — calculate + AI tag a trade, save to Supabase."""
    from data.db import _sb, _use_supabase, update_trade

    obj_tags, obj_notes = calculate_objective_tags(trade_data)
    ai_tags, coaching_note, grade = ai_tag_trade(trade_data, obj_tags, obj_notes)

    all_tags = list(set(obj_tags + ai_tags))

    print(f"🏷️  {trade_data.get('ticker')} — Tags: {all_tags}")
    print(f"   Grade: {grade} | Note: {coaching_note}")

    update_trade(trade_id, {
        "tags": all_tags,
        "session_grade": grade,
        "auto_tag_notes": coaching_note
    })

    return all_tags, grade, coaching_note

if __name__ == "__main__":
    # Test on a specific trade
    from data.db import _sb
    trade_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if trade_id:
        res = _sb().table("trades").select("*").eq("id", trade_id).execute()
        if res.data:
            tag_trade(trade_id, res.data[0])
