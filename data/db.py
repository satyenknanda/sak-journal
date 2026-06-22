# data/db.py — Auto-switches between Supabase (cloud) and SQLite (local)
import os
import sqlite3
from datetime import datetime

# ── Backend detection ─────────────────────────────────────────────────────────
def _use_supabase():
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if url and key:
            os.environ["SUPABASE_URL"] = url
            os.environ["SUPABASE_KEY"] = key
            return True
    except: pass
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))

def _sb():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def _local_db():
    db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "journal.db"))
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    return c

# ── Init ──────────────────────────────────────────────────────────────────────
def init_db():
    """No-op on cloud. Local SQLite is initialized separately."""
    pass

def last_sync_time():
    """Return truthy on cloud so first-run import is skipped."""
    if _use_supabase(): return "cloud"
    try:
        c = _local_db()
        r = c.execute("SELECT value FROM settings WHERE key='last_sync'").fetchone()
        c.close(); return r[0] if r else None
    except: return None

def import_from_excel(path=None):
    return 0, "OK"

def import_trading_journal():
    pass

# ── Trades ────────────────────────────────────────────────────────────────────
def get_trades(strategy="All", date_from=None, date_to=None, status=None, ticker=None):
    try:
        if _use_supabase():
            q = _sb().table("trades").select("*")
            if strategy and strategy != "All": q = q.eq("strategy", strategy)
            if status and status not in ("All", None): q = q.eq("status", status)
            if ticker and ticker != "All": q = q.ilike("ticker", f"%{ticker}%")
            if date_from and status not in (None, "All", "OPEN"):
                q = q.gte("exit_date", str(date_from))
            if date_to and status not in (None, "All", "OPEN"):
                q = q.lte("exit_date", str(date_to))
            res = q.order("entry_date", desc=True).execute()
            return res.data or []
    except Exception as e:
        print(f"get_trades supabase error: {e}")
    try:
        c = _local_db()
        q = "SELECT * FROM trades WHERE 1=1"
        params = []
        if strategy and strategy != "All": q += " AND strategy=?"; params.append(strategy)
        if status and status not in ("All", None): q += " AND status=?"; params.append(status)
        if ticker and ticker != "All": q += " AND ticker LIKE ?"; params.append(f"%{ticker}%")
        if date_from and status not in (None, "All", "OPEN"):
            q += " AND exit_date>=?"; params.append(str(date_from))
        if date_to and status not in (None, "All", "OPEN"):
            q += " AND exit_date<=?"; params.append(str(date_to))
        q += " ORDER BY entry_date DESC"
        rows = c.execute(q, params).fetchall(); c.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"get_trades local error: {e}"); return []

def get_journal_trades():
    return get_trades()

def add_trade(data):
    try:
        if _use_supabase():
            res = _sb().table("trades").insert(data).execute()
            return res.data[0] if res.data else None
    except Exception as e: print(f"add_trade error: {e}")
    try:
        c = _local_db()
        cols = ",".join(data.keys()); vals = ",".join(["?"]*len(data))
        cur = c.execute(f"INSERT INTO trades({cols})VALUES({vals})", list(data.values()))
        c.commit(); tid = cur.lastrowid; c.close(); return tid
    except Exception as e: print(f"add_trade local error: {e}"); return None

def update_trade(trade_id, data):
    try:
        if _use_supabase():
            _sb().table("trades").update(data).eq("id", trade_id).execute(); return
    except Exception as e: print(f"update_trade error: {e}")
    try:
        c = _local_db()
        sets = ",".join(f"{k}=?" for k in data.keys())
        c.execute(f"UPDATE trades SET {sets} WHERE id=?", list(data.values())+[trade_id])
        c.commit(); c.close()
    except Exception as e: print(f"update_trade local error: {e}")

def delete_trade(trade_id):
    try:
        if _use_supabase():
            _sb().table("trades").delete().eq("id", trade_id).execute(); return
    except Exception as e: print(f"delete_trade error: {e}")
    try:
        c = _local_db(); c.execute("DELETE FROM trades WHERE id=?", (trade_id,))
        c.commit(); c.close()
    except Exception as e: print(f"delete_trade local error: {e}")

def exit_trade(trade_id, exit_price, exit_date, exit_qty=None, commission=0):
    data = {"status":"CLOSED","exit_price":exit_price,"exit_date":str(exit_date)}
    if exit_qty: data["exit_qty"] = exit_qty
    if commission: data["commission_exit"] = commission
    update_trade(trade_id, data)

def get_strategies():
    try:
        trades = get_trades()
        return sorted(list({t.get("strategy") for t in trades if t.get("strategy")}))
    except: return []

def get_kpi_summary_extended(*args, **kwargs):
    trades = get_trades()
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    pnls = [float(t.get("pnl") or 0) for t in closed]
    win_p = [p for p in pnls if p > 0]
    loss_p = [p for p in pnls if p < 0]
    return {
        "total_pnl": sum(pnls),
        "win_rate": len(win_p)/len(pnls)*100 if pnls else 0,
        "profit_factor": abs(sum(win_p)/sum(loss_p)) if loss_p and sum(loss_p) else 0,
        "total_trades": len(closed),
        "avg_win": sum(win_p)/len(win_p) if win_p else 0,
        "avg_loss": sum(loss_p)/len(loss_p) if loss_p else 0,
    }

# ── Notes ─────────────────────────────────────────────────────────────────────
def get_all_notes():
    try:
        if _use_supabase():
            res = _sb().table("daily_notes").select("*").order("note_date", desc=True).execute()
            return res.data or []
    except Exception as e: print(f"get_all_notes error: {e}")
    try:
        c = _local_db()
        rows = c.execute("SELECT * FROM daily_notes ORDER BY note_date DESC").fetchall()
        c.close(); return [dict(r) for r in rows]
    except: return []

def get_note_by_date(d):
    notes = get_all_notes()
    return next((n for n in notes if n.get("note_date") == str(d)), None)

def save_note(d, text):
    try:
        if _use_supabase():
            _sb().table("daily_notes").upsert({"note_date":str(d),"note":text,"updated_at":str(datetime.now())}).execute(); return
    except Exception as e: print(f"save_note error: {e}")
    try:
        c = _local_db()
        c.execute("INSERT INTO daily_notes(note_date,note)VALUES(?,?)ON CONFLICT(note_date)DO UPDATE SET note=excluded.note",(str(d),text))
        c.commit(); c.close()
    except Exception as e: print(f"save_note local error: {e}")

def delete_note(d):
    try:
        if _use_supabase():
            _sb().table("daily_notes").delete().eq("note_date", str(d)).execute(); return
    except Exception as e: print(f"delete_note error: {e}")
    try:
        c = _local_db(); c.execute("DELETE FROM daily_notes WHERE note_date=?", (str(d),))
        c.commit(); c.close()
    except Exception as e: print(f"delete_note local error: {e}")

# ── Playbooks ─────────────────────────────────────────────────────────────────
def get_playbooks():
    try:
        if _use_supabase():
            res = _sb().table("playbooks").select("*").order("name").execute()
            return res.data or []
    except Exception as e: print(f"get_playbooks error: {e}")
    try:
        c = _local_db()
        rows = c.execute("SELECT * FROM playbooks ORDER BY name").fetchall()
        c.close(); return [dict(r) for r in rows]
    except: return []

def get_playbook(pid):
    pbs = get_playbooks()
    return next((p for p in pbs if p.get("id") == pid), None)

def create_playbook(data):
    try:
        if _use_supabase():
            res = _sb().table("playbooks").insert(data).execute()
            return res.data[0] if res.data else None
    except Exception as e: print(f"create_playbook error: {e}")
    try:
        c = _local_db()
        cols = ",".join(data.keys()); vals = ",".join(["?"]*len(data))
        cur = c.execute(f"INSERT INTO playbooks({cols})VALUES({vals})", list(data.values()))
        c.commit(); pid = cur.lastrowid; c.close(); return pid
    except Exception as e: print(f"create_playbook local error: {e}"); return None

def update_playbook(pid, data):
    try:
        if _use_supabase():
            _sb().table("playbooks").update(data).eq("id", pid).execute(); return
    except Exception as e: print(f"update_playbook error: {e}")
    try:
        c = _local_db()
        sets = ",".join(f"{k}=?" for k in data.keys())
        c.execute(f"UPDATE playbooks SET {sets} WHERE id=?", list(data.values())+[pid])
        c.commit(); c.close()
    except Exception as e: print(f"update_playbook local error: {e}")

def delete_playbook(pid):
    try:
        if _use_supabase():
            _sb().table("playbooks").delete().eq("id", pid).execute(); return
    except Exception as e: print(f"delete_playbook error: {e}")
    try:
        c = _local_db(); c.execute("DELETE FROM playbooks WHERE id=?", (pid,))
        c.commit(); c.close()
    except Exception as e: print(f"delete_playbook local error: {e}")

def get_trade_playbook(trade_id):
    trades = get_trades()
    t = next((tr for tr in trades if tr.get("id") == trade_id), None)
    if t and t.get("playbook"):
        return get_playbooks()
    return None

# ── Settings ──────────────────────────────────────────────────────────────────
def get_setting(key, default=None):
    try:
        if _use_supabase():
            res = _sb().table("settings").select("value").eq("key", key).execute()
            return res.data[0]["value"] if res.data else default
    except: pass
    try:
        c = _local_db()
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        c.close(); return r[0] if r else default
    except: return default

def set_setting(key, value):
    try:
        if _use_supabase():
            _sb().table("settings").upsert({"key":key,"value":str(value)}).execute(); return
    except Exception as e: print(f"set_setting error: {e}")
    try:
        c = _local_db()
        c.execute("INSERT INTO settings(key,value)VALUES(?,?)ON CONFLICT(key)DO UPDATE SET value=excluded.value",(key,str(value)))
        c.commit(); c.close()
    except Exception as e: print(f"set_setting local error: {e}")


# ── Playbook Rules ────────────────────────────────────────────────────────────
def get_playbook_rules(pid):
    try:
        if _use_supabase():
            res=_sb().table("playbook_rules").select("*").eq("playbook_id",pid).order("sort_order").execute()
            return res.data or []
    except: pass
    try:
        c2=_local_db()
        rows=c2.execute("SELECT * FROM playbook_rules WHERE playbook_id=? ORDER BY sort_order",(pid,)).fetchall()
        c2.close(); return [dict(r) for r in rows]
    except: return []

def save_playbook_rules(pid, rules):
    try:
        if _use_supabase():
            _sb().table("playbook_rules").delete().eq("playbook_id",pid).execute()
            for i,r in enumerate(rules):
                r["playbook_id"]=pid; r["sort_order"]=i
                _sb().table("playbook_rules").insert(r).execute()
    except: pass

def get_missed_trades(pid):
    return []

def save_trade_playbook(trade_id, playbook_name):
    update_trade(trade_id, {"playbook": playbook_name})

def get_trades_by_playbook(playbook_name):
    return [t for t in get_trades() if t.get("playbook")==playbook_name]


def add_missed_trade(pid, ticker, date, notes=""):
    try:
        if _use_supabase():
            _sb().table("missed_trades").insert({"playbook_id":pid,"ticker":ticker,"date":str(date),"notes":notes}).execute()
    except: pass

def delete_missed_trade(mid):
    try:
        if _use_supabase():
            _sb().table("missed_trades").delete().eq("id",mid).execute()
    except: pass


def get_trade_note(trade_id):
    trades = get_trades()
    t = next((tr for tr in trades if tr.get("id")==trade_id), None)
    return t.get("notes","") if t else ""

def save_trade_note(trade_id, note):
    update_trade(trade_id, {"notes": note})


def get_conn():
    """Return a SQLite connection for local use. Returns None on cloud."""
    try:
        if _use_supabase():
            return None
        return _local_db()
    except:
        return None


def get_capital_flows(year):
    """Returns dict of month -> added/withdrawn/mtf_interest/base_capital for a year."""
    try:
        res = _sb().table("capital_flows").select("*").eq("year", year).execute()
        out = {}
        for row in res.data:
            out[row["month"]] = {
                "added": float(row.get("added") or 0),
                "withdrawn": float(row.get("withdrawn") or 0),
                "mtf_interest": float(row.get("mtf_interest") or 0),
                "base_capital": float(row.get("base_capital") or 0),
            }
        return out
    except Exception:
        return {}


def save_capital_flow(year, month, added, withdrawn, base_capital=None, mtf_interest=None):
    """Upsert a single month's flow row. month=0 is the starting-capital anchor row."""
    try:
        payload = {"year": year, "month": month, "added": added, "withdrawn": withdrawn}
        if base_capital is not None:
            payload["base_capital"] = base_capital
        if mtf_interest is not None:
            payload["mtf_interest"] = mtf_interest
        _sb().table("capital_flows").upsert(payload, on_conflict="year,month").execute()
        return True
    except Exception as e:
        print("save_capital_flow error:", e)
        return False



def get_mtf_margins():
    """Returns list of dicts: [{ticker, margin_pct, leverage, updated_at}, ...] sorted by ticker."""
    try:
        res = _sb().table("mtf_margins").select("*").order("ticker").execute()
        return res.data or []
    except Exception:
        return []


def save_mtf_margin(ticker, margin_pct, leverage=None):
    """Upsert a ticker's margin %. Computes leverage automatically if not provided."""
    try:
        ticker = ticker.upper().strip()
        if leverage is None and margin_pct and float(margin_pct) > 0:
            leverage = round(100.0 / float(margin_pct), 2)
        payload = {"ticker": ticker, "margin_pct": margin_pct, "leverage": leverage,
                   "updated_at": "now()"}
        _sb().table("mtf_margins").upsert(payload, on_conflict="ticker").execute()
        return True
    except Exception as e:
        print("save_mtf_margin error:", e)
        return False


def delete_mtf_margin(ticker):
    """Remove a ticker from the MTF margin lookup table."""
    try:
        _sb().table("mtf_margins").delete().eq("ticker", ticker.upper().strip()).execute()
        return True
    except Exception as e:
        print("delete_mtf_margin error:", e)
        return False
