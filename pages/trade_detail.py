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

def _sb():
    from data.db import _sb as __sb
    return __sb()

def _save_note(d, t):
    try:
        _sb().table("daily_notes").upsert(
            {"note_date": d, "note": t},
            on_conflict="note_date"
        ).execute()
    except Exception as e:
        print(f"_save_note error: {e}")

def _get_note(d):
    try:
        r = _sb().table("daily_notes").select("note").eq("note_date", d).execute()
        return r.data[0]["note"] if r.data else ""
    except: return ""

def _get_executions(tid):
    try:
        r = _sb().table("trade_executions").select("*").eq("trade_id", tid).order("exec_date").order("exec_time").execute()
        return r.data or []
    except: return []

def _save_execution(tid, ed, et, price, qty, side, fee, comm, swap, notes):
    try:
        _sb().table("trade_executions").insert({
            "trade_id": tid, "exec_date": ed, "exec_time": et,
            "price": price, "qty": qty, "side": side,
            "fee": fee, "commission": comm, "swap": swap, "notes": notes
        }).execute()
    except Exception as e:
        print(f"_save_execution error: {e}")

def _del_execution(eid):
    try: _sb().table("trade_executions").delete().eq("id", eid).execute()
    except Exception as e: print(f"_del_execution error: {e}")

def _get_attachments(tid):
    try:
        r = _sb().table("trade_attachments").select("*").eq("trade_id", tid).order("created_at").execute()
        return r.data or []
    except: return []

def _save_attachment(tid, fn, fp, ft):
    try:
        _sb().table("trade_attachments").insert({
            "trade_id": tid, "filename": fn, "filepath": fp, "filetype": ft
        }).execute()
    except Exception as e:
        print(f"_save_attachment error: {e}")

def _del_attachment(aid, fp):
    try:
        _sb().table("trade_attachments").delete().eq("id", aid).execute()
        if os.path.exists(fp): os.remove(fp)
    except Exception as e:
        print(f"_del_attachment error: {e}")

def _get_pt_sl(tid):
    try:
        r = _sb().table("trade_pt_sl").select("*").eq("trade_id", tid).order("level_type").order("sort_order").execute()
        return r.data or []
    except: return []

def _save_pt_sl(tid, levels):
    try:
        _sb().table("trade_pt_sl").delete().eq("trade_id", tid).execute()
        for i, lv in enumerate(levels):
            _sb().table("trade_pt_sl").insert({
                "trade_id": tid, "level_type": lv["type"],
                "price": lv["price"], "qty": lv["qty"], "sort_order": i
            }).execute()
        pts = [l for l in levels if l["type"] == "PT" and l["price"] > 0]
        sls = [l for l in levels if l["type"] == "SL" and l["price"] > 0]
        from data.db import update_trade
        if pts: update_trade(tid, {"take_profit": pts[0]["price"]})
        if sls: update_trade(tid, {"stop_loss": sls[0]["price"]})
    except Exception as e:
        print(f"_save_pt_sl error: {e}")

def _get_templates():
    try:
        r = _sb().table("note_templates").select("*").order("used_at", desc=True).limit(10).execute()
        return r.data or []
    except: return []

def _save_template(name, content):
    try:
        _sb().table("note_templates").insert({"name": name, "content": content}).execute()
    except Exception as e:
        print(f"_save_template error: {e}")

def _del_template(tid2):
    try: _sb().table("note_templates").delete().eq("id", tid2).execute()
    except Exception as e: print(f"_del_template error: {e}")

def _save_trade_field(tid, **kwargs):
    from data.db import update_trade
    try: update_trade(tid, kwargs)
    except Exception as e: print(f"_save_trade_field error: {e}")

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

            # Full trade editor
            with st.expander("✏️ Edit Trade Fields"):
                st.markdown(f'<p style="font-size:10px;color:{MUTED};margin-bottom:8px">All fields editable. Click Save after changes.</p>', unsafe_allow_html=True)

                # ── Dates ─────────────────────────────────────────────
                st.markdown(f'<div style="font-size:10px;font-weight:700;color:{MUTED};letter-spacing:1px;margin:4px 0">DATES</div>', unsafe_allow_html=True)
                from datetime import date as _date
                def _parse_date(v):
                    for fmt in ["%Y-%m-%d","%d/%m/%y","%d/%m/%Y","%Y-%m-%dT%H:%M:%S"]:
                        try: return datetime.strptime(str(v)[:10],fmt).date()
                        except: pass
                    return _date.today()
                ed1,ed2=st.columns(2)
                new_entry_date=ed1.date_input("Entry Date",value=_parse_date(trade.get("entry_date")),key="td_entry_date")
                new_exit_date=ed2.date_input("Exit Date",value=_parse_date(trade.get("exit_date") or trade.get("entry_date")),key="td_exit_date")

                # ── Prices & Qty ──────────────────────────────────────
                st.markdown(f'<div style="font-size:10px;font-weight:700;color:{MUTED};letter-spacing:1px;margin:8px 0 4px">PRICES & QTY</div>', unsafe_allow_html=True)
                ep1,ep2,ep3=st.columns(3)
                new_entry_price=ep1.number_input("Entry Price ₹",value=float(trade.get("entry_price") or 0),step=0.05,format="%.2f",key="td_entry_price")
                new_exit_price=ep2.number_input("Exit Price ₹",value=float(trade.get("exit_price") or 0),step=0.05,format="%.2f",key="td_exit_price")
                new_qty=ep3.number_input("Qty",value=int(trade.get("qty") or 0),step=1,key="td_qty")
                ep4,ep5=st.columns(2)
                new_pnl=ep4.number_input("Net P&L ₹",value=float(trade.get("pnl") or 0),step=1.0,format="%.2f",key="td_pnl")
                new_sl=ep5.number_input("Stop Loss ₹",value=float(trade.get("stop_loss") or 0),step=0.05,format="%.2f",key="td_sl_edit")

                # ── Trade Meta ────────────────────────────────────────
                st.markdown(f'<div style="font-size:10px;font-weight:700;color:{MUTED};letter-spacing:1px;margin:8px 0 4px">TRADE META</div>', unsafe_allow_html=True)
                tm1,tm2=st.columns(2)
                STRATEGIES=["VCP","REVERSAL","SVRO","EP","NR 1HR","TS","MARS","Other"]
                cur_strat=trade.get("strategy","") or ""
                strat_idx=STRATEGIES.index(cur_strat) if cur_strat in STRATEGIES else 0
                new_strategy=tm1.selectbox("Strategy",STRATEGIES,index=strat_idx,key="td_strategy_edit")
                SIDES=["LONG","SHORT"]
                cur_side=str(trade.get("side","") or trade.get("direction","") or "LONG").upper()
                side_idx=SIDES.index(cur_side) if cur_side in SIDES else 0
                new_side=tm2.selectbox("Side",SIDES,index=side_idx,key="td_side_edit")
                tm3,tm4=st.columns(2)
                new_rmult=tm3.number_input("R-Multiple",value=float(trade.get("r_multiple") or 0),step=0.01,format="%.2f",key="td_rmult_edit")
                STATUSES=["CLOSED","OPEN"]
                cur_status=trade.get("status","CLOSED")
                new_status=tm4.selectbox("Status",STATUSES,index=STATUSES.index(cur_status) if cur_status in STATUSES else 0,key="td_status_edit")

                # ── Funding ───────────────────────────────────────────
                st.markdown(f'<div style="font-size:10px;font-weight:700;color:{MUTED};letter-spacing:1px;margin:8px 0 4px">FUNDING</div>', unsafe_allow_html=True)
                fm1,fm2=st.columns(2)
                FUNDING=["CASH","MTF"]
                cur_fund=str(trade.get("funding_type","CASH") or "CASH").upper()
                new_funding=fm1.selectbox("Funding Type",FUNDING,index=FUNDING.index(cur_fund) if cur_fund in FUNDING else 0,key="td_funding_edit")
                new_mtf_margin=fm2.number_input("MTF Margin %",value=float(trade.get("mtf_margin_pct") or 50.0),min_value=1.0,max_value=100.0,step=0.5,format="%.1f",key="td_mtf_margin_edit")

                # ── Open/Close/Best Exit ──────────────────────────────
                st.markdown(f'<div style="font-size:10px;font-weight:700;color:{MUTED};letter-spacing:1px;margin:8px 0 4px">TIMES & BEST EXIT</div>', unsafe_allow_html=True)
                e1,e2=st.columns(2)
                new_ot=e1.text_input("Open Time",value=open_t,key="td_ot",placeholder="2026-04-01 09:15")
                new_ct=e2.text_input("Close Time",value=close_t,key="td_ct",placeholder="2026-04-01 15:20")
                new_bep=e1.number_input("Best Exit ₹",value=best_ep,step=0.5,key="td_bep",format="%.2f")
                new_bet=e2.text_input("Best Exit Time",value=best_et,key="td_bet",placeholder="2026-04-01 10:30")

                if st.button("💾 Save All Changes",key="td_save_all",use_container_width=True,type="primary"):
                    _save_trade_field(trade_id,
                        entry_date=str(new_entry_date),
                        exit_date=str(new_exit_date),
                        entry_price=new_entry_price,
                        exit_price=new_exit_price,
                        qty=new_qty,
                        pnl=new_pnl,
                        stop_loss=new_sl,
                        strategy=new_strategy,
                        side=new_side,
                        r_multiple=new_rmult,
                        status=new_status,
                        funding_type=new_funding,
                        mtf_margin_pct=new_mtf_margin,
                        open_time=new_ot,
                        close_time=new_ct,
                        best_exit_price=new_bep,
                        best_exit_time=new_bet,
                    )
                    st.success("✅ Trade updated!"); st.rerun()

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

            # Colored setup chips — deterministic DNA_COLORS identity per setup name
            if new_setup:
                _sorted_setups = sorted(SETUP_OPTS)
                def _setup_color(name):
                    idx = _sorted_setups.index(name) if name in _sorted_setups else 0
                    return DNA_COLORS[idx % len(DNA_COLORS)]
                _chips_html = '<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:6px">'
                for _s in new_setup:
                    _c = _setup_color(_s)
                    _chips_html += f'<span style="background:{_c}1A;color:{_c};border:1px solid {_c}44;padding:2px 9px;border-radius:12px;font-size:11px;font-weight:600">{_s}</span>'
                _chips_html += '</div>'
                st.markdown(_chips_html, unsafe_allow_html=True)

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

            # Entry Type tags
            st.markdown(f'<div style="font-size:11px;font-weight:600;color:{TEXT};margin:8px 0 4px">Entry Type</div>',unsafe_allow_html=True)
            ENTRY_TYPE_OPTS=["Breakout","Pullback","Gap Up","Gap Down","ORB","Pyramid Add","Retest Entry","Limit Order","Market Order"]
            cur_entry_type=(trade.get("entry_type","") or "").split(",") if trade.get("entry_type") else []
            new_entry_type=st.multiselect("Entry Type",ENTRY_TYPE_OPTS,default=[e for e in cur_entry_type if e in ENTRY_TYPE_OPTS],label_visibility="collapsed",key="td_entry_type")
            new_entry_type_txt=st.text_input("Custom entry type",placeholder="Add custom entry type...",key="td_entry_type_custom")
            if new_entry_type_txt and st.button("＋ Add",key="td_add_entry_type"):
                combined=",".join(new_entry_type+[new_entry_type_txt])
                _save_trade_field(trade_id,entry_type=combined); st.rerun()
            elif new_entry_type!=cur_entry_type:
                _save_trade_field(trade_id,entry_type=",".join(new_entry_type)); st.rerun()

            # Exit Trigger tags
            st.markdown(f'<div style="font-size:11px;font-weight:600;color:{TEXT};margin:8px 0 4px">Exit Trigger</div>',unsafe_allow_html=True)
            EXIT_TRIGGER_OPTS=["Stop Loss Hit","Target Hit","Trailing Stop","Time Exit","Technical Breakdown","Partial Scale-Out","Manual Exit","Reversal Signal"]
            cur_exit_trigger=(trade.get("exit_trigger","") or "").split(",") if trade.get("exit_trigger") else []
            new_exit_trigger=st.multiselect("Exit Trigger",EXIT_TRIGGER_OPTS,default=[e for e in cur_exit_trigger if e in EXIT_TRIGGER_OPTS],label_visibility="collapsed",key="td_exit_trigger")
            new_exit_trigger_txt=st.text_input("Custom exit trigger",placeholder="Add custom exit trigger...",key="td_exit_trigger_custom")
            if new_exit_trigger_txt and st.button("＋ Add",key="td_add_exit_trigger"):
                combined=",".join(new_exit_trigger+[new_exit_trigger_txt])
                _save_trade_field(trade_id,exit_trigger=combined); st.rerun()
            elif new_exit_trigger!=cur_exit_trigger:
                _save_trade_field(trade_id,exit_trigger=",".join(new_exit_trigger)); st.rerun()

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
            iv=st.selectbox("Timeframe", ["Daily","Weekly","1H","30m","15m","5m"],
                index=0, label_visibility="collapsed", key=f"td_iv_{trade_id}")

            # ── Plotly Candlestick with trade markers ─────────────────
            try:
                import yfinance as yf
                import pandas as pd
                from datetime import datetime, timedelta

                def _tv_to_yf(t):
                    for px in ["BSE:","NSE:","NSE_EQ:"]: t = t.replace(px,"")
                    return {"NIFTY50":"^NSEI","BANKNIFTY":"^NSEBANK"}.get(t, f"{t}.NS")

                yft = _tv_to_yf(ticker)
                # Date range: 20 bars before entry, 20 bars after exit
                try:
                    ed = datetime.strptime(str(trade.get("entry_date",""))[:10],"%Y-%m-%d")
                    xd = datetime.strptime(str(trade.get("exit_date","") or trade.get("entry_date",""))[:10],"%Y-%m-%d")
                except:
                    ed = xd = datetime.today()

                iv_map = {"Daily":"1d","Weekly":"1wk","Monthly":"1mo","1H":"1h","15m":"15m","5m":"5m","30m":"30m"}
                yf_interval = iv_map.get(iv, "1d")
                days_held = (xd - ed).days

                if yf_interval in ("15m","30m","1h"):
                    start = (ed - timedelta(days=10)).strftime("%Y-%m-%d")
                    end   = (xd + timedelta(days=5)).strftime("%Y-%m-%d")
                else:
                    start = (ed - timedelta(days=40)).strftime("%Y-%m-%d")
                    end   = (xd + timedelta(days=30)).strftime("%Y-%m-%d")

                df = yf.download(yft, start=start, end=end, interval=yf_interval,
                                 progress=False, auto_adjust=True)
                if df.empty:
                    bse = _tv_to_yf(ticker).replace(".NS",".BO")
                    df = yf.download(bse, start=start, end=end, interval=yf_interval,
                                     progress=False, auto_adjust=True)

                if not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    df = df.reset_index()
                    date_col = "Datetime" if "Datetime" in df.columns else "Date"
                    df[date_col] = pd.to_datetime(df[date_col])
                    xs = df[date_col].dt.strftime("%d %b") if yf_interval=="1d" else df[date_col].dt.strftime("%d %b %H:%M")

                    fig_c = go.Figure()

                    # Candlesticks
                    fig_c.add_trace(go.Candlestick(
                        x=xs, open=df["Open"], high=df["High"],
                        low=df["Low"], close=df["Close"],
                        increasing=dict(line=dict(color="#10B981",width=1), fillcolor="#10B981"),
                        decreasing=dict(line=dict(color="#EF4444",width=1), fillcolor="#EF4444"),
                        name="Price", showlegend=False,
                        whiskerwidth=0.5))

                    # Volume bars (on secondary y-axis)
                    if "Volume" in df.columns:
                        vol_colors = ["rgba(16,185,129,0.35)" if c >= o else "rgba(239,68,68,0.35)"
                                     for c, o in zip(df["Close"], df["Open"])]
                        fig_c.add_trace(go.Bar(
                            x=xs, y=df["Volume"],
                            marker_color=vol_colors,
                            name="Volume", showlegend=False,
                            yaxis="y2", opacity=0.8))

                    # MAE dotted red horizontal line
                    if mae:
                        fig_c.add_hline(y=mae,
                            line=dict(color="#EF4444", width=1.5, dash="dot"),
                            annotation_text=f"▼ MAE  ₹{mae:,.2f}",
                            annotation_position="top left",
                            annotation_font=dict(color="#EF4444", size=10, family="Inter"),
                            annotation_bgcolor="rgba(254,226,226,0.9)",
                            annotation_bordercolor="#EF4444",
                            annotation_borderwidth=1,
                            annotation_borderpad=4)

                    # MFE dotted teal horizontal line
                    if mfe:
                        fig_c.add_hline(y=mfe,
                            line=dict(color="#0D9488", width=1.5, dash="dot"),
                            annotation_text=f"▲ MFE  ₹{mfe:,.2f}",
                            annotation_position="top left",
                            annotation_font=dict(color="#0D9488", size=10, family="Inter"),
                            annotation_bgcolor="rgba(209,250,229,0.9)",
                            annotation_bordercolor="#0D9488",
                            annotation_borderwidth=1,
                            annotation_borderpad=4)

                    # Stop Loss dashed line
                    if sl:
                        fig_c.add_hline(y=sl,
                            line=dict(color="#EF4444", width=1, dash="dash"),
                            annotation_text=f"SL ₹{sl:,.2f}",
                            annotation_position="right",
                            annotation_font=dict(color="#EF4444", size=9),
                            annotation_bgcolor="rgba(254,226,226,0.8)")

                    # Find closest x label to entry/exit dates
                    date_strs = xs.tolist()
                    entry_date_str = ed.strftime("%d %b")
                    exit_date_str  = xd.strftime("%d %b")

                    # Find nearest matching label
                    def _nearest(target, labels):
                        if target in labels: return target
                        # find closest
                        for l in labels:
                            if target[:2] in l and target[3:] in l: return l
                        return labels[-1] if labels else target

                    entry_x = _nearest(entry_date_str, date_strs)
                    exit_x  = _nearest(exit_date_str,  date_strs)

                    # Entry arrow — label to the LEFT of entry candle
                    if entry_p:
                        fig_c.add_annotation(
                            x=entry_x, y=entry_p,
                            text=f"▲ Open @ ₹{entry_p:,.2f}",
                            showarrow=True, arrowhead=2,
                            arrowcolor="#1D4ED8", arrowsize=1.2, arrowwidth=1.5,
                            ax=-80, ay=0,
                            font=dict(color="#1D4ED8", size=10, family="Inter"),
                            bgcolor="rgba(219,234,254,0.95)",
                            bordercolor="#1D4ED8", borderwidth=1, borderpad=4,
                            xanchor="right")

                    # Exit arrow — label to the RIGHT of exit candle
                    if exit_p:
                        fig_c.add_annotation(
                            x=exit_x, y=exit_p,
                            text=f"▼ Close @ ₹{exit_p:,.2f}",
                            showarrow=True, arrowhead=2,
                            arrowcolor="#DC2626", arrowsize=1.2, arrowwidth=1.5,
                            ax=80, ay=0,
                            font=dict(color="#DC2626", size=10, family="Inter"),
                            bgcolor="rgba(254,226,226,0.95)",
                            bordercolor="#DC2626", borderwidth=1, borderpad=4,
                            xanchor="left")

                    # Best Exit arrow — above, offset up
                    if best_ep:
                        fig_c.add_annotation(
                            x=exit_x, y=best_ep,
                            text="★ Best Exit",
                            showarrow=True, arrowhead=2,
                            arrowcolor="#F59E0B", arrowsize=1.2, arrowwidth=1.5,
                            ax=0, ay=-45,
                            font=dict(color="#B45309", size=10, family="Inter"),
                            bgcolor="rgba(254,243,199,0.95)",
                            bordercolor="#F59E0B", borderwidth=1, borderpad=4,
                            xanchor="center")

                    # Y axis range — focus on trade area with padding
                    prices = [p for p in [entry_p, exit_p, sl, mae, mfe] if p]
                    if prices:
                        y_min = min(prices) * 0.97
                        y_max = max(prices) * 1.05
                        # Also consider candle data in range
                        entry_idx = date_strs.index(entry_x) if entry_x in date_strs else 0
                        exit_idx  = date_strs.index(exit_x)  if exit_x  in date_strs else len(date_strs)-1
                        pad = max(5, (exit_idx - entry_idx))
                        show_from = max(0, entry_idx - pad)
                        show_to   = min(len(date_strs)-1, exit_idx + pad)
                        x_range = [date_strs[show_from], date_strs[show_to]]
                    else:
                        x_range = None
                        y_min = y_max = None

                    # Layout
                    fig_c.update_layout(
                        height=520,
                        paper_bgcolor="#FFFFFF",
                        plot_bgcolor="#FAFAFA",
                        xaxis=dict(
                            rangeslider=dict(visible=False),
                            gridcolor="#F1F5F9",
                            showgrid=True,
                            tickfont=dict(size=10, color="#94A3B8"),
                            type="category",
                            range=x_range,
                            tickangle=0),
                        yaxis=dict(
                            gridcolor="#F1F5F9",
                            showgrid=True,
                            tickfont=dict(size=10, color="#94A3B8"),
                            tickprefix="₹",
                            side="right",
                            domain=[0.22, 1.0],
                            range=[y_min, y_max] if y_min else None),
                        yaxis2=dict(
                            domain=[0, 0.18],
                            showgrid=False,
                            showticklabels=False),
                        margin=dict(l=10, r=90, t=20, b=40),
                        showlegend=False,
                        hovermode="x unified")

                    st.plotly_chart(fig_c, use_container_width=True,
                                   config={"displayModeBar":False},
                                   key=f"trade_candle_{trade_id}")
                else:
                    st.info(f"No price data available for {ticker}.")
            except Exception as _ce:
                st.warning(f"Chart error: {_ce}")

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
