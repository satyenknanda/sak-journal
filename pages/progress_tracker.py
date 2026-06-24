# -*- coding: utf-8 -*-
import streamlit as st
import json, os
from datetime import date, datetime, timedelta
from collections import defaultdict

from theme import *
from data.db import get_trades, get_kpi_summary_extended as get_kpi

G="#10B981"; R="#EF4444"; B="#3B82F6"; AM="#F59E0B"; PU="#7C3AED"
TEXT="#111827"; MUTED="#6B7280"; BORDER="#E5E7EB"; BG="#FFFFFF"; HEADER_BG="#F9FAFB"

# ── Persistence helpers ────────────────────────────────────────────────────────
from data.db import _sb as _get_sb

def init_pt_db():
    """Supabase tables created via SQL editor — nothing to init."""
    _seed_default_rules()

def _seed_default_rules():
    """Seed default rules if table is empty."""
    try:
        sb = _get_sb()
        existing = sb.table("pt_rules").select("id").limit(1).execute()
        if existing.data: return
        defaults = [
            ("Start my day by", "Enter your starting journal entry before your trading session", "automated", "time", "09:00", "Mon,Tue,Wed,Thu,Fri"),
            ("Trade has stop loss", "All trades opened today have a stop loss set", "automated", "pct", "100", "Mon,Tue,Wed,Thu,Fri"),
            ("Max loss per trade", "Maximum loss on a single trade", "automated", "amount", "5000", "Mon,Tue,Wed,Thu,Fri"),
            ("Max loss per day", "Maximum loss across all trades for the day", "automated", "amount", "10000", "Mon,Tue,Wed,Thu,Fri"),
            ("Link trades to playbook", "All trades opened must have a playbook attached.", "automated", "pct", "100", "Mon,Tue,Wed,Thu,Fri"),
            ("Input Stop loss to all trades", "All trades must have a stop loss value entered", "automated", "pct", "100", "Mon,Tue,Wed,Thu,Fri"),
            ("Net max loss /trade", "Maximum net loss on a single trade", "automated", "amount", "45000", "Mon,Tue,Wed,Thu,Fri"),
            ("Net max loss /day", "Maximum net loss across all trades for the day", "automated", "amount", "90000", "Mon,Tue,Wed,Thu,Fri"),
            ("Post Market Evening Routine", "Complete your post-market review", "manual", "checkbox", "", "Mon,Tue,Wed,Thu,Fri"),
            ("Morning Pre Market Routine", "Complete your pre-market preparation", "manual", "checkbox", "", "Mon,Tue,Wed,Thu,Fri"),
            ("Mid-day Trades Updates", "Update your trade journal mid-day", "manual", "checkbox", "", "Mon,Tue,Wed,Thu,Fri"),
            ("Daily Watchlist Update", "Update your watchlist for tomorrow", "manual", "checkbox", "", "Mon,Tue,Wed,Thu,Fri"),
        ]
        for i, (name, desc, rtype, ctype, cval, days) in enumerate(defaults):
            sb.table("pt_rules").insert({
                "name": name, "description": desc, "rule_type": rtype,
                "condition_type": ctype, "condition_value": cval,
                "active_days": days, "sort_order": i, "enabled": 1
            }).execute()
    except Exception as e:
        print(f"Seed error: {e}")

def get_rules():
    try:
        res = _get_sb().table("pt_rules").select("*").eq("enabled", 1).order("rule_type").order("sort_order").order("id").execute()
        return res.data or []
    except: return []

def get_all_rules():
    try:
        res = _get_sb().table("pt_rules").select("*").order("rule_type").order("sort_order").order("id").execute()
        return res.data or []
    except: return []

def save_rule(name, desc, rule_type, cond_type, cond_value, active_days, enabled=1):
    try:
        _get_sb().table("pt_rules").insert({
            "name": name, "description": desc, "rule_type": rule_type,
            "condition_type": cond_type, "condition_value": cond_value,
            "active_days": active_days, "enabled": enabled
        }).execute()
    except Exception as e: print(f"save_rule error: {e}")

def update_rule(rule_id, name, desc, cond_type, cond_value, active_days, enabled):
    try:
        _get_sb().table("pt_rules").update({
            "name": name, "description": desc, "condition_type": cond_type,
            "condition_value": cond_value, "active_days": active_days, "enabled": enabled
        }).eq("id", rule_id).execute()
    except Exception as e: print(f"update_rule error: {e}")

def delete_rule(rule_id):
    try:
        _get_sb().table("pt_checkins").delete().eq("rule_id", rule_id).execute()
        _get_sb().table("pt_rules").delete().eq("id", rule_id).execute()
    except Exception as e: print(f"delete_rule error: {e}")

def get_checkins(d_str):
    try:
        res = _get_sb().table("pt_checkins").select("rule_id,completed").eq("checkin_date", d_str).execute()
        return {r["rule_id"]: r["completed"] for r in (res.data or [])}
    except: return {}

def set_checkin(d_str, rule_id, completed):
    try:
        _get_sb().table("pt_checkins").upsert({
            "checkin_date": d_str, "rule_id": rule_id, "completed": completed
        }, on_conflict="checkin_date,rule_id").execute()
    except Exception as e: print(f"set_checkin error: {e}")

def get_checkins_range(start, end):
    try:
        res = _get_sb().table("pt_checkins").select("checkin_date,rule_id,completed").gte("checkin_date", start).lte("checkin_date", end).execute()
        return res.data or []
    except: return []

def seed_default_rules():
    """Already handled by _seed_default_rules() in init_pt_db — no-op here."""
    pass

def is_rule_active_today(rule, d=None):
    if d is None: d = date.today()
    day_abbr = d.strftime("%a")  # Mon, Tue etc
    active = rule.get("active_days","Mon,Tue,Wed,Thu,Fri")
    return day_abbr in active.split(",")

def evaluate_automated_rule(rule, trades_today, day_pnl):
    """All rules are now manual checkboxes."""
    return False

def score_day(rules, checkins, trades_today, day_pnl, d=None):
    """Return (completed, total) for a given day."""
    active = [r for r in rules if is_rule_active_today(r, d)]
    if not active: return 0, 0
    completed = 0
    for r in active:
        if checkins.get(r["id"], 0): completed += 1
    return completed, len(active)

# ── Heatmap ───────────────────────────────────────────────────────────────────
def build_heatmap(rules, all_trades, start_date, end_date):
    """Build GitHub-style heatmap data: date -> score 0-100."""
    by_date = defaultdict(list)
    daily_pnl = defaultdict(float)
    for t in all_trades:
        d = str(t.get("exit_date") or t.get("entry_date") or "")[:10]
        if d and d != "nan":
            by_date[d].append(t)
            daily_pnl[d] += float(t.get("pnl") or 0)

    scores = {}
    cur = start_date
    while cur <= end_date:
        d_str = cur.isoformat()
        checkins = get_checkins(d_str)
        trades = by_date.get(d_str, [])
        c, t = score_day(rules, checkins, trades, daily_pnl.get(d_str, 0), cur)
        if t > 0:
            scores[d_str] = int(c/t*100)
        cur += timedelta(days=1)
    return scores

def heatmap_html(scores, weeks=12):
    """Render GitHub-style activity heatmap."""
    today = date.today()
    start = today - timedelta(weeks=weeks)
    # Align to Sunday
    start = start - timedelta(days=start.weekday()+1) if start.weekday() != 6 else start

    # Build month labels
    months = {}
    cur = start
    col_idx = 0
    while cur <= today:
        mo = cur.strftime("%b")
        if mo not in months: months[mo] = col_idx
        cur += timedelta(weeks=1)
        col_idx += 1

    def cell_color(score):
        if score is None: return "#F3F4F6"
        if score >= 80: return "#1d4ed8"
        if score >= 60: return "#3b82f6"
        if score >= 40: return "#93c5fd"
        if score >= 20: return "#bfdbfe"
        return "#dbeafe"

    # Build grid week-by-week
    DAYS = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
    COL_W = 14; ROW_H = 14; GAP = 2

    html = f'<div style="overflow-x:auto;padding-bottom:4px">'
    html += '<table style="border-collapse:separate;border-spacing:{g}px {g}px">'.format(g=GAP)

    # Month row
    html += "<tr><td></td>"
    cur = start; col = 0
    last_mo = ""
    while cur <= today:
        mo = cur.strftime("%b")
        if mo != last_mo:
            html += f'<td colspan="1" style="font-size:9px;color:{MUTED};padding-bottom:2px">{mo}</td>'
            last_mo = mo
        else:
            html += "<td></td>"
        cur += timedelta(weeks=1); col += 1
    html += "</tr>"

    for day_idx in range(7):
        html += f'<tr><td style="font-size:9px;color:{MUTED};padding-right:4px;white-space:nowrap">{DAYS[day_idx]}</td>'
        cur = start + timedelta(days=day_idx)
        while cur <= today:
            d_str = cur.isoformat()
            score = scores.get(d_str)
            bg = cell_color(score)
            tip = f"{d_str}: {score}%" if score is not None else d_str
            html += f'<td title="{tip}" style="width:{COL_W}px;height:{ROW_H}px;background:{bg};border-radius:2px;cursor:default"></td>'
            cur += timedelta(weeks=1)
        html += "</tr>"

    html += "</table>"
    # Legend
    html += f'<div style="display:flex;align-items:center;gap:4px;margin-top:6px;font-size:9px;color:{MUTED}">'
    html += "Less "
    for bg in ["#dbeafe","#bfdbfe","#93c5fd","#3b82f6","#1d4ed8"]:
        html += f'<div style="width:12px;height:12px;background:{bg};border-radius:2px"></div>'
    html += " More</div></div>"
    return html

# ── Rules dialog ──────────────────────────────────────────────────────────────
@st.dialog("Edit Rules", width="large")
def rules_dialog():
    st.caption("Changes you make will only update your scoring for today and for future days.")

    all_r = get_all_rules()
    auto_rules   = [r for r in all_r if r["rule_type"]=="automated"]
    manual_rules = [r for r in all_r if r["rule_type"]=="manual"]
    existing     = {r["name"]: r for r in auto_rules}

    # ── Trading days ──────────────────────────────────────────────────────────
    st.markdown("**Trading days**")
    st.caption("The days on which these rules should be active.")
    _dl = ["Mo","Tu","We","Th","Fr","Sa","Su"]
    _df = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    _def = (auto_rules[0].get("active_days","Mon,Tue,Wed,Thu,Fri") if auto_rules else "Mon,Tue,Wed,Thu,Fri").split(",")
    _dcols = st.columns(7)
    _sel_days = []
    for _i,(_s,_f) in enumerate(zip(_dl,_df)):
        with _dcols[_i]:
            if st.checkbox(_s, value=_f in _def, key=f"td_{_f}"): _sel_days.append(_f)
    _active_days = ",".join(_sel_days) if _sel_days else "Mon,Tue,Wed,Thu,Fri"

    st.markdown("---")

    # ── Automated Rules ───────────────────────────────────────────────────────
    ADEFS = [
        ("Start my day by",               "The time you should start your day by and enter your starting journal entry before your trading session.", "time",   "09:15"),
        ("Link trades to playbook",        "All trades opened must have a playbook attached.",                                                         "pct",    "100"),
        ("Input Stop loss to all trades",  "All trades opened must have a stop loss added.",                                                           "pct",    "100"),
        ("Net max loss /trade",            "The maximum net loss on a trade in amount or in percentage of the trade account balance.",                  "amount", "5000"),
        ("Net max loss /day",              "The maximum net loss on a day among all accounts.",                                                        "amount", "10000"),
    ]
    st.markdown("#### Automated Rules")
    _upd = {}
    for _name, _desc, _ctype, _dval in ADEFS:
        _r = existing.get(_name, {"id": None, "enabled": 1, "condition_value": _dval})
        with st.container(border=True):
            _cc1, _cc2 = st.columns([3, 1])
            with _cc1:
                _en = st.toggle(f"**{_name}**", value=bool(_r.get("enabled",1)), key=f"ae_{_name}")
                st.caption(_desc)
            with _cc2:
                if _ctype == "time":
                    _val = st.text_input("Time (HH:MM)", value=_r.get("condition_value",_dval), key=f"av_{_name}", label_visibility="collapsed", placeholder="09:15")
                elif _ctype == "pct":
                    _val = st.text_input("%", value=_r.get("condition_value",_dval), key=f"av_{_name}", label_visibility="collapsed")
                    st.caption("% threshold")
                else:
                    _val = st.text_input("₹ Amount", value=_r.get("condition_value",_dval), key=f"av_{_name}", label_visibility="collapsed")
            _upd[_name] = {"enabled": int(_en), "condition_value": _val, "condition_type": _ctype, "description": _desc}

    st.markdown("---")

    # ── Manual Rules ──────────────────────────────────────────────────────────
    st.markdown("#### Manual Rules")
    st.caption("The rule will be added as a daily check list")

    _d3map = {"Mon-Fri":"Mon,Tue,Wed,Thu,Fri","Mon-Sat":"Mon,Tue,Wed,Thu,Fri,Sat","Every day":"Mon,Tue,Wed,Thu,Fri,Sat,Sun"}
    for _mr in manual_rules:
        with st.container(border=True):
            _mc1, _mc2, _mc3 = st.columns([3, 1.2, 0.3])
            _mname = _mc1.text_input("⠿ Rule", value=_mr["name"], key=f"mr_n_{_mr['id']}", label_visibility="collapsed")
            _mdays_raw = _mr.get("active_days","Mon,Tue,Wed,Thu,Fri")
            _midx = 0 if _mdays_raw=="Mon,Tue,Wed,Thu,Fri" else (1 if _mdays_raw=="Mon,Tue,Wed,Thu,Fri,Sat" else 2)
            _msel = _mc2.selectbox("Days", ["Mon-Fri","Mon-Sat","Every day"], index=_midx, key=f"mr_d_{_mr['id']}", label_visibility="collapsed")
            with _mc3:
                if st.button("🗑", key=f"mr_del_{_mr['id']}"): delete_rule(_mr["id"]); st.rerun()
            if st.button("Save", key=f"mr_sv_{_mr['id']}", use_container_width=True):
                update_rule(_mr["id"], _mname, _mr.get("description",""), "checkbox", "", _d3map.get(_msel,"Mon,Tue,Wed,Thu,Fri"), 1)
                st.rerun()

    st.markdown("---")
    if "pt_show_add" not in st.session_state: st.session_state.pt_show_add = False
    if st.button("＋ Add rule", key="pt_add_btn"): st.session_state.pt_show_add = True
    if st.session_state.pt_show_add:
        with st.container(border=True):
            _na1, _na2 = st.columns([3,1])
            _nn = _na1.text_input("Rule name", placeholder="e.g. Morning workout", key="pt_nr_name")
            _nd = _na2.selectbox("Days", ["Mon-Fri","Mon-Sat","Every day"], key="pt_nr_days")
            if st.button("Add", type="primary", key="pt_add_confirm"):
                if _nn.strip():
                    save_rule(_nn.strip(),"","manual","checkbox","",_d3map.get(_nd,"Mon,Tue,Wed,Thu,Fri"))
                    st.session_state.pt_show_add = False; st.rerun()

    st.markdown("---")

    # ── Reset ─────────────────────────────────────────────────────────────────
    st.markdown("**Reset your progress tracker**")
    st.caption("Start over with new rules, streak, and habit building.")
    if "pt_confirm_rst" not in st.session_state: st.session_state.pt_confirm_rst = False
    if st.button("🔄 Reset all progress", key="pt_rst_btn"):
        st.session_state.pt_confirm_rst = True
    if st.session_state.pt_confirm_rst:
        st.warning("⚠️ This will clear all checkins and streaks. Trades will NOT be deleted.")
        _rc1, _rc2 = st.columns(2)
        if _rc1.button("✅ Yes, reset", type="primary", key="pt_rst_yes"):
            try: _get_sb().table("pt_checkins").delete().neq("id", 0).execute()
            except Exception as _e: st.error(f"Reset failed: {_e}")
            st.session_state.pt_confirm_rst = False; st.success("Reset done!"); st.rerun()
        if _rc2.button("Cancel", key="pt_rst_no"):
            st.session_state.pt_confirm_rst = False; st.rerun()

    st.markdown("---")

    # ── Save / Cancel ─────────────────────────────────────────────────────────
    _sb1, _sb2 = st.columns(2)
    with _sb1:
        if st.button("Cancel", use_container_width=True, key="rules_cancel"): st.rerun()
    with _sb2:
        if st.button("Save changes", type="primary", use_container_width=True, key="rules_save"):
            for _aname, _adesc, _actype, _adval in ADEFS:
                _au = _upd.get(_aname, {})
                _ex = existing.get(_aname)
                if _ex:
                    update_rule(_ex["id"], _aname, _au.get("description",_adesc),
                                _au.get("condition_type",_actype), _au.get("condition_value",_adval),
                                _active_days, _au.get("enabled",1))
                else:
                    save_rule(_aname, _au.get("description",_adesc), "automated",
                              _au.get("condition_type",_actype), _au.get("condition_value",_adval),
                              _active_days, _au.get("enabled",1))
            st.success("✅ Rules saved!"); st.rerun()

# ── Main render ────────────────────────────────────────────────────────────────
def render():
    init_pt_db()
    seed_default_rules()

    today = date.today()
    today_str = today.isoformat()
    day_name = today.strftime("%A")

    # Load trades
    all_trades = get_trades()
    closed = [t for t in all_trades if t.get("status")=="CLOSED"]

    by_date = defaultdict(list)
    daily_pnl_map = defaultdict(float)
    for t in closed:
        d = str(t.get("exit_date") or "")[:10]
        if d and d != "nan":
            by_date[d].append(t)
            daily_pnl_map[d] += float(t.get("pnl") or 0)

    today_trades = by_date.get(today_str, [])
    today_pnl = daily_pnl_map.get(today_str, 0)

    rules = get_rules()
    checkins_today = get_checkins(today_str)

    # Today's score
    c, t = score_day(rules, checkins_today, today_trades, today_pnl)
    score_pct = int(c/t*100) if t else 0

    # ── Header ─────────────────────────────────────────────────────────────────
    h1, h2 = st.columns([4,1])
    with h1:
        st.markdown("## Progress Tracker")
        st.markdown(f'<p style="color:{MUTED};margin-top:-10px;margin-bottom:14px;font-size:0.88rem">Build good trading habits · Track consistency · Stay disciplined</p>', unsafe_allow_html=True)
    with h2:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("✏️ Edit Rules", use_container_width=True):
            rules_dialog()

    # ── Top row: Streak + Checklist + Heatmap ──────────────────────────────────
    col_streak, col_check, col_heat = st.columns([1, 1.2, 2.5])

    with col_streak:
        # Calculate streak
        streak = 0; d_check = today
        while True:
            ds = d_check.isoformat()
            ci = get_checkins(ds)
            dt = by_date.get(ds, [])
            dp = daily_pnl_map.get(ds, 0)
            sc, st2 = score_day(rules, ci, dt, dp, d_check)
            if st2 == 0 or sc < st2:
                break
            streak += 1; d_check -= timedelta(days=1)
            if streak > 365: break

        sc_col = G if score_pct >= 70 else AM if score_pct >= 40 else R
        emoji = "😊" if score_pct >= 70 else "😐" if score_pct >= 40 else "😟"

        st.markdown(f"""<div style="background:{BG};border:1px solid {BORDER};border-radius:12px;padding:20px;text-align:center;height:200px;display:flex;flex-direction:column;justify-content:center">
            <div style="font-size:11px;color:{MUTED};font-weight:600;letter-spacing:1px;margin-bottom:8px">CURRENT STREAK</div>
            <div style="font-size:48px;font-weight:800;color:{TEXT};line-height:1">{streak}</div>
            <div style="font-size:16px;margin:4px 0">{emoji}</div>
            <div style="font-size:13px;color:{MUTED}">{streak} day{"s" if streak!=1 else ""}</div>
        </div>""", unsafe_allow_html=True)

    with col_check:
        # Daily checklist
        active_rules = [r for r in rules if is_rule_active_today(r)]
        auto_r = [r for r in active_rules if r["rule_type"]=="automated"]
        manual_r = [r for r in active_rules if r["rule_type"]=="manual"]

        # Score gauge
        gauge_col = G if score_pct >= 70 else AM if score_pct >= 40 else R
        st.markdown(f"""<div style="background:{BG};border:1px solid {BORDER};border-radius:12px;padding:16px">
            <div style="font-size:12px;font-weight:700;color:{TEXT};margin-bottom:4px">Daily Checklist · {today.strftime('%b %d')}</div>
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
                <div style="font-size:28px;font-weight:800;color:{gauge_col}">{c}/{t}</div>
                <div style="flex:1;height:8px;background:#F3F4F6;border-radius:4px;overflow:hidden">
                    <div style="width:{score_pct}%;height:100%;background:{gauge_col};border-radius:4px;transition:width 0.3s"></div>
                </div>
            </div>""", unsafe_allow_html=True)

        if auto_r:
            st.markdown(f'<div style="font-size:10px;color:{MUTED};font-weight:600;letter-spacing:1px;margin-bottom:6px">AUTOMATED RULES ({len(auto_r)})</div>', unsafe_allow_html=True)
            for r in auto_r:
                completed = bool(checkins_today.get(r["id"], 0))
                cv = r.get("condition_value","")
                label = f"{r['name']} · {cv}" if cv else r["name"]
                new_val = st.checkbox(label, value=completed, key=f"chk_auto_{r['id']}_{today_str}")
                if new_val != completed:
                    set_checkin(today_str, r["id"], int(new_val))
                    st.rerun()

        if manual_r:
            st.markdown(f'<div style="font-size:10px;color:{MUTED};font-weight:600;letter-spacing:1px;margin:8px 0 4px">MANUAL RULES ({len(manual_r)})</div>', unsafe_allow_html=True)
            for r in manual_r:
                completed = bool(checkins_today.get(r["id"], 0))
                new_val = st.checkbox(r["name"], value=completed, key=f"chk_{r['id']}_{today_str}")
                if new_val != completed:
                    set_checkin(today_str, r["id"], int(new_val))
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    with col_heat:
        st.markdown(f"""<div style="background:{BG};border:1px solid {BORDER};border-radius:12px;padding:16px">
            <div style="font-size:12px;font-weight:700;color:{TEXT};margin-bottom:10px">Progress Tracker — Activity Heatmap</div>""", unsafe_allow_html=True)

        # Build heatmap
        heat_start = today - timedelta(weeks=12)
        scores = build_heatmap(rules, all_trades, heat_start, today)
        st.markdown(heatmap_html(scores, weeks=12), unsafe_allow_html=True)

        # Today's score
        st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;margin-top:10px;padding-top:10px;border-top:1px solid {BORDER}">
            <div>
                <div style="font-size:9px;color:{MUTED};letter-spacing:1px">TODAY'S SCORE</div>
                <div style="font-size:18px;font-weight:800;color:{gauge_col}">{c}/{t}</div>
            </div>
            <div style="flex:1;height:8px;background:#F3F4F6;border-radius:4px;overflow:hidden">
                <div style="width:{score_pct}%;height:100%;background:{gauge_col};border-radius:4px"></div>
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Current Rules table ───────────────────────────────────────────────────
    st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <span style="font-size:16px;font-weight:700;color:{TEXT}">Current Rules</span>
    </div>""", unsafe_allow_html=True)

    all_r = get_all_rules()
    if not all_r:
        st.info("No rules set up yet. Click **Edit Rules** to add some.")
        return

    # Calculate follow rates (last 30 days)
    hist_start = (today - timedelta(days=30)).isoformat()
    hist_rows = get_checkins_range(hist_start, today_str)
    checkin_hist = defaultdict(lambda: defaultdict(int))
    for row in hist_rows:
        checkin_hist[row["rule_id"]][row["checkin_date"]] = row["completed"]

    th = f"padding:9px 14px;text-align:left;color:{MUTED};font-size:10px;text-transform:uppercase;letter-spacing:0.07em;font-weight:600;border-bottom:2px solid {BORDER};background:{HEADER_BG};white-space:nowrap"
    td_s = f"padding:9px 14px;font-size:13px;border-bottom:1px solid {BORDER}"

    rows_html = ""
    for r in all_r:
        # Follow rate
        active_days_list = [today - timedelta(days=i) for i in range(30)
                            if is_rule_active_today(r, today - timedelta(days=i))]
        if r["rule_type"] == "automated":
            # Count days where rule passed
            passed_days = 0
            for d_obj in active_days_list:
                ds = d_obj.isoformat()
                dt = by_date.get(ds, [])
                dp = daily_pnl_map.get(ds, 0)
                if evaluate_automated_rule(r, dt, dp): passed_days += 1
            follow_rate = int(passed_days / len(active_days_list) * 100) if active_days_list else 0
        else:
            completed_count = sum(1 for d_obj in active_days_list
                                  if checkin_hist[r["id"]].get(d_obj.isoformat(), 0))
            follow_rate = int(completed_count / len(active_days_list) * 100) if active_days_list else 0

        fr_col = G if follow_rate >= 70 else AM if follow_rate >= 40 else R
        en_badge = f'<span style="background:#F0FDF4;color:{G};padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600">Active</span>' if r["enabled"] else f'<span style="background:#F3F4F6;color:{MUTED};padding:2px 8px;border-radius:20px;font-size:11px">Disabled</span>'
        type_badge = f'<span style="background:#EDE9FE;color:{PU};padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600">AUTO</span>' if r["rule_type"]=="automated" else f'<span style="background:#F0F9FF;color:{B};padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600">MANUAL</span>'

        cv = r.get("condition_value","") or "—"
        active_days = r.get("active_days","").replace(",","·")

        rows_html += f"""<tr style="background:{BG}">
            <td style="{td_s}">{type_badge}</td>
            <td style="{td_s};font-weight:600;color:{TEXT}">{r['name']}</td>
            <td style="{td_s};color:{MUTED};font-size:12px">{r.get('description','')}</td>
            <td style="{td_s};font-family:monospace;font-size:12px">{cv}</td>
            <td style="{td_s};font-size:12px;color:{MUTED}">{active_days}</td>
            <td style="{td_s}">{en_badge}</td>
            <td style="{td_s};font-weight:700;color:{fr_col}">{follow_rate}%</td>
        </tr>"""

    st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER};box-shadow:0 1px 3px rgba(0,0,0,0.05)">
    <table style="width:100%;border-collapse:collapse">
    <thead><tr>
        {"".join(f'<th style="{th}">{h}</th>' for h in ["Type","Rule","Description","Condition","Active Days","Status","Follow Rate (30d)"])}
    </tr></thead>
    <tbody>{rows_html}</tbody>
    </table></div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Historical performance ────────────────────────────────────────────────
    with st.expander("📊 Historical Score Breakdown (Last 30 Days)"):
        hist_data = []
        for i in range(30):
            d_obj = today - timedelta(days=i)
            ds = d_obj.isoformat()
            ci = get_checkins(ds)
            dt = by_date.get(ds, [])
            dp = daily_pnl_map.get(ds, 0)
            sc2, tt2 = score_day(rules, ci, dt, dp, d_obj)
            if tt2 > 0:
                hist_data.append({"Date": ds, "Day": d_obj.strftime("%a"), "Score": f"{sc2}/{tt2}", "Pct": int(sc2/tt2*100), "P&L": f"₹{dp:,.0f}"})

        if hist_data:
            import pandas as pd
            df = pd.DataFrame(hist_data)
            def color_pct(row):
                pct = row.get("Pct",0)
                c2 = G if pct>=70 else AM if pct>=40 else R
                return [""]*len(row.index) if not hasattr(row,"index") else [f"color:{c2}" if col=="Pct" else "" for col in df.columns]
            st.dataframe(df.drop(columns=["Pct"]), use_container_width=True, hide_index=True)
