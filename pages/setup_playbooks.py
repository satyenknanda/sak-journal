"""
Run once from the sak_journal root:
    cd ~/Desktop/sak_journal
    python3 setup_playbooks.py

Creates Sneaky Attack playbook and updates VCP, Oops Reversal, REVERSAL
with full entry/exit rules + notes.
"""

import sqlite3, json
from pathlib import Path

DB_PATH = Path(__file__).parent / "journal.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_playbook_by_name(conn, name):
    row = conn.execute("SELECT * FROM playbooks WHERE LOWER(name)=LOWER(?)", (name,)).fetchone()
    return dict(row) if row else None

def upsert_playbook(conn, name, emoji, color, description):
    existing = get_playbook_by_name(conn, name)
    if existing:
        conn.execute(
            "UPDATE playbooks SET emoji=?, color=?, description=? WHERE id=?",
            (emoji, color, description, existing["id"])
        )
        conn.commit()
        print(f"  Updated playbook: {name} (id={existing['id']})")
        return existing["id"]
    else:
        cur = conn.execute(
            "INSERT INTO playbooks (name, emoji, color, description) VALUES (?,?,?,?)",
            (name, emoji, color, description)
        )
        conn.commit()
        print(f"  Created playbook: {name} (id={cur.lastrowid})")
        return cur.lastrowid

def set_rules(conn, pb_id, entry_rules, exit_rules):
    conn.execute("DELETE FROM playbook_rules WHERE playbook_id=?", (pb_id,))
    for r in entry_rules:
        conn.execute(
            "INSERT INTO playbook_rules (playbook_id, rule_type, rule_text, show_when) VALUES (?,?,?,?)",
            (pb_id, "entry", r, "always")
        )
    for r in exit_rules:
        conn.execute(
            "INSERT INTO playbook_rules (playbook_id, rule_type, rule_text, show_when) VALUES (?,?,?,?)",
            (pb_id, "exit", r, "always")
        )
    conn.commit()
    print(f"  Set {len(entry_rules)} entry + {len(exit_rules)} exit rules for pb_id={pb_id}")


# ══════════════════════════════════════════════════════════════════════════════
# PLAYBOOK DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

PLAYBOOKS = [

    # ── VCP ──────────────────────────────────────────────────────────────────
    {
        "name": "VCP",
        "emoji": "🎯",
        "color": "#3B82F6",
        "description": (
            "VCP — Volatility Contraction Pattern\n\n"
            "FAST AND FORTUNATE | Chapter Four: Entry Methods — VCP (1H)\n\n"
            "DAILY = qualify the stock (Stage 2 + LF event + tight base) | "
            "1H = where the VCP forms and entry fires | "
            "Contraction must be <2.5% on 1H | Volume must dry then spike\n\n"
            "QUALIFY ON DAILY:\n"
            "• Stage 2 uptrend confirmed\n"
            "• LF Event: 5-10x vol burst in 1-2 days (purple dot)\n"
            "• Base: tight, blue days\n"
            "• MA20 / MA50 stacked\n"
            "• Sector in leadership\n\n"
            "ONCE DAILY QUALIFIES:\n"
            "• Put on watchlist\n"
            "• Next session: open 1H chart\n"
            "• Wait for VCP to form there\n"
            "• DO NOT enter from daily alone. The 1H VCP is the trigger.\n\n"
            "VCP — 1H CHART — ENTRY RULES:\n"
            "STRUCTURE:\n"
            "• Drop 1: wider swing down (8-12% range on 1H)\n"
            "• Recovery: stock bounces — note the SWING HIGH\n"
            "• Contraction: tighter drop, MAX 2.5% range, Volume MUST dry up here\n\n"
            "ENTRY:\n"
            "• Place bid just ABOVE the recovery high (swing high) (+0.1-0.2% buffer)\n"
            "• Do NOT chase the move — pre-place the bid and wait\n"
            "• When bid fires = entry live\n\n"
            "VOLUME RULES:\n"
            "• During contraction: DRY (confirms absorption)\n"
            "• On entry bar: SPIKE (confirms urgency)\n"
            "• No spike on entry = caution\n\n"
            "MAX CONTRACTION: 2.5% — wider than 2.5% on 1H = skip, find another setup\n\n"
            "STOP: Below the contraction low OR 2% from entry price, whichever is tighter\n\n"
            "AFTER ENTRY: Trail with 50-paise method (50p stop for every Rs1 gain)\n"
            "Target: move to breakeven ASAP as stock rises\n\n"
            "DAILY = Setup selection only | 1H chart = where entry happens\n"
            "This contraction is INVISIBLE on the daily chart. You need the 1H to see it."
        ),
        "entry_rules": [
            "Stock in Stage 2 uptrend on daily — MA20/MA50 stacked, price above both",
            "Liquidity Force (LF) event confirmed — 5-10x volume burst in 1-2 days on daily",
            "Base is tight on daily — blue/quiet days, no wide-range bars",
            "1H chart shows VCP structure: wide drop → recovery high → tight contraction <2.5%",
            "Volume dries up during 1H contraction — confirms absorption",
            "Pre-place bid just above 1H recovery/swing high (+0.1-0.2% buffer)",
            "Entry fires when bid is hit — do NOT chase, do NOT enter from daily alone",
            "Volume spikes on 1H entry bar — confirms institutional urgency",
        ],
        "exit_rules": [
            "Stop below 1H contraction low OR 2% from entry — whichever is tighter",
            "Trail with 50-paise method: move stop up 50p for every Rs1 gain",
            "Move to breakeven as fast as possible after entry",
            "Exit if stock struggles for more than 2-3 bars after entry with no follow-through",
            "No spike on entry bar = reduce size or exit early — caution signal",
        ],
    },

    # ── OOPS REVERSAL ────────────────────────────────────────────────────────
    {
        "name": "Oops Reversal",
        "emoji": "😮",
        "color": "#F59E0B",
        "description": (
            "The Oops Reversal — Entry Setup, Rules, and Risk/Reward\n\n"
            "FAST AND FORTUNATE | Chapter Four: Entry Methods\n\n"
            "Gap-down below prior day's low → immediate reversal → reclaim triggers entry | "
            "Stop below gap-open low | Target: 20-Day MA\n\n"
            "SETUP CONTEXT:\n"
            "• Stock in confirmed Stage 2 uptrend\n"
            "• 3-5 prior down days OR sharp gap-down\n"
            "• Institutional stock (FNO / high ADV)\n"
            "• Breadth oversold (<200 above 20MA)\n\n"
            "SIGNAL:\n"
            "• Opens below prior day's low (gap-down)\n"
            "• Then reclaims it within first few minutes\n"
            "• Strongest form: Open = Low of day\n\n"
            "ENTRY: Buy-stop just above prior day low\n"
            "STOP: Below gap-open low (1-2.5%)\n"
            "TARGET: 20-Day Moving Average\n\n"
            "❌ Do NOT enter after 5%+ recovery\n"
            "❌ Do NOT hold as swing trade — exit at MA\n\n"
            "OOPS DAY VOLUME: Must show institutional volume spike — blue bar on Oops day\n"
            "Prior Uptrend → Stock in Stage 2 → Sharp Decline → OOPS DAY → Recovery → 20MA"
        ),
        "entry_rules": [
            "Stock in confirmed Stage 2 uptrend — prior uptrend of ~100% or more",
            "3-5 prior down days OR sharp gap-down into the setup",
            "Institutional stock — FNO-eligible or high ADV; breadth oversold (<200 above 20MA)",
            "Today opens BELOW prior day's low (gap-down) — this is the Oops day",
            "Stock reclaims prior day's low within first few minutes — immediate reversal",
            "Strongest form: Open of day = Low of day (no wick below open)",
            "Buy-stop placed just above prior day low — entry triggers on reclaim",
            "Do NOT enter after 5%+ recovery from gap-open low — setup has passed",
        ],
        "exit_rules": [
            "Stop below gap-open low (1-2.5% risk) — if price returns here, setup failed",
            "Target: 20-Day Moving Average — do NOT hold as swing trade beyond MA",
            "Exit same day or within 1-2 days — this is NOT a swing trade",
            "Exit if stock fails to break prior day's high within first hour",
            "Do NOT add to position — Oops Reversal is a single-entry, single-exit setup",
        ],
    },

    # ── REVERSAL ─────────────────────────────────────────────────────────────
    {
        "name": "REVERSAL",
        "emoji": "🔄",
        "color": "#10B981",
        "description": (
            "The Reversal (Mean Reversion) Trade — Setup, Timing, and Entry Rules\n\n"
            "FAST AND FORTUNATE | Chapter Four: Entry Methods — Reversal\n\n"
            "Daily: strong uptrend → smooth decline → 90-degree angle change | "
            "15-min: extended red bars → first green sign = entry | Target: 20-Day MA\n\n"
            "SETUP (Daily):\n"
            "• Stock in strong prior uptrend (~100% gain, linear, institutional)\n"
            "• Purple dots visible in the rally\n"
            "• Stock is NOT broken — just extended\n\n"
            "THE SIGNAL:\n"
            "• Smooth decline phase (some days)\n"
            "• Then ANGLE CHANGE — 90-degree shift to accelerated, sharp fall\n"
            "• 3-5 days of fast red candles in a row\n"
            "• Invert the chart — it looks like a 90-degree spike = imminent reversal\n\n"
            "TIMING (Go one frame lower — 15-min):\n"
            "• See same extended fall on intraday\n"
            "• Many red bars in a row\n"
            "• Buy at FIRST GREEN SIGN — do not wait for the bar to close\n"
            "• Can also buy early (anticipate U-turn) but costs extra vs waiting for signal\n\n"
            "ENTRY QUALITY CHECK:\n"
            "• Must be in green INSTANTLY (first bar)\n"
            "• If struggling after 30 min — reduce size or exit entirely\n"
            "• Best reversals never go below entry\n\n"
            "STOP: Below the low of the entry bar — tight, typically 1-2%\n\n"
            "TARGET & EXIT:\n"
            "• 20-Day Moving Average\n"
            "• NOT a swing trade — take the snap-back\n"
            "• Exit same day or within 2-3 days\n\n"
            "REQUIRES screen time (1st hour or close)\n"
            "Skip if no screen time available"
        ),
        "entry_rules": [
            "Stock in strong prior uptrend (~100%+ gain, linear, institutional — purple dots visible)",
            "Stock NOT broken — just extended; daily chart shows smooth decline then ANGLE CHANGE",
            "Angle change: 3-5 days of fast, accelerated red candles — invert chart looks like 90° spike",
            "Drop to daily timeframe to open 15-min chart — see same extended fall intraday",
            "Buy at FIRST GREEN SIGN on 15-min — do not wait for bar to close",
            "Best reversals: must be in green instantly (first bar) — if not, reduce size",
            "Reversal day: opens near low, strong close, high volume — blue institutional bar",
        ],
        "exit_rules": [
            "Stop below the low of the entry bar — tight, 1-2% max",
            "Target: 20-Day Moving Average — take the snap-back, do NOT hold beyond",
            "Exit same day or within 2-3 days — NOT a swing trade",
            "If struggling after 30 min on 15-min chart — reduce size or exit entirely",
            "Best reversals never go below entry — if they do, exit immediately",
            "Do not re-enter if stopped out — setup has likely failed",
        ],
    },

    # ── SNEAKY ATTACK ─────────────────────────────────────────────────────────
    {
        "name": "Sneaky Attack",
        "emoji": "🥷",
        "color": "#8B5CF6",
        "description": (
            "The Sneaky Attack — Position 2 Entry Rules\n\n"
            "FAST AND FORTUNATE | Chapter Four B: The Sneaky Attack\n\n"
            "Day 1 tail forms on failed breakout | Day 2 inside bar confirms absorption | "
            "Day 3 crosses Day 1 high on volume = Position 2 active\n\n"
            "BEFORE (Prerequisites):\n"
            "• Valid Stage 2 setup with LF confirmed\n"
            "• Position 1 already open (SVRO or VCP)\n"
            "• Market breadth supportive\n\n"
            "DAY 1 — The Tail:\n"
            "• Opens strong, collapses by close\n"
            "• Long upper wick forms\n"
            "• Original stop NOT hit → HOLD Position 1\n"
            "• Measure tail: (High-Close)/Close x100\n"
            "• <2.5% = ideal | >5% = skip Position 2\n\n"
            "DAY 2 — Confirmation:\n"
            "• Inside bar (range within Day 1)\n"
            "• MUST close higher than Day 1 close\n"
            "• Place buy-stop above Day 1 High\n\n"
            "DAY 3 — Entry (Position 2):\n"
            "• Crosses Day 1 High with volume\n"
            "• Buy-stop fires = Position 2 active\n"
            "• Stop: below Day 1 Low or -2.5%\n\n"
            "URGENCY RULE:\n"
            "• Day 2 cross = full size\n"
            "• Day 3 cross = half size\n"
            "• Day 4+ = observe only\n"
            "• Day 5+ = ABANDON Position 2\n\n"
            "AFTER:\n"
            "• Trail both positions with 20-day MA\n"
            "• Exit on stop only — not early profit\n\n"
            "KEY INSIGHT: The Sneaky Attack lets you add to a winner at a low-risk point. "
            "The tail shows sellers tried and FAILED. Day 2 absorption confirms buyers in control. "
            "Day 3 is your trigger — high conviction, tight stop."
        ),
        "entry_rules": [
            "Valid Stage 2 setup with Liquidity Force event confirmed — Position 1 already open (SVRO or VCP)",
            "Market breadth supportive — not entering against broad weakness",
            "Day 1: Stock opens strong but collapses to form long upper wick (tail) — original stop NOT hit",
            "Day 1 tail measurement: (High-Close)/Close x100 — ideal <2.5%, skip if >5%",
            "Day 2: Inside bar — range entirely within Day 1, MUST close higher than Day 1 close",
            "Place buy-stop above Day 1 High after Day 2 confirms",
            "Day 3: Stock crosses Day 1 High with volume spike — buy-stop fires = Position 2 active",
            "Day 3 cross = full size | Day 4 cross = half size | Day 5+ = abandon Position 2",
        ],
        "exit_rules": [
            "Stop for Position 2: below Day 1 Low OR -2.5% from entry — whichever is tighter",
            "Trail BOTH Position 1 and Position 2 together with 20-day MA",
            "Exit on stop only — do NOT take early profit on Position 2",
            "If Day 2 closes lower than Day 1 close — abort, do not place the buy-stop",
            "If urgency fades (Day 5+) and buy-stop not triggered — abandon Position 2 entirely",
            "If Position 1 stop is hit — close Position 2 simultaneously",
        ],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    conn = get_conn()
    for pb_def in PLAYBOOKS:
        print(f"\n{'='*60}")
        print(f"Processing: {pb_def['name']}")
        pb_id = upsert_playbook(
            conn,
            pb_def["name"],
            pb_def["emoji"],
            pb_def["color"],
            pb_def["description"],
        )
        set_rules(conn, pb_id, pb_def["entry_rules"], pb_def["exit_rules"])
    conn.close()
    print("\n✅ All playbooks updated successfully.")
    print("   Copy chart images to ~/Desktop/sak_journal/assets/:")
    print("   - vcp_1h_rules_chart.png")
    print("   - oops_reversal_chart.png")
    print("   - reversal_chart.png")
    print("   - sneaky_attack_chart.png")

if __name__ == "__main__":
    main()
