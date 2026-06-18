import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, date
import json

DB_PATH = Path(__file__).parent.parent / "journal.db"
EXCEL_PATH = Path(__file__).parent.parent / "Daily_P__FY26-27_.xlsx"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_no         INTEGER,
            status           TEXT DEFAULT 'OPEN',
            entry_date       TEXT,
            side             TEXT DEFAULT 'Buy',
            qty              REAL,
            ticker           TEXT,
            strategy         TEXT,
            entry_price      REAL,
            stop_loss        REAL,
            take_profit      REAL,
            commission_entry REAL DEFAULT 0,
            tsl              REAL,
            live_price       REAL,
            change_pct       REAL,
            exit_date        TEXT,
            exit_qty         REAL,
            exit_price       REAL,
            commission_exit  REAL DEFAULT 0,
            risk_status      TEXT,
            notes            TEXT,
            pnl              REAL,
            r_multiple       REAL,
            mae_price        REAL,
            mfe_price        REAL,
            created_at       TEXT DEFAULT (datetime('now')),
            updated_at       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS trading_journal (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            week_number      INTEGER,
            trade_no         INTEGER,
            entry_date       TEXT,
            side             TEXT,
            qty              REAL,
            ticker           TEXT,
            strategy         TEXT,
            entry_price      REAL,
            stop_loss        REAL,
            take_profit      REAL,
            commission_entry REAL,
            one_r            REAL,
            position_size    REAL,
            max_profit       REAL,
            max_loss         REAL,
            risk_pct_trade   REAL,
            max_rr           REAL,
            exit_date        TEXT,
            exit_qty         REAL,
            exit_price       REAL,
            commission_exit  REAL,
            duration         TEXT,
            r_multiple       REAL,
            pnl              REAL,
            cumulative_pnl   REAL,
            win_loss         TEXT,
            status           TEXT,
            account_balance  REAL,
            gain_loss_pct    REAL,
            drawdown         REAL,
            remarks          TEXT
        );

        CREATE TABLE IF NOT EXISTS trade_notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            note_date   TEXT NOT NULL,
            title       TEXT,
            content     TEXT,
            template    TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS trade_notes_per_trade (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id    INTEGER,
            ticker      TEXT,
            note        TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );


        CREATE TABLE IF NOT EXISTS playbooks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            emoji       TEXT DEFAULT '📋',
            color       TEXT DEFAULT '#7C3AED',
            description TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS playbook_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            playbook_id INTEGER NOT NULL,
            rule_type   TEXT NOT NULL,  -- 'entry' or 'exit'
            rule_text   TEXT NOT NULL,
            show_when   TEXT DEFAULT 'always'  -- 'always','winner','loser'
        );

        CREATE TABLE IF NOT EXISTS trade_playbooks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id    INTEGER NOT NULL,
            playbook_id INTEGER NOT NULL,
            rules_followed TEXT,  -- JSON list of rule ids followed
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS missed_trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            playbook_id INTEGER NOT NULL,
            ticker      TEXT,
            trade_date  TEXT,
            entry_time  TEXT,
            exit_time   TEXT,
            entry_price REAL,
            exit_price  REAL,
            qty         INTEGER,
            notes       TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS sync_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at     TEXT DEFAULT (datetime('now')),
            rows_imported INTEGER,
            notes         TEXT
        );
    """)

    defaults = {
        "account_balance": "10000000",
        "risk_pct": "0.004",
        "fy": "2026-27",
        "strategies": json.dumps([
            "SVRO","VCP","EP","REVERSAL","NR 1HR","TS","MARS","RANDOM",
            "ETF'S","ANTICIPATION","EP PULLBACKS","Oops Reversal","Chirag Reversal"
        ]),
        "theme": "dark",
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Add mae_price / mfe_price columns if they don't exist yet (safe migration)
    for col in ("mae_price", "mfe_price"):
        try:
            c.execute(f"ALTER TABLE trades ADD COLUMN {col} REAL")
            conn.commit()
        except Exception:
            pass  # column already exists

    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def _parse_date(val):
    if val is None: return None
    try:
        if pd.isna(val): return None
    except Exception: pass
    if isinstance(val, str):
        val = val.strip()
        if not val or val.upper() == 'NAT': return None
        try: return pd.Timestamp(val).strftime("%Y-%m-%d")
        except: return None
    if isinstance(val, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(val).strftime("%Y-%m-%d")
    try:
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(float(val)))).strftime("%Y-%m-%d")
    except: return None


def _safe_float(val):
    try:
        if pd.isna(val): return None
        f = float(val)
        return None if pd.isna(f) else f
    except: return None


def _safe_int(val):
    try:
        if pd.isna(val): return None
        return int(float(val))
    except: return None


def _calc_pnl(entry_price, exit_price, exit_qty, commission_entry, commission_exit, side):
    try:
        ep = float(entry_price or 0)
        xp = float(exit_price or 0)
        qty = float(exit_qty or 0)
        comm = float(commission_entry or 0) + float(commission_exit or 0)
        if not (ep and xp and qty): return None
        if side == "Sell":
            return (ep - xp) * qty - comm
        return (xp - ep) * qty - comm
    except: return None


def _calc_r(entry_price, stop_loss, exit_price, side):
    try:
        ep = float(entry_price or 0)
        sl = float(stop_loss or 0)
        xp = float(exit_price or 0)
        if not (ep and sl and xp and ep != sl): return None
        risk = abs(ep - sl)
        gain = (xp - ep) if side != "Sell" else (ep - xp)
        return gain / risk
    except: return None


def import_from_excel(excel_path=None):
    path = excel_path or EXCEL_PATH
    if not Path(path).exists():
        return 0, "Excel file not found"

    try:
        df = pd.read_excel(path, sheet_name="DailyPlan", header=None)
    except Exception as e:
        return 0, str(e)

    # Find header row
    header_row = None
    for i, row in df.iterrows():
        vals = [str(v).strip() for v in row.values]
        if 'Status' in vals and 'Ticker' in vals:
            header_row = i
            break

    if header_row is None:
        return 0, "Could not find trade table in DailyPlan sheet"

    # Column positions (positional — handles duplicate col names)
    # 0=Status, 1=No, 2=Entry Date, 3=Side, 4=Qty, 5=Ticker, 6=Strategy
    # 7=Entry Price, 8=Stop Loss, 9=Take Profit, 10=Commission(entry)
    # 11=TSL, 12=Live Price, 13=Change%, 14=Exit Date, 15=Qty(exit)
    # 16=Exit Price, 17=Commission(exit), 18=Risk Status
    COL = dict(
        status=0, no=1, entry_date=2, side=3, qty=4,
        ticker=5, strategy=6, entry_price=7, stop_loss=8,
        take_profit=9, commission_entry=10, tsl=11,
        live_price=12, change_pct=13, exit_date=14,
        exit_qty=15, exit_price=16, commission_exit=17,
        risk_status=18
    )

    data_rows = df.iloc[header_row + 1:].reset_index(drop=True)

    conn = get_conn()
    conn.execute("DELETE FROM trades")

    imported = 0
    for _, row in data_rows.iterrows():
        vals = list(row)
        status = str(vals[COL["status"]] or "").strip().upper()
        if status not in ("OPEN", "CLOSED"):
            continue
        try:
            ep   = _safe_float(vals[COL["entry_price"]])
            xp   = _safe_float(vals[COL["exit_price"]])
            xqty = _safe_float(vals[COL["exit_qty"]])
            sl   = _safe_float(vals[COL["stop_loss"]])
            side = str(vals[COL["side"]] or "Buy").strip()
            ce   = _safe_float(vals[COL["commission_entry"]])
            cx   = _safe_float(vals[COL["commission_exit"]])

            pnl  = _calc_pnl(ep, xp, xqty, ce, cx, side)
            rmult = _calc_r(ep, sl, xp, side)

            r = {
                "trade_no":        _safe_int(vals[COL["no"]]),
                "status":          status,
                "entry_date":      _parse_date(vals[COL["entry_date"]]),
                "side":            side,
                "qty":             _safe_float(vals[COL["qty"]]),
                "ticker":          str(vals[COL["ticker"]] or "").strip(),
                "strategy":        str(vals[COL["strategy"]] or "").strip(),
                "entry_price":     ep,
                "stop_loss":       sl,
                "take_profit":     _safe_float(vals[COL["take_profit"]]),
                "commission_entry":ce,
                "tsl":             _safe_float(vals[COL["tsl"]]),
                "live_price":      _safe_float(vals[COL["live_price"]]),
                "change_pct":      _safe_float(vals[COL["change_pct"]]),
                "exit_date":       _parse_date(vals[COL["exit_date"]]),
                "exit_qty":        xqty,
                "exit_price":      xp,
                "commission_exit": cx,
                "risk_status":     str(vals[COL["risk_status"]] or "").strip(),
                "notes":           "",
                "pnl":             pnl,
                "r_multiple":      rmult,
            }

            cols = list(r.keys())
            conn.execute(
                f"INSERT INTO trades ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})",
                [r[c] for c in cols]
            )
            imported += 1
        except Exception:
            continue

    conn.execute(
        "INSERT INTO sync_log (rows_imported, notes) VALUES (?, ?)",
        (imported, "Imported from DailyPlan sheet")
    )
    conn.commit()
    conn.close()
    return imported, "OK"



def update_trade(trade_id: int, fields: dict):
    """Update any fields on a manually-added trade."""
    if not fields: return
    conn = get_conn()
    set_clause = ", ".join(f"{k}=?" for k in fields.keys())
    values = list(fields.values()) + [trade_id]
    conn.execute(f"UPDATE trades SET {set_clause} WHERE id=?", values)
    conn.commit(); conn.close()


def get_trade_by_id(trade_id: int):
    """Get a single trade by id."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_trades(status=None, strategy=None, ticker=None, date_from=None, date_to=None):
    conn = get_conn()
    q = "SELECT * FROM trades WHERE 1=1"
    params = []
    if status and status != "All":
        q += " AND status=?"; params.append(status)
    if strategy and strategy != "All":
        q += " AND strategy=?"; params.append(strategy)
    if ticker:
        q += " AND ticker LIKE ?"; params.append(f"%{ticker.upper()}%")
    if date_from:
        q += " AND entry_date >= ?"; params.append(str(date_from))
    if date_to:
        q += " AND entry_date <= ?"; params.append(str(date_to))
    q += " ORDER BY trade_no ASC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_trade(data: dict):
    conn = get_conn()
    cols = ["status","entry_date","side","qty","ticker","strategy",
            "entry_price","stop_loss","take_profit","commission_entry","tsl","notes"]
    vals = [data.get(c) for c in cols]
    conn.execute(
        f"INSERT INTO trades ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", vals
    )
    conn.commit()
    conn.close()


def exit_trade(trade_id, exit_date, exit_price, exit_qty, commission_exit, risk_status):
    conn = get_conn()
    row = dict(conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone())
    pnl   = _calc_pnl(row["entry_price"], exit_price, exit_qty,
                       row.get("commission_entry"), commission_exit, row.get("side","Buy"))
    rmult = _calc_r(row["entry_price"], row["stop_loss"], exit_price, row.get("side","Buy"))
    conn.execute("""
        UPDATE trades SET status='CLOSED', exit_date=?, exit_price=?, exit_qty=?,
        commission_exit=?, risk_status=?, pnl=?, r_multiple=?, updated_at=datetime('now')
        WHERE id=?
    """, (str(exit_date), exit_price, exit_qty, commission_exit, risk_status, pnl, rmult, trade_id))
    conn.commit()
    conn.close()


def delete_trade(trade_id):
    conn = get_conn()
    conn.execute("DELETE FROM trades WHERE id=?", (trade_id,))
    conn.commit()
    conn.close()


def get_strategies():
    raw = get_setting("strategies", "[]")
    try: return json.loads(raw)
    except: return []


def get_kpi_summary():
    conn = get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM trades").fetchall()]
    conn.close()
    if not rows: return {}

    df = pd.DataFrame(rows)
    total    = len(df)
    open_t   = len(df[df["status"] == "OPEN"])
    closed_df = df[df["status"] == "CLOSED"].copy()
    closed_t = len(closed_df)

    wins     = closed_df[closed_df["pnl"] > 0] if not closed_df.empty else pd.DataFrame()
    win_rate = len(wins) / closed_t if closed_t > 0 else 0
    total_pnl = float(closed_df["pnl"].sum()) if not closed_df.empty else 0

    pos_r = closed_df[closed_df["r_multiple"] > 0]["r_multiple"] if not closed_df.empty else pd.Series()
    neg_r = closed_df[closed_df["r_multiple"] <= 0]["r_multiple"] if not closed_df.empty else pd.Series()
    avg_win_r  = float(pos_r.mean()) if len(pos_r) else 0
    avg_loss_r = float(neg_r.mean()) if len(neg_r) else 0
    expectancy = (win_rate * avg_win_r) + ((1 - win_rate) * avg_loss_r)

    return {
        "total_trades": total,
        "open_trades":  open_t,
        "closed_trades":closed_t,
        "win_rate":     win_rate,
        "total_pnl":    total_pnl,
        "expectancy":   float(expectancy),
        "avg_win_r":    avg_win_r,
        "avg_loss_r":   avg_loss_r,
    }


def last_sync_time():
    conn = get_conn()
    row = conn.execute("SELECT synced_at FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row["synced_at"] if row else None


def get_kpi_summary_extended():
    """Full KPI summary including streaks, drawdown, unrealised P&L."""
    base = get_kpi_summary()
    if not base:
        return {}

    conn = get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM trades").fetchall()]
    conn.close()

    df       = pd.DataFrame(rows)
    open_df  = df[df["status"] == "OPEN"].copy()
    closed_df = df[df["status"] == "CLOSED"].copy()

    # Unrealised P&L from open trades
    unrealised = 0.0
    for _, row in open_df.iterrows():
        try:
            ep  = float(row.get("entry_price") or 0)
            lp  = float(row.get("live_price") or 0)
            qty = float(row.get("qty") or 0)
            if ep and lp and qty:
                unrealised += (lp - ep) * qty
        except Exception:
            pass

    # Account balance from settings
    acct_bal = float(get_setting("account_balance", "10000000") or 10_000_000)
    total_pnl = base["total_pnl"]
    current_val = acct_bal + total_pnl

    # Peak value from max cumulative P&L
    if not closed_df.empty and "pnl" in closed_df.columns:
        closed_sorted = closed_df.sort_values("id")
        cum = closed_sorted["pnl"].fillna(0).cumsum()
        peak_value = float(acct_bal + cum.max()) if len(cum) else current_val
    else:
        peak_value = current_val

    drawdown_pct = (current_val - peak_value) / peak_value if peak_value else 0

    # Streaks
    losing_streak = 0
    consec_wins   = 0
    if not closed_df.empty:
        recent = closed_df.sort_values("id", ascending=False)
        for _, r in recent.iterrows():
            p = r.get("pnl") or 0
            if p < 0:
                losing_streak += 1
            else:
                break
        for _, r in recent.iterrows():
            p = r.get("pnl") or 0
            if p > 0:
                consec_wins += 1
            else:
                break

    base.update({
        "unrealised_pnl": unrealised,
        "peak_value":     peak_value,
        "drawdown_pct":   drawdown_pct,
        "losing_streak":  losing_streak,
        "consec_wins":    consec_wins,
        "realised_roce":  total_pnl / acct_bal if acct_bal else 0,
        "account_balance":acct_bal,
    })
    return base


def import_trading_journal(excel_path=None):
    """Import Trading Journal sheet into trading_journal table."""
    path = excel_path or EXCEL_PATH
    if not Path(path).exists():
        return 0, "Excel file not found"
    try:
        df = pd.read_excel(path, sheet_name="Trading Journal", header=None)
    except Exception as e:
        return 0, str(e)

    COL = {
        "week": 0, "no": 2, "entry_date": 3, "side": 4, "qty": 5,
        "ticker": 6, "strategy": 7, "entry_price": 8, "stop_loss": 9,
        "take_profit": 10, "commission_entry": 11, "one_r": 12,
        "position_size": 13, "max_profit": 14, "max_loss": 15,
        "risk_pct": 16, "max_rr": 17, "exit_date": 18, "exit_qty": 19,
        "exit_price": 20, "commission_exit": 21, "duration": 22,
        "r_multiple": 23, "pnl": 24, "cumulative_pnl": 25,
        "win_loss": 26, "status": 27, "account_balance": 28,
        "gain_loss_pct": 29, "drawdown": 30, "remarks": 32,
    }

    data_df = df.iloc[3:].reset_index(drop=True)
    conn = get_conn()
    conn.execute("DELETE FROM trading_journal")
    imported = 0

    for _, row in data_df.iterrows():
        vals = list(row)
        status = str(vals[COL["status"]] or "").strip().upper()
        if status not in ("OPEN", "CLOSED"):
            continue
        trade_no = _safe_int(vals[COL["no"]])
        if trade_no is None:
            continue
        try:
            r = {
                "week_number":      _safe_int(vals[COL["week"]]),
                "trade_no":         trade_no,
                "entry_date":       _parse_date(vals[COL["entry_date"]]),
                "side":             str(vals[COL["side"]] or "Buy").strip(),
                "qty":              _safe_float(vals[COL["qty"]]),
                "ticker":           str(vals[COL["ticker"]] or "").strip(),
                "strategy":         str(vals[COL["strategy"]] or "").strip(),
                "entry_price":      _safe_float(vals[COL["entry_price"]]),
                "stop_loss":        _safe_float(vals[COL["stop_loss"]]),
                "take_profit":      _safe_float(vals[COL["take_profit"]]),
                "commission_entry": _safe_float(vals[COL["commission_entry"]]),
                "one_r":            _safe_float(vals[COL["one_r"]]),
                "position_size":    _safe_float(vals[COL["position_size"]]),
                "max_profit":       _safe_float(vals[COL["max_profit"]]),
                "max_loss":         _safe_float(vals[COL["max_loss"]]),
                "risk_pct_trade":   _safe_float(vals[COL["risk_pct"]]),
                "max_rr":           _safe_float(vals[COL["max_rr"]]),
                "exit_date":        _parse_date(vals[COL["exit_date"]]),
                "exit_qty":         _safe_float(vals[COL["exit_qty"]]),
                "exit_price":       _safe_float(vals[COL["exit_price"]]),
                "commission_exit":  _safe_float(vals[COL["commission_exit"]]),
                "duration":         str(vals[COL["duration"]] or "").strip(),
                "r_multiple":       _safe_float(vals[COL["r_multiple"]]),
                "pnl":              _safe_float(vals[COL["pnl"]]),
                "cumulative_pnl":   _safe_float(vals[COL["cumulative_pnl"]]),
                "win_loss":         str(vals[COL["win_loss"]] or "").strip(),
                "status":           status,
                "account_balance":  _safe_float(vals[COL["account_balance"]]),
                "gain_loss_pct":    _safe_float(vals[COL["gain_loss_pct"]]),
                "drawdown":         _safe_float(vals[COL["drawdown"]]),
                "remarks":          str(vals[COL["remarks"]] or "").strip(),
            }
            cols = list(r.keys())
            conn.execute(
                f"INSERT INTO trading_journal ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})",
                [r[c] for c in cols]
            )
            imported += 1
        except Exception:
            continue

    conn.execute(
        "INSERT INTO sync_log (rows_imported, notes) VALUES (?, ?)",
        (imported, "Imported from Trading Journal sheet")
    )
    conn.commit()
    conn.close()
    return imported, "OK"


def get_journal_trades(status=None, strategy=None, ticker=None,
                        win_loss=None, date_from=None, date_to=None,
                        week=None):
    """Merges Excel-imported trading_journal with manually-added trades,
    so trades added in Daily Plan automatically appear in Trading Journal."""
    conn = get_conn()

    # 1. Excel-imported journal rows
    q = "SELECT * FROM trading_journal WHERE 1=1"
    params = []
    if status and status != "All":
        q += " AND status=?"; params.append(status)
    if strategy and strategy != "All":
        q += " AND strategy=?"; params.append(strategy)
    if ticker:
        q += " AND ticker LIKE ?"; params.append(f"%{ticker.upper()}%")
    if win_loss and win_loss != "All":
        q += " AND win_loss=?"; params.append(win_loss)
    if date_from:
        q += " AND entry_date >= ?"; params.append(str(date_from))
    if date_to:
        q += " AND entry_date <= ?"; params.append(str(date_to))
    if week:
        q += " AND week_number=?"; params.append(week)
    q += " ORDER BY trade_no ASC"
    journal_rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    journal_trade_nos = {r["trade_no"] for r in journal_rows}

    # 2. Manually-added trades not already covered by journal
    q2 = "SELECT * FROM trades WHERE 1=1"
    p2 = []
    if status and status != "All":
        q2 += " AND status=?"; p2.append(status)
    if strategy and strategy != "All":
        q2 += " AND strategy=?"; p2.append(strategy)
    if ticker:
        q2 += " AND ticker LIKE ?"; p2.append(f"%{ticker.upper()}%")
    if date_from:
        q2 += " AND entry_date >= ?"; p2.append(str(date_from))
    if date_to:
        q2 += " AND entry_date <= ?"; p2.append(str(date_to))
    q2 += " ORDER BY trade_no ASC"
    manual_rows = [dict(r) for r in conn.execute(q2, p2).fetchall()]

    # Running totals starting from end of journal rows
    last_cum = float(journal_rows[-1]["cumulative_pnl"] or 0) if journal_rows else 0.0
    last_bal = float(journal_rows[-1]["account_balance"] or 10_000_000) if journal_rows else 10_000_000.0

    extra = []
    for t in manual_rows:
        if t["trade_no"] in journal_trade_nos:
            continue  # already in journal from Excel
        pnl = float(t.get("pnl") or 0)
        last_cum += pnl
        last_bal += pnl
        r = float(t.get("r_multiple") or 0)
        wl = ("WIN" if pnl > 0 else "LOSS") if t["status"] == "CLOSED" else ""
        if win_loss and win_loss != "All" and wl != win_loss:
            continue
        extra.append({
            "id":               t.get("id"),
            "week_number":      None,
            "trade_no":         t.get("trade_no"),
            "entry_date":       t.get("entry_date"),
            "side":             t.get("side"),
            "qty":              t.get("qty"),
            "ticker":           t.get("ticker"),
            "strategy":         t.get("strategy"),
            "entry_price":      t.get("entry_price"),
            "stop_loss":        t.get("stop_loss"),
            "take_profit":      t.get("take_profit"),
            "commission_entry": t.get("commission_entry"),
            "one_r":            None,
            "position_size":    float(t.get("entry_price") or 0) * float(t.get("qty") or 0),
            "max_profit":       None,
            "max_loss":         None,
            "risk_pct_trade":   None,
            "max_rr":           None,
            "exit_date":        t.get("exit_date"),
            "exit_qty":         t.get("exit_qty"),
            "exit_price":       t.get("exit_price"),
            "commission_exit":  t.get("commission_exit"),
            "duration":         None,
            "r_multiple":       r,
            "pnl":              pnl,
            "cumulative_pnl":   last_cum,
            "win_loss":         wl,
            "status":           t.get("status"),
            "account_balance":  last_bal,
            "gain_loss_pct":    None,
            "drawdown":         None,
            "remarks":          t.get("notes"),
        })

    conn.close()
    all_trades = journal_rows + extra
    all_trades.sort(key=lambda x: (x.get("trade_no") or 0))
    return all_trades


# ── Notebook / Notes ─────────────────────────────────────────────────────────
def get_all_notes():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM trade_notes ORDER BY note_date DESC, updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_note_by_date(note_date: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM trade_notes WHERE note_date=? ORDER BY updated_at DESC LIMIT 1",
        (note_date,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def save_note(note_date: str, title: str, content: str, template: str = ""):
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM trade_notes WHERE note_date=?", (note_date,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE trade_notes SET title=?, content=?, template=?, updated_at=datetime('now','localtime') WHERE note_date=?",
            (title, content, template, note_date)
        )
    else:
        conn.execute(
            "INSERT INTO trade_notes (note_date, title, content, template) VALUES (?,?,?,?)",
            (note_date, title, content, template)
        )
    conn.commit(); conn.close()

def delete_note(note_date: str):
    conn = get_conn()
    conn.execute("DELETE FROM trade_notes WHERE note_date=?", (note_date,))
    conn.commit(); conn.close()

def get_trade_note(trade_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM trade_notes_per_trade WHERE trade_id=? ORDER BY created_at DESC LIMIT 1",
        (trade_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def save_trade_note(trade_id: int, ticker: str, note: str):
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM trade_notes_per_trade WHERE trade_id=?", (trade_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE trade_notes_per_trade SET note=?, created_at=datetime('now','localtime') WHERE trade_id=?",
            (note, trade_id)
        )
    else:
        conn.execute(
            "INSERT INTO trade_notes_per_trade (trade_id, ticker, note) VALUES (?,?,?)",
            (trade_id, ticker, note)
        )
    conn.commit(); conn.close()


# ── Playbook CRUD ─────────────────────────────────────────────────────────────
def get_playbooks():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM playbooks ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_playbook(pb_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM playbooks WHERE id=?", (pb_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_playbook(name, emoji, color, description):
    conn = get_conn()
    cur = conn.execute("INSERT INTO playbooks (name,emoji,color,description) VALUES (?,?,?,?)",
                       (name, emoji, color, description))
    pb_id = cur.lastrowid
    conn.commit(); conn.close()
    return pb_id

def update_playbook(pb_id, name, emoji, color, description):
    conn = get_conn()
    conn.execute("UPDATE playbooks SET name=?,emoji=?,color=?,description=? WHERE id=?",
                 (name, emoji, color, description, pb_id))
    conn.commit(); conn.close()

def delete_playbook(pb_id):
    conn = get_conn()
    conn.execute("DELETE FROM playbooks WHERE id=?", (pb_id,))
    conn.execute("DELETE FROM playbook_rules WHERE playbook_id=?", (pb_id,))
    conn.execute("DELETE FROM trade_playbooks WHERE playbook_id=?", (pb_id,))
    conn.execute("DELETE FROM missed_trades WHERE playbook_id=?", (pb_id,))
    conn.commit(); conn.close()

def get_playbook_rules(pb_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM playbook_rules WHERE playbook_id=? ORDER BY rule_type,id", (pb_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_playbook_rules(pb_id, rules):
    """rules = list of {rule_type, rule_text, show_when}"""
    conn = get_conn()
    conn.execute("DELETE FROM playbook_rules WHERE playbook_id=?", (pb_id,))
    for r in rules:
        conn.execute("INSERT INTO playbook_rules (playbook_id,rule_type,rule_text,show_when) VALUES (?,?,?,?)",
                     (pb_id, r['rule_type'], r['rule_text'], r.get('show_when','always')))
    conn.commit(); conn.close()

def _resolve_trade_no(conn, trade_id):
    """trade_playbooks stores trade_no (sequential), not trades.id (autoincrement).
    Given a trades.id, return the corresponding trade_no for consistent lookups."""
    row = conn.execute("SELECT trade_no FROM trades WHERE id=?", (trade_id,)).fetchone()
    if row and row[0] is not None:
        return row[0]
    # Fallback: trade_id may already be a trade_no (e.g. legacy data)
    return trade_id

def get_trade_playbook(trade_id):
    conn = get_conn()
    trade_no = _resolve_trade_no(conn, trade_id)
    row = conn.execute(
        "SELECT * FROM trade_playbooks WHERE trade_id=? ORDER BY id DESC LIMIT 1",
        (trade_no,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def save_trade_playbook(trade_id, pb_id, rules_followed):
    import json
    conn = get_conn()
    trade_no = _resolve_trade_no(conn, trade_id)
    existing = conn.execute("SELECT id FROM trade_playbooks WHERE trade_id=?", (trade_no,)).fetchone()
    if existing:
        conn.execute("UPDATE trade_playbooks SET playbook_id=?,rules_followed=? WHERE trade_id=?",
                     (pb_id, json.dumps(rules_followed), trade_no))
    else:
        conn.execute("INSERT INTO trade_playbooks (trade_id,playbook_id,rules_followed) VALUES (?,?,?)",
                     (trade_no, pb_id, json.dumps(rules_followed)))
    conn.commit(); conn.close()

def get_missed_trades(pb_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM missed_trades WHERE playbook_id=? ORDER BY trade_date DESC", (pb_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_missed_trade(pb_id, ticker, trade_date, entry_price, exit_price, qty, notes):
    conn = get_conn()
    conn.execute("INSERT INTO missed_trades (playbook_id,ticker,trade_date,entry_price,exit_price,qty,notes) VALUES (?,?,?,?,?,?,?)",
                 (pb_id, ticker, trade_date, entry_price, exit_price, qty, notes))
    conn.commit(); conn.close()

def delete_missed_trade(mt_id):
    conn = get_conn()
    conn.execute("DELETE FROM missed_trades WHERE id=?", (mt_id,))
    conn.commit(); conn.close()
