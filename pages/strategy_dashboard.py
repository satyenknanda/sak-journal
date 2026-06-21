import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from collections import defaultdict
from data.db import get_journal_trades
from theme import *
# ── backwards-compat aliases ──────────────────────────────────────────────
kcard   = kpi_card          # old name used in some pages
G       = TEAL
R       = RED
B       = BLUE
AM      = AMBER
MUTED   = TEXT_MUTED
TEXT    = TEXT_H
TEXT2   = TEXT_BODY
DIM     = BORDER_LIGHT
BG      = PAGE_BG
CARD    = CARD_BG
BORDER_C= BORDER
SHADOW  = SHADOW_SM
# ─────────────────────────────────────────────────────────────────────────


def _strategy_color(name, all_names):
    """Deterministic per-strategy identity color from the shared DNA_COLORS
    palette — same strategy name always gets the same color across pages."""
    sorted_names = sorted(all_names)
    idx = sorted_names.index(name) if name in sorted_names else 0
    return DNA_COLORS[idx % len(DNA_COLORS)]


def render():
    st.markdown("## Strategy Dashboard")
    st.markdown(f'<p style="color:{MUTED};margin-top:-8px;margin-bottom:20px;font-size:0.85rem">FY 2026-27 · Per-strategy breakdown</p>', unsafe_allow_html=True)

    trades = get_journal_trades()
    closed = [t for t in trades if t["status"]=="CLOSED"]

    strat_map = defaultdict(lambda: {"pnl":0,"r":[],"wins":0,"closed":0,"open":0})
    for t in trades:
        s = t.get("strategy","")
        if not s: continue
        if t["status"]=="OPEN": strat_map[s]["open"]+=1
        else:
            strat_map[s]["closed"]+=1
            p=float(t.get("pnl") or 0); strat_map[s]["pnl"]+=p
            r=t.get("r_multiple")
            if r: strat_map[s]["r"].append(float(r))
            if p>0: strat_map[s]["wins"]+=1

    def ss(d):
        cl=d["closed"]; rs=d["r"]
        wr=d["wins"]/cl if cl else 0
        pos=[r for r in rs if r>0]; neg=[r for r in rs if r<=0]
        aw=float(np.mean(pos)) if pos else 0; al=float(np.mean(neg)) if neg else 0
        return wr,aw,al,wr*aw+(1-wr)*al

    active = [(s,d) for s,d in strat_map.items() if d["closed"]>=1]
    sorted_s = sorted(active, key=lambda x: ss(x[1])[3], reverse=True)
    all_strategy_names = [s for s,_ in active]

    top_s = sorted_s[0][0] if sorted_s else "—"
    bot_s = sorted_s[-1][0] if sorted_s else "—"
    best_exp = ss(sorted_s[0][1])[3] if sorted_s else 0
    n_total = sum(d["closed"] for _,d in sorted_s)
    combined_r = sum(sum(d["r"]) for _,d in sorted_s)
    combined_exp = combined_r/n_total if n_total else 0

    # KPI strip
    cols = st.columns(5)
    for col,(l,v,c) in zip(cols,[
        ("Active Strategies", str(len(active)),      BLUE),
        ("Top Strategy",      top_s,                 TEAL),
        ("Bottom Strategy",   bot_s,                 RED),
        ("Best Expectancy",   f"{best_exp:.2f}R",    TEAL),
        ("Combined Exp.",     f"{combined_exp:.2f}R",TEAL if combined_exp>0 else RED),
    ]): col.markdown(kpi_card(l,v,color=c), unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Strategy cards 3 per row
    def badge(exp):
        if exp>0.5:  return f'<span style="background:{TEAL}1A;color:{TEAL};padding:2px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;border:1px solid {TEAL}33">Positive</span>'
        if exp>-0.3: return f'<span style="background:{AMBER}1A;color:{AMBER};padding:2px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;border:1px solid {AMBER}33">Marginal</span>'
        return f'<span style="background:{RED}1A;color:{RED};padding:2px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;border:1px solid {RED}33">Negative</span>'

    def pcolor(v): return TEAL if v>0 else RED if v<0 else MUTED

    max_abs_pnl = max((abs(d["pnl"]) for _,d in sorted_s), default=1)

    rows_of_3 = [sorted_s[i:i+3] for i in range(0, len(sorted_s), 3)]
    for row in rows_of_3:
        cols3 = st.columns(3)
        for col,(s,d) in zip(cols3,row):
            wr,aw,al,exp = ss(d)
            bar_w = int(abs(d["pnl"])/max_abs_pnl*100)
            bar_c = TEAL if d["pnl"]>=0 else RED
            id_color = _strategy_color(s, all_strategy_names)
            with col:
                st.markdown(f"""
                <div style="background:{CARD};border:1px solid {BORDER};border-top:3px solid {id_color};border-radius:12px;
                    padding:16px 18px;margin-bottom:10px;box-shadow:{SHADOW}">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                        <span style="display:inline-flex;align-items:center;gap:7px">
                            <span style="width:9px;height:9px;border-radius:50%;background:{id_color};display:inline-block"></span>
                            <span style="font-size:1rem;font-weight:700;color:{TEXT}">{s}</span>
                        </span>
                        {badge(exp)}
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 16px;font-size:13px">
                        <div style="color:{MUTED}">Trades</div>
                        <div style="color:{TEXT};font-weight:500">{d['closed']} closed</div>
                        <div style="color:{MUTED}">Win Rate</div>
                        <div style="color:{pcolor(wr-0.4)};font-weight:600">{wr*100:.1f}%</div>
                        <div style="color:{MUTED}">Avg Win R</div>
                        <div style="color:{TEAL};font-weight:600">+{aw:.2f}R</div>
                        <div style="color:{MUTED}">Avg Loss R</div>
                        <div style="color:{RED};font-weight:600">{al:.2f}R</div>
                        <div style="color:{MUTED}">Expectancy</div>
                        <div style="color:{pcolor(exp)};font-weight:700">{'+' if exp>=0 else ''}{exp:.2f}R</div>
                        <div style="color:{MUTED}">Total P&L</div>
                        <div style="color:{pcolor(d['pnl'])};font-weight:700">{'+' if d['pnl']>=0 else ''}₹{d['pnl']:,.0f}</div>
                    </div>
                    <div style="height:4px;background:{DIM};border-radius:2px;margin-top:12px;overflow:hidden">
                        <div style="height:100%;width:{bar_w}%;background:{bar_c};border-radius:2px;
                            transition:width 0.3s ease"></div>
                    </div>
                </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Charts
    c1, c2 = st.columns(2)
    snames = [s for s,_ in sorted_s]
    exps   = [ss(d)[3] for _,d in sorted_s]
    wrs    = [ss(d)[0] for _,d in sorted_s]

    with c1:
        fig = go.Figure()
        fig.add_hline(y=0, line=dict(color=DIM, width=1))
        for s,e in zip(snames,exps):
            id_color = _strategy_color(s, all_strategy_names)
            fig.add_trace(go.Bar(x=[s],y=[e],
                marker=dict(color=id_color, opacity=0.85, line=dict(width=2, color=(TEAL if e>=0 else RED))),
                showlegend=False,
                hovertemplate=f"<b>{s}</b><br>Expectancy: %{{y:.2f}}R<extra></extra>"))
        l=chart_layout(height=240,title="Expectancy per Strategy")
        l["bargap"]=0.35; l["yaxis"]["ticksuffix"]="R"
        fig.update_layout(**l)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    with c2:
        fig2 = go.Figure()
        fig2.add_hline(y=0.4, line=dict(color=BLUE, width=1.5, dash="dash"),
            annotation_text="40% break-even", annotation_font_color=BLUE, annotation_font_size=9)
        for s,w in zip(snames,wrs):
            id_color = _strategy_color(s, all_strategy_names)
            fig2.add_trace(go.Bar(x=[s],y=[w*100],
                marker=dict(color=id_color, opacity=0.85, line=dict(width=2, color=(TEAL if w>=0.4 else RED))),
                showlegend=False,
                hovertemplate=f"<b>{s}</b><br>Win Rate: %{{y:.1f}}%<extra></extra>"))
        l2=chart_layout(height=240,title="Win Rate per Strategy")
        l2["bargap"]=0.35; l2["yaxis"]["ticksuffix"]="%"; l2["yaxis"]["range"]=[0,85]
        fig2.update_layout(**l2)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

    # Full table
    trows=[]
    for s,d in sorted_s:
        wr,aw,al,exp=ss(d)
        avg_pnl=d["pnl"]/d["closed"] if d["closed"] else 0
        trows.append({"Strategy":s,"Total":d["closed"]+d["open"],"Closed":d["closed"],
            "Open":d["open"],"Win Rate":f"{wr*100:.1f}%","Avg Win R":aw,"Avg Loss R":al,
            "Expectancy":exp,"Total P&L":d["pnl"],"Avg P&L/Trade":avg_pnl})
    if trows:
        df=pd.DataFrame(trows)
        def sty(row):
            idx=df.columns.tolist(); styles=[""]*len(row)
            for col,colors in [("Expectancy",(TEAL,RED)),("Total P&L",(TEAL,RED)),("Avg P&L/Trade",(TEAL,RED))]:
                if col in idx:
                    v=row.get(col,0)
                    styles[idx.index(col)]=f"color:{colors[0]};font-weight:600" if v>0 else f"color:{colors[1]};font-weight:600" if v<0 else ""
            if "Avg Loss R" in idx:
                styles[idx.index("Avg Loss R")]=f"color:{RED}"
            if "Avg Win R" in idx:
                styles[idx.index("Avg Win R")]=f"color:{TEAL}"
            return styles
        st.dataframe(df.style.apply(sty,axis=1)
            .format({"Total P&L":lambda v:f"{'+' if v>=0 else ''}₹{v:,.0f}",
                     "Avg P&L/Trade":lambda v:f"{'+' if v>=0 else ''}₹{v:,.0f}",
                     "Avg Win R":lambda v:f"{v:.2f}R","Avg Loss R":lambda v:f"{v:.2f}R",
                     "Expectancy":lambda v:f"{'+' if v>=0 else ''}{v:.2f}R"})
            .set_properties(**{"font-size":"13px"}).set_table_styles(TABLE_STYLES),
            use_container_width=True, hide_index=True)
