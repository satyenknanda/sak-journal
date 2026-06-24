import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from collections import defaultdict
import numpy as np
import calendar as cal_mod
import math, re
from datetime import date, timedelta, datetime
from data.db import get_journal_trades, get_kpi_summary_extended as get_kpi
from position_utils import combine_open_positions
from theme import *

# ── SVG helpers ──────────────────────────────────────────────────────────────
def svg_gauge(pct, color, size=80):
    pct = max(0.0, min(1.0, pct))
    cx = cy = size/2; r = size/2 - 7
    bg = f"M {cx-r},{cy} A {r},{r} 0 0,1 {cx+r},{cy}"
    if pct >= 0.999: val = f"M {cx-r},{cy} A {r},{r} 0 1,1 {cx+r-0.01},{cy}"
    elif pct <= 0.001: val = ""
    else:
        ex = cx + r*math.cos(math.pi*(1-pct))
        ey = cy - r*math.sin(math.pi*pct)
        val = f"M {cx-r},{cy} A {r},{r} 0 {1 if pct>0.5 else 0},1 {ex:.2f},{ey:.2f}"
    h = int(size/2) + 6
    return (f'<svg width="{size}" height="{h}" viewBox="0 0 {size} {h}">'
        f'<path d="{bg}" fill="none" stroke="#E2E8F0" stroke-width="7" stroke-linecap="round"/>'
        + (f'<path d="{val}" fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round"/>' if val else "")
        + f'</svg>')

def spark_svg(ys, color, w=160, h=36):
    if len(ys) < 2: return ""
    mn, mx = min(ys), max(ys); rng = mx-mn if mx != mn else 1
    pts = " ".join([f"{i/(len(ys)-1)*w:.1f},{(1-(y-mn)/rng)*(h-4)+2:.1f}" for i,y in enumerate(ys)])
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>')

def streak_circle(n, color, label, size=54):
    return (f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px">'
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;border:3px solid {color};'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:{size//3}px;font-weight:700;color:{color}">{n}</div>'
        f'<div style="font-size:9px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.05em">{label}</div>'
        f'</div>')

def fmt_k(v):
    if abs(v) >= 1_000_000: return f"₹{v/1_000_000:.1f}M"
    if abs(v) >= 1_000: return f"₹{v/1_000:.1f}K"
    return f"₹{v:,.0f}"


# ── Main render ──────────────────────────────────────────────────────────────
def render():
    trades  = get_journal_trades()
    open_t  = [t for t in trades if t["status"] == "OPEN"]
    kpi     = get_kpi()

    # FY 2026-27: Apr 1 2026 → Mar 31 2027
    FY_START = "2026-04-01"
    FY_END   = "2027-03-31"
    all_closed = [t for t in trades if t["status"] == "CLOSED"]
    closed  = [t for t in all_closed
               if FY_START <= str(t.get("exit_date","") or "")[:10] <= FY_END]

    acct    = float(kpi.get("account_balance", 10_000_000))
    wr      = float(kpi.get("win_rate", 0))
    pnl     = sum(float(t.get("pnl") or 0) for t in closed)

    win_pnls  = [float(t.get("pnl") or 0) for t in closed if float(t.get("pnl") or 0) > 0]
    loss_pnls = [float(t.get("pnl") or 0) for t in closed if float(t.get("pnl") or 0) < 0]
    # Recalculate win rate from FY data
    wr = len(win_pnls)/len(closed) if closed else 0
    avg_win   = float(np.mean(win_pnls))  if win_pnls  else 0
    avg_loss  = float(np.mean(loss_pnls)) if loss_pnls else 0
    pf        = abs(sum(win_pnls)/sum(loss_pnls)) if loss_pnls and sum(loss_pnls) != 0 else 0
    bar_ratio = avg_win/(avg_win+abs(avg_loss)) if (avg_win+abs(avg_loss)) else 0.5

    # Daily aggregates
    daily_pnl    = defaultdict(float)
    daily_trades = defaultdict(int)
    daily_wins   = defaultdict(int)
    for t in closed:
        d = str(t.get("exit_date","") or "")[:10]
        if d and d != "nan":
            p = float(t.get("pnl") or 0)
            daily_pnl[d]    += p
            daily_trades[d] += 1
            if p > 0: daily_wins[d] += 1

    day_wins_n  = sum(1 for v in daily_pnl.values() if v > 0)
    day_total   = len(daily_pnl)
    day_wr      = day_wins_n/day_total if day_total else 0

    # Cumulative P&L series by date
    dates_sorted = sorted(daily_pnl.keys())
    cum_by_date  = []; running = 0
    for d in dates_sorted:
        running += daily_pnl[d]
        cum_by_date.append((d, running))

    spark_ys = [p for _,p in cum_by_date[-30:]] if cum_by_date else []
    pnl_col  = TEAL if pnl >= 0 else RED

    # Drawdown (by date)
    peak_dd = 0; dd_series = []; max_dd = 0; max_dd_date = ""
    for d, cum in cum_by_date:
        if cum > peak_dd: peak_dd = cum
        dd = cum - peak_dd
        dd_series.append((d, dd))
        if dd < max_dd: max_dd = dd; max_dd_date = d

    # Streaks
    win_streak = loss_streak = cur_w = cur_l = 0
    for t in sorted(closed, key=lambda x: str(x.get("exit_date","") or "")):
        p = float(t.get("pnl") or 0)
        if p > 0: cur_w += 1; cur_l = 0; win_streak = max(win_streak, cur_w)
        else:     cur_l += 1; cur_w = 0; loss_streak = max(loss_streak, cur_l)
    cur_trade_streak = cur_w if cur_w else -cur_l

    # Day streaks
    day_win_streak = day_loss_streak = dcw = dcl = 0
    for d in dates_sorted:
        if daily_pnl[d] > 0: dcw += 1; dcl = 0; day_win_streak = max(day_win_streak, dcw)
        else:                  dcl += 1; dcw = 0; day_loss_streak = max(day_loss_streak, dcl)
    cur_day_streak = dcw if dcw else -dcl


    # ── FILTERS BAR (must come before metrics calculation) ───────────────────
    FY_START2, FY_END2 = "2026-04-01", "2027-03-31"
    all_strategies = sorted({str(t.get("strategy","") or "").strip() for t in closed if t.get("strategy")})
    all_symbols    = sorted({str(t.get("ticker","") or "").strip() for t in closed if t.get("ticker")})

    _fb1, _fb2, _fb3, _fb4, _fb5, _fb6 = st.columns([2, 2, 1.5, 1.5, 1.5, 0.8])
    with _fb1:
        date_range = st.selectbox("Date Range", [
            "This FY (2026-27)", "This Month", "Last Month",
            "Last 30 Days", "Last 90 Days", "Custom"
        ], key="flt_daterange", label_visibility="visible")
    with _fb2:
        strat_filter = st.multiselect("Strategy", all_strategies,
            default=[], placeholder="All strategies", key="flt_strategy",
            label_visibility="visible")
    with _fb3:
        symbol_filter = st.multiselect("Symbol", all_symbols,
            default=[], placeholder="All symbols", key="flt_symbol",
            label_visibility="visible")
    with _fb4:
        side_filter = st.selectbox("Side", ["All", "LONG", "SHORT"],
            key="flt_side", label_visibility="visible")
    with _fb5:
        result_filter = st.selectbox("Result", ["All", "Win", "Loss", "Breakeven"],
            key="flt_result", label_visibility="visible")
    with _fb6:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        if st.button("↺ Reset", key="flt_reset", use_container_width=True):
            for _k in ["flt_daterange","flt_strategy","flt_symbol","flt_side","flt_result","flt_cust_start","flt_cust_end"]:
                if _k in st.session_state: del st.session_state[_k]
            st.rerun()

    if date_range == "Custom":
        _cd1, _cd2, _ = st.columns([1,1,4])
        _cust_start = _cd1.date_input("From", value=date(2026,4,1), key="flt_cust_start")
        _cust_end   = _cd2.date_input("To",   value=date.today(),   key="flt_cust_end")
        _d_start, _d_end = _cust_start.isoformat(), _cust_end.isoformat()
    else:
        _today = date.today()
        if date_range == "This FY (2026-27)":   _d_start, _d_end = FY_START2, FY_END2
        elif date_range == "This Month":         _d_start, _d_end = _today.replace(day=1).isoformat(), _today.isoformat()
        elif date_range == "Last Month":
            _first = _today.replace(day=1); _lm = _first - timedelta(days=1)
            _d_start, _d_end = _lm.replace(day=1).isoformat(), _lm.isoformat()
        elif date_range == "Last 30 Days":       _d_start, _d_end = (_today-timedelta(days=30)).isoformat(), _today.isoformat()
        elif date_range == "Last 90 Days":       _d_start, _d_end = (_today-timedelta(days=90)).isoformat(), _today.isoformat()
        else:                                    _d_start, _d_end = FY_START2, FY_END2

    # Apply filters — recompute closed from filtered set
    closed = [t for t in closed if _d_start <= str(t.get("exit_date","") or "")[:10] <= _d_end]
    if strat_filter:
        closed = [t for t in closed if str(t.get("strategy","") or "").strip() in strat_filter]
    if symbol_filter:
        closed = [t for t in closed if str(t.get("ticker","") or "").strip() in symbol_filter]
    if side_filter != "All":
        closed = [t for t in closed if str(t.get("direction","") or t.get("side","") or "").upper() == side_filter]
    if result_filter == "Win":
        closed = [t for t in closed if float(t.get("pnl") or 0) > 0]
    elif result_filter == "Loss":
        closed = [t for t in closed if float(t.get("pnl") or 0) < 0]
    elif result_filter == "Breakeven":
        closed = [t for t in closed if float(t.get("pnl") or 0) == 0]

    _active = sum([bool(strat_filter), bool(symbol_filter), side_filter!="All",
                   result_filter!="All", date_range!="This FY (2026-27)"])
    if _active:
        st.markdown(f'<p style="font-size:11px;color:{TEAL};margin:2px 0 8px">'
                    f'✓ {_active} filter{"s" if _active>1 else ""} active — {len(closed)} trades</p>',
                    unsafe_allow_html=True)

    # ── Recompute all metrics from filtered closed list ───────────────────────
    win_pnls  = [float(t.get("pnl") or 0) for t in closed if float(t.get("pnl") or 0) > 0]
    loss_pnls = [float(t.get("pnl") or 0) for t in closed if float(t.get("pnl") or 0) < 0]
    pnl       = sum(float(t.get("pnl") or 0) for t in closed)
    wr        = len(win_pnls)/len(closed) if closed else 0
    avg_win   = float(np.mean(win_pnls))  if win_pnls  else 0
    avg_loss  = float(np.mean(loss_pnls)) if loss_pnls else 0
    pf        = abs(sum(win_pnls)/sum(loss_pnls)) if loss_pnls and sum(loss_pnls)!=0 else 0
    bar_ratio = avg_win/(avg_win+abs(avg_loss)) if (avg_win+abs(avg_loss)) else 0.5

    daily_pnl2    = defaultdict(float)
    daily_trades2 = defaultdict(int)
    daily_wins2   = defaultdict(int)
    for _t in closed:
        _d = str(_t.get("exit_date","") or "")[:10]
        if _d and _d != "nan":
            _p = float(_t.get("pnl") or 0)
            daily_pnl2[_d]    += _p
            daily_trades2[_d] += 1
            if _p > 0: daily_wins2[_d] += 1
    daily_pnl    = daily_pnl2
    daily_trades = daily_trades2
    daily_wins   = daily_wins2

    day_wins_n  = sum(1 for v in daily_pnl.values() if v > 0)
    day_total   = len(daily_pnl)
    day_wr      = day_wins_n/day_total if day_total else 0

    dates_sorted = sorted(daily_pnl.keys())
    cum_by_date  = []; _running = 0
    for _d in dates_sorted:
        _running += daily_pnl[_d]
        cum_by_date.append((_d, _running))

    # ── Daily starting balance for correct % view ─────────────────────────────
    # starting balance for each day = acct + cumulative P&L up to previous day
    day_start_bal = {}
    _bal = acct
    for _d in dates_sorted:
        day_start_bal[_d] = _bal
        _bal += daily_pnl[_d]

    # Week starting balance = balance on first traded day of that week
    week_start_bal = {}
    for _d in dates_sorted:
        _dt = datetime.strptime(_d, "%Y-%m-%d")
        _wk_start = (_dt - timedelta(days=_dt.weekday())).strftime("%Y-%m-%d")
        if _wk_start not in week_start_bal:
            week_start_bal[_wk_start] = day_start_bal[_d]

    # Month starting balance = balance on first traded day of that month
    month_start_bal = {}
    for _d in dates_sorted:
        _mo_key = _d[:7]
        if _mo_key not in month_start_bal:
            month_start_bal[_mo_key] = day_start_bal[_d]

    spark_ys = [_p for _,_p in cum_by_date[-30:]] if cum_by_date else []
    pnl_col  = TEAL if pnl >= 0 else RED

    peak_dd = 0; dd_series = []; max_dd = 0; max_dd_date = ""
    for _d, _cum in cum_by_date:
        if _cum > peak_dd: peak_dd = _cum
        _dd = _cum - peak_dd
        dd_series.append((_d, _dd))
        if _dd < max_dd: max_dd = _dd; max_dd_date = _d

    win_streak = loss_streak = cur_w = cur_l = 0
    for _t in sorted(closed, key=lambda x: str(x.get("exit_date","") or "")):
        _p = float(_t.get("pnl") or 0)
        if _p > 0: cur_w += 1; cur_l = 0; win_streak = max(win_streak, cur_w)
        else:      cur_l += 1; cur_w = 0; loss_streak = max(loss_streak, cur_l)
    cur_trade_streak = cur_w if cur_w else -cur_l

    day_win_streak = day_loss_streak = dcw = dcl = 0
    for _d in dates_sorted:
        if daily_pnl[_d] > 0: dcw += 1; dcl = 0; day_win_streak = max(day_win_streak, dcw)
        else:                   dcl += 1; dcw = 0; day_loss_streak = max(day_loss_streak, dcl)
    cur_day_streak = dcw if dcw else -dcl

    # ── Header + View selector ───────────────────────────────────────────────
    now_h = datetime.now().hour
    greeting = "Good morning" if now_h < 12 else "Good afternoon" if now_h < 17 else "Good evening"

    h1, h2 = st.columns([5, 1])
    with h1:
        st.markdown(f'<h2 style="margin-bottom:2px">{greeting}!</h2>', unsafe_allow_html=True)
        st.markdown(f'<p style="color:{TEXT_SUBTLE};font-size:11px;margin-bottom:8px">FY 2026-27 · NSE Systematic Trading</p>', unsafe_allow_html=True)
    with h2:
        VIEW_OPTIONS = {
            "₹ Rupee":     "dollar",
            "% Percentage":"pct",
            "🔒 Privacy":  "privacy",
            "R R-Multiple":"rmult",
        }
        if "dash_view" not in st.session_state:
            st.session_state.dash_view = "dollar"
        view_label = st.selectbox("View", list(VIEW_OPTIONS.keys()),
                                   index=0, key="dash_view_sel",
                                   label_visibility="collapsed")
        st.session_state.dash_view = VIEW_OPTIONS[view_label]
    VIEW = st.session_state.dash_view

    # ── View-aware formatting helpers ─────────────────────────────────────────
    def fmt_val(v, base=None):
        """Format a P&L value based on current view.
        base = starting balance for that period (day/week/month) for % view."""
        if VIEW == "privacy":
            return "••••"
        elif VIEW == "pct":
            denom = base or acct or 1
            return f"{'+'if v>=0 else ''}{v/denom*100:.2f}%"
        elif VIEW == "rmult":
            one_r = float(kpi.get("avg_risk_per_trade", abs(avg_loss) or 1000))
            r = v/one_r if one_r else 0
            return f"{'+'if r>=0 else ''}{r:.2f}R"
        else:  # dollar
            return f"{'+'if v>=0 else ''}₹{abs(v):,.0f}"

    def fmt_day(v, d_str):
        """Format daily P&L using day's starting balance for %."""
        return fmt_val(v, base=day_start_bal.get(d_str, acct))

    def fmt_week(v, wk_start):
        """Format weekly P&L using week's starting balance for %."""
        return fmt_val(v, base=week_start_bal.get(wk_start, acct))

    def fmt_month(v, mo_key):
        """Format monthly P&L using month's starting balance for %."""
        return fmt_val(v, base=month_start_bal.get(mo_key, acct))

    def fmt_pnl_val(v):
        return fmt_val(v)

    def mask(v, fmt=None):
        """Hide value in privacy mode."""
        if VIEW == "privacy": return "••••"
        return fmt if fmt else f"{'+'if v>=0 else ''}₹{abs(v):,.0f}"

    # ── WIDGET TEMPLATE SYSTEM ──────────────────────────────────────────────
    WIDGET_DEFAULTS = {
        "net_pnl":True,"win_pct":True,"avg_wl":True,"streak":True,"max_dd":True,
        "drawdown_chart":True,"balance_chart":True,"daily_cum_chart":True,
        "net_daily_chart":True,"your_score":True,"progress_tracker":True,
    }
    WIDGET_LABELS = {
        "net_pnl":"Net P&L","win_pct":"Trade Win %","avg_wl":"Avg Win/Loss",
        "streak":"Current Streak","max_dd":"Max Drawdown",
        "drawdown_chart":"Drawdown","balance_chart":"Account Balance",
        "daily_cum_chart":"Daily & Cumulative P&L","net_daily_chart":"Net Daily P&L",
        "your_score":"Your Score","progress_tracker":"Progress Tracker",
    }
    if "dash_widgets" not in st.session_state:
        st.session_state.dash_widgets = dict(WIDGET_DEFAULTS)
    if "dash_edit_mode" not in st.session_state:
        st.session_state.dash_edit_mode = False

    W = st.session_state.dash_widgets  # shorthand — defined BEFORE any use

    # Edit widgets button
    _ec, _blank = st.columns([1.2, 8])
    with _ec:
        if st.button("⚙️ Edit Widgets", key="dash_edit_btn"):
            st.session_state.dash_edit_mode = not st.session_state.dash_edit_mode
            st.rerun()

    if st.session_state.dash_edit_mode:
        st.markdown(
            f'<div style="background:{CARD_BG};border:1px solid {TEAL};border-radius:10px;padding:14px 18px;margin-bottom:12px">',
            unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:11px;font-weight:700;color:{TEXT_H};margin-bottom:8px">Upper Widgets</p>', unsafe_allow_html=True)
        _uw = st.columns(5)
        for _col, _k in zip(_uw, ["net_pnl","win_pct","avg_wl","streak","max_dd"]):
            W[_k] = _col.checkbox(WIDGET_LABELS[_k], value=W[_k], key=f"w_{_k}")
        st.markdown(f'<p style="font-size:10px;color:{TEXT_SUBTLE};margin:10px 0 6px">Lower Charts</p>', unsafe_allow_html=True)
        _lw = st.columns(5)
        for _col, _k in zip(_lw, ["drawdown_chart","balance_chart","daily_cum_chart","net_daily_chart","your_score"]):
            W[_k] = _col.checkbox(WIDGET_LABELS[_k], value=W[_k], key=f"w_{_k}")
        _s1, _s2, _ = st.columns([1,1,6])
        if _s1.button("✅ Done", key="dash_save"):
            st.session_state.dash_edit_mode = False; st.rerun()
        if _s2.button("↺ Reset", key="dash_reset"):
            st.session_state.dash_widgets = dict(WIDGET_DEFAULTS); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── UPPER WIDGET STRIP ───────────────────────────────────────────────────
    KH = "150px"
    w1, w2, w3, w4, w5 = st.columns(5)

    # 1. Net P&L + sparkline
    cnt = f'<span style="background:{BLUE_BG};color:{BLUE};padding:1px 6px;border-radius:9px;font-size:9px;margin-left:4px">{len(closed)}</span>'
    if W.get("net_pnl", True):
        w1.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
            padding:14px 16px;box-shadow:{SHADOW_SM};height:{KH};box-sizing:border-box;overflow:hidden">
            <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:4px">Net P&L {cnt}</div>
            <div style="font-size:21px;font-weight:700;color:{pnl_col};margin-bottom:2px">
                {fmt_val(pnl, acct)}</div>
            <div style="font-size:10px;color:{TEXT_MUTED};margin-bottom:6px">
                P&L: <span style="color:{pnl_col}">{fmt_val(pnl, acct)}</span></div>
            {spark_svg(spark_ys, pnl_col)}
        </div>""", unsafe_allow_html=True)

    # 2. Trade Win % + gauge
    wr_col = TEAL if wr >= 0.4 else AMBER
    wins_n = len(win_pnls); losses_n = len(loss_pnls)
    if W.get("win_pct", True):
        w2.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
            padding:14px 16px;box-shadow:{SHADOW_SM};height:{KH};box-sizing:border-box;overflow:hidden">
            <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:4px">Trade Win %</div>
            <div style="font-size:21px;font-weight:700;color:{wr_col};margin-bottom:2px">{wr*100:.2f}%</div>
            <div style="display:flex;align-items:center;gap:8px;margin-top:4px">
                {svg_gauge(wr, wr_col, 70)}
                <div style="font-size:10px;color:{TEXT_MUTED};line-height:1.6">
                    <span style="color:{TEAL}">▲ {wins_n}</span><br>
                    <span style="color:{TEXT_SUBTLE}">▼ {losses_n}</span><br>
                    <span style="color:{BLUE}">=&nbsp;{len(closed)-wins_n-losses_n}</span>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

    # 3. Avg Win/Loss Trade bar
    if W.get("avg_wl", True):
        w3.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
            padding:14px 16px;box-shadow:{SHADOW_SM};height:{KH};box-sizing:border-box;overflow:hidden">
            <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:4px">Avg Win/Loss Trade</div>
            <div style="font-size:21px;font-weight:700;color:{TEXT_H};margin-bottom:8px">
                {avg_win/abs(avg_loss):.2f}R</div>
            <div style="height:6px;background:{BORDER_LIGHT};border-radius:3px;overflow:hidden;margin-bottom:6px">
                <div style="width:{bar_ratio*100:.0f}%;height:100%;background:{TEAL};
                    display:inline-block;vertical-align:top"></div>
                <div style="width:{(1-bar_ratio)*100:.0f}%;height:100%;background:{RED};
                    display:inline-block;vertical-align:top"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:11px">
                <span style="color:{TEAL};font-weight:600">{fmt_val(avg_win, acct)}</span>
                <span style="color:{RED};font-weight:600">{fmt_val(avg_loss, acct)}</span>
            </div>
        </div>""", unsafe_allow_html=True)

    # 4. Current Streak
    streak_col = TEAL if cur_day_streak >= 0 else RED
    trade_col  = TEAL if cur_trade_streak >= 0 else RED
    if W.get("streak", True):
        w4.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
            padding:14px 16px;box-shadow:{SHADOW_SM};height:{KH};box-sizing:border-box;overflow:hidden">
            <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:8px">Current Streak</div>
            <div style="display:flex;gap:14px;align-items:flex-start">
                <div>
                    <div style="font-size:8px;color:{TEXT_SUBTLE};font-weight:700;
                        text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">DAYS</div>
                    {streak_circle(abs(cur_day_streak), streak_col, '')}
                </div>
                <div style="flex:1">
                    <div style="font-size:10px;color:{TEAL};margin-bottom:2px">{day_win_streak} days</div>
                    <div style="font-size:10px;color:{RED}">{day_loss_streak} days</div>
                </div>
                <div>
                    <div style="font-size:8px;color:{TEXT_SUBTLE};font-weight:700;
                        text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">TRADES</div>
                    {streak_circle(abs(cur_trade_streak), trade_col, '')}
                </div>
                <div style="flex:1">
                    <div style="font-size:10px;color:{TEAL};margin-bottom:2px">{win_streak} trades</div>
                    <div style="font-size:10px;color:{RED}">{loss_streak} trades</div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

    # 5. Max Drawdown
    max_dd_pct = abs(max_dd/acct*100) if acct else 0
    dd_col = RED if max_dd < 0 else TEAL
    avg_dd = float(np.mean([dd for _,dd in dd_series])) if dd_series else 0
    if W.get("max_dd", True):
        w5.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
            padding:14px 16px;box-shadow:{SHADOW_SM};height:{KH};box-sizing:border-box;overflow:hidden">
            <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;
                letter-spacing:0.07em;margin-bottom:4px">Max Drawdown</div>
            <div style="font-size:21px;font-weight:700;color:{dd_col};margin-bottom:2px">
                {fmt_val(max_dd, acct)}</div>
            <div style="font-size:10px;color:{TEXT_MUTED};margin-bottom:4px">
                <span style="background:rgba(239,68,68,0.08);color:{RED};padding:1px 5px;
                    border-radius:4px;font-size:9px">-{max_dd_pct:.1f}%</span>
                {'  '+max_dd_date if max_dd_date else ''}
            </div>
            <div style="font-size:9px;color:{TEXT_SUBTLE}">Avg drawdown:
                <span style="color:{RED}">{fmt_val(avg_dd, acct)}</span>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.divider()

    all_months = sorted({d[:7] for d in daily_pnl.keys()})
    if not all_months: return

    if "dash_cal_idx" not in st.session_state:
        st.session_state.dash_cal_idx = len(all_months)-1

    sel = all_months[st.session_state.dash_cal_idx]
    yr = int(sel[:4]); mo = int(sel[5:])
    today_str = date.today().strftime("%Y-%m-%d")
    today_month = date.today().strftime("%Y-%m")

    # Monthly data
    month_data = {d:v for d,v in daily_pnl.items() if d[:7]==sel}
    m_pnl  = sum(month_data.values())
    m_days = len(month_data)
    m_pnl_col = TEAL if m_pnl >= 0 else RED

    # ── Calendar grid setup ───────────────────────────────────────────────────
    days_in_month = cal_mod.monthrange(yr, mo)[1]
    first_dow = (date(yr, mo, 1).weekday() + 1) % 7  # Mon=1 → Sun=0
    cells = [None]*first_dow + list(range(1, days_in_month+1))
    cells += [None]*((7-len(cells)%7)%7)
    week_rows = [cells[i:i+7] for i in range(0, len(cells), 7)]

    weekly_stats = []
    for wrow in week_rows:
        wp = sum(daily_pnl.get(f"{yr}-{mo:02d}-{d:02d}", 0) for d in wrow if d)
        wd = sum(1 for d in wrow if d and f"{yr}-{mo:02d}-{d:02d}" in daily_pnl)
        weekly_stats.append((wp, wd))

    # ── Nav row — rendered AFTER divider, guaranteed new block ───────────────
    _n1, _n2, _n3, _n4, _n5 = st.columns([0.5, 1.1, 0.5, 4, 5])
    with _n1:
        if st.button("◀", key="dcal_prev"):
            st.session_state.dash_cal_idx = max(0, st.session_state.dash_cal_idx-1)
            st.rerun()
    with _n2:
        if st.button("TODAY", key="dcal_today", type="primary", use_container_width=True):
            if today_month in all_months:
                st.session_state.dash_cal_idx = all_months.index(today_month)
                st.rerun()
    with _n3:
        if st.button("▶", key="dcal_next"):
            st.session_state.dash_cal_idx = min(len(all_months)-1, st.session_state.dash_cal_idx+1)
            st.rerun()
    with _n4:
        st.markdown(
            f'<p style="font-size:16px;font-weight:600;color:{TEXT_H};padding-top:5px;margin:0">'
            f'{cal_mod.month_name[mo]} {yr}</p>', unsafe_allow_html=True)
    with _n5:
        st.markdown(
            f'<div style="text-align:right;padding-top:5px">'
            f'<span style="font-size:12px;color:{TEXT_MUTED}">Monthly stats: </span>'
            f'<span style="background:{m_pnl_col};color:white;font-size:12px;font-weight:700;'
            f'padding:3px 12px;border-radius:20px;margin:0 6px">'
            f'{fmt_val(m_pnl, base=month_start_bal.get(sel, acct))}</span>'
            f'<span style="font-size:12px;color:{TEXT_MUTED}">'
            f'{m_days} day{"s" if m_days!=1 else ""}</span></div>', unsafe_allow_html=True)

    # ── Build full calendar as a single HTML table ───────────────────────────
    CELL_H = "90px"
    TH_STYLE = (f"text-align:center;font-size:11px;font-weight:600;color:{TEXT_SUBTLE};"
                f"padding:8px 4px;border-bottom:2px solid {BORDER};width:13%")
    WK_TH = (f"text-align:center;font-size:9px;font-weight:600;color:{TEXT_SUBTLE};"
             f"padding:8px 4px;border-bottom:2px solid {BORDER};width:9%;text-transform:uppercase")

    # Header row
    cal_html = f"""<table style="width:100%;border-collapse:separate;border-spacing:3px;margin-top:4px">
<thead><tr>
  <th style="{TH_STYLE}">Sun</th><th style="{TH_STYLE}">Mon</th>
  <th style="{TH_STYLE}">Tue</th><th style="{TH_STYLE}">Wed</th>
  <th style="{TH_STYLE}">Thu</th><th style="{TH_STYLE}">Fri</th>
  <th style="{TH_STYLE}">Sat</th><th style="{WK_TH}">Week</th>
</tr></thead><tbody>"""

    for w_idx, (row, (wp, wd)) in enumerate(zip(week_rows, weekly_stats)):
        cal_html += "<tr>"
        for day in row:
            if day is None:
                cal_html += (f'<td style="height:{CELL_H};background:{PAGE_BG};'
                             f'border:1px solid {BORDER_LIGHT};border-radius:6px;'
                             f'vertical-align:top;padding:6px"></td>')
            else:
                d_str = f"{yr}-{mo:02d}-{day:02d}"
                p  = daily_pnl.get(d_str)
                n  = daily_trades.get(d_str, 0)
                nw = daily_wins.get(d_str, 0)
                is_today = (d_str == today_str)
                if p is not None:
                    # Light colors like TradeZella — intensity based on P&L size
                    if p > 0:
                        if   p > 50000: bg="#bbf7d0"; tc="#14532d"
                        elif p > 10000: bg="#d1fae5"; tc="#065f46"
                        else:           bg="#ecfdf5"; tc="#047857"
                        bc="#10B981"
                    elif p < 0:
                        if   p < -50000: bg="#fecaca"; tc="#7f1d1d"
                        elif p < -10000: bg="#fee2e2"; tc="#991b1b"
                        else:            bg="#fff1f2"; tc="#b91c1c"
                        bc="#EF4444"
                    else:
                        bg="#F3F4F6"; tc="#374151"; bc=BORDER
                    wr_d = f"{nw/n*100:.1f}%" if n else ""
                    # Format cell value based on VIEW with correct daily base
                    if VIEW == "privacy":
                        cell_val = "••••"
                    elif VIEW == "pct":
                        _base = day_start_bal.get(d_str, acct)
                        cell_val = f"{'+'if p>=0 else ''}{p/_base*100:.2f}%"
                    elif VIEW == "rmult":
                        one_r = float(kpi.get("avg_risk_per_trade", abs(avg_loss) or 1000))
                        r = p/one_r if one_r else 0
                        cell_val = f"{'+'if r>=0 else ''}{r:.1f}R"
                    else:
                        sign = "+" if p>0 else "-" if p<0 else ""
                        cell_val = f"{sign}₹{abs(p)/1e3:.2f}K" if abs(p) < 1000 else f"{sign}₹{abs(p)/1e3:.1f}K"
                    cal_html += (
                        f'<td style="height:{CELL_H};background:{bg};border:1px solid {bc}33;'
                        f'border-radius:6px;vertical-align:top;padding:7px 8px">'
                        f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                        f'<span style="font-size:13px;font-weight:700;color:{tc}">{cell_val}</span>'
                        f'<span style="color:{tc}99;font-size:11px;font-weight:500">{day}</span></div>'
                        f'<div style="font-size:9px;color:{tc}aa;margin-top:5px">'
                        f'{n} trade{"s" if n!=1 else ""}</div>'
                        f'<div style="font-size:9px;color:{tc}aa">{wr_d}</div></td>')
                else:
                    bc2 = f"border:2px solid {TEAL}" if is_today else f"border:1px solid {BORDER_LIGHT}"
                    dc  = TEAL if is_today else TEXT_SUBTLE
                    day_n = f'<span style="font-size:11px;color:{dc};font-weight:{"600" if is_today else "400"}">{day}</span>'
                    cal_html += (f'<td style="height:{CELL_H};background:{CARD_BG};{bc2};'
                                 f'border-radius:6px;vertical-align:top;padding:7px 8px">'
                                 f'<div style="display:flex;justify-content:flex-end">{day_n}</div></td>')

        # Weekly sidebar cell — matches TradeZella style
        pc = TEAL if wp >= 0 else RED
        pc_bg = "#ecfdf5" if wp >= 0 else "#fff1f2"
        # Get week start date for correct % base
        _first_day_of_week = next((f"{yr}-{mo:02d}-{d:02d}" for d in row if d), None)
        _dt_row = datetime(yr, mo, row[0]) if row[0] else None
        _wk_key = (_dt_row - timedelta(days=_dt_row.weekday())).strftime("%Y-%m-%d") if _dt_row else ""
        _wk_base = week_start_bal.get(_wk_key, acct)
        if VIEW == "privacy":
            wk_val = "••••"
        elif VIEW == "pct":
            wk_val = f"{'+'if wp>=0 else ''}{wp/_wk_base*100:.2f}%"
        elif VIEW == "rmult":
            one_r = float(kpi.get("avg_risk_per_trade", abs(avg_loss) or 1000))
            r = wp/one_r if one_r else 0
            wk_val = f"{'+'if r>=0 else ''}{r:.1f}R"
        else:
            wp_sign = "+" if wp>0 else "-" if wp<0 else ""
            wk_val = f"{wp_sign}₹{abs(wp)/1e3:.1f}K"
        cal_html += (
            f'<td style="height:{CELL_H};vertical-align:middle;padding:8px 10px;'
            f'background:{pc_bg if wd>0 else "transparent"};border-radius:6px;'
            f'border-left:3px solid {pc if wd>0 else BORDER_LIGHT}">'
            f'<div style="font-size:9px;color:{TEXT_SUBTLE};margin-bottom:3px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px">Week {w_idx+1}</div>'
            f'<div style="font-size:13px;font-weight:700;color:{pc if wd>0 else TEXT_SUBTLE}">{wk_val if wd>0 else "₹0"}</div>'
            f'<div style="font-size:9px;color:{TEXT_SUBTLE};margin-top:2px">{wd} day{"s" if wd!=1 else ""}</div></td>')
        cal_html += "</tr>"

    cal_html += "</tbody></table>"
    st.markdown(cal_html, unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── RECENT TRADES + OPEN POSITIONS (tabbed, below calendar) ─────────────
    rt_tab, op_tab = st.tabs(["RECENT TRADES", "OPEN POSITIONS"])

    with rt_tab:
        recent = sorted([t for t in closed if t.get("exit_date")],
                       key=lambda x: str(x.get("exit_date","")), reverse=True)[:12]
        TH = f"font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.05em;padding:0 0 6px"
        TD = f"font-size:12px;border-bottom:1px solid {BORDER_LIGHT};padding:6px 0"
        rows_html = ""
        for t in recent:
            p = float(t.get("pnl") or 0)
            pc = TEAL if p >= 0 else RED
            d  = str(t.get("exit_date",""))[:10]
            pnl_sign = "+" if p > 0 else "-" if p < 0 else ""
            rows_html += (f'<tr>'
                f'<td style="{TD};color:{TEXT_MUTED};width:100px">{d}</td>'
                f'<td style="{TD};font-weight:600;color:{TEXT_H}">{t.get("ticker","")}</td>'
                f'<td style="{TD};font-weight:600;color:{pc};text-align:right">'
                f'{fmt_val(p, acct)}</td></tr>')
        st.markdown(f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr><th style="{TH};text-align:left">Close Date</th>'
            f'<th style="{TH};text-align:left">Symbol</th>'
            f'<th style="{TH};text-align:right">Net P&L</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True)

    with op_tab:
        if open_t:
            TH_OP = f"padding:7px 10px;font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid {BORDER}"
            TD_OP = f"padding:8px 10px;font-size:12px;border-bottom:1px solid {BORDER_LIGHT}"
            op_rows = ""
            # Combine same-ticker open positions: merge strategies, weighted-avg entry,
            # show widest (most conservative) stop loss among combined trades
            _combined_open = combine_open_positions(open_t)
            # Recover individual SLs per ticker for "widest stop" display
            _sl_by_ticker = {}
            for t in open_t:
                tk = t.get("ticker","")
                sl = float(t.get("stop_loss") or 0)
                if sl:
                    side = str(t.get("side","")).upper()
                    if tk not in _sl_by_ticker:
                        _sl_by_ticker[tk] = sl
                    else:
                        # For longs, widest/safest stop is the lowest; for shorts, the highest
                        if side in ("BUY","LONG"):
                            _sl_by_ticker[tk] = min(_sl_by_ticker[tk], sl)
                        else:
                            _sl_by_ticker[tk] = max(_sl_by_ticker[tk], sl)

            for tk, agg in list(_combined_open.items())[:15]:
                ep = agg["avg_entry"]
                sl = _sl_by_ticker.get(tk, 0)
                strat = ", ".join(sorted(agg["strategies"])) or "—"
                op_rows += (f'<tr>'
                    f'<td style="{TD_OP};font-weight:700;color:{TEXT_H}">{tk}</td>'
                    f'<td style="{TD_OP};color:{TEXT_MUTED}">{strat}</td>'
                    f'<td style="{TD_OP};color:{TEXT_H}">₹{ep:,.2f}</td>'
                    f'<td style="{TD_OP};color:{RED};text-align:right">SL ₹{sl:,.2f}</td>'
                    f'</tr>')
            st.markdown(
                f'<table style="width:100%;border-collapse:collapse">'
                f'<thead><tr>'
                f'<th style="{TH_OP};text-align:left">Symbol</th>'
                f'<th style="{TH_OP};text-align:left">Strategy</th>'
                f'<th style="{TH_OP};text-align:left">Entry ₹</th>'
                f'<th style="{TH_OP};text-align:right">Stop Loss</th>'
                f'</tr></thead><tbody>{op_rows}</tbody></table>',
                unsafe_allow_html=True)
        else:
            st.markdown(f'<p style="font-size:12px;color:{TEXT_SUBTLE};margin-top:8px">No open positions</p>',
                       unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── CSS card borders (Streamlit-compatible: style columns directly) ─────
    st.markdown("""<style>
    [data-testid="stHorizontalBlock"] > div > [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stVerticalBlock"] { gap: 0 !important; }
    div.chart-card { background: var(--card-bg, #FFFFFF);
        border: 1px solid #E2E8F0; border-radius: 10px;
        padding: 14px 16px; margin-bottom: 0; }
    </style>""", unsafe_allow_html=True)

    CHART_H = 300  # unified chart height for all lower charts

    # ── Chart type selector helper ────────────────────────────────────────────
    CTYPES = ["Line", "Bar", "Area", "Scatter"]

    def _make_trace(x, y, chart_type, color, name="", y2=False):
        """Return a plotly trace based on chart type.
        color can be a hex string or "dual" (green/red per value)."""
        kw = dict(yaxis="y2") if y2 else {}
        dual = (color == "dual")
        real_color = TEAL if dual else color
        dual_colors = [TEAL if v>=0 else RED for v in y]
        # Hover format based on VIEW
        if VIEW == "privacy":
            hover = "%{x}<br>••••<extra></extra>"
        elif VIEW == "pct":
            hover = f"%{{x}}<br>%{{y:.2f}}%<extra></extra>"
        elif VIEW == "rmult":
            hover = f"%{{x}}<br>%{{y:.2f}}R<extra></extra>"
        else:
            hover = f"%{{x}}<br>₹%{{y:,.0f}}<extra></extra>"

        if chart_type == "Bar":
            return go.Bar(x=x, y=y, name=name,
                marker=dict(color=dual_colors if dual else color,
                           opacity=0.85, line=dict(width=0)),
                hovertemplate=hover, **kw)
        elif chart_type == "Scatter":
            return go.Scatter(x=x, y=y, mode="markers", name=name,
                marker=dict(color=dual_colors if dual else color, size=5),
                hovertemplate=hover, **kw)
        elif chart_type == "Area":
            fc = ("rgba(16,185,129,0.20)" if real_color==TEAL
                  else "rgba(124,58,237,0.15)" if real_color=="#7C3AED"
                  else "rgba(239,68,68,0.20)")
            return go.Scatter(x=x, y=y, mode="lines", name=name,
                line=dict(color=real_color, width=2),
                fill="tozeroy", fillcolor=fc,
                hovertemplate=hover, **kw)
        else:  # Line
            return go.Scatter(x=x, y=y, mode="lines", name=name,
                line=dict(color=real_color, width=2),
                hovertemplate=hover, **kw)

    # ── LOWER CHARTS ROW ─────────────────────────────────────────────────────
    ch1, ch2, ch3 = st.columns(3)

    # Drawdown chart
    with ch1:
        with st.container(border=True):
            _tc1, _tc2 = st.columns([3,1])
            _tc1.markdown(f'<p style="font-size:11px;font-weight:600;color:{TEXT_H};margin:0">Drawdown</p>', unsafe_allow_html=True)
            dd_ctype = _tc2.selectbox("Chart type", CTYPES, index=2, key="dd_ctype", label_visibility="collapsed")
            if dd_series:
                ds_dates = [d for d,_ in dd_series]
                ds_vals  = [v for _,v in dd_series]
                fig_dd = go.Figure()
                fig_dd.add_trace(_make_trace(ds_dates, ds_vals, dd_ctype, "#7C3AED", "Drawdown"))
                fig_dd.add_hline(y=0, line=dict(color=BORDER_LIGHT, width=1))
                l_dd = chart_layout(height=CHART_H, title="")
                l_dd["yaxis"]["tickprefix"] = "" if VIEW in ("pct","rmult","privacy") else "₹"
                l_dd["yaxis"]["ticksuffix"] = "%" if VIEW=="pct" else "R" if VIEW=="rmult" else ""
                l_dd["margin"] = dict(l=70, r=12, t=10, b=40)
                if dd_ctype == "Bar": l_dd["bargap"] = 0.2
                fig_dd.update_layout(**l_dd)
                st.plotly_chart(fig_dd, use_container_width=True, config={"displayModeBar":False})

    # Account Balance chart
    with ch2:
        with st.container(border=True):
            _bc1, _bc2 = st.columns([3,1])
            _bc1.markdown(f'<p style="font-size:11px;font-weight:600;color:{TEXT_H};margin:0">Account Balance</p>', unsafe_allow_html=True)
            bal_ctype = _bc2.selectbox("Balance chart type", CTYPES, index=2, key="bal_ctype", label_visibility="collapsed")
            bal_pts = [(str(t.get("exit_date",""))[:10], float(t.get("account_balance") or 0))
                       for t in closed if t.get("account_balance") and t.get("exit_date")]
            if bal_pts:
                bal_pts_s = sorted(bal_pts)
                bxs = [d for d,_ in bal_pts_s]
                bys = [v for _,v in bal_pts_s]
                fig_b = go.Figure()
                fig_b.add_trace(_make_trace(bxs, bys, bal_ctype, TEAL, "Balance"))
                lb = chart_layout(height=CHART_H, title="")
                lb["yaxis"]["tickprefix"] = "" if VIEW in ("pct","rmult","privacy") else "₹"
                lb["yaxis"]["ticksuffix"] = "%" if VIEW=="pct" else "R" if VIEW=="rmult" else ""
                lb["margin"] = dict(l=80, r=12, t=10, b=40)
                if bal_ctype == "Bar": lb["bargap"] = 0.2
                fig_b.update_layout(**lb)
                st.plotly_chart(fig_b, use_container_width=True, config={"displayModeBar":False})

    # Daily & Cumulative Net P&L
    with ch3:
        with st.container(border=True):
            _dcc1, _dcc2, _dcc3 = st.columns([3, 1, 1])
            _dcc1.markdown(f'<p style="font-size:11px;font-weight:600;color:{TEXT_H};margin:0">Daily & Cumulative P&L</p>', unsafe_allow_html=True)
            dc_daily_type = _dcc2.selectbox("Daily", CTYPES, index=1, key="dc_daily_type", label_visibility="collapsed")
            dc_cum_type   = _dcc3.selectbox("Cum", ["Line","Area"], index=1, key="dc_cum_type", label_visibility="collapsed")
            if dates_sorted:
                daily_vals = [daily_pnl[d] for d in dates_sorted]
                cum_vals   = [v for _,v in cum_by_date]
                fig_dc = go.Figure()
                # Cumulative on y2
                fig_dc.add_trace(_make_trace(dates_sorted, cum_vals, dc_cum_type, TEAL, "Cumulative", y2=True))
                # Daily bars/line
                fig_dc.add_trace(_make_trace(dates_sorted, daily_vals, dc_daily_type, "dual", "Daily"))
                ldc = chart_layout(height=CHART_H, title="")
                ldc["yaxis"]["tickprefix"] = "" if VIEW in ("pct","rmult","privacy") else "₹"
                ldc["yaxis"]["ticksuffix"] = "%" if VIEW=="pct" else "R" if VIEW=="rmult" else ""
                ldc["yaxis2"] = dict(overlaying="y", side="right", showgrid=False,
                                      tickprefix="" if VIEW in ("pct","rmult","privacy") else "₹", tickfont=dict(size=9))
                ldc["bargap"] = 0.2
                ldc["margin"] = dict(l=70, r=60, t=10, b=40)
                ldc["legend"] = dict(orientation="h", y=-0.2, font=dict(size=9))
                fig_dc.update_layout(**ldc)
                st.plotly_chart(fig_dc, use_container_width=True, config={"displayModeBar":False})

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── NET DAILY P&L + YOUR SCORE ────────────────────────────────────────────
    ch4, ch5 = st.columns([1, 1])

    # Shared height for both bottom cards
    BOTTOM_H = CHART_H - 38  # accounts for selectbox in Net Daily P&L

    with ch4:
        with st.container(border=True):
            ndp_ctype = st.selectbox("Net Daily P&L", CTYPES, index=1, key="ndp_ctype")
            if dates_sorted:
                daily_vals2 = [daily_pnl[d] for d in dates_sorted]
                fig_ndp = go.Figure()
                fig_ndp.add_hline(y=0, line=dict(color=BORDER_LIGHT, width=1))
                fig_ndp.add_trace(_make_trace(dates_sorted, daily_vals2, ndp_ctype, "dual", "Net Daily P&L"))
                lndp = chart_layout(height=BOTTOM_H, title="")
                lndp["yaxis"]["tickprefix"] = "" if VIEW in ("pct","rmult","privacy") else "₹"
                lndp["yaxis"]["ticksuffix"] = "%" if VIEW=="pct" else "R" if VIEW=="rmult" else ""
                lndp["bargap"] = 0.25
                lndp["margin"] = dict(l=70, r=12, t=10, b=40)
                fig_ndp.update_layout(**lndp)
                st.plotly_chart(fig_ndp, use_container_width=True, config={"displayModeBar":False})

    with ch5:
        with st.container(border=True):

            # ── Zella Score — 6 metrics with correct formulas ────────────────
            # 1. Avg Win/Loss ratio (using ₹ P&L, not R)
            awl_ratio = avg_win / abs(avg_loss) if avg_loss else 0
            if   awl_ratio >= 2.6:  awl_score = 100
            elif awl_ratio >= 2.4:  awl_score = 90 + (awl_ratio-2.4)/0.2*10
            elif awl_ratio >= 2.2:  awl_score = 80 + (awl_ratio-2.2)/0.2*10
            elif awl_ratio >= 2.0:  awl_score = 70 + (awl_ratio-2.0)/0.2*10
            elif awl_ratio >= 1.9:  awl_score = 60 + (awl_ratio-1.9)/0.1*10
            elif awl_ratio >= 1.8:  awl_score = 50 + (awl_ratio-1.8)/0.1*10
            else:                   awl_score = 20

            # 2. Trade Win % — (win%/60)*100 capped at 100
            win_pct_score = min((wr * 100 / 60) * 100, 100)

            # 3. Max Drawdown — 100 - drawdown%
            if pnl > 0 and max_dd < 0:
                max_dd_pct2 = abs(max_dd) / pnl * 100
            else:
                max_dd_pct2 = 0
            max_dd_score = max(0, 100 - max_dd_pct2)

            # 4. Profit Factor
            if   pf >= 2.6:  pf_score = 100
            elif pf >= 2.4:  pf_score = 90 + (pf-2.4)/0.2*10
            elif pf >= 2.2:  pf_score = 80 + (pf-2.2)/0.2*10
            elif pf >= 2.0:  pf_score = 70 + (pf-2.0)/0.2*10
            elif pf >= 1.9:  pf_score = 60 + (pf-1.9)/0.1*10
            elif pf >= 1.8:  pf_score = 50 + (pf-1.8)/0.1*10
            else:             pf_score = 20

            # 5. Recovery Factor = net profit / |max drawdown|
            rf = pnl / abs(max_dd) if max_dd < 0 else (3.5 if pnl > 0 else 0)
            if   rf >= 3.5:  rf_score = 100
            elif rf >= 3.0:  rf_score = 70 + (rf-3.0)/0.5*19
            elif rf >= 2.5:  rf_score = 60 + (rf-2.5)/0.5*10
            elif rf >= 2.0:  rf_score = 50 + (rf-2.0)/0.5*10
            elif rf >= 1.5:  rf_score = 30 + (rf-1.5)/0.5*19
            elif rf >= 1.0:  rf_score = 1  + (rf-1.0)/0.5*28
            else:             rf_score = 0

            # 6. Consistency — std dev of daily P&L / total profit
            daily_profits = list(daily_pnl.values())
            if pnl > 0 and len(daily_profits) > 1:
                cons_raw = float(np.std(daily_profits)) / pnl * 100
                cons_score = max(0, 100 - cons_raw)
            else:
                cons_score = 0

            # Weighted Zella Score
            # Recovery 10%, Win% 15%, AvgWL 20%, PF 25%, MaxDD 20%, Consistency 10%
            zella_score = (
                rf_score      * 0.10 +
                win_pct_score * 0.15 +
                awl_score     * 0.20 +
                pf_score      * 0.25 +
                max_dd_score  * 0.20 +
                cons_score    * 0.10
            )
            zella_score = round(zella_score, 2)

            # Radar data — 6 axes with score values in labels like TradeZella
            cats = [
                f"Win % ({win_pct_score:.0f})",
                f"Profit Factor ({pf_score:.0f})",
                f"Avg Win/Loss ({awl_score:.0f})",
                f"Recovery ({rf_score:.0f})",
                f"Max Drawdown ({max_dd_score:.0f})",
                f"Consistency ({cons_score:.0f})",
            ]
            vals = [win_pct_score, pf_score, awl_score, rf_score, max_dd_score, cons_score]

            st.markdown(f'<div style="height:28px;display:flex;align-items:center">'
                        f'<p style="font-size:11px;font-weight:600;color:{TEXT_H};margin:0">Your Score</p></div>',
                        unsafe_allow_html=True)
            # Spacer to match the selectbox height in Net Daily P&L
            st.markdown("<div style='height:38px'></div>", unsafe_allow_html=True)

            _sc1, _sc2 = st.columns([1.6, 1])
            with _sc1:
                fig_r = go.Figure(go.Scatterpolar(
                    r=vals+[vals[0]], theta=cats+[cats[0]],
                    fill="toself", fillcolor="rgba(124,58,237,0.15)",
                    line=dict(color="#7C3AED", width=1.5),
                    marker=dict(color="#7C3AED", size=4)))
                fig_r.update_layout(
                    polar=dict(bgcolor="rgba(0,0,0,0)",
                        radialaxis=dict(visible=True, range=[0,100], showticklabels=False,
                                       gridcolor="#94A3B8", linecolor="#94A3B8", gridwidth=1.5),
                        angularaxis=dict(tickfont=dict(size=9, color=TEXT_H),
                                        gridcolor="#94A3B8", linecolor="#94A3B8", linewidth=1.5)),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    height=BOTTOM_H, margin=dict(l=55, r=55, t=30, b=30), showlegend=False)
                st.plotly_chart(fig_r, use_container_width=True, config={"displayModeBar":False})

            with _sc2:
                # Score color
                score_col = "#EF4444" if zella_score < 40 else "#F59E0B" if zella_score < 65 else "#10B981"
                # Metric rows without the label suffix
                metric_names = ["Win %","Profit Factor","Avg Win/Loss","Recovery","Max Drawdown","Consistency"]
                metric_vals  = [win_pct_score, pf_score, awl_score, rf_score, max_dd_score, cons_score]
                rows_html = "".join(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:4px 0;border-bottom:1px solid {BORDER_LIGHT};font-size:10px">'
                    f'<span style="color:{TEXT_MUTED}">{n}</span>'
                    f'<span style="color:{TEXT_H};font-weight:600">{v:.0f}</span></div>'
                    for n,v in zip(metric_names, metric_vals))
                st.markdown(f"""<div style="display:flex;flex-direction:column;
                    justify-content:center;height:{BOTTOM_H}px;padding:0 8px">
                    <div style="font-size:9px;color:{TEXT_SUBTLE};letter-spacing:1px;text-transform:uppercase;margin-bottom:2px">ZELLA SCORE</div>
                    <div style="font-size:40px;font-weight:800;color:{score_col};
                        line-height:1;margin-bottom:4px">{zella_score}</div>
                    <div style="position:relative;height:8px;
                        background:linear-gradient(to right,#EF4444,#F59E0B,#10B981);
                        border-radius:4px;margin-bottom:3px">
                        <div style="position:absolute;top:-4px;left:{min(zella_score,97):.0f}%;
                            width:16px;height:16px;background:white;
                            border:2px solid {score_col};border-radius:50%;
                            transform:translateX(-50%)"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;
                        font-size:9px;color:{TEXT_SUBTLE};margin-bottom:10px">
                        <span>0</span><span>50</span><span>100</span>
                    </div>
                    {rows_html}
                </div>""", unsafe_allow_html=True)

    # ── PROGRESS TRACKER WIDGET ───────────────────────────────────────────────
    if W.get("progress_tracker", True):
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            pt_h1, pt_h2 = st.columns([4,1])
            with pt_h1:
                st.markdown(f'<p style="font-size:11px;font-weight:600;color:{TEXT_H};margin:0">Progress Tracker</p>', unsafe_allow_html=True)
            with pt_h2:
                if st.button("View more →", key="pt_view_more"):
                    st.session_state.page = "progress"
                    st.rerun()

            pt_col1, pt_col2 = st.columns([1.8, 1])

            # ── shared PT helpers ─────────────────────────────────────────────
            import sqlite3 as _sq3
            from datetime import date as _date, timedelta as _td
            from collections import defaultdict as _dd

            # DB is always journal.db in the parent of pages/
            _DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "journal.db"))

            def _pt_rules():
                try:
                    _c = _sq3.connect(_DB); _c.row_factory = _sq3.Row
                    _rows = _c.execute("SELECT * FROM pt_rules WHERE enabled=1 ORDER BY sort_order,id").fetchall()
                    _c.close(); return [dict(r) for r in _rows]
                except: return []

            def _pt_checkins_today(_d_str):
                try:
                    _c = _sq3.connect(_DB); _c.row_factory = _sq3.Row
                    _rows = _c.execute("SELECT rule_id,completed FROM pt_checkins WHERE checkin_date=?", (_d_str,)).fetchall()
                    _c.close(); return {r["rule_id"]: r["completed"] for r in _rows}
                except: return {}

            def _pt_scores(weeks=12):
                """Score each trading day from automated rule evaluation."""
                try:
                    _today2 = _date.today()
                    _start2 = _today2 - _td(weeks=weeks)
                    _rules2 = _pt_rules()
                    if not _rules2: return {}
                    # Build daily trade map from closed trades
                    _by_day = _dd(list)
                    _day_pnl = _dd(float)
                    for _t2 in closed:
                        _d2 = str(_t2.get("exit_date","") or "")[:10]
                        if _d2 and _d2 >= _start2.isoformat():
                            _by_day[_d2].append(_t2)
                            _day_pnl[_d2] += float(_t2.get("pnl") or 0)
                    # Also get manual checkins
                    _c2 = _sq3.connect(_DB); _c2.row_factory = _sq3.Row
                    _ci2 = _dd(dict)
                    for _row2 in _c2.execute("SELECT checkin_date,rule_id,completed FROM pt_checkins WHERE checkin_date>=?", (_start2.isoformat(),)).fetchall():
                        _ci2[_row2["checkin_date"]][_row2["rule_id"]] = _row2["completed"]
                    _c2.close()
                    _scores2 = {}
                    for _d2 in _by_day:
                        _done2 = 0
                        for _r2 in _rules2:
                            _rn2 = _r2.get("name","").lower()
                            if _r2.get("rule_type") == "manual":
                                if _ci2[_d2].get(_r2["id"],0): _done2 += 1
                            elif "stop loss" in _rn2:
                                if all(_t2.get("stop_loss") for _t2 in _by_day[_d2]): _done2 += 1
                            elif "max loss per trade" in _rn2:
                                try: _lim2 = float(_r2.get("condition_value") or 9999999)
                                except: _lim2 = 9999999
                                if min((float(_t2.get("pnl") or 0) for _t2 in _by_day[_d2]), default=0) >= -abs(_lim2): _done2 += 1
                            elif "max loss per day" in _rn2:
                                try: _lim2 = float(_r2.get("condition_value") or 9999999)
                                except: _lim2 = 9999999
                                if _day_pnl[_d2] >= -abs(_lim2): _done2 += 1
                        _scores2[_d2] = int(_done2/len(_rules2)*100)
                    return _scores2
                except: return {}

            def _cell_col(score):
                if score is None: return "#F3F4F6"
                if score>=80: return "#1d4ed8"
                if score>=60: return "#3b82f6"
                if score>=40: return "#93c5fd"
                if score>=20: return "#bfdbfe"
                return "#dbeafe"

            _pt_rules_list   = _pt_rules()
            _today_str2      = _date.today().isoformat()
            _ci_today        = _pt_checkins_today(_today_str2)
            _total_rules = len(_pt_rules_list)
            # Evaluate automated rules from today's trades
            _done_rules = 0
            for _r in _pt_rules_list:
                if _r.get("rule_type") == "manual":
                    if _ci_today.get(_r["id"], 0): _done_rules += 1
                else:
                    # Automated — check against trades
                    _rn = _r.get("name","").lower()
                    _cv = _r.get("condition_value","") or "0"
                    try: _lim = float(_cv)
                    except: _lim = 0
                    _today_pnl2 = sum(float(t.get("pnl") or 0) for t in closed
                                     if str(t.get("exit_date","") or "")[:10] == _today_str2)
                    _today_t2   = [t for t in closed if str(t.get("exit_date","") or "")[:10] == _today_str2]
                    if "stop loss" in _rn:
                        _passed = all(t.get("stop_loss") for t in _today_t2) if _today_t2 else True
                    elif "max loss per trade" in _rn:
                        _worst = min((float(t.get("pnl") or 0) for t in _today_t2), default=0)
                        _passed = _worst >= -abs(_lim) if _lim else True
                    elif "max loss per day" in _rn:
                        _passed = _today_pnl2 >= -abs(_lim) if _lim else True
                    else:
                        _passed = False
                    if _passed: _done_rules += 1
            _score_pct2      = int(_done_rules/_total_rules*100) if _total_rules else 0
            _sc_col2         = "#10B981" if _score_pct2>=70 else "#F59E0B" if _score_pct2>=40 else "#EF4444"
            _heat_scores     = _pt_scores()

            with pt_col1:
                # Heatmap
                _today3 = _date.today()
                _start3 = _today3 - _td(weeks=12)
                _DAYS   = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]

                _html = '<div style="overflow-x:auto">'
                _html += '<table style="border-collapse:separate;border-spacing:2px 2px">'
                _html += "<tr><td></td>"
                _cur3 = _start3; _last_mo3 = ""
                while _cur3 <= _today3:
                    _mo3 = _cur3.strftime("%b")
                    _html += f'<td style="font-size:8px;color:{TEXT_MUTED};padding-bottom:1px">{"" if _mo3==_last_mo3 else _mo3}</td>'
                    _last_mo3 = _mo3; _cur3 += _td(weeks=1)
                _html += "</tr>"

                for _di in range(7):
                    _html += f'<tr><td style="font-size:8px;color:{TEXT_MUTED};padding-right:3px;white-space:nowrap">{_DAYS[_di]}</td>'
                    _cur3 = _start3 + _td(days=_di)
                    while _cur3 <= _today3:
                        _ds3 = _cur3.isoformat()
                        _sc3 = _heat_scores.get(_ds3)
                        _html += f'<td title="{_ds3}{": "+str(_sc3)+"%" if _sc3 is not None else ""}" style="width:11px;height:11px;background:{_cell_col(_sc3)};border-radius:2px"></td>'
                        _cur3 += _td(weeks=1)
                    _html += "</tr>"

                _html += "</table>"
                _html += f'<div style="display:flex;align-items:center;gap:3px;margin-top:5px;font-size:8px;color:{TEXT_MUTED}">Less '
                for _bg3 in ["#dbeafe","#bfdbfe","#93c5fd","#3b82f6","#1d4ed8"]:
                    _html += f'<div style="width:10px;height:10px;background:{_bg3};border-radius:2px"></div>'
                _html += " More</div></div>"
                st.markdown(_html, unsafe_allow_html=True)

            with pt_col2:
                if not _pt_rules_list:
                    st.markdown(f'<p style="font-size:11px;color:{TEXT_MUTED};padding:12px 0">No rules set up yet.<br><a href="#" style="color:{TEAL}">Go to Progress Tracker</a> to add rules.</p>', unsafe_allow_html=True)
                else:
                    _checklist_html = f"""<div style="padding:4px 0">
                        <div style="font-size:9px;color:{TEXT_SUBTLE};letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">TODAY'S SCORE</div>
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                            <span style="font-size:22px;font-weight:800;color:{_sc_col2}">{_done_rules}/{_total_rules}</span>
                            <div style="flex:1;height:8px;background:#F3F4F6;border-radius:4px;overflow:hidden">
                                <div style="width:{_score_pct2}%;height:100%;background:{_sc_col2};border-radius:4px"></div>
                            </div>
                        </div>
                        <div style="font-size:9px;color:{TEXT_SUBTLE};letter-spacing:1px;text-transform:uppercase;margin-bottom:5px">DAILY CHECKLIST</div>"""
                    for r in _pt_rules_list[:6]:
                        _tick = "✅" if _ci_today.get(r["id"],0) else "⬜"
                        _checklist_html += f'<div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:11px;border-bottom:1px solid {BORDER_LIGHT}"><span>{_tick}</span><span style="color:{TEXT_H}">{r["name"]}</span></div>'
                    _checklist_html += "</div>"
                    st.markdown(_checklist_html, unsafe_allow_html=True)
