import streamlit as st
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from collections import defaultdict
import json as _json
from data.db import (get_all_notes, get_note_by_date, save_note, delete_note,
                     get_journal_trades, get_trade_note, save_trade_note, get_conn)
from theme import *

# ── DB helpers ────────────────────────────────────────────────────────────────
def get_folders():
    try:
        conn = get_conn(); row = conn.execute("SELECT value FROM settings WHERE key='nb_folders'").fetchone(); conn.close()
        return _json.loads(row[0]) if row else []
    except: return []

def save_folders(f):
    conn = get_conn(); conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('nb_folders',?)",(_json.dumps(f),)); conn.commit(); conn.close()

# ── Templates ─────────────────────────────────────────────────────────────────
TEMPLATES = {
    "Daily Game Plan": "🕵️ Pre Market game Plan\nMarket:\nWatchlist:\n\n🕵️ Day Recap\nMistakes I made:\nWhat I did great:\nReinforcement to myself:\n\n🕵️ Overall Recap\nOverall feeling about the day:\nKey lesson:",
    "Daily Game plan & Report Card": "Daily Game plan & Report Card\n\nPrevious Day Summary:\nSymbol 1:\nSymbol 2:\nSymbol 3:\n\nPre-Market Summary:\nSymbol 1:\nSymbol 2:\nSymbol 3:\n\nPre-market Context:\n\nScenarios on the Day:\n\nReminder:\n• Stick to your thesis\n• Be selective in your setups",
    "Weekly Recap": "DATE OF THE WEEK 📅\n\nTHOUGHTS ON PREVIOUS WEEK:\n•\n\nBest/Worst:\nTicker   | Best: ___ | Worst: ___\nSetup    | Best: ___ | Worst: ___\nDuration | Best: ___ | Worst: ___\n\nWHAT DID I DO WELL? 💪\n•\n\nWHAT CAN I REPLICATE? 🔄\n•\n\nWHAT TO IMPROVE? 📈\n•",
    "Weekly Report Card": "Week of:\nTotal trades:  Win rate:  P&L:\n\nBest trade:\nWorst trade:\n\nWhat worked:\n1.\n2.\n3.\n\nNeeds improvement:\n1.\n2.\n3.\n\nFocus next week:",
    "Monthly Report Card": "Overall Monthly Grade:\n\nInstruments Traded:\n\nTop 3 Mistakes:\n1.\n2.\n3.\n\nTop 3 Good Points:\n1.\n2.\n3.\n\nGood Playbook Setups:\nFailed Setups:\nPlan for next month:",
    "Trade Recap: Basic": "TRADE REVIEW: [TICKER] 🔥\n\nOverview:\n•\n•\n\nSetup:\n• Entry:\n• Position Size:\n• Exit:\n• P&L:\n\nWhat went right:\nWhat went wrong:\nWhat I'd do differently:",
    "Strengths & Weaknesses": "MY STRENGTHS & LIMITATIONS 💪\n\nMENTAL\nStrengths:\nLimitations:\n\nTECHNICAL\nStrengths:\nLimitations:\n\nOTHER\nStrengths:\nLimitations:",
    "Quarterly Roadmap": "QUARTERLY ROADMAP 📈\n\nQ GOAL:\nWHY?:\n\nQ1: MENTAL\n1)  2)  3)\n\nQ2: HESITATION\n1)  2)  3)\n\nQ3: ZONES\n1)  2)  3)",
    "Becoming Aware of Emotions": "BECOMING AWARE OF YOUR EMOTIONS 😡\n\nEMOTION | MIND TELLS YOU | HOW YOU ACT\nFear of missing out:\nFear of losing:\nOverconfidence:\nRevenge trading:\nHesitation:\n\nTriggers:\nWhat I'll do:",
    "Emotional Check-in": "How I felt today:\nEnergy (1-10):   Focus (1-10):   Confidence (1-10):\n\nEmotional triggers:\n\nDid emotions affect trading?\n\nWhat I'll do differently:",
}

SYSTEM_FOLDERS = ["All notes", "Trade Notes", "Daily Journal", "Sessions Recap", "Backtesting Session Notes"]

def inject_template(sel, tname, notes_map):
    existing = get_note_by_date(sel)
    prev = existing["content"] if existing else ""
    injected = (prev + "\n\n" if prev else "") + TEMPLATES[tname]
    st.session_state[f"nb_content_{sel}"] = injected
    st.session_state[f"nb_area_{sel}"]    = injected


def render():
    # ── CSS — hide button labels in left panels, style panels ────────────────
    st.markdown("""<style>
    [data-testid="stMainBlockContainer"] { padding-top: 1rem !important; }
    </style>""", unsafe_allow_html=True)

    trades   = get_journal_trades()
    closed   = [t for t in trades if t["status"]=="CLOSED"]
    all_notes= get_all_notes()
    notes_map= {n["note_date"]: n for n in all_notes}
    custom_folders = get_folders()

    daily_pnl    = defaultdict(float)
    daily_trades = defaultdict(list)
    for t in closed:
        d = str(t.get("exit_date","") or "")[:10]
        if d and d!="nan":
            daily_pnl[d]    += float(t.get("pnl") or 0)
            daily_trades[d].append(t)

    all_dates = sorted(set(list(daily_pnl.keys())+list(notes_map.keys())), reverse=True)
    if not all_dates: all_dates = [str(date.today())]

    if "nb_date"   not in st.session_state: st.session_state.nb_date   = all_dates[0]
    if "nb_folder" not in st.session_state: st.session_state.nb_folder = "All notes"

    sel        = st.session_state.nb_date
    sel_folder = st.session_state.nb_folder

    # ── 3-column layout ───────────────────────────────────────────────────────
    col_folders, col_dates, col_note = st.columns([1, 1.4, 3.6])

    # ════════════════════════════════════════════════════════════════════════
    # COL 1 — Folders
    # ════════════════════════════════════════════════════════════════════════
    with col_folders:
        st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
            <span style="font-size:13px;font-weight:700;color:{TEXT_H}">Notebook</span>
        </div>""", unsafe_allow_html=True)

        # Search
        st.text_input("", placeholder="🔍 Search notes…", key="nb_search", label_visibility="collapsed")

        st.markdown(f'<p style="font-size:10px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:10px 0 4px">Folders</p>', unsafe_allow_html=True)

        all_folders = SYSTEM_FOLDERS + custom_folders
        # Deterministic per-folder identity color from the shared DNA_COLORS
        # palette — same folder name always gets the same color.
        _sorted_folders = sorted(all_folders)
        def _folder_color(name):
            idx = _sorted_folders.index(name) if name in _sorted_folders else 0
            return DNA_COLORS[idx % len(DNA_COLORS)]

        for folder in all_folders:
            is_sel_f = sel_folder == folder
            is_sys   = folder in SYSTEM_FOLDERS
            lc = _folder_color(folder)
            bg_f = "rgba(124,58,237,0.09)" if is_sel_f else "transparent"
            fw_f = "600" if is_sel_f else "400"
            tc_f = "#7C3AED" if is_sel_f else TEXT_BODY

            dots = "" if is_sys else f'<span style="font-size:11px;color:{TEXT_SUBTLE}">···</span>'
            st.markdown(
                f'<div style="background:{bg_f};border-radius:7px;padding:5px 8px;margin-bottom:2px;'
                f'display:flex;align-items:center;gap:8px;cursor:pointer">'
                f'<div style="width:4px;height:18px;background:{lc};border-radius:2px;flex-shrink:0"></div>'
                f'<span style="font-size:12.5px;font-weight:{fw_f};color:{tc_f};flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">{folder}</span>'
                f'{dots}'
                f'</div>', unsafe_allow_html=True)
            if st.button(folder, key=f"fld_{folder}", use_container_width=True):
                st.session_state.nb_folder = folder; st.rerun()

        # Add folder
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        if st.button("📁 Add folder", use_container_width=True):
            st.session_state["adding_folder"] = True
        if st.session_state.get("adding_folder"):
            fn = st.text_input("Name", placeholder="Folder name…", key="new_folder_input", label_visibility="collapsed")
            fc1, fc2 = st.columns(2)
            with fc1:
                if st.button("Add", key="add_folder_ok", use_container_width=True):
                    if fn and fn not in custom_folders:
                        custom_folders.append(fn); save_folders(custom_folders)
                    st.session_state["adding_folder"] = False; st.rerun()
            with fc2:
                if st.button("✕", key="add_folder_cancel", use_container_width=True):
                    st.session_state["adding_folder"] = False; st.rerun()

        # Tags
        tags_html = ""
        for d, note in list(notes_map.items())[:50]:
            for tag in (note.get("template") or "").split(","):
                tag = tag.strip()
                if tag and len(tag)<20 and tag not in TEMPLATES:
                    tags_html += f'<span style="display:inline-block;background:{BLUE_BG};color:{BLUE};border:1px solid {BLUE_BORDER};padding:2px 7px;border-radius:10px;font-size:10px;margin:2px 2px 0 0">{tag}</span>'
        if tags_html:
            st.markdown(f'<p style="font-size:10px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.08em;margin:12px 0 4px">Tags</p>', unsafe_allow_html=True)
            st.markdown(tags_html, unsafe_allow_html=True)

        # Recently deleted
        st.markdown(f'<div style="margin-top:16px;font-size:12px;color:{TEXT_SUBTLE}">🗑 Recently deleted</div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════════
    # COL 2 — Date list
    # ════════════════════════════════════════════════════════════════════════
    with col_dates:
        # Filter dates by folder
        if sel_folder == "All notes":           show = all_dates
        elif sel_folder == "Trade Notes":       show = [d for d in all_dates if d in daily_trades]
        elif sel_folder == "Daily Journal":     show = [d for d in all_dates if d in notes_map]
        else:                                   show = [d for d in all_dates if notes_map.get(d,{}).get("template","") == sel_folder]

        srch = st.session_state.get("nb_search","").lower()
        if srch:
            show = [d for d in show if srch in (notes_map.get(d,{}).get("content","") or "").lower() or srch in d]

        # New note button
        if st.button("＋ New note", use_container_width=True, type="primary"):
            st.session_state.nb_date = str(date.today()); st.rerun()

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        for d in show[:60]:
            p        = daily_pnl.get(d, 0)
            has_note = d in notes_map
            is_sel   = (d == sel)
            try:
                d_obj    = datetime.strptime(d, "%Y-%m-%d")
                d_label  = d_obj.strftime("%a, %b %d, %Y")
                d_sub    = d_obj.strftime("%m/%d/%Y")
            except: d_label = d_sub = d

            pnl_col = TEAL if p>0 else RED if p<0 else TEXT_SUBTLE
            pnl_str = f"{'+'if p>0 else ''}₹{p:,.0f}" if p!=0 else "₹0"
            bl  = "3px solid #7C3AED" if is_sel else f"3px solid transparent"
            bg_d = "rgba(124,58,237,0.06)" if is_sel else "transparent"
            tc_d = "#7C3AED" if is_sel else TEXT_BODY
            fw_d = "600" if is_sel else "400"
            dot  = " 🔵" if has_note else ""

            st.markdown(
                f'<div style="background:{bg_d};border-left:{bl};padding:8px 8px 8px 10px;margin-bottom:2px">'
                f'<div style="font-size:12px;font-weight:{fw_d};color:{tc_d}">{d_label}{dot}</div>'
                f'<div style="font-size:10px;color:{TEXT_SUBTLE}">{d_sub}</div>'
                f'</div>', unsafe_allow_html=True)
            if st.button(d_label, key=f"nb_{d}", use_container_width=True):
                st.session_state.nb_date = d; st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # COL 3 — Note editor
    # ════════════════════════════════════════════════════════════════════════
    with col_note:
        try:
            sel_obj   = datetime.strptime(sel, "%Y-%m-%d")
            hdr_label = sel_obj.strftime("%a %b %d, %Y")
        except: hdr_label = sel

        day_p     = daily_pnl.get(sel, 0)
        day_tlist = daily_trades.get(sel, [])
        note      = notes_map.get(sel)

        wins        = sum(1 for t in day_tlist if float(t.get("pnl") or 0)>0)
        losers      = len(day_tlist)-wins
        commissions = sum(float(t.get("commission_entry") or 0)+float(t.get("commission_exit") or 0) for t in day_tlist)
        volume      = sum(int(t.get("qty") or 0) for t in day_tlist)
        gross_pnl   = day_p
        win_rate    = f"{wins/len(day_tlist)*100:.0f}%" if day_tlist else "--"
        pf_den      = sum(abs(float(t.get("pnl") or 0)) for t in day_tlist if float(t.get("pnl") or 0)<0)
        pf_num      = sum(float(t.get("pnl") or 0) for t in day_tlist if float(t.get("pnl") or 0)>0)
        pf_val      = pf_num/pf_den if pf_den else None

        # Header
        pnl_col = TEAL if day_p>=0 else RED
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding-bottom:8px;border-bottom:1px solid {BORDER};margin-bottom:10px">
            <span style="font-size:18px">📅</span>
            <span style="font-size:18px;font-weight:700;color:{TEXT_H}">{hdr_label}</span>
        </div>
        <div style="font-size:15px;font-weight:700;color:{pnl_col};margin-bottom:4px">Net P&L {'+'if day_p>=0 else ''}₹{day_p:,.0f}</div>
        """, unsafe_allow_html=True)

        if note:
            st.markdown(f'<div style="font-size:11px;color:{TEXT_SUBTLE};margin-bottom:10px">Created: {{note.get("created_at","")[:16]}} &nbsp;&nbsp; Last updated: {{note.get("updated_at","")[:16]}}</div>', unsafe_allow_html=True)

        # Chart LEFT + Stats RIGHT
        ch, st_col2 = st.columns([1.6, 1])
        with ch:
            if day_tlist:
                cum=[]; running=0
                for t in day_tlist:
                    running+=float(t.get("pnl") or 0); cum.append(running)
                color = TEAL if day_p>=0 else RED
                ri,gi,bi = int(color[1:3],16),int(color[3:5],16),int(color[5:7],16)
                fig = go.Figure(go.Scatter(x=list(range(len(cum))),y=cum,mode="lines",
                    line=dict(color=color,width=2.5,shape="spline",smoothing=0.3),
                    fill="tozeroy",fillcolor=f"rgba({ri},{gi},{bi},0.10)",
                    showlegend=False,hovertemplate="₹%{y:,.0f}<extra></extra>"))
                fig.add_hline(y=0,line=dict(color=BORDER_LIGHT,width=1))
                l=chart_layout(height=140); l["margin"]=dict(l=60,r=10,t=8,b=25)
                l["xaxis"]["showticklabels"]=False
                l["yaxis"]["tickprefix"]="₹"; l["yaxis"]["tickformat"]=",.0f"
                fig.update_layout(**l)
                st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
            else:
                st.markdown(f'<div style="height:120px;display:flex;align-items:center;justify-content:center;color:{{TEXT_SUBTLE}};font-size:12px;background:{{PAGE_BG}};border-radius:8px;">No Closed NET P&L on this day</div>', unsafe_allow_html=True)

        with st_col2:
            for l1,v1,l2,v2 in [
                ("Total trades",str(len(day_tlist)),"Winners",str(wins)),
                ("Gross P&L",f"₹{gross_pnl:,.0f}","Commissions",f"₹{commissions:,.0f}"),
                ("Winrate",win_rate,"Losers",str(losers)),
                ("Volume",str(volume),"Profit factor",f"{pf_val:.2f}" if pf_val else "--"),
            ]:
                c1,c2 = st.columns(2)
                c1.markdown(f'<div style="margin-bottom:8px"><div style="font-size:10px;color:{BLUE};font-weight:500;margin-bottom:1px">{l1}</div><div style="font-size:13px;font-weight:700;color:{TEXT_H}">{v1}</div></div>', unsafe_allow_html=True)
                c2.markdown(f'<div style="margin-bottom:8px"><div style="font-size:10px;color:{BLUE};font-weight:500;margin-bottom:1px">{l2}</div><div style="font-size:13px;font-weight:700;color:{TEXT_H}">{v2}</div></div>', unsafe_allow_html=True)

        st.markdown(f'<div style="border-top:1px solid {{BORDER}};margin:6px 0 10px"></div>', unsafe_allow_html=True)

        # Recently used templates row
        tpl_names = list(TEMPLATES.keys())
        st.markdown(f'<span style="font-size:11px;color:{{TEXT_MUTED}}">Recently used templates</span>', unsafe_allow_html=True)
        tp_cols = st.columns([1.2,1.5,1.2,1.8])
        for i, tname in enumerate(tpl_names[:3]):
            short = tname[:14]+"…" if len(tname)>14 else tname
            if tp_cols[i].button(short, key=f"tpl_pill_{tname}_{sel}", use_container_width=True):
                inject_template(sel, tname, notes_map); st.rerun()
        if tp_cols[3].button("＋ Add Template", key=f"add_tpl_toggle_{sel}", use_container_width=True):
            st.session_state[f"show_tpl_{sel}"] = not st.session_state.get(f"show_tpl_{sel}", False)

        if st.session_state.get(f"show_tpl_{sel}"):
            dc1, dc2 = st.columns([4,1])
            with dc1:
                chosen = st.selectbox("Template", ["— Pick —"]+tpl_names, key=f"tpl_drop_{sel}", label_visibility="collapsed")
            with dc2:
                if st.button("Use", key=f"tpl_use_{sel}", type="primary", use_container_width=True):
                    if chosen != "— Pick —":
                        inject_template(sel, chosen, notes_map)
                        st.session_state[f"show_tpl_{sel}"] = False; st.rerun()

        # Add tag
        tag = st.text_input("", placeholder="🏷 Add tag…", key=f"tag_{sel}", label_visibility="collapsed")

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # Tabs
        tab_daily, tab_trades = st.tabs(["📓  Daily Journal", "📌  Trade Notes"])

        with tab_daily:
            existing    = get_note_by_date(sel)
            def_content = st.session_state.get(f"nb_content_{sel}", existing["content"] if existing else "")
            def_title   = existing["title"] if existing else f"Journal — {hdr_label}"

            title = st.text_input("Title", value=def_title, placeholder="Note title…",
                label_visibility="collapsed", key=f"nb_title_{sel}")
            content = st.text_area("Journal", value=def_content, height=360,
                label_visibility="collapsed",
                placeholder="Write your morning prep, trade plan, post-session review, emotions, lessons...",
                key=f"nb_area_{sel}")

            b1,b2,b3 = st.columns([3,1,1])
            with b1:
                if existing: st.caption(f"Last saved: {existing.get('updated_at','')[:16]}")
            with b2:
                if existing:
                    if st.button("🗑 Delete", key=f"del_nb_{sel}", use_container_width=True):
                        delete_note(sel)
                        for k in [f"nb_content_{sel}", f"nb_area_{sel}"]:
                            if k in st.session_state: del st.session_state[k]
                        st.success("Deleted"); st.rerun()
            with b3:
                if st.button("Save", type="primary", key=f"save_nb_{sel}", use_container_width=True):
                    save_note(sel, title, content, tag)
                    for k in [f"nb_content_{sel}"]:
                        if k in st.session_state: del st.session_state[k]
                    st.success("✅ Saved!"); st.rerun()

        with tab_trades:
            if not day_tlist:
                st.info("No closed trades on this day.")
            else:
                for t in day_tlist:
                    p   = float(t.get("pnl") or 0)
                    emo = "🟢" if p>0 else "🔴"
                    with st.expander(f"{emo}  {t.get('ticker','')}  ·  {t.get('strategy','')}  ·  {'+'if p>=0 else ''}₹{abs(p):,.0f}", expanded=False):
                        mc1,mc2,mc3,mc4 = st.columns(4)
                        mc1.metric("Entry ₹", f"₹{float(t.get('entry_price') or 0):,.2f}")
                        mc2.metric("Exit ₹",  f"₹{float(t.get('exit_price') or 0):,.2f}" if t.get("exit_price") else "—")
                        mc3.metric("Qty",     str(t.get("qty","—")))
                        mc4.metric("R-Mult",  f"{float(t.get('r_multiple') or 0):.2f}R")
                        tn_ex = get_trade_note(t["id"]) if t.get("id") else None
                        tn = st.text_area("Note", value=tn_ex["note"] if tn_ex else "", height=100,
                            placeholder="Entry thesis, execution quality, emotions, lessons…",
                            label_visibility="collapsed", key=f"tn_{t['id']}")
                        if st.button("Save note", key=f"save_tn_{t['id']}", type="primary"):
                            save_trade_note(t["id"], t.get("ticker",""), tn); st.success("✅ Saved!")
