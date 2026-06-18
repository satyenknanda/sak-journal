# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import os, sqlite3, hashlib
from datetime import date, datetime

from theme import *
from data.db import get_trades, delete_trade

G="#10B981"; R="#EF4444"; B="#3B82F6"; AM="#F59E0B"; PU="#7C3AED"
TEXT="#111827"; MUTED="#6B7280"; BORDER="#E5E7EB"; BG="#FFFFFF"; DARK="#1E293B"

_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "journal.db"))
_ATTACH_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "attachments"))
os.makedirs(_ATTACH_DIR, exist_ok=True)

# ── DB ────────────────────────────────────────────────────────────────────────
def _init():
    c=sqlite3.connect(_DB)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS trade_attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,filename TEXT,filepath TEXT,filetype TEXT,
            created_at TEXT DEFAULT(datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS trade_pt_sl(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,level_type TEXT,price REAL,qty REAL,sort_order INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS trade_executions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,exec_date TEXT,exec_time TEXT,
            price REAL,qty REAL,side TEXT,fee REAL DEFAULT 0,
            commission REAL DEFAULT 0,swap REAL DEFAULT 0,notes TEXT,
            created_at TEXT DEFAULT(datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS note_templates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,content TEXT,
            used_at TEXT DEFAULT(datetime('now','localtime')));
    """)
    for col in ["trade_rating","best_exit_price","best_exit_time","open_time","close_time","reviewed","playbook","setup","mistakes","tags"]:
        try: c.execute(f"ALTER TABLE trades ADD COLUMN {col} TEXT")
        except: pass
    c.commit(); c.close()

def _db(sql,params=(),fetch=None):
    c=sqlite3.connect(_DB); c.row_factory=sqlite3.Row
    cur=c.execute(sql,params); c.commit()
    result=cur.fetchall() if fetch=="all" else cur.fetchone() if fetch=="one" else None
    c.close()
    return [dict(r) for r in result] if result and fetch=="all" else (dict(result) if result and fetch=="one" else None)

def _save_note(d,t): _db("INSERT INTO daily_notes(note_date,note,updated_at)VALUES(?,?,datetime('now','localtime'))ON CONFLICT(note_date)DO UPDATE SET note=excluded.note,updated_at=excluded.updated_at",(d,t))
def _get_note(d):
    r=_db("SELECT note FROM daily_notes WHERE note_date=?",(d,),fetch="one")
    return r["note"] if r else ""

def _get_executions(tid): return _db("SELECT * FROM trade_executions WHERE trade_id=? ORDER BY exec_date,exec_time",(tid,),fetch="all") or []
def _save_execution(tid,ed,et,price,qty,side,fee,comm,swap,notes):
    _db("INSERT INTO trade_executions(trade_id,exec_date,exec_time,price,qty,side,fee,commission,swap,notes)VALUES(?,?,?,?,?,?,?,?,?,?)",(tid,ed,et,price,qty,side,fee,comm,swap,notes))
def _del_execution(eid): _db("DELETE FROM trade_executions WHERE id=?",(eid,))

def _get_attachments(tid): return _db("SELECT * FROM trade_attachments WHERE trade_id=? ORDER BY created_at",(tid,),fetch="all") or []
def _save_attachment(tid,fn,fp,ft): _db("INSERT INTO trade_attachments(trade_id,filename,filepath,filetype)VALUES(?,?,?,?)",(tid,fn,fp,ft))
def _del_attachment(aid,fp):
    _db("DELETE FROM trade_attachments WHERE id=?",(aid,))
    if os.path.exists(fp): os.remove(fp)

def _get_pt_sl(tid): return _db("SELECT * FROM trade_pt_sl WHERE trade_id=? ORDER BY level_type,sort_order",(tid,),fetch="all") or []
def _save_pt_sl(tid,levels):
    _db("DELETE FROM trade_pt_sl WHERE trade_id=?",(tid,))
    for i,lv in enumerate(levels):
        _db("INSERT INTO trade_pt_sl(trade_id,level_type,price,qty,sort_order)VALUES(?,?,?,?,?)",(tid,lv["type"],lv["price"],lv["qty"],i))
    pts=[l for l in levels if l["type"]=="PT" and l["price"]>0]
    sls=[l for l in levels if l["type"]=="SL" and l["price"]>0]
    if pts: _db("UPDATE trades SET take_profit=? WHERE id=?",(pts[0]["price"],tid))
    if sls: _db("UPDATE trades SET stop_loss=? WHERE id=?",(sls[0]["price"],tid))

def _get_templates(): return _db("SELECT * FROM note_templates ORDER BY used_at DESC LIMIT 10",fetch="all") or []
def _save_template(name,content): _db("INSERT INTO note_templates(name,content)VALUES(?,?)",(name,content))
def _del_template(tid2): _db("DELETE FROM note_templates WHERE id=?",(tid2,))

def _save_trade_field(tid,**kwargs):
    for k,v in kwargs.items():
        try: _db(f"UPDATE trades SET {k}=? WHERE id=?",(v,tid))
        except: pass

def _get_playbooks():
    try:
        rows=_db("SELECT name FROM playbooks ORDER BY name",fetch="all") or []
        return [r["name"] for r in rows]
    except: return []

def tv_sym(sym):
    m={"NIFTY50":"NSE:NIFTY50","BANKNIFTY":"NSE:BANKNIFTY","SENSEX":"BSE:SENSEX","FINNIFTY":"NSE:FINNIFTY"}
    return m.get(sym,f"BSE:{sym}")

def sr(label,value):
    return f'<div style="display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid {BORDER}"><span style="font-size:12px;color:{MUTED}">{label}</span><span style="font-size:12px;color:{TEXT}">{value}</span></div>'

def chip(label,val,color,bg):
    return f'<div style="background:{bg};border:1px solid {color}44;border-radius:6px;padding:6px 12px;text-align:center"><div style="font-size:9px;color:{color};letter-spacing:1px;margin-bottom:2px">{label}</div><div style="font-size:13px;font-weight:700;color:{color}">{val}</div></div>'

def render():
    _init()
    trade_id=st.session_state.get("td_trade_id")
    all_trades=get_trades()
    if not trade_id:
        st.info("No trade selected.")
        if st.button("← Trade Log"): st.session_state.page="journal"; st.rerun()
        return
    trade=next((t for t in all_trades if t.get("id")==trade_id),None)
    if not trade:
        if st.button("← Back"): st.session_state.page="journal"; st.rerun()
        return

    d_str=str(trade.get("exit_date") or trade.get("entry_date") or "")[:10]
    day_trades=[t for t in all_trades if str(t.get("exit_date") or t.get("entry_date") or "")[:10]==d_str]
    day_pnl=sum(float(t.get("pnl") or 0) for t in day_trades)

    ticker  =trade.get("ticker","")
    pnl     =float(trade.get("pnl") or 0)
    entry_p =float(trade.get("entry_price") or 0)
    exit_p  =float(trade.get("exit_price") or 0)
    sl      =float(trade.get("stop_loss") or 0)
    qty     =int(trade.get("qty") or 0)
    r_mult  =trade.get("r_multiple")
    strategy=trade.get("strategy","") or "—"
    side    =trade.get("side","") or trade.get("direction","") or "—"
    mae     =float(trade.get("mae_price") or 0)
    mfe     =float(trade.get("mfe_price") or 0)
    rating  =int(trade.get("trade_rating") or 0)
    reviewed=bool(trade.get("reviewed",0))
    best_ep =float(trade.get("best_exit_price") or 0)
    best_et =str(trade.get("best_exit_time") or "")
    open_t  =str(trade.get("open_time") or str(trade.get("entry_date") or "")[:16])
    close_t =str(trade.get("close_time") or str(trade.get("exit_date") or "")[:16])
    pnl_col =G if pnl>=0 else R

    try: d_label=datetime.strptime(d_str,"%Y-%m-%d").strftime("%a, %b %d, %Y")
    except: d_label=d_str

    # ── Header ────────────────────────────────────────────────────────────────
    ph1,ph2,ph3=st.columns([0.4,3.5,2.5])
    with ph1:
        if st.button("☰",key="td_menu"): st.session_state.td_sidebar=not st.session_state.get("td_sidebar",True); st.rerun()
    with ph2:
        wl="WIN" if pnl>0 else "LOSS" if pnl<0 else "BE"
        wb="#F0FDF4" if pnl>0 else "#FEF2F2" if pnl<0 else "#F3F4F6"
        st.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding-top:4px"><span style="font-size:18px;font-weight:800;color:{TEXT}">{ticker}</span><span style="background:{wb};color:{pnl_col};padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700">{wl}</span><span style="font-size:13px;color:{MUTED}">{d_label}</span></div>',unsafe_allow_html=True)
    with ph3:
        hc1,hc2,hc3,hc4=st.columns(4)
        if hc1.button("✓ Done" if reviewed else "Review",key="td_rev",use_container_width=True):
            _save_trade_field(trade_id,reviewed=0 if reviewed else 1); st.rerun()
        if hc2.button("🔗 Share",key="td_share_btn",use_container_width=True):
            st.session_state.td_show_share=not st.session_state.get("td_show_share",False)
        if hc3.button("← Log",key="td_back",use_container_width=True):
            st.session_state.page="journal"; st.rerun()
        if hc4.button("🗑",key="td_del",use_container_width=True,type="secondary"):
            delete_trade(trade_id); st.session_state.page="journal"; st.rerun()

    if st.session_state.get("td_show_share"):
        r_str=f" | {float(r_mult):+.2f}R" if r_mult else ""
        share_txt=f"{ticker} {d_label} | {'+'if pnl>=0 else ''}₹{abs(pnl):,.0f}{r_str} | {strategy} | {side}"
        with st.container(border=True):
            sc1,sc2=st.columns([5,1])
            sc1.text_input("Share text",value=share_txt,key="td_share_txt",label_visibility="collapsed")
            if sc2.button("✕",key="td_share_close"): st.session_state.td_show_share=False; st.rerun()
            st.code(share_txt,language=None)

    st.markdown(f'<hr style="border:none;border-top:1px solid {BORDER};margin:6px 0 10px">',unsafe_allow_html=True)

    show_sb=st.session_state.get("td_sidebar",True)
    if show_sb: sb,main=st.columns([1,3])
    else: main=st.container()

    # ── SIDEBAR ───────────────────────────────────────────────────────────────
    if show_sb:
      with sb:
        all_s=sorted([t for t in all_trades if t.get("status")=="CLOSED"],key=lambda x:str(x.get("exit_date") or ""))
        idx=next((i for i,t in enumerate(all_s) if t.get("id")==trade_id),0)
        n1,n2,n3=st.columns([1,2,1])
        with n1:
            if idx>0 and st.button("◀",key="td_prev"):
                st.session_state.td_trade_id=all_s[idx-1]["id"]
                for k in ["td_pts","td_sls"]: st.session_state.pop(k,None)
                st.rerun()
        n2.markdown(f'<div style="text-align:center;padding-top:6px;font-size:11px;color:{MUTED}">{idx+1}/{len(all_s)}</div>',unsafe_allow_html=True)
        with n3:
            if idx<len(all_s)-1 and st.button("▶",key="td_next"):
                st.session_state.td_trade_id=all_s[idx+1]["id"]
                for k in ["td_pts","td_sls"]: st.session_state.pop(k,None)
                st.rerun()

        stab=st.tabs(["Stats","Playbook","Executions","Attachments"])

        # ── STATS ─────────────────────────────────────────────────────────────
        with stab[0]:
            # Reviewed inline
            rev_col=G if reviewed else MUTED
            rc1,rc2=st.columns([3,1])
            rc1.markdown(f'<div style="font-size:10px;color:{MUTED};margin-bottom:2px">Net P&L</div><div style="font-size:26px;font-weight:800;color:{pnl_col}">{"+"if pnl>=0 else ""}₹{abs(pnl):,.0f}</div>',unsafe_allow_html=True)
            with rc2:
                st.markdown("<div style='height:4px'></div>",unsafe_allow_html=True)
                if st.button("✓ Reviewed" if reviewed else "○ Review",key="td_rev2",use_container_width=True):
                    _save_trade_field(trade_id,reviewed=0 if reviewed else 1); st.rerun()

            rows=""
            rows+=sr("Side",f'<span style="color:{G if side.upper() in ("LONG","BUY") else R};font-weight:700">{side.upper()}</span>')
            rows+=sr("Strategy",strategy)
            rows+=sr("Qty",f"{qty:,}")
            comm=float(trade.get("commission_entry") or 0)+float(trade.get("commission_exit") or 0)
            rows+=sr("Commissions",f"₹{comm:,.2f}")
            if entry_p and qty:
                roi=pnl/(entry_p*qty)*100
                rows+=sr("Net ROI",f'<span style="color:{pnl_col}">{"+"if roi>=0 else ""}{roi:.2f}%</span>')
            rows+=sr("Gross P&L",f'<span style="color:{pnl_col}">{"+"if pnl>=0 else ""}₹{abs(pnl):,.0f}</span>')
            rows+=sr("Adjusted Cost",f"₹{entry_p*qty:,.2f}" if entry_p and qty else "—")
            # Open/Close time
            rows+=sr("Open Time",open_t[:16] if open_t else "—")
            rows+=sr("Close Time",close_t[:16] if close_t else "—")
            # Best Exit
            rows+=sr("Best Exit Price",f"₹{best_ep:,.2f}" if best_ep else "—")
            rows+=sr("Best Exit Time",best_et[:16] if best_et else "—")
            # Zella Scale
            if r_mult:
                try:
                    rv=float(r_mult); pct=min(abs(rv)/5*100,100); zc=G if rv>0 else R
                    zb=f'<div style="display:flex;align-items:center;gap:5px"><div style="width:65px;height:6px;background:#F3F4F6;border-radius:3px;overflow:hidden"><div style="width:{pct}%;height:100%;background:{zc}"></div></div><span style="color:{zc};font-size:11px">{rv:+.2f}R</span></div>'
                    rows+=sr("Zella Scale",zb)
                except: pass
            # MAE/MFE
            if mae or mfe:
                mc=f'<span style="background:#FEF2F2;color:{R};padding:1px 7px;border-radius:8px;font-size:11px;font-weight:600">₹{mae:,.2f}</span>'
                fc=f'<span style="background:#F0FDF4;color:{G};padding:1px 7px;border-radius:8px;font-size:11px;font-weight:600">₹{mfe:,.2f}</span>'
                rows+=sr("Price MAE / MFE",f"{mc} / {fc}")

            st.markdown(f'<div style="margin:6px 0">{rows}</div>',unsafe_allow_html=True)

            # Calc MAE/MFE button if missing
            if not (mae or mfe):
                if st.button("📊 Calculate MAE/MFE",use_container_width=True,key="td_calc"):
                    with st.spinner("Fetching price data..."):
                        try:
                            import sys; sys.path.insert(0,os.path.expanduser("~/Desktop/sak_journal"))
                            import calc_mae_mfe,importlib; importlib.reload(calc_mae_mfe)
                            df2=calc_mae_mfe.get_price_data(ticker,trade.get("entry_date"),trade.get("exit_date"))
                            t2={"id":trade_id,"ticker":ticker,"side":side,"entry_price":entry_p,"exit_price":exit_p,"qty":qty,"entry_date":trade.get("entry_date"),"exit_date":trade.get("exit_date")}
                            mv,fv=calc_mae_mfe.calc_mae_mfe(t2,df2)
                            if mv: calc_mae_mfe.save_mae_mfe(trade_id,mv,fv); st.success(f"✅ MAE:₹{mv:,.2f} MFE:₹{fv:,.2f}"); st.rerun()
                            else: st.warning("No price data.")
                        except Exception as e: st.error(str(e))

            # Best Exit Price/Time editor
            with st.expander("✏️ Edit Open/Close/Best Exit"):
                e1,e2=st.columns(2)
                new_ot=e1.text_input("Open Time",value=open_t,key="td_ot",placeholder="2026-04-01 09:15")
                new_ct=e2.text_input("Close Time",value=close_t,key="td_ct",placeholder="2026-04-01 15:20")
                new_bep=e1.number_input("Best Exit ₹",value=best_ep,step=0.5,key="td_bep",format="%.2f")
                new_bet=e2.text_input("Best Exit Time",value=best_et,key="td_bet",placeholder="2026-04-01 10:30")
                if st.button("💾 Save",key="td_save_times",use_container_width=True,type="primary"):
                    _save_trade_field(trade_id,open_time=new_ot,close_time=new_ct,best_exit_price=new_bep,best_exit_time=new_bet)
                    st.success("Saved!"); st.rerun()

            # Trade Rating
            st.markdown(f'<div style="font-size:11px;color:{MUTED};margin:10px 0 4px">Trade Rating</div>',unsafe_allow_html=True)
            rcols=st.columns(5)
            for i in range(5):
                with rcols[i]:
                    if st.button("★" if i<rating else "☆",key=f"td_s{i}"):
                        _save_trade_field(trade_id,trade_rating=i+1 if i+1!=rating else 0); st.rerun()

            st.markdown(f'<hr style="border:none;border-top:1px solid {BORDER};margin:10px 0">',unsafe_allow_html=True)

            # PT/SL
            pt_sl=_get_pt_sl(trade_id)
            pts_db=[l for l in pt_sl if l["level_type"]=="PT"]
            sls_db=[l for l in pt_sl if l["level_type"]=="SL"]
            if "td_pts" not in st.session_state:
                st.session_state.td_pts=pts_db or [{"type":"PT","price":float(trade.get("take_profit") or 0),"qty":qty}]
            if "td_sls" not in st.session_state:
                st.session_state.td_sls=sls_db or [{"type":"SL","price":sl,"qty":qty}]

            st.markdown(f'<div style="font-size:12px;font-weight:700;color:{G};margin-bottom:4px">Profit Targets</div>',unsafe_allow_html=True)
            for i,lv in enumerate(st.session_state.td_pts):
                c1,c2,c3=st.columns([2,1.5,0.5])
                p=c1.number_input(f"PT{i+1}",value=float(lv.get("price") or 0),step=0.5,key=f"td_pt_{i}",label_visibility="collapsed",format="%.2f")
                q=c2.number_input("Q",value=float(lv.get("qty") or qty),step=1.0,key=f"td_ptq_{i}",label_visibility="collapsed",format="%.0f")
                if c3.button("✕",key=f"td_ptd_{i}") and len(st.session_state.td_pts)>1:
                    st.session_state.td_pts.pop(i); st.rerun()
                st.session_state.td_pts[i]={"type":"PT","price":p,"qty":q}
            if st.button("＋ PT",key="td_add_pt",use_container_width=True):
                st.session_state.td_pts.append({"type":"PT","price":0.0,"qty":qty}); st.rerun()

            st.markdown(f'<div style="font-size:12px;font-weight:700;color:{R};margin:8px 0 4px">Stop Losses</div>',unsafe_allow_html=True)
            for i,lv in enumerate(st.session_state.td_sls):
                c1,c2,c3=st.columns([2,1.5,0.5])
                p=c1.number_input(f"SL{i+1}",value=float(lv.get("price") or 0),step=0.5,key=f"td_sl_{i}",label_visibility="collapsed",format="%.2f")
                q=c2.number_input("Q",value=float(lv.get("qty") or qty),step=1.0,key=f"td_slq_{i}",label_visibility="collapsed",format="%.0f")
                if c3.button("✕",key=f"td_sld_{i}") and len(st.session_state.td_sls)>1:
                    st.session_state.td_sls.pop(i); st.rerun()
                st.session_state.td_sls[i]={"type":"SL","price":p,"qty":q}
            if st.button("＋ SL",key="td_add_sl",use_container_width=True):
                st.session_state.td_sls.append({"type":"SL","price":0.0,"qty":qty}); st.rerun()

            if st.button("💾 Save PT/SL",use_container_width=True,key="td_save_ptsl",type="primary"):
                _save_pt_sl(trade_id,st.session_state.td_pts+st.session_state.td_sls); st.success("Saved!"); st.rerun()

            # R metrics
            all_pts2=st.session_state.td_pts; all_sls2=st.session_state.td_sls
            pt_px=[l["price"] for l in all_pts2 if l.get("price",0)>0]
            sl_px=[l["price"] for l in all_sls2 if l.get("price",0)>0]
            if pt_px and sl_px and entry_p:
                pt_v=sum(l["price"]*l["qty"] for l in all_pts2 if l.get("price",0)>0)
                pt_q=sum(l["qty"] for l in all_pts2 if l.get("price",0)>0)
                sl_v=sum(l["price"]*l["qty"] for l in all_sls2 if l.get("price",0)>0)
                sl_q=sum(l["qty"] for l in all_sls2 if l.get("price",0)>0)
                avg_pt=pt_v/pt_q if pt_q else 0; avg_sl=sl_v/sl_q if sl_q else 0
                if side.upper() in ("LONG","BUY"):
                    it=(avg_pt-entry_p)*min(pt_q,qty); tr=(entry_p-avg_sl)*min(sl_q,qty)
                else:
                    it=(entry_p-avg_pt)*min(pt_q,qty); tr=(avg_sl-entry_p)*min(sl_q,qty)
                pr=it/tr if tr else 0; rr=pnl/tr if tr else 0
                rrows=""
                rrows+=sr("Initial Target",f'<span style="color:{G}">₹{it:,.0f}</span>')
                rrows+=sr("Trade Risk",f'<span style="color:{R}">-₹{abs(tr):,.0f}</span>')
                rrows+=sr("Planned R",f'<span style="color:{G if pr>=0 else R}">{pr:.2f}R</span>')
                rrows+=sr("Realized R",f'<span style="color:{G if rr>=0 else R}">{rr:+.2f}R</span>')
                st.markdown(f'<div style="margin-top:8px">{rrows}</div>',unsafe_allow_html=True)

            st.markdown(f'<hr style="border:none;border-top:1px solid {BORDER};margin:10px 0">',unsafe_allow_html=True)
            exrows=sr("Avg Entry",f"₹{entry_p:,.2f}" if entry_p else "—")+sr("Avg Exit",f"₹{exit_p:,.2f}" if exit_p else "—")+sr("Entry Date",str(trade.get("entry_date",""))[:10])+sr("Exit Date",str(trade.get("exit_date",""))[:10] or "—")
            st.markdown(f'<div>{exrows}</div>',unsafe_allow_html=True)

            # Day trades list
            st.markdown(f'<div style="font-size:10px;font-weight:600;color:{MUTED};letter-spacing:1px;margin:12px 0 6px">DAY TRADES</div>',unsafe_allow_html=True)
            dp_col2=G if day_pnl>=0 else R
            st.markdown(f'<div style="background:{DARK};border-radius:7px;padding:8px;margin-bottom:8px;text-align:center"><div style="font-size:9px;color:#64748B">Day P&L</div><div style="font-size:16px;font-weight:800;color:{dp_col2}">{"+"if day_pnl>=0 else ""}₹{abs(day_pnl):,.0f}</div></div>',unsafe_allow_html=True)
            for t in sorted(day_trades,key=lambda x:str(x.get("entry_date") or "")):
                p=float(t.get("pnl") or 0); pc=G if p>0 else R if p<0 else MUTED
                is_cur=t.get("id")==trade_id
                st.markdown(f'<div style="background:{"#EDE9FE" if is_cur else BG};border:{"2px solid "+PU if is_cur else "1px solid "+BORDER};border-radius:7px;padding:7px 10px;margin-bottom:5px"><div style="display:flex;justify-content:space-between"><span style="font-size:12px;font-weight:700;color:{TEXT}">{t.get("ticker","")}</span><span style="font-size:12px;font-weight:700;color:{pc}">{"+"if p>0 else ""}₹{abs(p):,.0f}</span></div><div style="font-size:10px;color:{MUTED};margin-top:2px">{t.get("strategy","") or "—"}</div></div>',unsafe_allow_html=True)
                if not is_cur:
                    if st.button("→",key=f"td_sw_{t['id']}",use_container_width=True):
                        st.session_state.td_trade_id=t["id"]
                        for k in ["td_pts","td_sls"]: st.session_state.pop(k,None)
                        st.rerun()

        # ── PLAYBOOK TAB ──────────────────────────────────────────────────────
        with stab[1]:
            # Playbook dropdown
            pbs=_get_playbooks()
            cur_pb=trade.get("playbook","") or ""
            if pbs:
                opts=["— Select Playbook —"]+pbs
                idx_pb=pbs.index(cur_pb)+1 if cur_pb in pbs else 0
                sel_pb=st.selectbox("Playbook",opts,index=idx_pb,label_visibility="collapsed",key="td_pb_sel")
                if sel_pb!="— Select Playbook —" and sel_pb!=cur_pb:
                    _save_trade_field(trade_id,playbook=sel_pb); st.rerun()
            else:
                st.info("No playbooks found. Create one in the Playbook page.")
                if cur_pb:
                    st.markdown(f'<div style="background:#EDE9FE;border:1px solid #C4B5FD;border-radius:8px;padding:10px;margin-bottom:8px"><div style="font-size:9px;color:{PU}">PLAYBOOK</div><div style="font-size:14px;font-weight:700;color:{PU}">{cur_pb}</div></div>',unsafe_allow_html=True)

            st.markdown(f'<hr style="border:none;border-top:1px solid {BORDER};margin:8px 0">',unsafe_allow_html=True)

            # Setup tags
            st.markdown(f'<div style="font-size:11px;font-weight:600;color:{TEXT};margin-bottom:4px">Setups</div>',unsafe_allow_html=True)
            SETUP_OPTS=["VCP","SVRO","EP","Reversal","NR 1HR","MARS","TS","Momentum Burst","Gap Up","Gap Down","Inside Bar","Breakout"]
            cur_setup=(trade.get("setup","") or "").split(",") if trade.get("setup") else []
            new_setup=st.multiselect("Setups",SETUP_OPTS,default=[s for s in cur_setup if s in SETUP_OPTS],label_visibility="collapsed",key="td_setup")
            new_setup_txt=st.text_input("Custom setup",placeholder="Add custom setup tag...",key="td_setup_custom")
            if new_setup_txt and st.button("＋ Add",key="td_add_setup"):
                combined=",".join(new_setup+[new_setup_txt])
                _save_trade_field(trade_id,setup=combined); st.rerun()
            elif new_setup!=cur_setup:
                _save_trade_field(trade_id,setup=",".join(new_setup)); st.rerun()

            # Mistakes tags
            st.markdown(f'<div style="font-size:11px;font-weight:600;color:{TEXT};margin:8px 0 4px">Mistakes</div>',unsafe_allow_html=True)
            MISTAKE_OPTS=["Early Entry","Early Exit","Late Entry","Late Exit","Oversized","FOMO","Revenge Trade","Ignored SL","No Stop Set","Chased","Wrong Setup"]
            cur_mistakes=(trade.get("mistakes","") or "").split(",") if trade.get("mistakes") else []
            new_mistakes=st.multiselect("Mistakes",MISTAKE_OPTS,default=[m for m in cur_mistakes if m in MISTAKE_OPTS],label_visibility="collapsed",key="td_mistakes")
            new_mistake_txt=st.text_input("Custom mistake",placeholder="Add custom mistake...",key="td_mistake_custom")
            if new_mistake_txt and st.button("＋ Add",key="td_add_mistake"):
                combined=",".join(new_mistakes+[new_mistake_txt])
                _save_trade_field(trade_id,mistakes=combined); st.rerun()
            elif new_mistakes!=cur_mistakes:
                _save_trade_field(trade_id,mistakes=",".join(new_mistakes)); st.rerun()

            # Custom tags
            st.markdown(f'<div style="font-size:11px;font-weight:600;color:{TEXT};margin:8px 0 4px">Tags</div>',unsafe_allow_html=True)
            cur_tags=(trade.get("tags","") or "")
            new_tags=st.text_input("Tags",value=cur_tags,placeholder="e.g. earnings,gap-up,sector-rotation",key="td_tags",label_visibility="collapsed")
            if new_tags!=cur_tags:
                _save_trade_field(trade_id,tags=new_tags)
            # Show tag chips
            if cur_tags:
                tags_html='<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">'
                for tag in cur_tags.split(","):
                    if tag.strip():
                        tags_html+=f'<span style="background:#F3F4F6;color:{MUTED};padding:2px 8px;border-radius:12px;font-size:11px">{tag.strip()}</span>'
                tags_html+='</div>'
                st.markdown(tags_html,unsafe_allow_html=True)

        # ── EXECUTIONS TAB ────────────────────────────────────────────────────
        with stab[2]:
            execs=_get_executions(trade_id)
            # If no manual executions, show default from trade
            if not execs:
                th=f"font-size:10px;color:{MUTED};font-weight:600;padding:6px 4px;border-bottom:1px solid {BORDER}"
                td2=f"font-size:11px;padding:6px 4px;border-bottom:1px solid {BORDER}"
                st.markdown(f'<div style="font-size:11px;font-weight:600;color:{TEXT};margin-bottom:6px">2 executions</div>',unsafe_allow_html=True)
                st.markdown(f"""<table style="width:100%;border-collapse:collapse">
                    <thead><tr><th style="{th}">Date/Time</th><th style="{th}">Price</th><th style="{th}">Qty</th><th style="{th}">Fee</th><th style="{th}">Comm</th><th style="{th}">Gross P&L</th></tr></thead>
                    <tbody>
                    <tr><td style="{td2}">{str(trade.get("entry_date",""))[:10]}</td><td style="{td2}">₹{entry_p:,.2f}</td><td style="{td2}">+{qty}</td><td style="{td2}">—</td><td style="{td2}">₹{float(trade.get("commission_entry") or 0):,.2f}</td><td style="{td2}">—</td></tr>
                    {"<tr><td style='"+td2+"'>"+str(trade.get("exit_date",""))[:10]+"</td><td style='"+td2+"'>₹"+f"{exit_p:,.2f}"+"</td><td style='"+td2+"'>-"+str(qty)+"</td><td style='"+td2+"'>—</td><td style='"+td2+"'>₹"+f"{float(trade.get('commission_exit') or 0):,.2f}"+"</td><td style='"+td2+";color:"+pnl_col+"'>"+("+"if pnl>=0 else "")+"₹"+f"{abs(pnl):,.0f}"+"</td></tr>" if exit_p else ""}
                    </tbody></table>""",unsafe_allow_html=True)
            else:
                # Show saved executions
                total_fee=sum(float(e.get("fee") or 0) for e in execs)
                total_comm=sum(float(e.get("commission") or 0) for e in execs)
                total_swap=sum(float(e.get("swap") or 0) for e in execs)
                st.markdown(f'<div style="font-size:11px;font-weight:600;color:{TEXT};margin-bottom:6px">{len(execs)} executions · Fees: ₹{total_fee:,.2f} · Comm: ₹{total_comm:,.2f} · Swap: ₹{total_swap:,.2f}</div>',unsafe_allow_html=True)
                for e in execs:
                    ec1,ec2=st.columns([4,1])
                    p_e=float(e.get("price") or 0); q_e=float(e.get("qty") or 0)
                    ec1.markdown(f'<div style="background:#F9FAFB;border:1px solid {BORDER};border-radius:6px;padding:7px 10px;margin-bottom:4px;font-size:11px"><b>{e.get("exec_date","")} {e.get("exec_time","")}</b> · {e.get("side","")} {int(q_e)} @ ₹{p_e:,.2f} · Fee:₹{float(e.get("fee") or 0):.2f} · Comm:₹{float(e.get("commission") or 0):.2f} · Swap:₹{float(e.get("swap") or 0):.2f}</div>',unsafe_allow_html=True)
                    if ec2.button("🗑",key=f"td_del_exec_{e['id']}"):
                        _del_execution(e["id"]); st.rerun()

            # Add execution
            st.markdown(f'<div style="font-size:11px;font-weight:700;color:{TEXT};margin:10px 0 6px">＋ Add Execution</div>',unsafe_allow_html=True)
            with st.container(border=True):
                ae1,ae2,ae3=st.columns(3)
                ae_date=ae1.text_input("Date",value=d_str,key="td_ae_date",placeholder="YYYY-MM-DD")
                ae_time=ae2.text_input("Time",value="09:15",key="td_ae_time",placeholder="HH:MM")
                ae_side=ae3.selectbox("Side",["BUY","SELL"],key="td_ae_side",label_visibility="visible")
                ae4,ae5=st.columns(2)
                ae_price=ae4.number_input("Price ₹",value=entry_p,step=0.5,key="td_ae_price",format="%.2f")
                ae_qty=ae5.number_input("Qty",value=float(qty),step=1.0,key="td_ae_qty",format="%.0f")
                ae6,ae7,ae8=st.columns(3)
                ae_fee=ae6.number_input("Fee ₹",value=0.0,step=1.0,key="td_ae_fee",format="%.2f")
                ae_comm=ae7.number_input("Commission ₹",value=0.0,step=1.0,key="td_ae_comm",format="%.2f")
                ae_swap=ae8.number_input("Swap ₹",value=0.0,step=1.0,key="td_ae_swap",format="%.2f",help="Forex swap fees (+ or -)")
                ae_notes=st.text_input("Notes",placeholder="Optional notes for this execution",key="td_ae_notes",label_visibility="collapsed")
                if st.button("＋ Add Execution",type="primary",use_container_width=True,key="td_add_exec"):
                    _save_execution(trade_id,ae_date,ae_time,ae_price,ae_qty,ae_side,ae_fee,ae_comm,ae_swap,ae_notes)
                    st.success("Execution added!"); st.rerun()

        # ── ATTACHMENTS TAB ───────────────────────────────────────────────────
        with stab[3]:
            attachments=_get_attachments(trade_id)
            uploaded=st.file_uploader("Upload chart/screenshot",type=["png","jpg","jpeg","gif","webp"],key=f"td_up_{trade_id}",label_visibility="collapsed")
            if uploaded:
                ext=uploaded.name.split(".")[-1].lower()
                fname=f"t{trade_id}_{hashlib.md5(uploaded.name.encode()).hexdigest()[:8]}.{ext}"
                fpath=os.path.join(_ATTACH_DIR,fname)
                with open(fpath,"wb") as f: f.write(uploaded.read())
                _save_attachment(trade_id,uploaded.name,fpath,ext)
                st.success("Uploaded!"); st.rerun()
            if not attachments:
                st.markdown(f'<div style="text-align:center;padding:20px;color:{MUTED};font-size:12px">📎 No attachments yet.<br>Upload chart screenshots above.</div>',unsafe_allow_html=True)
            else:
                for att in attachments:
                    fp=att.get("filepath","")
                    if os.path.exists(fp):
                        st.image(fp,caption=att.get("filename",""),use_container_width=True)
                        if st.button(f"🗑 Delete",key=f"td_dela_{att['id']}"):
                            _del_attachment(att["id"],fp); st.rerun()

    # ── MAIN ──────────────────────────────────────────────────────────────────
    with main:
        ct1,ct2,ct3=st.tabs(["📈 Chart","📝 Notes","📊 Running P&L"])

        with ct1:
            INTERVALS={"1m":"1","5m":"5","15m":"15","30m":"30","1H":"60","4H":"240","1D":"D","1W":"W"}
            ivk=list(INTERVALS.keys())
            iv_sel=st.selectbox("IV",ivk,index=ivk.index("1D"),label_visibility="collapsed",key=f"td_iv_{trade_id}")
            iv=INTERVALS[iv_sel]

            # Chart settings
            with st.expander("⚙️ Chart Settings"):
                cs1,cs2,cs3,cs4=st.columns(4)
                show_events=cs1.toggle("Show Events",value=False,key="td_cs_events")
                smooth_candles=cs2.toggle("Smooth Candles",value=False,key="td_cs_smooth")
                hide_volume=cs3.toggle("Hide Volume",value=False,key="td_cs_vol")
                show_premarket=cs4.toggle("Pre-market",value=False,key="td_cs_pre")
                cs5,cs6=st.columns(2)
                chart_style=cs5.selectbox("Chart Type",["Candles","Bars","Line","Area","Heikin Ashi"],key="td_cs_type")
                STYLE_MAP={"Candles":"1","Bars":"0","Line":"2","Area":"3","Heikin Ashi":"8"}
                exec_arrows=cs6.toggle("Execution arrows at price level",value=True,key="td_cs_arrows")

            dsym=tv_sym(ticker)
            chart_style_id=STYLE_MAP.get(chart_style,"1")

            tv_html=f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>html,body{{margin:0;padding:0;background:#131722;overflow:hidden}}
.tw{{width:100%;height:555px}}</style></head><body><div class="tw">
<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
{{"autosize":true,"symbol":"{dsym}","interval":"{iv}","timezone":"Asia/Kolkata",
"theme":"dark","style":"{chart_style_id}","locale":"en",
"allow_symbol_change":false,"hide_volume":{str(hide_volume).lower()},
"calendar":{str(show_events).lower()},"hide_top_toolbar":false,
"support_host":"https://www.tradingview.com"}}
</script></div></body></html>"""
            components.html(tv_html,height=570,scrolling=False)

            # Reference strip
            ref='<div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">'
            if entry_p: ref+=chip("ENTRY",f"₹{entry_p:,.2f}",B,"#EFF6FF")
            if sl:      ref+=chip("STOP", f"₹{sl:,.2f}",R,"#FEF2F2")
            if exit_p:  ref+=chip("EXIT", f"₹{exit_p:,.2f}",G,"#F0FDF4")
            ref+=chip("P&L",f"{'+'if pnl>=0 else ''}₹{abs(pnl):,.0f}",pnl_col,f"{pnl_col}15")
            if r_mult:
                try: rv2=float(r_mult); ref+=chip("R-MULT",f"{rv2:+.2f}R",G if rv2>0 else R,f"{'#F0FDF4' if rv2>0 else '#FEF2F2'}")
                except: pass
            if mae: ref+=chip("▼ MAE",f"₹{mae:,.2f}",R,"#FEF2F2")
            if mfe: ref+=chip("▲ MFE",f"₹{mfe:,.2f}",G,"#F0FDF4")
            if best_ep: ref+=chip("★ BEST EXIT",f"₹{best_ep:,.2f}",AM,"#FFFBEB")
            for lv in (st.session_state.get("td_pts") or []):
                if lv.get("price",0)>0: ref+=chip("▲ PT",f"₹{lv['price']:,.2f}",G,"#F0FDF4")
            for lv in (st.session_state.get("td_sls") or []):
                if lv.get("price",0)>0: ref+=chip("▼ SL",f"₹{lv['price']:,.2f}",R,"#FEF2F2")
            ref+='</div>'
            st.markdown(ref,unsafe_allow_html=True)

        with ct2:
            # Templates
            templates=_get_templates()
            if templates:
                st.markdown(f'<div style="font-size:11px;color:{MUTED};margin-bottom:4px">Recently used templates</div>',unsafe_allow_html=True)
                tcols=st.columns(min(len(templates),4))
                for i,tmpl in enumerate(templates[:4]):
                    with tcols[i]:
                        if st.button(tmpl["name"],key=f"td_tmpl_{tmpl['id']}",use_container_width=True):
                            st.session_state[f"td_tn_{trade_id}"]=(trade.get("notes","") or "")+"\n\n"+tmpl["content"]
                            st.rerun()

            nt1,nt2=st.tabs(["Trade note","Daily Journal"])
            with nt1:
                tn=trade.get("notes","") or ""
                new_tn=st.text_area("Trade note",value=st.session_state.get(f"td_tn_{trade_id}",tn),height=200,
                    placeholder="Observations, lessons, analysis...\n\nUse templates above or add your own below.",
                    label_visibility="collapsed",key=f"td_tn_{trade_id}")
                nc1,nc2=st.columns([3,1])
                if nc1.button("💾 Save Trade Note",type="primary",use_container_width=True,key=f"td_tsv_{trade_id}"):
                    _save_trade_field(trade_id,notes=new_tn); st.success("Saved!")
                # Save as template
                with st.expander("＋ Add Template"):
                    tmpl_name=st.text_input("Template name",placeholder="e.g. Daily Report Card, Intraday Check-in",key="td_tmpl_name")
                    tmpl_content=st.text_area("Template content",height=100,key="td_tmpl_content",
                        placeholder="e.g. Setup: \nEntry reason: \nExit reason: \nLesson: ")
                    if st.button("Save Template",key="td_save_tmpl",use_container_width=True):
                        if tmpl_name.strip() and tmpl_content.strip():
                            _save_template(tmpl_name.strip(),tmpl_content.strip()); st.success("Template saved!"); st.rerun()
                    if templates:
                        st.markdown(f'<div style="font-size:11px;color:{MUTED};margin-top:8px">Manage templates</div>',unsafe_allow_html=True)
                        for tmpl in templates:
                            tc1,tc2=st.columns([4,1])
                            tc1.markdown(f'<div style="font-size:11px;color:{TEXT}">{tmpl["name"]}</div>',unsafe_allow_html=True)
                            if tc2.button("🗑",key=f"td_del_tmpl_{tmpl['id']}"):
                                _del_template(tmpl["id"]); st.rerun()

            with nt2:
                dn=_get_note(d_str)
                new_dn=st.text_area("Day note",value=dn,height=200,placeholder="Notes for the entire trading day...",label_visibility="collapsed",key=f"td_dn_{d_str}")
                if st.button("💾 Save Day Note",type="primary",use_container_width=True,key=f"td_dsv_{d_str}"):
                    _save_note(d_str,new_dn); st.success("Saved!")

        with ct3:
            if entry_p and exit_p and qty:
                steps=50
                prices=[entry_p+(exit_p-entry_p)*i/steps for i in range(steps+1)]
                pnls2=[(p-entry_p)*qty if side.upper() in ("LONG","BUY") else (entry_p-p)*qty for p in prices]
                fig_r=go.Figure()
                fig_r.add_trace(go.Scatter(y=pnls2,mode="lines",line=dict(color=pnl_col,width=2),fill="tozeroy",
                    fillcolor=f"rgba(16,185,129,0.1)"if pnl>=0 else"rgba(239,68,68,0.1)",
                    hovertemplate="₹%{y:,.0f}<extra></extra>"))
                if mae and entry_p:
                    mae_pnl=(mae-entry_p)*qty if side.upper() in ("LONG","BUY") else (entry_p-mae)*qty
                    fig_r.add_hline(y=mae_pnl,line=dict(color=R,width=1,dash="dot"),annotation_text=f"MAE ₹{mae:,.2f}",annotation_position="right",annotation_font_color=R)
                if mfe and entry_p:
                    mfe_pnl=(mfe-entry_p)*qty if side.upper() in ("LONG","BUY") else (entry_p-mfe)*qty
                    fig_r.add_hline(y=mfe_pnl,line=dict(color=G,width=1,dash="dot"),annotation_text=f"MFE ₹{mfe:,.2f}",annotation_position="right",annotation_font_color=G)
                fig_r.add_hline(y=0,line=dict(color=BORDER,width=1))
                fig_r.update_layout(height=320,margin=dict(l=70,r=100,t=20,b=40),
                    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=False,color=MUTED,title="Trade progression"),
                    yaxis=dict(showgrid=True,gridcolor=BORDER,color=MUTED,tickprefix="₹"),
                    showlegend=False,title=dict(text="Running P&L",font=dict(size=12,color=MUTED),x=0))
                st.plotly_chart(fig_r,use_container_width=True,config={"displayModeBar":False})
            else:
                st.info("Entry and exit price required for Running P&L chart.")
