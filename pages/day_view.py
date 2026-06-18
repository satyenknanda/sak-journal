import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import calendar as cal_mod
from datetime import date, timedelta
from collections import defaultdict
from data.db import get_journal_trades
from theme import *

def render():
    st.markdown("## Day View")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:14px;font-size:11px">FY 2026-27 · Daily trade breakdown</p>', unsafe_allow_html=True)

    trades = get_journal_trades()
    closed = [t for t in trades if t["status"] == "CLOSED"]

    daily = defaultdict(list)
    for t in closed:
        d = str(t.get("exit_date","") or "")[:10]
        if d and d != "nan": daily[d].append(t)

    if not daily:
        st.info("No closed trades yet."); return

    # ── Layout: left=day sections, right=mini calendar ─────────────────
    left_col, right_col = st.columns([3, 1])

    with right_col:
        # Mini calendar
        if "dv_cal_idx" not in st.session_state:
            all_months = sorted({d[:7] for d in daily.keys()})
            st.session_state.dv_cal_idx = len(all_months)-1
            st.session_state.dv_months  = all_months

        all_months = st.session_state.get("dv_months", sorted({d[:7] for d in daily.keys()}))

        cc1, cc2, cc3 = st.columns([1,3,1])
        with cc1:
            if st.button("◀", key="dv_prev"):
                st.session_state.dv_cal_idx = max(0, st.session_state.dv_cal_idx-1)
        with cc2:
            idx = st.session_state.dv_cal_idx
            sel = all_months[idx] if all_months else date.today().strftime("%Y-%m")
            yr = int(sel[:4]); mo = int(sel[5:])
            st.markdown(f'<div style="text-align:center;font-size:11px;font-weight:600;color:{TEXT_H};padding-top:4px">{cal_mod.month_abbr[mo]} {yr}</div>', unsafe_allow_html=True)
        with cc3:
            if st.button("▶", key="dv_next"):
                st.session_state.dv_cal_idx = min(len(all_months)-1, st.session_state.dv_cal_idx+1)

        # Day headers
        DAY_HDRS = ["Su","Mo","Tu","We","Th","Fr","Sa"]
        hdr_cols = st.columns(7)
        for col, h in zip(hdr_cols, DAY_HDRS):
            col.markdown(f'<div style="text-align:center;font-size:9px;color:{TEXT_SUBTLE};padding:2px 0">{h}</div>', unsafe_allow_html=True)

        # Build daily P&L for calendar
        daily_pnl = {d: sum(float(t.get("pnl") or 0) for t in tlist) for d, tlist in daily.items()}

        days_in_month = cal_mod.monthrange(yr, mo)[1]
        # Tradezella calendar starts Sunday
        first_dow = (date(yr, mo, 1).weekday() + 1) % 7

        cells = [None]*first_dow + list(range(1, days_in_month+1))
        cells += [None]*((7 - len(cells)%7)%7)

        for row_start in range(0, len(cells), 7):
            row = cells[row_start:row_start+7]
            cols = st.columns(7)
            for col, day in zip(cols, row):
                if day is None:
                    col.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
                    continue
                d_str = f"{yr}-{mo:02d}-{day:02d}"
                p = daily_pnl.get(d_str)
                is_today = (d_str == date.today().strftime("%Y-%m-%d"))
                is_selected = d_str in daily

                if p is not None:
                    bg = "rgba(16,185,129,0.15)" if p>=0 else "rgba(239,68,68,0.15)"
                    fc = TEAL if p>=0 else RED
                    col.markdown(f'<div style="height:22px;border-radius:3px;background:{bg};display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;color:{fc}">{day}</div>', unsafe_allow_html=True)
                elif is_today:
                    col.markdown(f'<div style="height:22px;border-radius:3px;border:1.5px solid {TEAL};display:flex;align-items:center;justify-content:center;font-size:9px;color:{TEAL};font-weight:600">{day}</div>', unsafe_allow_html=True)
                else:
                    col.markdown(f'<div style="height:22px;border-radius:3px;background:{BORDER_LIGHT};display:flex;align-items:center;justify-content:center;font-size:9px;color:{TEXT_SUBTLE}">{day}</div>', unsafe_allow_html=True)

        # Legend
        st.markdown(f"""
        <div style="margin-top:8px;display:flex;flex-direction:column;gap:4px">
            <div style="display:flex;align-items:center;gap:5px;font-size:9px;color:{TEXT_SUBTLE}">
                <div style="width:10px;height:10px;border-radius:2px;background:rgba(16,185,129,0.15)"></div> Profit
            </div>
            <div style="display:flex;align-items:center;gap:5px;font-size:9px;color:{TEXT_SUBTLE}">
                <div style="width:10px;height:10px;border-radius:2px;background:rgba(239,68,68,0.15)"></div> Loss
            </div>
        </div>""", unsafe_allow_html=True)

    with left_col:
        # Controls
        cc1, cc2 = st.columns([2,6])
        with cc1:
            date_from = st.date_input("From", value=date.today()-timedelta(days=60), label_visibility="collapsed")
        with cc2:
            date_to = st.date_input("To", value=date.today(), label_visibility="collapsed")

        filtered = sorted([d for d in daily.keys() if str(date_from)<=d<=str(date_to)], reverse=True)

        if not filtered:
            st.info("No trades in selected range."); return

        st.caption(f"{len(filtered)} trading days")

        for d_str in filtered:
            day_trades = daily[d_str]
            day_pnl    = sum(float(t.get("pnl") or 0) for t in day_trades)
            winners    = [t for t in day_trades if (t.get("pnl") or 0)>0]
            losers     = [t for t in day_trades if (t.get("pnl") or 0)<=0]
            win_rate   = len(winners)/len(day_trades)*100 if day_trades else 0
            commissions= sum(float(t.get("commission_entry") or 0)+float(t.get("commission_exit") or 0) for t in day_trades)
            volume     = sum(int(t.get("qty") or 0) for t in day_trades)
            pf_val     = abs(sum(float(t.get("pnl") or 0) for t in winners)/sum(float(t.get("pnl") or 0) for t in losers)) if losers and any(float(t.get("pnl") or 0)<0 for t in losers) else 0

            try:
                d_obj = date.fromisoformat(d_str)
                d_label = d_obj.strftime("%a, %b %d, %Y")
            except: d_label = d_str

            pnl_color = TEAL if day_pnl>=0 else RED
            pnl_str   = f"Net P&L {'+'if day_pnl>=0 else ''}₹{day_pnl:,.2f}"

            with st.expander(f"**{d_label}** — {pnl_str}", expanded=(d_str==filtered[0])):
                ec1, ec2 = st.columns([1, 2])

                with ec1:
                    # Mini equity curve
                    cum = []; running = 0
                    for t in day_trades:
                        running += float(t.get("pnl") or 0)
                        cum.append(running)
                    if len(cum) > 1:
                        color = TEAL if day_pnl>=0 else RED
                        rgba  = f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.12)"
                        fig   = go.Figure()
                        fig.add_hline(y=0, line=dict(color=BORDER_LIGHT, width=1))
                        fig.add_trace(go.Scatter(
                            x=list(range(len(cum))), y=cum, mode="lines",
                            line=dict(color=color, width=2, shape="spline"),
                            fill="tozeroy", fillcolor=rgba,
                            showlegend=False,
                            hovertemplate="₹%{y:,.0f}<extra></extra>"))
                        l = chart_layout(height=110)
                        l["margin"] = dict(l=45,r=8,t=8,b=20)
                        l["xaxis"]["showticklabels"] = False
                        l["yaxis"]["tickprefix"] = "₹"; l["yaxis"]["tickformat"] = ",.0f"
                        fig.update_layout(**l)
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                    else:
                        st.markdown(f'<div style="height:80px;display:flex;align-items:center;justify-content:center;color:{TEXT_SUBTLE};font-size:11px">No Closed NET P&L on this day</div>', unsafe_allow_html=True)

                with ec2:
                    # 8-stat grid — exact Tradezella layout
                    stats = [
                        ("Total trades", str(len(day_trades)), TEXT_H),
                        ("Winners",      str(len(winners)),    TEAL),
                        ("Gross P&L",    f"₹{day_pnl:,.2f}",  TEAL if day_pnl>=0 else RED),
                        ("Commissions",  f"₹{commissions:,.0f}", TEXT_MUTED),
                        ("Winrate",      f"{win_rate:.0f}%",   TEAL if win_rate>=40 else RED),
                        ("Losers",       str(len(losers)),      RED),
                        ("Volume",       f"{volume:,}",         TEXT_MUTED),
                        ("Profit factor",f"{pf_val:.2f}" if pf_val else "—", TEXT_MUTED),
                    ]
                    grid = "".join([f"""
                    <div>
                        <div style="font-size:9.5px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px">{l}</div>
                        <div style="font-size:13px;font-weight:600;color:{c}">{v}</div>
                    </div>""" for l,v,c in stats])
                    st.markdown(f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px 16px;padding:4px 0">{grid}</div>', unsafe_allow_html=True)

                # Trade list
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                rows = []
                for t in day_trades:
                    p = float(t.get("pnl") or 0)
                    rows.append({
                        "Symbol":   t.get("ticker",""),
                        "Strategy": t.get("strategy",""),
                        "Entry ₹":  float(t.get("entry_price") or 0),
                        "Exit ₹":   float(t.get("exit_price") or 0),
                        "Qty":      int(t.get("qty") or 0),
                        "Net P&L":  p,
                        "R-Mult":   float(t.get("r_multiple") or 0),
                    })
                df = pd.DataFrame(rows)
                def sty_d(row):
                    idx=df.columns.tolist(); s=[""]*len(row)
                    p=row.get("Net P&L",0)
                    if "Net P&L" in idx: s[idx.index("Net P&L")]=f"color:{TEAL};font-weight:600" if p>0 else f"color:{RED};font-weight:600" if p<0 else ""
                    return s
                st.dataframe(df.style.apply(sty_d,axis=1)
                    .format({"Entry ₹":lambda v:f"₹{v:,.2f}","Exit ₹":lambda v:f"₹{v:,.2f}" if v else "—",
                             "Net P&L":lambda v:f"{'+₹' if v>=0 else '₹'}{abs(v):,.0f}",
                             "R-Mult":lambda v:f"{v:.2f}R" if v else "—","Qty":"{:,}"})
                    .set_properties(**{"font-size":"12px"}).set_table_styles(TABLE_STYLES),
                    use_container_width=True, hide_index=True)
