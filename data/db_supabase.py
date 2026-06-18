# data/db_supabase.py
# Supabase database layer — drop-in replacement for SQLite db.py
import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL","")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY","")

def _sb():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_trades(strategy="All", date_from=None, date_to=None):
    try:
        q = _sb().table("trades").select("*")
        if strategy and strategy != "All":
            q = q.eq("strategy", strategy)
        if date_from:
            q = q.gte("exit_date", str(date_from))
        if date_to:
            q = q.lte("exit_date", str(date_to))
        res = q.order("entry_date", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"get_trades error: {e}"); return []

def get_journal_trades():
    return get_trades()

def add_trade(trade_data):
    try:
        res = _sb().table("trades").insert(trade_data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"add_trade error: {e}"); return None

def update_trade(trade_id, trade_data):
    try:
        res = _sb().table("trades").update(trade_data).eq("id", trade_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"update_trade error: {e}"); return None

def delete_trade(trade_id):
    try:
        _sb().table("trades").delete().eq("id", trade_id).execute()
    except Exception as e:
        print(f"delete_trade error: {e}")

def get_strategies():
    try:
        res = _sb().table("trades").select("strategy").execute()
        strats = list({r["strategy"] for r in res.data if r.get("strategy")})
        return sorted(strats)
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

def get_setting(key, default=None):
    try:
        res = _sb().table("settings").select("value").eq("key", key).execute()
        return res.data[0]["value"] if res.data else default
    except: return default

def import_trading_journal(): pass
