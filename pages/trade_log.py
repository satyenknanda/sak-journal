# -*- coding: utf-8 -*-
import streamlit as st
import plotly.graph_objects as go
import csv, io, os
from datetime import date, timedelta

from theme import *
from data.db import get_trades, get_strategies, delete_trade

G="#10B981"; R="#EF4444"; B="#3B82F6"; AM="#F59E0B"; PU="#7C3AED"
TEXT="#111827"; MUTED="#6B7280"; BORDER="#E5E7EB"; BG="#FFFFFF"; HBG="#F9FAFB"

try:
    from components.trade_modals import render_add_trade_modal, render_exit_trade_modal, render_edit_trade_modal
    @st.dialog("Add Trade", width="large")
    def add_trade_dialog(): render_add_trade_modal()
    @st.dialog("Edit Trade", width="large")
    def edit_trade_dialog(trade): render_edit_trade_modal(trade)
    @st.dialog("Exit Trade", width="large")
    def exit_trade_dialog(trade): render_exit_trade_modal(trade)
    HAS_MODALS = True
except: HAS_MODALS = False

@st.dialog("Select Columns", width="large")
def select_columns_dialog():
    st.caption("Choose the columns you want to display in the table")
    ALL_COLS = ["Open Date","Symbol","Strategy","Status","Side","Close Date",
                "Entry Price","Exit Price","Net P&L","Net ROI","R-Multiple",
                "Stop Loss","Qty","Gross P&L","Commissions","Zella Scale"]
    DEFAULT = ["Open Date","Symbol","Strategy","Status","Side","Close Date",
               "Entry Price","Exit Price","Net P&L","R-Multiple"]
    if "tl_cols" not in st.session_state:
        st.session_state.tl_cols = DEFAULT[:]
    c1,c2,c3 = st.columns(3)
    if c1.button("All"):   st.session_state.tl_cols=ALL_COLS[:]; st.rerun()
    if c2.button("None"):  st.session_state.tl_cols=[]; st.rerun()
    if c3.button("Default"): st.session_state.tl_cols=DEFAULT[:]; st.rerun()
    sel=[]
    cols4=st.columns(4)
    for i,c in enumerate(ALL_COLS):
        with cols4[i%4]:
            if st.checkbox(c, value=c in st.session_state.tl_cols, key=f"cc_{c}"): sel.append(c)
    b1,b2=st.columns(2)
    if b1.button("Cancel",use_container_width=True): st.rerun()
    if b2.button("Update",type="primary",use_container_width=True):
        st.session_state.tl_cols=sel; st.rerun()

def chip(text, color, bg):
    return f'<span style="background:{bg};color:{color};padding:2px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;border:1px solid {color}22;white-space:nowrap">{text}</span>'

def status_chip(pnl):
    try: p=float(pnl or 0)
    except: p=0
    if p>0: return chip("WIN", G, "#F0FDF4")
    if p<0: return chip("LOSS", R, "#FEF2F2")
    return chip("BE", MUTED, "#F3F4F6")

def zella_bar(r):
    try:
        rv=float(r or 0)
        if rv==0: return "—"
        pct=min(abs(rv)/5*100,100); c=G if rv>0 else R
        return f'<div style="width:60px;height:7px;background:#F3F4F6;border-radius:4px;overflow:hidden;display:inline-block"><div style="width:{pct}%;height:100%;background:{c};border-radius:4px"></div></div>'
    except: return "—"

def render():
    # ── State init ────────────────────────────────────────────────────────────
    defaults = {"tl_cols":["Open Date","Symbol","Strategy","Status","Side","Close Date",
                            "Entry Price","Exit Price","Net P&L","R-Multiple"],
                "tl_sort":"exit_date","tl_asc":False,"tl_page":1,"tl_pp":50,
                "tl_show_filters":False}
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v

    # ── Header ────────────────────────────────────────────────────────────────
    hc1,hc2,hc3,hc4 = st.columns([3,1,1,1])
    with hc1: st.markdown("## Trade Log")
    with hc2:
        f_active = st.session_state.tl_show_filters
        if st.button(f"🔽 Filters{'  ●' if f_active else ''}", use_container_width=True,
                     type="primary" if f_active else "secondary", key="tl_fb"):
            st.session_state.tl_show_filters = not f_active; st.rerun()
    with hc3:
        dr = st.selectbox("DR",["This FY","This Month","Last 30d","Last 90d","All Time"],
                          label_visibility="collapsed", key="tl_dr")
    with hc4:
        if HAS_MODALS and st.button("＋ Add Trade",type="primary",use_container_width=True,key="tl_add"):
            add_trade_dialog()

    # ── Date range ────────────────────────────────────────────────────────────
    today = date.today()
    DR_MAP = {"This FY":(date(2026,4,1),date(2027,3,31)),"This Month":(today.replace(day=1),today),
              "Last 30d":(today-timedelta(30),today),"Last 90d":(today-timedelta(90),today),
              "All Time":(date(2020,1,1),today)}
    d_from, d_to = DR_MAP.get(dr,(date(2026,4,1),today))

    # ── Filters panel ─────────────────────────────────────────────────────────
    if st.session_state.tl_show_filters:
        with st.container(border=True):
            st.markdown(f'<span style="font-size:12px;font-weight:700;color:{TEXT}">Filters</span>', unsafe_allow_html=True)
            r1c1,r1c2,r1c3,r1c4 = st.columns(4)
            with r1c1: st.multiselect("Strategy",get_strategies(),key="tl_fs",label_visibility="visible")
            with r1c2: st.selectbox("Status",["All","OPEN","CLOSED"],key="tl_fstatus",label_visibility="visible")
            with r1c3: st.selectbox("Side",["All","Long","Short"],key="tl_fside",label_visibility="visible")
            with r1c3: st.selectbox("Result",["All","Win","Loss"],key="tl_fres",label_visibility="visible")
            with r1c4: st.text_input("Symbol",placeholder="HDFCBANK",key="tl_fsym",label_visibility="visible")
            if st.button("↺ Reset Filters",key="tl_reset"):
                for k in ["tl_fs","tl_fside","tl_fres","tl_fsym"]:
                    st.session_state.pop(k,None)
                st.rerun()

    # ── Load + filter ─────────────────────────────────────────────────────────
    fstatus = st.session_state.get("tl_fstatus","All") or "All"
    all_trades = get_trades()
    if fstatus == "OPEN":
        base = [t for t in all_trades if t.get("status")=="OPEN"]
    elif fstatus == "CLOSED":
        base = [t for t in all_trades if t.get("status")=="CLOSED"]
    else:
        base = all_trades

    # Date filter
    # Date filter — open trades always included
    trades = [t for t in base if
              t.get("status")=="OPEN" or
              d_from.isoformat() <= str(t.get("exit_date","") or "")[:10] <= d_to.isoformat()]
    # Other filters — read widget state directly
    fs   = st.session_state.get("tl_fs",[]) or []
    fside= st.session_state.get("tl_fside","All") or "All"
    fres = st.session_state.get("tl_fres","All") or "All"
    fsym = (st.session_state.get("tl_fsym","") or "").strip().upper()

    if fs:    trades=[t for t in trades if t.get("strategy","") in fs]
    if fside!="All": trades=[t for t in trades if str(t.get("side","") or "").upper()==fside.upper()]
    if fres=="Win":  trades=[t for t in trades if float(t.get("pnl") or 0)>0]
    elif fres=="Loss": trades=[t for t in trades if float(t.get("pnl") or 0)<0]
    if fsym: trades=[t for t in trades if fsym in (t.get("ticker","") or "").upper()]

    n_active = sum([bool(fs),fside!="All",fres!="All",bool(fsym)])
    if n_active:
        st.markdown(f'<p style="font-size:11px;color:{G};margin:4px 0">✓ {n_active} filter{"s" if n_active>1 else ""} active · {len(trades)} trades shown</p>',unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    pnls=[float(t.get("pnl") or 0) for t in trades]
    win_p=[p for p in pnls if p>0]; loss_p=[p for p in pnls if p<0]
    total=sum(pnls); pf=abs(sum(win_p)/sum(loss_p)) if loss_p and sum(loss_p)!=0 else 0
    wr=len(win_p)/len(pnls)*100 if pnls else 0
    aw=sum(win_p)/len(win_p) if win_p else 0
    al=sum(loss_p)/len(loss_p) if loss_p else 0
    pc=G if total>=0 else R

    cum=0; sy=[]
    for t in sorted(trades,key=lambda x:str(x.get("exit_date","") or "")):
        cum+=float(t.get("pnl") or 0); sy.append(cum)

    k1,k2,k3,k4 = st.columns(4)

    with k1:
        st.markdown(f"""<div style="border:1px solid {BORDER};border-radius:8px;padding:14px 16px;background:{BG}">
        <div style="font-size:9px;color:{MUTED};font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">
            NET CUMULATIVE P&L <span style="background:#EFF6FF;color:{B};padding:1px 5px;border-radius:8px;font-size:8px">{len(trades)}</span></div>
        <div style="font-size:22px;font-weight:700;color:{pc}">{"+"if total>=0 else ""}₹{abs(total):,.0f}</div>
        </div>""", unsafe_allow_html=True)
        if sy:
            fig=go.Figure(go.Scatter(y=sy,mode="lines",line=dict(color=pc,width=1.5),fill="tozeroy",
                fillcolor="rgba(16,185,129,0.08)"if total>=0 else"rgba(239,68,68,0.08)"))
            fig.update_layout(height=55,margin=dict(l=0,r=0,t=0,b=0),
                paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(visible=False),yaxis=dict(visible=False),showlegend=False)
            st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

    with k2:
        pfc=G if pf>=1 else R
        fg=go.Figure(go.Indicator(mode="gauge",value=min(pf,3),
            gauge=dict(axis=dict(range=[0,3],visible=False),bar=dict(color=pfc,thickness=0.25),
                bgcolor="rgba(0,0,0,0)",borderwidth=0,
                steps=[dict(range=[0,1],color="#FEE2E2"),dict(range=[1,3],color="#DCFCE7")])))
        fg.update_layout(height=80,margin=dict(l=10,r=10,t=5,b=0),paper_bgcolor="rgba(0,0,0,0)")
        st.markdown(f"""<div style="border:1px solid {BORDER};border-radius:8px;padding:14px 16px;background:{BG}">
        <div style="font-size:9px;color:{MUTED};font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">PROFIT FACTOR</div>
        <div style="font-size:22px;font-weight:700;color:{pfc};margin-bottom:4px">{pf:.2f}</div>
        </div>""", unsafe_allow_html=True)
        st.plotly_chart(fg,use_container_width=True,config={"displayModeBar":False})

    with k3:
        wc=G if wr>=50 else AM
        wins_n=len(win_p); losses_n=len(loss_p); be_n=len(pnls)-wins_n-losses_n
        fg2=go.Figure(go.Indicator(mode="gauge",value=wr,
            gauge=dict(axis=dict(range=[0,100],visible=False),bar=dict(color=wc,thickness=0.25),
                bgcolor="rgba(0,0,0,0)",borderwidth=0,
                steps=[dict(range=[0,50],color="#FEE2E2"),dict(range=[50,100],color="#DCFCE7")])))
        fg2.update_layout(height=80,margin=dict(l=10,r=10,t=5,b=0),paper_bgcolor="rgba(0,0,0,0)")
        st.markdown(f"""<div style="border:1px solid {BORDER};border-radius:8px;padding:14px 16px;background:{BG}">
        <div style="font-size:9px;color:{MUTED};font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">TRADE WIN %</div>
        <div style="font-size:22px;font-weight:700;color:{wc};margin-bottom:4px">{wr:.2f}%</div>
        </div>""", unsafe_allow_html=True)
        st.plotly_chart(fg2,use_container_width=True,config={"displayModeBar":False})
        st.markdown(f'<div style="display:flex;justify-content:center;gap:16px;font-size:10px;margin-top:-16px"><span style="color:{G}">{wins_n}</span><span style="color:{MUTED}">{be_n}</span><span style="color:{R}">{losses_n}</span></div>',unsafe_allow_html=True)

    with k4:
        ratio=aw/abs(al) if al else 0
        bw=int(aw/(aw+abs(al))*100) if (aw+abs(al)) else 50
        st.markdown(f"""<div style="border:1px solid {BORDER};border-radius:8px;padding:14px 16px;background:{BG}">
        <div style="font-size:9px;color:{MUTED};font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">AVG WIN/LOSS TRADE</div>
        <div style="font-size:22px;font-weight:700;color:{TEXT};margin-bottom:12px">{ratio:.2f}</div>
        <div style="height:8px;background:{BORDER};border-radius:4px;overflow:hidden;margin-bottom:6px">
            <div style="width:{bw}%;height:100%;background:{G};display:inline-block;vertical-align:top"></div>
            <div style="width:{100-bw}%;height:100%;background:{R};display:inline-block;vertical-align:top"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px">
            <span style="color:{G}">+₹{aw:,.0f}</span>
            <span style="color:{R}">-₹{abs(al):,.0f}</span>
        </div></div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>",unsafe_allow_html=True)

    # ── Toolbar ───────────────────────────────────────────────────────────────
    total_n=len(trades)
    pp=st.session_state.tl_pp
    total_pages=max(1,(total_n+pp-1)//pp)
    if st.session_state.tl_page>total_pages: st.session_state.tl_page=1
    start=(st.session_state.tl_page-1)*pp

    tb1,tb2,tb3,tb4 = st.columns([2,2,2,1])
    with tb1:
        st.markdown(f'<div style="padding-top:8px;font-size:12px;color:{MUTED}">{start+1}–{min(start+pp,total_n)} of {total_n} trades</div>',unsafe_allow_html=True)
    with tb2:
        bulk=st.selectbox("B",["— Bulk Actions —","Export to CSV","Delete selected"],
                          label_visibility="collapsed",key="tl_bulk")
        if bulk=="Export to CSV":
            buf=io.StringIO(); w=csv.DictWriter(buf,fieldnames=["id","ticker","strategy","side","qty","entry_price","exit_price","pnl","r_multiple","entry_date","exit_date"])
            w.writeheader()
            for t in trades: w.writerow({k:t.get(k,"") for k in w.fieldnames})
            st.download_button("⬇ Download",buf.getvalue(),"trades.csv","text/csv",key="tl_dl")
    with tb3:
        st.markdown("") # spacer
    with tb4:
        if st.button("⚙️ Columns",use_container_width=True,key="tl_colbtn"):
            select_columns_dialog()

    # ── Sort ──────────────────────────────────────────────────────────────────
    FMAP={"Open Date":"entry_date","Symbol":"ticker","Strategy":"strategy","Status":"pnl",
          "Side":"side","Close Date":"exit_date","Entry Price":"entry_price","Exit Price":"exit_price",
          "Net P&L":"pnl","R-Multiple":"r_multiple","Net ROI":"pnl","Stop Loss":"stop_loss","Qty":"qty"}
    NUM={"pnl","entry_price","exit_price","r_multiple","qty","stop_loss"}
    sc=FMAP.get(st.session_state.tl_sort,"exit_date")
    trades_s=sorted(trades,key=lambda x:float(x.get(sc) or 0) if sc in NUM else str(x.get(sc,"") or ""),
                    reverse=not st.session_state.tl_asc)
    page_t=trades_s[start:start+pp]
    COLS=st.session_state.tl_cols

    # ── Table header ──────────────────────────────────────────────────────────
    th=f"font-size:0.62rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:600;color:{MUTED};padding:7px 6px;border-bottom:2px solid {BORDER};white-space:nowrap"
    td=f"font-size:0.8rem;padding:7px 6px;border-bottom:1px solid {BORDER};white-space:nowrap;vertical-align:middle"

    # Column widths: narrow for checkbox and arrow, auto for data
    col_w=[0.25]+[1.4]*len(COLS)+[0.3]
    hdr_cols=st.columns(col_w)
    hdr_cols[0].markdown(f'<div style="{th}">☐</div>',unsafe_allow_html=True)
    for i,col in enumerate(COLS):
        arr=(" ▲" if st.session_state.tl_asc else " ▼") if st.session_state.tl_sort==FMAP.get(col,col) else ""
        hdr_cols[i+1].markdown(f'<div style="{th}">{col}{arr}</div>',unsafe_allow_html=True)
    hdr_cols[-1].markdown(f'<div style="{th}">→</div>',unsafe_allow_html=True)

    # ── Table rows ────────────────────────────────────────────────────────────
    def cv(t,col):
        pnl=t.get("pnl"); r=t.get("r_multiple")
        p=float(pnl or 0) if pnl is not None else 0
        rc=G if p>0 else R if p<0 else MUTED
        if col=="Open Date":   return str(t.get("entry_date","") or "")[:10]
        if col=="Symbol":      return f'<b style="color:{TEXT}">{t.get("ticker","")}</b>'
        if col=="Strategy":    return t.get("strategy","") or "—"
        if col=="Status":      return status_chip(pnl)
        if col=="Side":        return t.get("side","") or t.get("direction","") or "—"
        if col=="Close Date":  return str(t.get("exit_date","") or "")[:10] or "—"
        if col=="Entry Price": return f'₹{float(t.get("entry_price") or 0):,.2f}'
        if col=="Exit Price":  return f'₹{float(t.get("exit_price") or 0):,.2f}' if t.get("exit_price") else "—"
        if col=="Net P&L":
            bg="#F0FDF4" if p>0 else "#FEF2F2" if p<0 else BG
            return f'<span style="color:{rc};font-weight:700;background:{bg};padding:2px 7px;border-radius:8px;border:1px solid {rc}22">{"+"if p>0 else ""}₹{abs(p):,.0f}</span>'
        if col=="R-Multiple":
            if r:
                try: rv=float(r); return f'<span style="color:{G if rv>0 else R};font-weight:600">{rv:+.2f}R</span>'
                except: pass
            return "—"
        if col=="Net ROI":
            ep=float(t.get("entry_price") or 0); qty=float(t.get("qty") or 0)
            if ep and qty and pnl is not None:
                roi=p/(ep*qty)*100; return f'<span style="color:{rc}">{"+"if roi>0 else ""}{roi:.2f}%</span>'
            return "—"
        if col=="Stop Loss":   return f'<span style="color:{R}">₹{float(t.get("stop_loss") or 0):,.2f}</span>' if t.get("stop_loss") else "—"
        if col=="Qty":         return f'{int(t.get("qty") or 0):,}'
        if col=="Zella Scale": return zella_bar(r)
        if col=="Commissions":
            c2=float(t.get("commission_entry") or 0)+float(t.get("commission_exit") or 0)
            return f'₹{c2:,.0f}'
        if col=="Gross P&L":   return f'<span style="color:{rc}">{"+"if p>0 else ""}₹{abs(p):,.0f}</span>'
        return "—"

    for t in page_t:
        p=float(t.get("pnl") or 0) if t.get("pnl") is not None else 0
        rb="#F0FDF4" if p>0 else "#FEF2F2" if p<0 else BG
        row_cols=st.columns(col_w)
        row_cols[0].markdown(f'<div style="{td};background:{rb}">☐</div>',unsafe_allow_html=True)
        for i,col in enumerate(COLS):
            row_cols[i+1].markdown(f'<div style="{td};background:{rb}">{cv(t,col)}</div>',unsafe_allow_html=True)
        with row_cols[-1]:
            if st.button("→",key=f"tv_{t['id']}",help=f"Open {t.get('ticker','')}"):
                st.session_state.td_trade_id=t["id"]
                st.session_state.page="tradedetail"
                st.rerun()

    # ── Pagination ────────────────────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>",unsafe_allow_html=True)
    p1,p2,p3,p4,p5=st.columns([3,1,1,0.5,0.5])
    with p1:
        new_pp=st.selectbox("pp",[25,50,100],index=[25,50,100].index(pp) if pp in [25,50,100] else 1,
                             label_visibility="collapsed",key="tl_pp_sel")
        if new_pp!=pp: st.session_state.tl_pp=new_pp; st.session_state.tl_page=1; st.rerun()
    with p2:
        st.markdown(f'<div style="padding-top:6px;font-size:12px;color:{MUTED}">{start+1}–{min(start+pp,total_n)} of {total_n}</div>',unsafe_allow_html=True)
    with p3:
        pg=st.selectbox("pg",list(range(1,total_pages+1)),index=st.session_state.tl_page-1,
                        label_visibility="collapsed",key="tl_pg")
        if pg!=st.session_state.tl_page: st.session_state.tl_page=pg; st.rerun()
    with p4:
        if st.button("◀",key="tl_prev") and st.session_state.tl_page>1:
            st.session_state.tl_page-=1; st.rerun()
    with p5:
        if st.button("▶",key="tl_next") and st.session_state.tl_page<total_pages:
            st.session_state.tl_page+=1; st.rerun()

    # ── Trade actions ─────────────────────────────────────────────────────────
    if HAS_MODALS:
        with st.expander("🔧 Trade Actions"):
            open_t=[t for t in all_trades if t.get("status")=="OPEN"]
            a1,a2,a3=st.columns(3)
            with a1:
                opts=[f"#{t['id']} {t['ticker']}" for t in open_t]
                if opts:
                    sel=st.selectbox("Exit",opts,key="tl_exit_sel")
                    if st.button("Exit →",type="primary",use_container_width=True,key="tl_exit_btn"):
                        tid=int(sel.split("#")[1].split(" ")[0])
                        tr=next((t for t in open_t if t["id"]==tid),None)
                        if tr: exit_trade_dialog(tr)
                else: st.caption("No open trades.")
            with a2:
                aopts=[f"#{t['id']} {t['ticker']}" for t in all_trades]
                if aopts:
                    sel_e=st.selectbox("Edit",aopts,key="tl_edit_sel")
                    if st.button("✏️ Edit",use_container_width=True,key="tl_edit_btn"):
                        tid=int(sel_e.split("#")[1].split(" ")[0])
                        tr=next((t for t in all_trades if t["id"]==tid),None)
                        if tr: edit_trade_dialog(tr)
            with a3:
                if aopts:
                    sel_d=st.selectbox("Delete",aopts,key="tl_del_sel")
                    if st.button("🗑 Delete",use_container_width=True,key="tl_del_btn"):
                        tid=int(sel_d.split("#")[1].split(" ")[0])
                        delete_trade(tid); st.success("Deleted"); st.rerun()
