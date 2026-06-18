import streamlit as st
import pandas as pd
import calendar as cal_mod
from datetime import date
from collections import defaultdict
from data.db import get_journal_trades
from theme import *

def render():
    st.markdown("## Calendar")
    st.markdown(f'<p style="color:{TEXT_MUTED};margin-top:-8px;margin-bottom:18px;font-size:12px">FY 2026-27 · Daily P&L view</p>', unsafe_allow_html=True)

    trades = get_journal_trades()
    closed = [t for t in trades if t["status"] == "CLOSED"]

    all_months = sorted({str(t.get("exit_date","") or "")[:7]
                         for t in closed if t.get("exit_date") and str(t.get("exit_date",""))[:7] != "nan"})
    if not all_months:
        st.info("No closed trades yet."); return

    # Month nav
    if "cal_idx" not in st.session_state:
        st.session_state.cal_idx = len(all_months) - 1

    c1, c2, c3, _ = st.columns([1, 2, 1, 6])
    with c1:
        if st.button("◀", key="cal_prev"):
            st.session_state.cal_idx = max(0, st.session_state.cal_idx - 1)
    with c2:
        sel = all_months[st.session_state.cal_idx]
        yr = int(sel[:4]); mo = int(sel[5:])
        st.markdown(f'<div style="font-size:15px;font-weight:600;color:{TEXT_H};padding-top:5px">{cal_mod.month_name[mo]} {yr}</div>', unsafe_allow_html=True)
    with c3:
        if st.button("▶", key="cal_next"):
            st.session_state.cal_idx = min(len(all_months)-1, st.session_state.cal_idx + 1)

    # Build daily P&L
    daily = defaultdict(lambda: {"pnl":0,"trades":0,"wins":0,"losses":0})
    for t in closed:
        d = str(t.get("exit_date","") or "")[:10]
        if not d or d == "nan": continue
        p = float(t.get("pnl") or 0)
        daily[d]["pnl"]    += p
        daily[d]["trades"] += 1
        if p > 0: daily[d]["wins"] += 1
        else:     daily[d]["losses"] += 1

    # Month summary strip
    month_data = {d:v for d,v in daily.items() if d[:7] == sel}
    m_pnl  = sum(v["pnl"] for v in month_data.values())
    m_wins = sum(v["wins"] for v in month_data.values())
    m_loss = sum(v["losses"] for v in month_data.values())
    m_days = len(month_data)
    m_wr   = m_wins/(m_wins+m_loss)*100 if (m_wins+m_loss) else 0
    pc     = TEAL if m_pnl >= 0 else RED

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:24px;padding:10px 0 12px;
        border-bottom:1px solid {BORDER_LIGHT};margin-bottom:14px;flex-wrap:wrap">
        <span style="font-size:12px;color:{TEXT_MUTED}">Monthly stats:</span>
        <span style="font-size:14px;font-weight:700;color:{pc}">{'+'if m_pnl>=0 else ''}₹{m_pnl:,.0f}</span>
        <span style="font-size:12px;color:{TEXT_MUTED}">{m_days} days traded</span>
        <span style="font-size:12px;color:{TEXT_MUTED}">Win Rate: <b style="color:{TEXT_H}">{m_wr:.1f}%</b></span>
        <span style="font-size:12px;color:{TEAL}">Wins: <b>{m_wins}</b></span>
        <span style="font-size:12px;color:{RED}">Losses: <b>{m_loss}</b></span>
    </div>
    """, unsafe_allow_html=True)

    # Build calendar using st.columns (avoids raw HTML grid issues)
    days_in_month = cal_mod.monthrange(yr, mo)[1]
    first_dow     = date(yr, mo, 1).weekday()  # 0=Mon

    DAY_HDRS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    hdr_cols = st.columns(7)
    for col, h in zip(hdr_cols, DAY_HDRS):
        col.markdown(f'<div style="text-align:center;font-size:11px;font-weight:500;color:{TEXT_MUTED};padding:4px 0">{h}</div>',
            unsafe_allow_html=True)

    # Flatten cells: blanks + days + trailing blanks
    cells = [None]*first_dow + list(range(1, days_in_month+1))
    total = len(cells)
    remainder = (7 - total % 7) % 7
    cells += [None]*remainder

    # Render rows of 7
    for row_start in range(0, len(cells), 7):
        row = cells[row_start:row_start+7]
        cols = st.columns(7)
        for col, day in zip(cols, row):
            if day is None:
                col.markdown(f'<div style="min-height:72px;background:{PAGE_BG};border-radius:8px"></div>',
                    unsafe_allow_html=True)
                continue

            d_str   = f"{yr}-{mo:02d}-{day:02d}"
            d_data  = daily.get(d_str)
            is_today = (d_str == date.today().strftime("%Y-%m-%d"))

            if d_data:
                p  = d_data["pnl"]
                wr = d_data["wins"]/d_data["trades"]*100 if d_data["trades"] else 0
                bg     = "rgba(16,185,129,0.08)" if p>=0 else "rgba(239,68,68,0.08)"
                br_c   = "#10B98133" if p>=0 else "#EF444433"
                val_c  = TEAL if p>=0 else RED
                sign   = "+" if p>=0 else ""
                col.markdown(f"""
                <div style="background:{bg};border:1px solid {br_c};border-radius:8px;
                    min-height:72px;padding:8px 10px">
                    <div style="font-size:11px;font-weight:500;color:{TEXT_MUTED}">{day}</div>
                    <div style="font-size:12.5px;font-weight:700;color:{val_c};margin-top:3px">{sign}₹{abs(p):,.0f}</div>
                    <div style="font-size:10px;color:{TEXT_MUTED};margin-top:2px">{d_data['trades']} trade{'s' if d_data['trades']!=1 else ''}</div>
                    <div style="font-size:10px;color:{TEXT_MUTED}">{wr:.0f}%</div>
                </div>""", unsafe_allow_html=True)
            else:
                today_style = f"border:2px solid {TEAL};" if is_today else f"border:1px solid {BORDER_LIGHT};"
                col.markdown(f"""
                <div style="background:{CARD_BG};{today_style}border-radius:8px;
                    min-height:72px;padding:8px 10px">
                    <div style="font-size:11px;font-weight:{'600' if is_today else '400'};
                        color:{TEAL if is_today else TEXT_MUTED}">{day}</div>
                </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Weekly summary table
    st.markdown(f'<p style="font-size:11px;color:{TEXT_MUTED};font-weight:500;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:8px">Weekly Summary</p>', unsafe_allow_html=True)

    week_map = defaultdict(lambda: {"pnl":0,"trades":0,"wins":0,"losses":0,"days":0})
    for d_str, v in month_data.items():
        try:
            d_obj = date.fromisoformat(d_str)
            wk = d_obj.isocalendar()[1]
            week_map[wk]["pnl"]    += v["pnl"]
            week_map[wk]["trades"] += v["trades"]
            week_map[wk]["wins"]   += v["wins"]
            week_map[wk]["losses"] += v["losses"]
            week_map[wk]["days"]   += 1
        except: pass

    if week_map:
        wrows = []
        for wk, d in sorted(week_map.items()):
            cl = d["wins"] + d["losses"]
            wrows.append({
                "Week":     f"Week {wk}",
                "P&L ₹":    d["pnl"],
                "Trades":   d["trades"],
                "Win Rate": f"{d['wins']/cl*100:.0f}%" if cl else "—",
                "Days":     d["days"],
            })
        wdf = pd.DataFrame(wrows)
        def sty_w(row):
            idx = wdf.columns.tolist(); s = [""]*len(row)
            v = row.get("P&L ₹", 0)
            if "P&L ₹" in idx:
                s[idx.index("P&L ₹")] = f"color:{TEAL};font-weight:600" if v>0 else f"color:{RED};font-weight:600" if v<0 else ""
            return s
        st.dataframe(wdf.style.apply(sty_w, axis=1)
            .format({"P&L ₹": lambda v: f"{'+' if v>=0 else ''}₹{v:,.0f}"})
            .set_properties(**{"font-size":"13px"}).set_table_styles(TABLE_STYLES),
            use_container_width=True, hide_index=True)
