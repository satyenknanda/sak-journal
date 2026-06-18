# -*- coding: utf-8 -*-
import streamlit as st
import plotly.graph_objects as go
import json, os, sqlite3
from datetime import date, datetime, timedelta
from collections import defaultdict

from theme import *
from data.db import get_trades, get_strategies, delete_trade, get_kpi_summary_extended as get_kpi, get_setting
from components.trade_modals import render_add_trade_modal, render_exit_trade_modal, render_edit_trade_modal

G = "#10B981"; R = "#EF4444"; B = "#3B82F6"; AM = "#F59E0B"
TEXT = "#111827"; MUTED = "#6B7280"; DIM = "#D1D5DB"
BG = "#FFFFFF"; BORDER = "#E5E7EB"; HEADER_BG = "#F9FAFB"
ROW_WIN = "#F0FDF4"; ROW_LOSS = "#FEF2F2"; ROW_OPEN = "#EFF6FF"

# ── Daily notes DB helpers ────────────────────────────────────────────────────
_DJ_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "journal.db"))

def _init_notes_table():
    conn = sqlite3.connect(_DJ_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        note_date TEXT UNIQUE,
        note TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    conn.commit(); conn.close()

def _get_note(d_str):
    try:
        conn = sqlite3.connect(_DJ_DB); conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT note FROM daily_notes WHERE note_date=?", (d_str,)).fetchone()
        conn.close()
        return row["note"] if row else ""
    except: return ""

def _save_note(d_str, text):
    conn = sqlite3.connect(_DJ_DB)
    conn.execute("""INSERT INTO daily_notes (note_date, note, updated_at) VALUES (?,?,datetime('now','localtime'))
        ON CONFLICT(note_date) DO UPDATE SET note=excluded.note, updated_at=excluded.updated_at""",
        (d_str, text))
    conn.commit(); conn.close()

def _has_note(d_str):
    return bool(_get_note(d_str).strip())

# ── Dialogs ───────────────────────────────────────────────────────────────────
@st.dialog("Add Trade", width="large")
def add_trade_dialog(): render_add_trade_modal()

@st.dialog("Edit Trade", width="large")
def edit_trade_dialog(trade): render_edit_trade_modal(trade)

@st.dialog("Exit Trade", width="large")
def exit_trade_dialog(trade): render_exit_trade_modal(trade)

@st.dialog("Daily Log", width="large")
def daily_log_dialog(d_str, day_trades, day_pnl):
    """TradeZella-style Daily Log popup with stats and notes editor."""
    try: d_label = datetime.strptime(d_str, "%Y-%m-%d").strftime("%a, %b %d, %Y")
    except: d_label = d_str
    pnl_col = G if day_pnl >= 0 else R

    # Header
    st.markdown(f"""<div style="margin-bottom:12px">
        <span style="font-size:15px;font-weight:700;color:{TEXT}">{d_label}</span>
        &nbsp;&nbsp;
        <span style="font-size:14px;font-weight:700;color:{pnl_col}">Net P&L {'+'if day_pnl>=0 else ''}₹{abs(day_pnl):,.0f}</span>
    </div>""", unsafe_allow_html=True)

    if day_trades:
        # Intraday chart
        sorted_t = sorted(day_trades, key=lambda x: str(x.get("exit_date") or x.get("entry_date") or ""))
        cum = 0; xs=[]; ys=[]
        for t in sorted_t:
            cum += float(t.get("pnl") or 0)
            xs.append(str(t.get("exit_date") or t.get("entry_date") or "")[:16])
            ys.append(cum)
        if xs:
            fc = "rgba(16,185,129,0.15)" if day_pnl>=0 else "rgba(239,68,68,0.15)"
            fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines",
                line=dict(color=pnl_col, width=2), fill="tozeroy", fillcolor=fc,
                hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"))
            fig.update_layout(height=160, margin=dict(l=50,r=10,t=5,b=30),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, color=MUTED, tickfont=dict(size=9)),
                yaxis=dict(showgrid=True, gridcolor=BORDER, color=MUTED,
                           tickprefix="₹", tickfont=dict(size=9)), showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

        # Stats grid
        n = len(day_trades)
        wins = sum(1 for t in day_trades if (t.get("pnl") or 0) > 0)
        losses = sum(1 for t in day_trades if (t.get("pnl") or 0) < 0)
        wr = wins/n if n else 0
        gross = sum(float(t.get("pnl") or 0) for t in day_trades)
        comm = sum(float(t.get("commission_entry") or 0)+float(t.get("commission_exit") or 0) for t in day_trades)
        vol = sum(int(t.get("qty") or 0) for t in day_trades)
        winners_pnl = [float(t.get("pnl") or 0) for t in day_trades if (t.get("pnl") or 0)>0]
        losers_pnl  = [float(t.get("pnl") or 0) for t in day_trades if (t.get("pnl") or 0)<0]
        pf = abs(sum(winners_pnl)/sum(losers_pnl)) if losers_pnl and sum(losers_pnl)!=0 else 0

        st.markdown(f"""<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:{BORDER};border-radius:8px;overflow:hidden;margin-bottom:14px">
            {"".join(f'<div style="background:{BG};padding:10px 14px"><div style="font-size:10px;color:{MUTED};margin-bottom:3px">{lbl}</div><div style="font-size:14px;font-weight:700;color:{TEXT}">{val}</div></div>'
                for lbl,val in [
                    ("Total Trades", str(n)), ("Winners", str(wins)), ("Gross P&L", f"{'+'if gross>=0 else ''}₹{abs(gross):,.0f}"),
                    ("Win Rate", f"{wr*100:.1f}%"), ("Losers", str(losses)), ("Commissions", f"₹{comm:,.0f}"),
                    ("Volume", str(vol)), ("Profit Factor", f"{pf:.2f}"), ("", ""),
                ])}
        </div>""", unsafe_allow_html=True)

    # Notes editor
    st.markdown(f'<div style="font-size:11px;color:{MUTED};margin-bottom:6px">📝 Notes & Lessons Learned</div>', unsafe_allow_html=True)
    existing_note = _get_note(d_str)
    note_text = st.text_area(
        "Notes", value=existing_note, height=200,
        placeholder="Enter some text...\n\nDocument your lessons learned, market observations, emotional state, or anything relevant about today's trading session.",
        label_visibility="collapsed", key=f"note_ta_{d_str}"
    )

    sc1, sc2 = st.columns([3,1])
    with sc2:
        if st.button("💾 Save", type="primary", use_container_width=True, key=f"note_save_{d_str}"):
            _save_note(d_str, note_text)
            st.success("Note saved!"); st.rerun()

@st.dialog("Log Day", width="small")
def log_day_dialog():
    """Log a note for any day — even without trades."""
    st.markdown("Select a date to log notes for:")
    sel_date = st.date_input("Date", value=date.today(), label_visibility="collapsed", key="log_day_date")
    d_str = sel_date.isoformat()
    existing = _get_note(d_str)
    note = st.text_area("Notes", value=existing, height=180,
                         placeholder="Enter notes, observations, plan for the day...",
                         label_visibility="collapsed", key="log_day_note")
    sc1, sc2 = st.columns([1,1])
    with sc1:
        if st.button("Cancel", use_container_width=True, key="log_day_cancel"): st.rerun()
    with sc2:
        if st.button("💾 Save", type="primary", use_container_width=True, key="log_day_save"):
            _save_note(d_str, note)
            st.success(f"Saved for {d_str}!"); st.rerun()

def _p(v, d=2):
    try: f=float(v); return f"₹{f:,.{d}f}" if f else "—"
    except: return "—"

def _pct(v):
    try: f=float(v); return f"{'+'if f>0 else ''}{f:.2f}%"
    except: return "—"

def pnl_chip(pnl, r_mult=None):
    if pnl is None or pnl==0: return '<span style="color:#9CA3AF">—</span>'
    color=G if pnl>0 else R; bg="#F0FDF4" if pnl>0 else "#FEF2F2"
    r_str=f'<span style="font-size:0.68rem;opacity:0.75;margin-left:3px">({r_mult:+.1f}R)</span>' if r_mult else ""
    return f'<span style="background:{bg};color:{color};padding:2px 8px;border-radius:12px;font-size:0.78rem;font-weight:700;border:1px solid {color}22">{"+" if pnl>0 else ""}₹{abs(pnl):,.0f}{r_str}</span>'

def status_chip(status, risk_status=""):
    if status=="OPEN":
        label=risk_status if risk_status else "OPEN"
        if "SL Breached" in label: bg,fg="#FEF2F2",R
        elif "In Profits" in label: bg,fg="#F0FDF4",G
        else: bg,fg="#EFF6FF",B
    else: bg,fg="#F3F4F6",MUTED; label="CLOSED"
    return f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:20px;font-size:0.7rem;font-weight:600;border:1px solid {fg}22">{label}</span>'

def generate_insights(day_trades, day_pnl, prev_trades=None):
    """Generate TradeZella-style insights for a trading day."""
    insights = []
    if not day_trades: return insights

    wins = [t for t in day_trades if (t.get("pnl") or 0) > 0]
    losses = [t for t in day_trades if (t.get("pnl") or 0) < 0]
    win_pnls = [float(t.get("pnl") or 0) for t in wins]
    loss_pnls = [float(t.get("pnl") or 0) for t in losses]
    wr = len(wins)/len(day_trades) if day_trades else 0
    n = len(day_trades)
    avg_win = sum(win_pnls)/len(win_pnls) if win_pnls else 0
    avg_loss = sum(loss_pnls)/len(loss_pnls) if loss_pnls else 0

    # 1. High conviction day
    if n == 1 and day_pnl > 0:
        r = float(day_trades[0].get("r_multiple") or 0)
        insights.append({"type":"positive","title":"High Conviction Day",
            "desc":f"You placed just 1 trade today and nailed it with {r:.1f}R and ₹{day_pnl:,.0f} in profit. High-precision execution."})

    # 2. Average loss exceeds average win
    if win_pnls and loss_pnls and abs(avg_loss) > avg_win and wr > 0.5:
        insights.append({"type":"warning","title":"Avg Loss Exceeds Avg Win",
            "desc":f"High win rate ({wr*100:.0f}%) but your avg loss ₹{abs(avg_loss):,.0f} exceeds avg win ₹{avg_win:,.0f}. Strategy may not be profitable long-term."})

    # 3. Overtrading
    if prev_trades is not None:
        prev_30 = [t for t in prev_trades if t.get("exit_date")]
        if len(prev_30) > 0:
            avg_daily = len(prev_30) / 30 if len(prev_30) > 0 else 1
            if n > avg_daily * 2 and avg_daily > 0:
                insights.append({"type":"warning","title":"Overtrading Day",
                    "desc":f"You placed {n} trades today — {(n/avg_daily-1)*100:.0f}% over your 30-day average ({avg_daily:.1f}). Quality over quantity."})

    # 4. Revenge trading
    sorted_t = sorted(day_trades, key=lambda x: str(x.get("entry_date") or ""))
    for i in range(1, len(sorted_t)):
        if (sorted_t[i-1].get("pnl") or 0) < 0 and (sorted_t[i].get("pnl") or 0) < 0:
            insights.append({"type":"danger","title":"Possible Revenge Trading",
                "desc":f"A losing trade was followed quickly by another loss. Consider a cooling-off period after losses."})
            break

    # 5. Green to red (if we have MAE/MFE data)
    for t in day_trades:
        mae = float(t.get("mae") or 0)
        mfe = float(t.get("mfe") or 0)
        pnl = float(t.get("pnl") or 0)
        if mfe > 0 and pnl < 0:
            insights.append({"type":"danger","title":"Green to Red Trade",
                "desc":f"You were up ₹{mfe:,.0f} on {t.get('ticker','')} but ended with a loss of ₹{abs(pnl):,.0f}. Consider locking in profits earlier."})

    # 6. Perfect day
    if wins and not losses and n <= 3:
        insights.append({"type":"positive","title":"Perfect Day",
            "desc":f"Clean execution — all {n} trade{'s' if n>1 else ''} closed green with no losses. This is your gold standard."})

    # 7. Flip flop
    sides = [str(t.get("side","")).upper() for t in day_trades]
    if len(set(sides)) > 1 and n >= 3:
        if day_pnl > 0:
            insights.append({"type":"neutral","title":"Flip Flop Day — Positive",
                "desc":f"Green day, but you switched between LONG and SHORT. Could you have caught the main move more cleanly?"})
        else:
            insights.append({"type":"warning","title":"Flip Flop Day — Negative",
                "desc":f"You ended red and traded both sides multiple times. Lack of directional conviction — wait for clearer setups."})

    return insights[:4]  # max 4 insights per day

@st.dialog("Intraday Cumulative Net P&L", width="large")
def intraday_chart_dialog(day_trades, day_pnl):
    """Full-screen intraday P&L chart popup like TradeZella."""
    sorted_t = sorted(day_trades, key=lambda x: str(x.get("exit_date") or x.get("entry_date") or ""))
    cumulative = 0; xs = []; ys = []; labels = []
    for i, t in enumerate(sorted_t):
        p = float(t.get("pnl") or 0)
        cumulative += p
        ticker = t.get("ticker","") or ""
        # Use trade number as X if timestamps are just dates
        ts = str(t.get("exit_date") or t.get("entry_date") or "")
        label = f"{ticker} Trade {i+1}: ₹{cumulative:,.0f}"
        xs.append(f"Trade {i+1}\n{ticker}")
        ys.append(cumulative)
        labels.append(label)

    if not xs:
        st.info("No trade data for this day."); return

    color = G if day_pnl >= 0 else R
    fc = "rgba(16,185,129,0.12)" if day_pnl >= 0 else "rgba(239,68,68,0.12)"

    # Add starting point at 0
    xs_full = ["Start"] + xs
    ys_full = [0] + ys
    labels_full = ["Start: ₹0"] + labels

    fig = go.Figure()
    # Fill area
    fig.add_trace(go.Scatter(
        x=xs_full, y=ys_full, mode="lines+markers",
        line=dict(color="#4338CA", width=2.5),
        marker=dict(color="#4338CA", size=7, symbol="circle"),
        fill="tozeroy",
        fillcolor=fc,
        text=labels_full,
        hovertemplate="%{text}<extra></extra>"
    ))
    # Zero line
    fig.add_hline(y=0, line=dict(color=BORDER, width=1))

    fig.update_layout(
        height=400,
        margin=dict(l=70, r=20, t=30, b=50),
        paper_bgcolor=BG, plot_bgcolor=BG,
        title=dict(text="INTRADAY CUMULATIVE NET P&L", font=dict(size=11, color=MUTED), x=0),
        xaxis=dict(showgrid=True, gridcolor=BORDER, color=MUTED,
                   tickfont=dict(size=10), zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=BORDER, color=MUTED,
                   tickprefix="₹", tickfont=dict(size=10), zeroline=False),
        showlegend=False, hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Trade breakdown
    st.markdown(f'<div style="font-size:10px;font-weight:600;color:{MUTED};margin:8px 0 4px;letter-spacing:1px">TRADE BREAKDOWN</div>', unsafe_allow_html=True)
    cum2 = 0
    for i, t in enumerate(sorted_t):
        p = float(t.get("pnl") or 0); cum2 += p
        pc = G if p >= 0 else R
        st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;
            padding:7px 10px;border-bottom:1px solid {BORDER};font-size:12px;background:{'#F0FDF4' if p>=0 else '#FEF2F2' if p<0 else BG}">
            <span style="font-weight:700;color:{TEXT};min-width:80px">{t.get('ticker','')}</span>
            <span style="color:{MUTED}">{t.get('strategy','')}</span>
            <span style="color:{pc};font-weight:700">{'+'if p>=0 else ''}₹{abs(p):,.0f}</span>
            <span style="color:{MUTED};font-size:11px">Cum: <b style="color:{G if cum2>=0 else R}">{'+'if cum2>=0 else ''}₹{abs(cum2):,.0f}</b></span>
        </div>""", unsafe_allow_html=True)

def intraday_chart(day_trades, height=160):
    """Mini intraday cumulative P&L chart."""
    sorted_t = sorted(day_trades, key=lambda x: str(x.get("exit_date") or x.get("entry_date") or ""))
    cumulative = 0; xs = []; ys = []; labels = []
    for i, t in enumerate(sorted_t):
        p = float(t.get("pnl") or 0)
        cumulative += p
        ticker = t.get("ticker","") or ""
        xs.append(f"Trade {i+1}\n{ticker}")
        ys.append(cumulative)
        labels.append(f"{ticker}: ₹{cumulative:,.0f}")
    if not xs: return None

    xs_full = ["Start"] + xs
    ys_full = [0] + ys
    labels_full = ["₹0"] + labels

    color = G if ys[-1] >= 0 else R
    fc = "rgba(16,185,129,0.12)" if ys[-1] >= 0 else "rgba(239,68,68,0.12)"

    fig = go.Figure(go.Scatter(
        x=xs_full, y=ys_full, mode="lines+markers",
        line=dict(color="#4338CA", width=2),
        marker=dict(color="#4338CA", size=5),
        fill="tozeroy", fillcolor=fc,
        text=labels_full,
        hovertemplate="%{text}<extra></extra>"
    ))
    fig.add_hline(y=0, line=dict(color=BORDER, width=1))
    fig.update_layout(
        height=height, margin=dict(l=50, r=10, t=5, b=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color=MUTED, tickfont=dict(size=8), zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=BORDER, color=MUTED,
                   tickprefix="₹", tickfont=dict(size=8), zeroline=False),
        showlegend=False
    )
    return fig

def mini_calendar(trades_by_date, selected_month, selected_year):
    """Mini calendar sidebar showing green/red days."""
    import calendar
    cal = calendar.monthcalendar(selected_year, selected_month)
    month_name = datetime(selected_year, selected_month, 1).strftime("%B %Y")

    html = f"""<div style="background:#fff;border:1px solid {BORDER};border-radius:10px;padding:12px;margin-bottom:12px">
    <div style="font-size:12px;font-weight:700;color:{TEXT};text-align:center;margin-bottom:8px">{month_name}</div>
    <table style="width:100%;border-collapse:collapse;font-size:10px;text-align:center">
    <tr>{"".join(f'<th style="color:{MUTED};padding:2px;font-weight:600">{d}</th>' for d in ["S","M","T","W","T","F","S"])}</tr>"""

    for week in cal:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += '<td style="padding:3px"></td>'
            else:
                d_str = f"{selected_year}-{selected_month:02d}-{day:02d}"
                pnl = trades_by_date.get(d_str)
                today_str = date.today().isoformat()
                if pnl is not None:
                    bg = "#16A34A" if pnl > 0 else "#DC2626"
                    html += f'<td style="padding:2px"><div style="width:22px;height:22px;background:{bg};border-radius:50%;display:flex;align-items:center;justify-content:center;margin:auto;color:white;font-weight:700;font-size:9px">{day}</div></td>'
                elif d_str == today_str:
                    html += f'<td style="padding:2px"><div style="width:22px;height:22px;border:2px solid {B};border-radius:50%;display:flex;align-items:center;justify-content:center;margin:auto;color:{B};font-weight:700;font-size:9px">{day}</div></td>'
                else:
                    html += f'<td style="padding:2px"><div style="width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:auto;color:{MUTED};font-size:9px">{day}</div></td>'
        html += "</tr>"
    html += "</table></div>"
    return html

def render():
    _init_notes_table()
    st.markdown("## Daily Journal")
    st.markdown(f'<p style="color:{MUTED};margin-top:-10px;margin-bottom:14px;font-size:0.88rem">FY 2026-27 · NSE Equity · Day-by-day trade log</p>', unsafe_allow_html=True)

    # ── Top bar ───────────────────────────────────────────────────────────────
    tb1, tb2, tb3, tb4, tb5 = st.columns([1.5, 1.5, 1.5, 1, 1])
    with tb1:
        date_from = st.date_input("From", value=date(2026,4,1), label_visibility="collapsed", key="dj_from")
    with tb2:
        date_to = st.date_input("To", value=date.today(), label_visibility="collapsed", key="dj_to")
    with tb3:
        strats = ["All"] + get_strategies()
        strat_f = st.selectbox("Strategy", strats, label_visibility="collapsed", key="dj_strat")
    with tb4:
        if st.button("＋ Log Day", use_container_width=True, key="dj_log"):
            log_day_dialog()
    with tb5:
        if st.button("＋ Add Trade", type="primary", use_container_width=True, key="dj_add"):
            add_trade_dialog()

    if st.session_state.pop("show_add_trade", False):
        add_trade_dialog()

    # ── Load trades ───────────────────────────────────────────────────────────
    all_trades = get_trades(strategy=strat_f if strat_f != "All" else "All",
                            date_from=date_from, date_to=date_to)
    closed = [t for t in all_trades if t.get("status") == "CLOSED"]

    # Group by exit date
    by_date = defaultdict(list)
    for t in closed:
        d = str(t.get("exit_date") or "")[:10]
        if d and d != "nan": by_date[d].append(t)

    # Daily P&L for calendar
    daily_pnl_map = {d: sum(float(t.get("pnl") or 0) for t in ts) for d, ts in by_date.items()}

    dates_sorted = sorted(by_date.keys(), reverse=True)

    if not dates_sorted:
        st.info("No closed trades in selected range."); return

    # ── Layout: main content + sidebar ────────────────────────────────────────
    main_col, side_col = st.columns([3.5, 1])

    with side_col:
        # Mini calendar
        today = date.today()
        if "dj_cal_month" not in st.session_state: st.session_state.dj_cal_month = today.month
        if "dj_cal_year"  not in st.session_state: st.session_state.dj_cal_year  = today.year

        cn1, cn2, cn3 = st.columns([1,2,1])
        with cn1:
            if st.button("◀", key="dj_prev_mo"):
                if st.session_state.dj_cal_month == 1:
                    st.session_state.dj_cal_month = 12; st.session_state.dj_cal_year -= 1
                else: st.session_state.dj_cal_month -= 1
        with cn2:
            st.markdown(f'<div style="text-align:center;font-size:11px;font-weight:700;padding-top:6px">{datetime(st.session_state.dj_cal_year,st.session_state.dj_cal_month,1).strftime("%b %Y")}</div>', unsafe_allow_html=True)
        with cn3:
            if st.button("▶", key="dj_next_mo"):
                if st.session_state.dj_cal_month == 12:
                    st.session_state.dj_cal_month = 1; st.session_state.dj_cal_year += 1
                else: st.session_state.dj_cal_month += 1

        st.markdown(mini_calendar(daily_pnl_map, st.session_state.dj_cal_month, st.session_state.dj_cal_year), unsafe_allow_html=True)

        # Month summary
        mo_key = f"{st.session_state.dj_cal_year}-{st.session_state.dj_cal_month:02d}"
        mo_pnl = sum(v for d,v in daily_pnl_map.items() if d.startswith(mo_key))
        mo_days = sum(1 for d in daily_pnl_map if d.startswith(mo_key))
        mo_col = G if mo_pnl >= 0 else R
        st.markdown(f"""<div style="background:#F9FAFB;border:1px solid {BORDER};border-radius:8px;padding:10px;text-align:center;margin-bottom:10px">
            <div style="font-size:9px;color:{MUTED};letter-spacing:1px;margin-bottom:3px">MONTHLY P&L</div>
            <div style="font-size:18px;font-weight:800;color:{mo_col}">{'+'if mo_pnl>=0 else ''}₹{abs(mo_pnl):,.0f}</div>
            <div style="font-size:10px;color:{MUTED};margin-top:2px">{mo_days} trading days</div>
        </div>""", unsafe_allow_html=True)

        # Collapse / Expand all
        ce1, ce2 = st.columns(2)
        with ce1:
            if st.button("↑ Collapse All", use_container_width=True, key="dj_collapse"):
                for d in dates_sorted: st.session_state[f"dj_exp_{d}"] = False
        with ce2:
            if st.button("↓ Expand All", use_container_width=True, key="dj_expand"):
                for d in dates_sorted: st.session_state[f"dj_exp_{d}"] = True

    with main_col:
        for d_str in dates_sorted:
            day_trades = by_date[d_str]
            day_pnl = sum(float(t.get("pnl") or 0) for t in day_trades)
            day_wins = sum(1 for t in day_trades if (t.get("pnl") or 0) > 0)
            day_losses = sum(1 for t in day_trades if (t.get("pnl") or 0) < 0)
            n = len(day_trades)
            wr = day_wins/n if n else 0
            gross_pnl = sum(float(t.get("pnl") or 0) for t in day_trades)
            commissions = sum(float(t.get("commission_entry") or 0) + float(t.get("commission_exit") or 0) for t in day_trades)

            pnl_col = G if day_pnl >= 0 else R
            pnl_bg  = "#F0FDF4" if day_pnl >= 0 else "#FEF2F2"
            pnl_str = f"{'+'if day_pnl>=0 else ''}₹{abs(day_pnl):,.0f}"

            try: d_label = datetime.strptime(d_str, "%Y-%m-%d").strftime("%a, %b %d, %Y")
            except: d_label = d_str

            # Expand/collapse state
            exp_key = f"dj_exp_{d_str}"
            if exp_key not in st.session_state: st.session_state[exp_key] = False

            # Day header
            hc1, hc2, hc3, hc4 = st.columns([0.3, 3.5, 1.5, 1])
            with hc1:
                arrow = "▼" if st.session_state[exp_key] else "▶"
                if st.button(arrow, key=f"dj_tog_{d_str}"):
                    st.session_state[exp_key] = not st.session_state[exp_key]
                    st.rerun()
            with hc2:
                has_note = _has_note(d_str)
                note_dot = f' <span style="color:{B};font-size:10px" title="Has notes">📝</span>' if has_note else ""
                st.markdown(f'<div style="padding-top:6px;font-size:14px;font-weight:700;color:{TEXT}">{d_label}{note_dot}</div>', unsafe_allow_html=True)
            with hc3:
                st.markdown(f'<div style="padding-top:4px;text-align:right"><span style="font-size:15px;font-weight:800;color:{pnl_col}">Net P&L {pnl_str}</span></div>', unsafe_allow_html=True)
            with hc4:
                if st.button("✏️ Add Note", key=f"dj_note_{d_str}", use_container_width=True):
                    daily_log_dialog(d_str, day_trades, day_pnl)

            if st.session_state[exp_key]:
                # Intraday chart + stats
                chart_c, stats_c = st.columns([1.2, 2])
                with chart_c:
                    fig = intraday_chart(day_trades)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                        if st.button("⛶ Intraday Cumulative Net P&L", key=f"dj_expand_{d_str}",
                                     use_container_width=True):
                            intraday_chart_dialog(day_trades, day_pnl)

                with stats_c:
                    st.markdown(f"""<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:8px 0">
                        <div style="text-align:center;padding:8px;background:#F9FAFB;border-radius:8px;border:1px solid {BORDER}">
                            <div style="font-size:9px;color:{MUTED};margin-bottom:3px">TOTAL TRADES</div>
                            <div style="font-size:18px;font-weight:700;color:{TEXT}">{n}</div>
                        </div>
                        <div style="text-align:center;padding:8px;background:#F0FDF4;border-radius:8px;border:1px solid #BBF7D0">
                            <div style="font-size:9px;color:{MUTED};margin-bottom:3px">WINNERS</div>
                            <div style="font-size:18px;font-weight:700;color:{G}">{day_wins}</div>
                        </div>
                        <div style="text-align:center;padding:8px;background:#FEF2F2;border-radius:8px;border:1px solid #FECACA">
                            <div style="font-size:9px;color:{MUTED};margin-bottom:3px">LOSERS</div>
                            <div style="font-size:18px;font-weight:700;color:{R}">{day_losses}</div>
                        </div>
                        <div style="text-align:center;padding:8px;background:#F9FAFB;border-radius:8px;border:1px solid {BORDER}">
                            <div style="font-size:9px;color:{MUTED};margin-bottom:3px">WIN RATE</div>
                            <div style="font-size:18px;font-weight:700;color:{G if wr>=0.5 else AM}">{wr*100:.0f}%</div>
                        </div>
                        <div style="text-align:center;padding:8px;background:#F9FAFB;border-radius:8px;border:1px solid {BORDER}">
                            <div style="font-size:9px;color:{MUTED};margin-bottom:3px">GROSS P&L</div>
                            <div style="font-size:14px;font-weight:700;color:{pnl_col}">{'+'if gross_pnl>=0 else ''}₹{abs(gross_pnl):,.0f}</div>
                        </div>
                        <div style="text-align:center;padding:8px;background:#F9FAFB;border-radius:8px;border:1px solid {BORDER}">
                            <div style="font-size:9px;color:{MUTED};margin-bottom:3px">COMMISSIONS</div>
                            <div style="font-size:14px;font-weight:700;color:{TEXT}">₹{commissions:,.0f}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)

                # Insights
                insights = generate_insights(day_trades, day_pnl, closed)
                if insights:
                    ins_cols = st.columns(2)
                    for idx, ins in enumerate(insights):
                        ic = G if ins["type"]=="positive" else R if ins["type"]=="danger" else AM if ins["type"]=="warning" else MUTED
                        ib = "#F0FDF4" if ins["type"]=="positive" else "#FEF2F2" if ins["type"]=="danger" else "#FEF9C3" if ins["type"]=="warning" else "#F9FAFB"
                        emoji = "✅" if ins["type"]=="positive" else "🔴" if ins["type"]=="danger" else "⚠️" if ins["type"]=="warning" else "💡"
                        with ins_cols[idx % 2]:
                            st.markdown(f"""<div style="background:{ib};border:1px solid {ic}33;border-radius:8px;padding:10px 12px;margin-bottom:8px">
                                <div style="font-size:11px;font-weight:700;color:{ic};margin-bottom:4px">{emoji} {ins['title']}</div>
                                <div style="font-size:11px;color:{TEXT};line-height:1.5">{ins['desc']}</div>
                            </div>""", unsafe_allow_html=True)

                # Trade table
                th = f"padding:7px 10px;text-align:left;color:{MUTED};font-size:0.65rem;text-transform:uppercase;letter-spacing:0.07em;font-weight:600;white-space:nowrap;border-bottom:2px solid {BORDER};background:{HEADER_BG}"
                td_s = f"padding:7px 10px;font-size:0.8rem;white-space:nowrap;border-bottom:1px solid {BORDER}"
                rows = ""
                for t in sorted(day_trades, key=lambda x: str(x.get("entry_date") or "")):
                    pnl = float(t.get("pnl") or 0)
                    rb = ROW_WIN if pnl > 0 else ROW_LOSS if pnl < 0 else BG
                    r_mult = t.get("r_multiple")
                    rows += f"""<tr style="background:{rb}">
                        <td style="{td_s}">{status_chip(t.get('status',''), t.get('risk_status','') or '')}</td>
                        <td style="{td_s};font-weight:700;color:{TEXT}">{t.get('ticker','')}</td>
                        <td style="{td_s}">{t.get('strategy','') or '—'}</td>
                        <td style="{td_s}">{t.get('side','')}</td>
                        <td style="{td_s};font-family:monospace">{int(t.get('qty') or 0):,}</td>
                        <td style="{td_s};font-family:monospace">{_p(t.get('entry_price'))}</td>
                        <td style="{td_s};font-family:monospace;color:{R}">{_p(t.get('stop_loss'))}</td>
                        <td style="{td_s};font-family:monospace">{_p(t.get('exit_price')) if t.get('exit_price') else '—'}</td>
                        <td style="{td_s}">{pnl_chip(pnl, float(r_mult) if r_mult else None)}</td>
                        <td style="{td_s}">
                            <button onclick="" style="background:transparent;border:none;cursor:pointer;color:{MUTED};font-size:12px" title="Edit">✏️</button>
                        </td>
                    </tr>"""

                st.markdown(f"""<div style="overflow-x:auto;border-radius:8px;border:1px solid {BORDER};margin:8px 0 4px">
                <table style="width:100%;border-collapse:collapse">
                    <thead><tr>
                        {"".join(f'<th style="{th}">{h}</th>' for h in ["Status","Ticker","Strategy","Side","Qty","Entry ₹","Stop ₹","Exit ₹","P&L",""])}
                    </tr></thead>
                    <tbody>{rows}</tbody>
                </table></div>""", unsafe_allow_html=True)

                # Action row
                ac1, ac2, ac3 = st.columns([2, 2, 1])
                day_open = [t for t in day_trades if t.get("status")=="OPEN"]
                with ac1:
                    if day_open:
                        opts = [f"#{t['id']} {t['ticker']}" for t in day_open]
                        sel = st.selectbox("Exit", opts, key=f"exit_sel_{d_str}", label_visibility="collapsed")
                        if st.button("Exit →", key=f"exit_btn_{d_str}", type="primary"):
                            tid = int(sel.split("#")[1].split(" ")[0])
                            trade = next((t for t in day_open if t["id"]==tid), None)
                            if trade: exit_trade_dialog(trade)
                with ac2:
                    all_opts = [f"#{t['id']} {t['ticker']}" for t in day_trades]
                    if all_opts:
                        sel_e = st.selectbox("Edit", all_opts, key=f"edit_sel_{d_str}", label_visibility="collapsed")
                        if st.button("✏️ Edit", key=f"edit_btn_{d_str}"):
                            tid = int(sel_e.split("#")[1].split(" ")[0])
                            trade = next((t for t in day_trades if t["id"]==tid), None)
                            if trade: edit_trade_dialog(trade)
                with ac3:
                    if all_opts:
                        sel_d = st.selectbox("Del", all_opts, key=f"del_sel_{d_str}", label_visibility="collapsed")
                        if st.button("🗑", key=f"del_btn_{d_str}"):
                            tid = int(sel_d.split("#")[1].split(" ")[0])
                            delete_trade(tid); st.success("Deleted"); st.rerun()

            st.markdown(f'<hr style="border:none;border-top:1px solid {BORDER};margin:8px 0">', unsafe_allow_html=True)
