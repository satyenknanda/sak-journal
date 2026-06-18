import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import date
from data.db import get_journal_trades, get_strategies
from theme import *

def render():
    st.markdown("## Trade View")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:14px;font-size:11px">FY 2026-27 · NSE Equity · Full trade record</p>', unsafe_allow_html=True)

    trades = get_journal_trades()
    closed = [t for t in trades if t["status"]=="CLOSED"]
    open_t = [t for t in trades if t["status"]=="OPEN"]

    # ── KPI strip (Tradezella Trade View style) ────────────────────────
    rs       = [float(t.get("r_multiple") or 0) for t in closed]
    pos_r    = [r for r in rs if r>0]; neg_r = [r for r in rs if r<=0]
    aw       = float(np.mean(pos_r)) if pos_r else 0
    al       = float(np.mean(neg_r)) if neg_r else 0
    pf       = (aw*len(pos_r))/(abs(al)*len(neg_r)) if neg_r and al!=0 else 0
    wr       = len(pos_r)/len(closed) if closed else 0
    total_pnl= sum(float(t.get("pnl") or 0) for t in closed)
    cum_pts  = [(t["trade_no"], float(t["cumulative_pnl"])) for t in closed if t.get("cumulative_pnl")]
    win_pnls = [float(t.get("pnl") or 0) for t in closed if (t.get("pnl") or 0)>0]
    loss_pnls= [float(t.get("pnl") or 0) for t in closed if (t.get("pnl") or 0)<0]
    avg_win  = float(np.mean(win_pnls))  if win_pnls  else 0
    avg_loss = float(np.mean(loss_pnls)) if loss_pnls else 0


    def svg_gauge(pct, color, size=90):
        import math
        pct = max(0.0, min(1.0, pct))
        cx = cy = size / 2; r = size/2 - 8
        bg = f"M {cx-r},{cy} A {r},{r} 0 0,1 {cx+r},{cy}"
        if pct >= 0.999: val = f"M {cx-r},{cy} A {r},{r} 0 1,1 {cx+r-0.01},{cy}"
        elif pct <= 0.001: val = ""
        else:
            ex = cx + r*math.cos(math.pi*(1-pct)); ey = cy - r*math.sin(math.pi*pct)
            val = f"M {cx-r},{cy} A {r},{r} 0 {1 if pct>0.5 else 0},1 {ex:.2f},{ey:.2f}"
        h = int(size/2)+6
        return (f'<svg width="{size}" height="{h}" viewBox="0 0 {size} {h}" style="display:block">'
            f'<path d="{bg}" fill="none" stroke="#E5E7EB" stroke-width="8" stroke-linecap="round"/>'
            +(f'<path d="{val}" fill="none" stroke="{color}" stroke-width="8" stroke-linecap="round"/>' if val else "")
            +f'</svg>')

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        spark_ys = [p[1] for p in cum_pts[-30:]] if cum_pts else []
        fig_s = go.Figure(go.Scatter(x=list(range(len(spark_ys))), y=spark_ys,
            mode="lines", line=dict(color=TEAL, width=1.5),
            fill="tozeroy", fillcolor="rgba(16,185,129,0.1)", showlegend=False))
        fig_s.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=55, margin=dict(l=0,r=0,t=0,b=0),
            xaxis=dict(visible=False), yaxis=dict(visible=False))
        cnt = f'<span style="background:{BLUE_BG};color:{BLUE};padding:1px 5px;border-radius:9px;font-size:9px;margin-left:4px">{len(closed)}</span>'
        st.markdown(f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px 4px;box-shadow:{SHADOW_SM}">'
            f'<div style="font-size:9px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:3px">Net cumulative P&L {cnt}</div>'
            f'<div style="font-size:17px;font-weight:700;color:{TEAL};letter-spacing:-0.02em">{"+" if total_pnl>=0 else ""}₹{total_pnl:,.2f}</div>'
            f'</div>', unsafe_allow_html=True)
        st.plotly_chart(fig_s, use_container_width=True, config={"displayModeBar":False})

    with k2:
        # Profit factor gauge
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=min(pf,5)*20,
            number=dict(font=dict(size=1, color="rgba(0,0,0,0)")),
            gauge=dict(axis=dict(range=[0,100], tickwidth=0, tickcolor="rgba(0,0,0,0)",
                         showticklabels=False),
                bar=dict(color=TEAL if pf>=1 else RED, thickness=0.5),
                bgcolor="rgba(0,0,0,0)", borderwidth=0,
                steps=[dict(range=[0,100], color=BORDER_LIGHT)])))
        fig_g.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=90, margin=dict(l=20,r=20,t=5,b=30))
        st.markdown(f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px 0;box-shadow:{SHADOW_SM}">'
            f'<div style="font-size:9px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:2px">Profit factor</div>'
            f'<div style="font-size:17px;font-weight:700;color:{TEXT_H}">{pf:.2f}</div>'
            f'</div>', unsafe_allow_html=True)
        st.plotly_chart(fig_g, use_container_width=True, config={"displayModeBar":False})

    with k3:
        # Trade win% gauge
        fig_g2 = go.Figure(go.Indicator(mode="gauge+number", value=wr*100,
            number=dict(suffix="%", font=dict(size=1, color="rgba(0,0,0,0)")),
            gauge=dict(axis=dict(range=[0,100], tickwidth=0, tickcolor="rgba(0,0,0,0)",
                         showticklabels=False),
                bar=dict(color=TEAL if wr>=0.4 else RED, thickness=0.5),
                bgcolor="rgba(0,0,0,0)", borderwidth=0,
                steps=[dict(range=[0,100], color=BORDER_LIGHT)])))
        fig_g2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=90, margin=dict(l=20,r=20,t=5,b=30))
        cnt2 = f'<span style="background:{TEAL_BG};color:{TEAL};padding:1px 5px;border-radius:9px;font-size:9px;margin-left:3px">{len(pos_r)}</span>'
        cnt3 = f'<span style="background:{RED_BG};color:{RED};padding:1px 5px;border-radius:9px;font-size:9px;margin-left:3px">{len(neg_r)}</span>'
        st.markdown(f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px 0;box-shadow:{SHADOW_SM}">'
            f'<div style="font-size:9px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:2px">Trade win % {cnt2}{cnt3}</div>'
            f'<div style="font-size:17px;font-weight:700;color:{TEAL if wr>=0.4 else AMBER}">{wr*100:.2f}%</div>'
            f'</div>', unsafe_allow_html=True)
        st.plotly_chart(fig_g2, use_container_width=True, config={"displayModeBar":False})

    with k4:
        bar_ratio = avg_win/(avg_win+abs(avg_loss)) if (avg_win+abs(avg_loss)) else 0.5
        st.markdown(f"""
        <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px;box-shadow:{SHADOW_SM};height:105px">
            <div style="font-size:9px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:6px">Avg win/loss trade</div>
            <div style="font-size:17px;font-weight:700;color:{TEXT_H};margin-bottom:8px">{pf:.2f}</div>
            <div style="height:6px;background:{BORDER_LIGHT};border-radius:3px;overflow:hidden;margin-bottom:5px">
                <div style="width:{bar_ratio*100:.0f}%;height:100%;background:{TEAL};border-radius:3px 0 0 3px;display:inline-block"></div>
                <div style="width:{(1-bar_ratio)*100:.0f}%;height:100%;background:{RED};border-radius:0 3px 3px 0;display:inline-block"></div>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:10px">
                <span style="color:{TEAL};font-weight:600">+₹{avg_win:,.0f}</span>
                <span style="color:{RED};font-weight:600">₹{avg_loss:,.0f}</span>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ── Filters ────────────────────────────────────────────────────────
    fc = st.columns([1, 1.4, 1.2, 1.4, 1.4, 1.4])
    with fc[0]: status_f  = st.selectbox("Status", ["All","OPEN","CLOSED"], label_visibility="collapsed")
    with fc[1]:
        strats = ["All"] + get_strategies()
        strat_f = st.selectbox("Strategy", strats, label_visibility="collapsed")
    with fc[2]: wl_f      = st.selectbox("W/L", ["All","WIN","LOSS"], label_visibility="collapsed")
    with fc[3]: ticker_f  = st.text_input("Ticker", placeholder="Search symbol…", label_visibility="collapsed")
    with fc[4]: date_from = st.date_input("From", value=date(2026,4,1), label_visibility="collapsed")
    with fc[5]: date_to   = st.date_input("To",   value=date.today(),   label_visibility="collapsed")

    filtered = get_journal_trades(status=status_f, strategy=strat_f, ticker=ticker_f,
        win_loss=wl_f, date_from=date_from, date_to=date_to)

    st.caption(f"{len(filtered)} trades")

    # ── Trade table — Tradezella Trade View style ──────────────────────
    def status_pill(status, wl):
        if status == "OPEN":
            return f'<span style="background:{BLUE_BG};color:{BLUE};border:1px solid {BLUE_BORDER};padding:2px 8px;border-radius:20px;font-size:9.5px;font-weight:600">OPEN</span>'
        if wl == "WIN":
            return f'<span style="background:{TEAL_BG};color:{TEAL};border:1px solid {TEAL_BORDER};padding:2px 8px;border-radius:20px;font-size:9.5px;font-weight:600">WIN</span>'
        if wl == "LOSS":
            return f'<span style="background:{RED_BG};color:{RED};border:1px solid {RED_BORDER};padding:2px 8px;border-radius:20px;font-size:9.5px;font-weight:600">LOSS</span>'
        return f'<span style="background:{PAGE_BG};color:{TEXT_MUTED};border:1px solid {BORDER};padding:2px 8px;border-radius:20px;font-size:9.5px;font-weight:600">—</span>'

    rows_html = []
    for t in filtered:
        pnl  = float(t.get("pnl") or 0)
        r    = float(t.get("r_multiple") or 0)
        ep   = float(t.get("entry_price") or 0)
        xp   = float(t.get("exit_price") or 0)
        roi  = (xp-ep)/ep*100 if ep and xp else None
        wl   = (t.get("win_loss") or "").strip()
        stat = t.get("status","")

        pnl_html = f'<span style="color:{TEAL};font-weight:600">+₹{pnl:,.2f}</span>' if pnl>0 else f'<span style="color:{RED};font-weight:600">₹{pnl:,.2f}</span>' if pnl<0 else '<span style="color:#94A3B8">(open) ₹0</span>'
        roi_html = f'<span style="color:{TEAL};font-size:11px">+{roi:.2f}%</span>' if roi and roi>0 else f'<span style="color:{RED};font-size:11px">{roi:.2f}%</span>' if roi and roi<0 else '<span style="color:#94A3B8">—</span>'

        def td(content, mono=False):
            s = f"padding:8px 12px;white-space:nowrap;font-size:12.5px;"
            if mono: s += f"font-variant-numeric:tabular-nums;"
            return f'<td style="{s}">{content}</td>'

        row_bg = f"background:rgba(16,185,129,0.03)" if wl=="WIN" else f"background:rgba(239,68,68,0.03)" if wl=="LOSS" else ""
        rows_html.append(f"""
        <tr style="border-bottom:1px solid {BORDER_LIGHT};{row_bg};transition:background 0.1s"
            onmouseover="this.style.background='{TABLE_HEAD_BG}'"
            onmouseout="this.style.background='{"rgba(16,185,129,0.03)" if wl=="WIN" else "rgba(239,68,68,0.03)" if wl=="LOSS" else ""}'">
            {td(str(t.get("entry_date","") or "")[:10])}
            {td(f'<span style="font-weight:700;color:{TEXT_H};font-size:13px">{t.get("ticker","")}</span>')}
            {td(status_pill(stat, wl))}
            {td(str(t.get("exit_date","") or "")[:10] or "—")}
            {td(f'₹{ep:,.2f}' if ep else "—", mono=True)}
            {td(f'₹{xp:,.2f}' if xp else "—", mono=True)}
            {td(f'{int(t.get("qty") or 0):,}', mono=True)}
            {td(pnl_html, mono=True)}
            {td(roi_html, mono=True)}
        </tr>""")

    th = f"padding:9px 12px;text-align:left;color:{TEXT_SUBTLE};font-size:9.5px;font-weight:500;text-transform:uppercase;letter-spacing:0.07em;white-space:nowrap;border-bottom:1px solid {BORDER};background:{TABLE_HEAD_BG}"

    table_html = f"""
    <div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER};
        box-shadow:{SHADOW_SM};background:{CARD_BG}">
    <table style="width:100%;border-collapse:collapse">
        <thead>
        <tr>{"".join(f'<th style="{th}">{h}</th>' for h in ["Open date","Symbol","Status","Close date","Entry ₹","Exit ₹","Qty","Net P&L","Net ROI"])}</tr>
        </thead>
        <tbody>{"".join(rows_html)}</tbody>
    </table>
    </div>"""

    st.markdown(table_html, unsafe_allow_html=True)
