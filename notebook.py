import streamlit as st
from datetime import date, datetime
from collections import defaultdict
from data.db import (get_all_notes, get_note_by_date, save_note, delete_note,
                     get_journal_trades, get_trade_note, save_trade_note, get_conn)
import json as _json

# ── Folder helpers ────────────────────────────────────────────────────────────
SYSTEM_FOLDERS = ["All notes", "Trade Notes", "Daily Journal", "Sessions Recap", "Backtesting Session Notes"]

def get_folders():
    try:
        conn = get_conn()
        row = conn.execute("SELECT value FROM settings WHERE key='nb_folders'").fetchone()
        conn.close()
        if row: return _json.loads(row[0])
    except: pass
    return []

def save_folders(folders):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('nb_folders',?)", (_json.dumps(folders),))
    conn.commit(); conn.close()

def get_tags():
    try:
        conn = get_conn()
        row = conn.execute("SELECT value FROM settings WHERE key='nb_tags'").fetchone()
        conn.close()
        if row: return _json.loads(row[0])
    except: pass
    return {}

def save_tags(tags):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('nb_tags',?)", (_json.dumps(tags),))
    conn.commit(); conn.close()
from theme import *

TEMPLATES = {
    "Daily Game Plan": """🕵️ Pre Market game Plan
Market:
Watchlist:

🕵️ Day Recap
Mistakes I made:
What I did great:
Reinforcement to myself:

🕵️ Overall Recap
Overall feeling about the day:
Key lesson:""",

    "Daily Game plan & Report Card": """Daily Game plan & Report Card

Previous Day Summary:
Symbol 1:
Symbol 2:
Symbol 3:

Pre-Market Summary:
Symbol 1:
Symbol 2:
Symbol 3:

Pre-market Context:

Scenarios on the Day:

Reminder on the Day:
• Stick to your thesis and focus on the high probability trades
• Be selective in your setups""",

    "Weekly Recap": """DATE OF THE WEEK 📅

THOUGHTS ON PREVIOUS WEEK:
• Text goes here

Best / Worst:
Ticker   | Best: ___ | Worst: ___
Setup    | Best: ___ | Worst: ___
Duration | Best: ___ | Worst: ___

WHAT DID I DO WELL LAST WEEK? 💪
•

WHAT CAN I REPLICATE THIS UPCOMING WEEK? 🔄
•

WHAT DO I NEED TO IMPROVE? 📈
•""",

    "Weekly Report Card": """Week of:
Total trades:  Win rate:  P&L:

Best trade:
Worst trade:

What worked this week:
1.
2.
3.

What needs improvement:
1.
2.
3.

Focus for next week:""",

    "Monthly Report Card": """Overall Monthly Performance Grade:

Instruments Traded:

Top 3 Mistakes of the month:
1.
2.
3.

Top 3 good points of the month:
1.
2.
3.

Good Playbook Setups:
Failed Setups:
Plan for next month:""",

    "Trade Recap: Basic": """TRADE REVIEW: [TICKER] 🔥

Overview:
•
•

Setup Details:
• Entry:
• Position Size:
• Exit:
• Profit/Loss:

What went right:
What went wrong:
What would I do differently:""",

    "Strengths & Weaknesses": """MY CURRENT STRENGTHS & LIMITATIONS 💪

MENTAL
Strengths:
Limitations:

TECHNICAL
Strengths:
Limitations:

OTHER
Strengths:
Limitations:""",

    "Quarterly Roadmap": """QUARTERLY ROADMAP 📈

Q GOAL:
WHY?:

Q1: MENTAL
1)  2)  3)

Q2: HESITATION
1)  2)  3)

Q3: ZONES
1)  2)  3)

Q4: N/A
1)""",

    "Becoming Aware of Emotions": """BECOMING AWARE OF YOUR EMOTIONS 😡

EMOTION | WHAT YOUR MIND TELLS YOU | HOW YOU ACT

Fear of missing out:  |  |
Fear of losing:       |  |
Overconfidence:       |  |
Revenge trading:      |  |
Hesitation:           |  |

What triggers these emotions:
What I will do when I notice them:""",

    "Emotional Check-in": """How I felt today:
Energy (1-10):   Focus (1-10):   Confidence (1-10):

Emotional triggers I noticed:

Did emotions affect my trading?

What I'll do differently:""",
}


def render():
    st.markdown("## Notebook")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:14px;font-size:11px">FY 2026-27 · Daily journal & trade notes</p>', unsafe_allow_html=True)

    trades   = get_journal_trades()
    closed   = [t for t in trades if t["status"] == "CLOSED"]

    # Daily P&L map
    daily_pnl    = defaultdict(float)
    daily_trades = defaultdict(list)
    for t in closed:
        d = str(t.get("exit_date","") or "")[:10]
        if d and d != "nan":
            daily_pnl[d]    += float(t.get("pnl") or 0)
            daily_trades[d].append(t)

    all_notes  = get_all_notes()
    notes_map  = {n["note_date"]: n for n in all_notes}

    # All dates (trading days + note days)
    all_dates = sorted(
        set(list(daily_pnl.keys()) + list(notes_map.keys())),
        reverse=True
    )
    if not all_dates:
        all_dates = [str(date.today())]

    if "nb_date" not in st.session_state:
        st.session_state.nb_date = all_dates[0]

    # ── Layout ────────────────────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 3])

    # ── LEFT — folders + date list ──────────────────────────────────────────
    with left_col:
        custom_folders = get_folders()
        tags_map       = get_tags()

        if "nb_folder" not in st.session_state:
            st.session_state.nb_folder = "All notes"

        search = st.text_input("", placeholder="🔍 Search notes…", label_visibility="collapsed")

        ac1, ac2 = st.columns([2,1])
        with ac1:
            if st.button("📁 Add folder", use_container_width=True):
                st.session_state["adding_folder"] = True
        with ac2:
            if st.button("＋ Note", use_container_width=True, type="primary"):
                st.session_state.nb_date = str(date.today())
                st.rerun()

        if st.session_state.get("adding_folder"):
            fn = st.text_input("Folder name", placeholder="e.g. Weekly Plan", key="new_folder_name")
            fc1, fc2 = st.columns(2)
            with fc1:
                if fc1.button("Add", use_container_width=True):
                    if fn and fn not in custom_folders:
                        custom_folders.append(fn)
                        save_folders(custom_folders)
                    st.session_state["adding_folder"] = False
                    st.rerun()
            with fc2:
                if fc2.button("Cancel", use_container_width=True):
                    st.session_state["adding_folder"] = False
                    st.rerun()

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px">Folders</p>', unsafe_allow_html=True)

        SYSTEM_FOLDERS_LOCAL = ["All notes","Trade Notes","Daily Journal","Sessions Recap","Backtesting Session Notes"]
        all_folders = SYSTEM_FOLDERS_LOCAL + custom_folders
        FOLDER_COLOR = "#7C3AED"

        for folder in all_folders:
            is_sel_f = st.session_state.nb_folder == folder
            bg_f   = "rgba(124,58,237,0.08)" if is_sel_f else "transparent"
            fw_f   = "600" if is_sel_f else "400"
            tc_f   = "#7C3AED" if is_sel_f else TEXT_BODY
            is_sys = folder in SYSTEM_FOLDERS_LOCAL
            dots   = "" if is_sys else "···"

            st.markdown(
                f'<div style="background:{bg_f};border-radius:6px;padding:5px 6px;margin-bottom:2px;'
                f'display:flex;align-items:center;gap:8px">'
                f'<div style="width:4px;height:18px;background:{FOLDER_COLOR};border-radius:2px;flex-shrink:0"></div>'
                f'<span style="font-size:12.5px;font-weight:{fw_f};color:{tc_f};flex:1">{folder}</span>'
                f'<span style="font-size:10px;color:{TEXT_SUBTLE}">{dots}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button(folder, key=f"folder_{folder}", use_container_width=True):
                st.session_state.nb_folder = folder
                st.rerun()

        # Tags section
        st.markdown(f'<p style="font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.08em;margin:10px 0 4px">Tags</p>', unsafe_allow_html=True)
        all_tags = {}
        for d, note in notes_map.items():
            for tag in (note.get("template") or "").split(","):
                tag = tag.strip()
                if tag and len(tag)<20: all_tags[tag] = all_tags.get(tag,0)+1
        tag_html = ""
        for tag, cnt in list(all_tags.items())[:8]:
            tag_html += (f'<span style="display:inline-block;background:{BLUE_BG};color:{BLUE};'
                f'border:1px solid {BLUE_BORDER};padding:2px 8px;border-radius:12px;'
                f'font-size:10px;margin:2px 2px 0 0">{tag} {cnt}</span>')
        if tag_html:
            st.markdown(tag_html, unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Date list filtered by folder
        sel_folder = st.session_state.nb_folder
        if sel_folder == "All notes":           show_dates = all_dates
        elif sel_folder == "Trade Notes":       show_dates = [d for d in all_dates if d in daily_trades]
        elif sel_folder == "Daily Journal":     show_dates = [d for d in all_dates if d in notes_map]
        else:                                   show_dates = [d for d in all_dates if notes_map.get(d,{}).get("template","") == sel_folder]

        filtered = [d for d in show_dates
                    if not search or search.lower() in (notes_map.get(d,{}).get("content","") or "").lower()
                    or search.lower() in d]

        for d in filtered[:50]:
            p        = daily_pnl.get(d, 0)
            has_note = d in notes_map
            is_sel   = (d == st.session_state.nb_date)
            try:
                d_obj   = datetime.strptime(d, "%Y-%m-%d")
                d_short = d_obj.strftime("%a, %b %d, %Y")
                d_sub   = d_obj.strftime("%m/%d/%Y")
            except: d_short = d_sub = d

            pnl_col = TEAL if p>0 else RED if p<0 else TEXT_SUBTLE
            pnl_str = (f"+{p:,.0f}" if p>0 else f"{p:,.0f}") if p!=0 else "₹0"
            bl = "3px solid #7C3AED" if is_sel else "3px solid transparent"
            bg_d = "rgba(124,58,237,0.06)" if is_sel else "transparent"
            tc_d = "#7C3AED" if is_sel else TEXT_BODY

            st.markdown(
                f'<div style="background:{bg_d};border-left:{bl};padding:8px 6px;margin-bottom:2px">'
                f'<div style="font-size:12px;font-weight:{"600" if is_sel else "400"};color:{tc_d}">'
                f'{d_short}{"  🔵" if has_note else ""}</div>'
                f'<div style="font-size:10px;color:{TEXT_SUBTLE};margin-top:1px">{d_sub}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button(d_short, key=f"nb_{d}", use_container_width=True):
                st.session_state.nb_date = d
                st.rerun()

    # ── RIGHT — note editor ───────────────────────────────────────────────────
    with right_col:
        sel   = st.session_state.nb_date
        note  = notes_map.get(sel)

        try:
            sel_obj   = datetime.strptime(sel, "%Y-%m-%d")
            hdr_label = sel_obj.strftime("%a %b %d, %Y")
        except:
            hdr_label = sel

        day_p      = daily_pnl.get(sel, 0)
        day_tlist  = daily_trades.get(sel, [])
        wins       = sum(1 for t in day_tlist if float(t.get("pnl") or 0) > 0)
        losers     = len(day_tlist) - wins
        commissions= sum(float(t.get("commission_entry") or 0) + float(t.get("commission_exit") or 0) for t in day_tlist)
        volume     = sum(int(t.get("qty") or 0) for t in day_tlist)
        gross_pnl  = sum(float(t.get("pnl") or 0) for t in day_tlist)
        win_rate   = f"{wins/len(day_tlist)*100:.0f}%" if day_tlist else "--"
        pf_val     = abs(sum(float(t.get("pnl") or 0) for t in day_tlist if float(t.get("pnl") or 0)>0) /
                     sum(float(t.get("pnl") or 0) for t in day_tlist if float(t.get("pnl") or 0)<0)) \
                     if any(float(t.get("pnl") or 0)<0 for t in day_tlist) else None

        # ── Header row ────────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding-bottom:10px;border-bottom:1px solid {BORDER};margin-bottom:12px">
            <span style="font-size:18px">📅</span>
            <span style="font-size:18px;font-weight:700;color:{TEXT_H}">{hdr_label}</span>
        </div>
        <div style="font-size:15px;font-weight:700;color:{TEXT_H};margin-bottom:4px">Net P&L <span style="color:{TEAL if day_p>=0 else RED}">{'+'if day_p>=0 else ''}₹{day_p:,.0f}</span></div>
        """, unsafe_allow_html=True)

        if note:
            st.markdown(f'<div style="font-size:11px;color:{TEXT_SUBTLE};margin-bottom:12px">Created: {note.get("created_at","")[:16]}  &nbsp;&nbsp; Last updated: {note.get("updated_at","")[:16]}</div>', unsafe_allow_html=True)

        # ── Chart LEFT + Stats RIGHT ──────────────────────────────────────────
        import plotly.graph_objects as go
        chart_col, stat_col = st.columns([1.6, 1])
        with chart_col:
            if day_tlist:
                cum = []; running = 0
                for t in day_tlist:
                    running += float(t.get("pnl") or 0)
                    cum.append(running)
                color = TEAL if day_p >= 0 else RED
                fig = go.Figure(go.Scatter(
                    x=list(range(len(cum))), y=cum, mode="lines",
                    line=dict(color=color, width=2.5, shape="spline"),
                    fill="tozeroy",
                    fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.1)",
                    showlegend=False,
                    hovertemplate="₹%{y:,.0f}<extra></extra>"))
                fig.add_hline(y=0, line=dict(color=BORDER_LIGHT, width=1))
                l = chart_layout(height=160)
                l["margin"] = dict(l=60, r=10, t=8, b=30)
                l["xaxis"]["showticklabels"] = False
                l["yaxis"]["tickprefix"] = "₹"; l["yaxis"]["tickformat"] = ",.0f"
                fig.update_layout(**l)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.markdown(f'<div style="height:160px;display:flex;align-items:center;justify-content:center;color:{TEXT_SUBTLE};font-size:12px;background:{PAGE_BG};border-radius:8px">No Closed NET P&L on this day</div>', unsafe_allow_html=True)

        with stat_col:
            # 2x3 stat grid matching Tradezella
            stats = [
                ("Total trades", str(len(day_tlist)) if day_tlist else "0",   "Winners",      str(wins)),
                ("Gross P&L",    f"₹{gross_pnl:,.0f}" if day_tlist else "₹0", "Commissions",  f"₹{commissions:,.0f}"),
                ("Winrate",      win_rate,                                      "Losers",       str(losers)),
            ]
            for row in stats:
                r1, r2 = st.columns(2)
                r1.markdown(f'<div style="margin-bottom:14px"><div style="font-size:10px;color:{BLUE};font-weight:500;margin-bottom:3px">{row[0]}</div><div style="font-size:15px;font-weight:700;color:{TEXT_H}">{row[1]}</div></div>', unsafe_allow_html=True)
                r2.markdown(f'<div style="margin-bottom:14px"><div style="font-size:10px;color:{BLUE};font-weight:500;margin-bottom:3px">{row[2]}</div><div style="font-size:15px;font-weight:700;color:{TEXT_H}">{row[3]}</div></div>', unsafe_allow_html=True)

        st.markdown(f'<div style="border-top:1px solid {BORDER};margin:8px 0 12px"></div>', unsafe_allow_html=True)

        # ── Template pills ────────────────────────────────────────────────────
        st.markdown(f'<span style="font-size:11px;color:{TEXT_MUTED};margin-right:10px">Recently used templates</span>', unsafe_allow_html=True)
        tpl_names = list(TEMPLATES.keys())

        def inject_template(tname):
            existing = get_note_by_date(sel)
            prev = existing["content"] if existing else ""
            injected = (prev + "\n\n" if prev else "") + TEMPLATES[tname]
            st.session_state[f"nb_content_{sel}"] = injected
            st.session_state[f"nb_area_{sel}"] = injected

        tc1, tc2 = st.columns([4, 1])
        with tc1:
            chosen = st.selectbox(
                "Pick template",
                ["— Select a template —"] + tpl_names,
                key=f"tpl_drop_{sel}",
                label_visibility="collapsed"
            )
        with tc2:
            if st.button("Use", key=f"tpl_use_{sel}", type="primary", use_container_width=True):
                if chosen != "— Select a template —":
                    inject_template(chosen)
                    st.rerun()

        # ── Tags row ──────────────────────────────────────────────────────────
        tag = st.text_input("", placeholder="🏷 Add tag…", label_visibility="collapsed", key=f"tag_{sel}")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # ── Tabs: Daily Journal | Trade Notes ─────────────────────────────────
        tab_daily, tab_trades = st.tabs(["📓  Daily Journal", "📌  Trade Notes"])

        with tab_daily:
            existing   = get_note_by_date(sel)
            def_content = st.session_state.get(f"nb_content_{sel}", existing["content"] if existing else "")
            def_title   = existing["title"] if existing else f"Journal — {hdr_label}"

            title = st.text_input("Title", value=def_title,
                placeholder="Note title…", label_visibility="collapsed",
                key=f"nb_title_{sel}")

            content = st.text_area("Journal",
                value=def_content, height=340,
                label_visibility="collapsed",
                placeholder="Write your morning prep, trade plan, post-session review, emotions, lessons...",
                key=f"nb_area_{sel}")

            btn1, btn2, btn3 = st.columns([3, 1, 1])
            with btn1:
                if existing:
                    st.caption(f"Last saved: {existing.get('updated_at','')[:16]}")
            with btn2:
                if existing:
                    if st.button("🗑 Delete", key=f"del_nb_{sel}", use_container_width=True):
                        delete_note(sel)
                        if f"nb_content_{sel}" in st.session_state:
                            del st.session_state[f"nb_content_{sel}"]
                        st.success("Deleted"); st.rerun()
            with btn3:
                if st.button("Save", type="primary", key=f"save_nb_{sel}", use_container_width=True):
                    save_note(sel, title, content)
                    if f"nb_content_{sel}" in st.session_state:
                        del st.session_state[f"nb_content_{sel}"]
                    st.success("✅ Saved!"); st.rerun()

        with tab_trades:
            if not day_tlist:
                st.info("No closed trades on this day.")
            else:
                for t in day_tlist:
                    p   = float(t.get("pnl") or 0)
                    emo = "🟢" if p > 0 else "🔴"
                    with st.expander(
                        f"{emo}  {t.get('ticker','')}  ·  {t.get('strategy','')}  ·  {'+'if p>=0 else ''}₹{abs(p):,.0f}",
                        expanded=False
                    ):
                        mc1, mc2, mc3, mc4 = st.columns(4)
                        mc1.metric("Entry ₹", f"₹{float(t.get('entry_price') or 0):,.2f}")
                        mc2.metric("Exit ₹",  f"₹{float(t.get('exit_price') or 0):,.2f}" if t.get("exit_price") else "—")
                        mc3.metric("Qty",     str(t.get("qty","—")))
                        mc4.metric("R-Mult",  f"{float(t.get('r_multiple') or 0):.2f}R")

                        tn_existing = get_trade_note(t["id"]) if t.get("id") else None
                        tn_val = tn_existing["note"] if tn_existing else ""
                        tn = st.text_area("Note", value=tn_val, height=100,
                            placeholder="Entry thesis, execution quality, emotions, lessons…",
                            label_visibility="collapsed", key=f"tn_{t['id']}")
                        if st.button("Save note", key=f"save_tn_{t['id']}", type="primary"):
                            save_trade_note(t["id"], t.get("ticker",""), tn)
                            st.success("✅ Saved!")
