#!/usr/bin/env python3
"""
SAK Journal — Supabase Setup
Creates all tables in Supabase and migrates data from journal.db
"""
import os, sys, sqlite3, json
from datetime import datetime

SUPABASE_URL = "https://snkniguooepasteokexp.supabase.co"
SUPABASE_KEY = "sb_publishable_2JSM84nvCWzUwRCC_QVKPA_oJb0aaP2"

try:
    from supabase import create_client
except ImportError:
    print("Installing supabase..."); os.system("pip3 install supabase --break-system-packages --quiet")
    from supabase import create_client

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

DB = os.path.expanduser("~/Desktop/sak_journal/journal.db")

def migrate():
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row

    # ── trades ────────────────────────────────────────────────────────────────
    print("Migrating trades...")
    rows = conn.execute("SELECT * FROM trades").fetchall()
    if rows:
        data = []
        for r in rows:
            d = dict(r)
            # Convert None to null-safe values
            data.append({k: v for k, v in d.items() if v is not None})
        # Insert in batches of 100
        for i in range(0, len(data), 100):
            batch = data[i:i+100]
            try:
                sb.table("trades").upsert(batch).execute()
                print(f"  ✅ trades {i+1}–{min(i+100,len(data))}")
            except Exception as e:
                print(f"  ⚠️ {e}")

    # ── daily_notes ───────────────────────────────────────────────────────────
    print("Migrating daily_notes...")
    try:
        rows = conn.execute("SELECT * FROM daily_notes").fetchall()
        if rows:
            data = [dict(r) for r in rows]
            sb.table("daily_notes").upsert(data).execute()
            print(f"  ✅ {len(data)} notes")
    except Exception as e: print(f"  ⚠️ {e}")

    # ── playbooks ─────────────────────────────────────────────────────────────
    print("Migrating playbooks...")
    try:
        rows = conn.execute("SELECT * FROM playbooks").fetchall()
        if rows:
            data = [dict(r) for r in rows]
            sb.table("playbooks").upsert(data).execute()
            print(f"  ✅ {len(data)} playbooks")
    except Exception as e: print(f"  ⚠️ {e}")

    # ── morning_brief ─────────────────────────────────────────────────────────
    print("Migrating morning_brief...")
    try:
        rows = conn.execute("SELECT * FROM morning_brief").fetchall()
        if rows:
            data = [dict(r) for r in rows]
            sb.table("morning_brief").upsert(data).execute()
            print(f"  ✅ {len(data)} briefs")
    except Exception as e: print(f"  ⚠️ {e}")

    # ── pt_rules / pt_checkins ────────────────────────────────────────────────
    for tbl in ["pt_rules","pt_checkins","trade_attachments","trade_pt_sl","note_templates"]:
        print(f"Migrating {tbl}...")
        try:
            rows = conn.execute(f"SELECT * FROM {tbl}").fetchall()
            if rows:
                data = [dict(r) for r in rows]
                sb.table(tbl).upsert(data).execute()
                print(f"  ✅ {len(data)} rows")
            else:
                print(f"  — empty")
        except Exception as e: print(f"  ⚠️ {e}")

    conn.close()
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    migrate()
