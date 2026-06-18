# data/db.py — Auto-switches between SQLite (local) and Supabase (cloud)
import os

# Use Supabase if credentials are available, otherwise SQLite
def _use_supabase():
    try:
        import streamlit as st
        url = st.secrets.get("SUPABASE_URL","")
        key = st.secrets.get("SUPABASE_KEY","")
        if url and key:
            os.environ["SUPABASE_URL"] = url
            os.environ["SUPABASE_KEY"] = key
            return True
    except: pass
    url = os.environ.get("SUPABASE_URL","")
    key = os.environ.get("SUPABASE_KEY","")
    return bool(url and key)

if _use_supabase():
    from data.db_supabase import (
        get_trades, get_journal_trades, add_trade, update_trade,
        delete_trade, get_strategies, get_kpi_summary_extended,
        get_setting, import_trading_journal
    )
else:
    # Local SQLite fallback
    import sqlite3
    from datetime import datetime

    DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "journal.db"))

    def _conn():
        c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

    def get_trades(strategy="All", date_from=None, date_to=None):
        c = _conn()
        q = "SELECT * FROM trades WHERE 1=1"
        params = []
        if strategy and strategy != "All":
            q += " AND strategy=?"; params.append(strategy)
        if date_from:
            q += " AND exit_date>=?"; params.append(str(date_from))
        if date_to:
            q += " AND exit_date<=?"; params.append(str(date_to))
        q += " ORDER BY entry_date DESC"
        rows = c.execute(q, params).fetchall(); c.close()
        return [dict(r) for r in rows]

    def get_journal_trades(): return get_trades()

    def add_trade(data):
        c = _conn()
        cols = ",".join(data.keys()); vals = ",".join(["?"]*len(data))
        c.execute(f"INSERT INTO trades({cols})VALUES({vals})", list(data.values()))
        c.commit(); tid = c.lastrowid; c.close(); return tid

    def update_trade(tid, data):
        c = _conn()
        sets = ",".join(f"{k}=?" for k in data.keys())
        c.execute(f"UPDATE trades SET {sets} WHERE id=?", list(data.values())+[tid])
        c.commit(); c.close()

    def delete_trade(tid):
        c = _conn(); c.execute("DELETE FROM trades WHERE id=?", (tid,)); c.commit(); c.close()

    def get_strategies():
        c = _conn()
        rows = c.execute("SELECT DISTINCT strategy FROM trades WHERE strategy IS NOT NULL ORDER BY strategy").fetchall()
        c.close(); return [r[0] for r in rows]

    def get_kpi_summary_extended(*args, **kwargs):
        trades = get_trades()
        closed = [t for t in trades if t.get("status")=="CLOSED"]
        pnls = [float(t.get("pnl") or 0) for t in closed]
        win_p = [p for p in pnls if p>0]; loss_p = [p for p in pnls if p<0]
        return {
            "total_pnl": sum(pnls),
            "win_rate": len(win_p)/len(pnls)*100 if pnls else 0,
            "profit_factor": abs(sum(win_p)/sum(loss_p)) if loss_p and sum(loss_p) else 0,
            "total_trades": len(closed),
            "avg_win": sum(win_p)/len(win_p) if win_p else 0,
            "avg_loss": sum(loss_p)/len(loss_p) if loss_p else 0,
        }

    def get_setting(key, default=None):
        try:
            c = _conn()
            r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            c.close(); return r[0] if r else default
        except: return default

    def import_trading_journal(): pass


# ── Compatibility stubs ───────────────────────────────────────────────────────
def init_db():
    """No-op on cloud — Supabase handles schema."""
    pass

def import_from_excel(path=None):
    """No-op on cloud — data already in Supabase."""
    return 0, "OK"

def last_sync_time():
    """Always return a value on cloud so first-run import is skipped."""
    try:
        import streamlit as st
        if st.secrets.get("SUPABASE_URL"):
            return "cloud"
    except: pass
    return None


def exit_trade(trade_id, exit_price, exit_date, exit_qty=None, commission=0):
    """Exit a trade."""
    try:
        data = {"status": "CLOSED", "exit_price": exit_price, "exit_date": str(exit_date)}
        if exit_qty: data["exit_qty"] = exit_qty
        if commission: data["commission_exit"] = commission
        update_trade(trade_id, data)
    except Exception as e:
        print(f"exit_trade error: {e}")

def get_open_trades():
    return [t for t in get_trades() if t.get("status") == "OPEN"]

def get_trade_by_id(trade_id):
    trades = get_trades()
    return next((t for t in trades if t.get("id") == trade_id), None)


# ── Missing stubs for cloud compatibility ─────────────────────────────────────

def get_all_notes():
    try:
        if _use_supabase():
            res=_sb().table("daily_notes").select("*").order("note_date",desc=True).execute()
            return res.data or []
    except: pass
    try:
        import sqlite3,os
        db=os.path.abspath(os.path.join(os.path.dirname(__file__),"..","journal.db"))
        c2=sqlite3.connect(db); c2.row_factory=sqlite3.Row
        rows=c2.execute("SELECT * FROM daily_notes ORDER BY note_date DESC").fetchall()
        c2.close(); return [dict(r) for r in rows]
    except: return []

def get_note_by_date(d):
    notes=get_all_notes()
    return next((n for n in notes if n.get("note_date")==str(d)),None)

def save_note(d,text):
    try:
        if _use_supabase():
            _sb().table("daily_notes").upsert({"note_date":str(d),"note":text,"updated_at":str(__import__("datetime").datetime.now())}).execute()
            return
    except: pass
    try:
        import sqlite3,os
        db=os.path.abspath(os.path.join(os.path.dirname(__file__),"..","journal.db"))
        c2=sqlite3.connect(db)
        c2.execute("INSERT INTO daily_notes(note_date,note)VALUES(?,?)ON CONFLICT(note_date)DO UPDATE SET note=excluded.note",(str(d),text))
        c2.commit(); c2.close()
    except: pass

def delete_note(d):
    try:
        if _use_supabase():
            _sb().table("daily_notes").delete().eq("note_date",str(d)).execute(); return
    except: pass

def get_playbooks():
    try:
        if _use_supabase():
            res=_sb().table("playbooks").select("*").order("name").execute()
            return res.data or []
    except: pass
    try:
        import sqlite3,os
        db=os.path.abspath(os.path.join(os.path.dirname(__file__),"..","journal.db"))
        c2=sqlite3.connect(db); c2.row_factory=sqlite3.Row
        rows=c2.execute("SELECT * FROM playbooks ORDER BY name").fetchall()
        c2.close(); return [dict(r) for r in rows]
    except: return []

def get_playbook(pid):
    pbs=get_playbooks()
    return next((p for p in pbs if p.get("id")==pid),None)

def create_playbook(data):
    try:
        if _use_supabase():
            res=_sb().table("playbooks").insert(data).execute()
            return res.data[0] if res.data else None
    except: pass

def update_playbook(pid,data):
    try:
        if _use_supabase():
            _sb().table("playbooks").update(data).eq("id",pid).execute()
    except: pass

def get_trade_playbook(tid):
    t=get_trade_by_id(tid)
    if t and t.get("playbook"):
        pbs=get_playbooks()
        return next((p for p in pbs if p.get("name")==t["playbook"]),None)
    return None

def set_setting(key,value):
    try:
        if _use_supabase():
            _sb().table("settings").upsert({"key":key,"value":str(value)}).execute()
    except: pass

def get_kpi_summary_extended(*args,**kwargs):
    trades=get_trades()
    closed=[t for t in trades if t.get("status")=="CLOSED"]
    pnls=[float(t.get("pnl") or 0) for t in closed]
    win_p=[p for p in pnls if p>0]; loss_p=[p for p in pnls if p<0]
    return {
        "total_pnl":sum(pnls),
        "win_rate":len(win_p)/len(pnls)*100 if pnls else 0,
        "profit_factor":abs(sum(win_p)/sum(loss_p)) if loss_p and sum(loss_p) else 0,
        "total_trades":len(closed),
        "avg_win":sum(win_p)/len(win_p) if win_p else 0,
        "avg_loss":sum(loss_p)/len(loss_p) if loss_p else 0,
    }


def delete_playbook(pid):
    try:
        if _use_supabase():
            _sb().table("playbooks").delete().eq("id", pid).execute()
    except Exception as e:
        print(f"delete_playbook error: {e}")


def get_playbook_rules(pid):
    try:
        if _use_supabase():
            res=_sb().table("playbook_rules").select("*").eq("playbook_id",pid).order("sort_order").execute()
            return res.data or []
    except: pass
    try:
        import sqlite3,os
        db=os.path.abspath(os.path.join(os.path.dirname(__file__),"..","journal.db"))
        c2=sqlite3.connect(db); c2.row_factory=sqlite3.Row
        rows=c2.execute("SELECT * FROM playbook_rules WHERE playbook_id=? ORDER BY sort_order",(pid,)).fetchall()
        c2.close(); return [dict(r) for r in rows]
    except: return []

def save_playbook_rules(pid, rules):
    try:
        if _use_supabase():
            _sb().table("playbook_rules").delete().eq("playbook_id",pid).execute()
            for r in rules:
                r["playbook_id"]=pid
                _sb().table("playbook_rules").insert(r).execute()
    except: pass

def get_playbook_trades(pid):
    try:
        pbs=get_playbooks()
        pb=next((p for p in pbs if p.get("id")==pid),None)
        if pb:
            return [t for t in get_trades() if t.get("playbook")==pb.get("name")]
    except: pass
    return []
