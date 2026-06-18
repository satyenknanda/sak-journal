import streamlit as st
import streamlit.components.v1 as components
import json
import numpy as np
from datetime import date
from data.db import (get_playbooks, get_playbook, create_playbook, update_playbook,
                     delete_playbook, get_playbook_rules, save_playbook_rules,
                     get_journal_trades, get_trade_playbook, save_trade_playbook,
                     get_missed_trades, add_missed_trade, delete_missed_trade, init_db)
from theme import *

EMOJIS = ["📋","🔄","📈","📉","⚡","🎯","🔥","💡","🏹","🎲","🌊","⚔️","🛡️","🚀","💎"]
COLORS = ["#7C3AED","#10B981","#3B82F6","#F59E0B","#EF4444","#EC4899","#8B5CF6","#06B6D4"]

def render():
    init_db()

    # ── Row-button CSS ─────────────────────────────────────────────────────────
    st.markdown("""<style>
    /* Breadcrumb + name/ticker buttons — plain link style */
    [data-testid="stButton"]:has(button[kind="secondary"]) button {
        background: transparent !important;
        border: none !important;
        border-bottom: 1px solid #F1F5F9 !important;
        border-radius: 0 !important;
        padding: 8px 4px !important;
        text-align: left !important;
        box-shadow: none !important;
        color: #0F172A !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        justify-content: flex-start !important;
    }
    [data-testid="stButton"]:has(button[kind="secondary"]) button:hover {
        background: #F5F3FF !important;
        color: #7C3AED !important;
        border-bottom-color: #7C3AED !important;
    }
    /* Breadcrumb back button specifically */
    [data-testid="stButton"]:has(button[key="bc_back"]) button {
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 2px 4px !important;
        font-size: 13px !important;
        font-weight: 400 !important;
        color: #64748B !important;
        box-shadow: none !important;
    }
    [data-testid="stButton"]:has(button[key="bc_back"]) button:hover {
        color: #7C3AED !important;
        background: transparent !important;
        text-decoration: underline !important;
    }
    </style>""", unsafe_allow_html=True)

    # ── State management ──────────────────────────────────────────────────────
    if "pb_view"    not in st.session_state: st.session_state.pb_view    = "list"  # list | detail | create
    if "pb_sel_id"  not in st.session_state: st.session_state.pb_sel_id  = None
    if "pb_tab"     not in st.session_state: st.session_state.pb_tab     = "overview"

    trades   = get_journal_trades()
    closed   = [t for t in trades if t["status"] == "CLOSED"]
    playbooks = get_playbooks()

    # ══════════════════════════════════════════════════════════════════════════
    # CREATE PLAYBOOK VIEW
    # ══════════════════════════════════════════════════════════════════════════
    if st.session_state.pb_view == "create":
        st.markdown("## Create Playbook")
        st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:14px;font-size:11px">Define your trading setup and rules</p>', unsafe_allow_html=True)

        with st.form("create_pb_form"):
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1: name = st.text_input("Playbook name *", placeholder="e.g. Morning Top Reversal")
            with c2: emoji = st.selectbox("Icon", EMOJIS)
            with c3: color = st.selectbox("Color", COLORS)

            desc = st.text_area("Description", placeholder="What is this setup? When does it occur?", height=80)

            st.markdown(f'<p style="font-size:12px;font-weight:600;color:{TEXT_H};margin:12px 0 6px">Entry Rules</p>', unsafe_allow_html=True)
            entry_rules = []
            for i in range(5):
                r = st.text_input(f"Entry rule {i+1}", placeholder=f"e.g. Gap Up, Break of key level…", key=f"er_{i}", label_visibility="collapsed")
                if r: entry_rules.append(r)

            st.markdown(f'<p style="font-size:12px;font-weight:600;color:{TEXT_H};margin:12px 0 6px">Exit Rules</p>', unsafe_allow_html=True)
            exit_rules = []
            for i in range(5):
                r = st.text_input(f"Exit rule {i+1}", placeholder=f"e.g. Stop Loss Hit, Target Reached…", key=f"xr_{i}", label_visibility="collapsed")
                if r: exit_rules.append(r)

            bc1, bc2 = st.columns(2)
            submitted = bc1.form_submit_button("Create Playbook", type="primary", use_container_width=True)
            cancelled = bc2.form_submit_button("Cancel", use_container_width=True)

            if submitted and name:
                pb_id = create_playbook(name, emoji, color, desc)
                rules = [{"rule_type":"entry","rule_text":r,"show_when":"always"} for r in entry_rules]
                rules += [{"rule_type":"exit", "rule_text":r,"show_when":"always"} for r in exit_rules]
                if rules: save_playbook_rules(pb_id, rules)
                st.session_state.pb_view   = "detail"
                st.session_state.pb_sel_id = pb_id
                st.session_state.pb_tab    = "overview"
                st.success(f"✅ {name} created!"); st.rerun()
            if cancelled:
                st.session_state.pb_view = "list"; st.rerun()
        return

    # ══════════════════════════════════════════════════════════════════════════
    # DETAIL VIEW
    # ══════════════════════════════════════════════════════════════════════════
    if st.session_state.pb_view == "detail" and st.session_state.pb_sel_id:
        pb      = get_playbook(st.session_state.pb_sel_id)
        if not pb:
            st.session_state.pb_view = "list"; st.rerun()
        rules   = get_playbook_rules(pb["id"])
        entry_r = [r for r in rules if r["rule_type"]=="entry"]
        exit_r  = [r for r in rules if r["rule_type"]=="exit"]
        missed  = get_missed_trades(pb["id"])

        # Trades tagged to this playbook
        pb_trades = []
        for t in trades:  # include open + closed
            tp = get_trade_playbook(t["id"]) if t.get("id") else None
            if tp and tp.get("playbook_id") == pb["id"]:
                pb_trades.append((t, tp))

        closed_pb  = [(t,tp) for t,tp in pb_trades if t.get("status")=="CLOSED"]
        wins       = sum(1 for t,_ in closed_pb if float(t.get("pnl") or 0)>0)
        total_pnl  = sum(float(t.get("pnl") or 0) for t,_ in closed_pb)
        wr         = wins/len(closed_pb)*100 if closed_pb else 0
        win_pnls   = [float(t.get("pnl") or 0) for t,_ in closed_pb if float(t.get("pnl") or 0)>0]
        loss_pnls  = [abs(float(t.get("pnl") or 0)) for t,_ in closed_pb if float(t.get("pnl") or 0)<0]
        pf         = (sum(win_pnls)/sum(loss_pnls)) if loss_pnls else 0

        # Breadcrumb
        bc1, bc2, bc3 = st.columns([1.2, 6, 1])
        with bc1:
            if st.button("← Playbook", key="bc_back", use_container_width=True):
                st.session_state.pb_view = "list"; st.rerun()
        with bc2:
            st.markdown(f"""<div style="display:flex;align-items:center;gap:8px;padding-top:6px">
                <span style="color:{TEXT_SUBTLE}">/</span>
                <span style="font-size:13px;color:{TEXT_SUBTLE}">{pb['name']}</span>
                <span style="color:{TEXT_SUBTLE}">/</span>
                <span style="font-size:13px;font-weight:600;color:{TEXT_H}">{st.session_state.pb_tab.replace('_',' ').title()}</span>
            </div>""", unsafe_allow_html=True)
        with bc3:
            pass

        # Header
        st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
            <div style="width:44px;height:44px;border-radius:10px;background:{pb['color']};
                display:flex;align-items:center;justify-content:center;font-size:22px">{pb['emoji']}</div>
            <div>
                <div style="font-size:20px;font-weight:700;color:{TEXT_H}">{pb['name']}</div>
                <div style="font-size:11px;color:{TEXT_SUBTLE}">{pb.get('description','') or ''}</div>
            </div>
        </div>""", unsafe_allow_html=True)

        # Tabs
        # Tab styling - plain underline like Tradezella
        st.markdown(f"""<style>
        [data-testid="stTabs"] [data-baseweb="tab-list"]{{
            background:transparent!important;border:none!important;
            border-bottom:1px solid {BORDER}!important;padding:0!important;gap:0!important}}
        [data-testid="stTabs"] [data-baseweb="tab"]{{
            background:transparent!important;color:{TEXT_MUTED}!important;
            font-size:13px!important;font-weight:400!important;
            padding:10px 20px!important;border-radius:0!important;
            border-bottom:2px solid transparent!important}}
        [data-testid="stTabs"] [aria-selected="true"]{{
            background:transparent!important;color:#7C3AED!important;
            font-weight:600!important;border-bottom:2px solid #7C3AED!important}}
        </style>""", unsafe_allow_html=True)

        tab_ov, tab_rules, tab_exec, tab_missed, tab_notes = st.tabs([
            "Overview","Playbook Rules","Executed Trades","Missed Trades","Notes"])

        # ── OVERVIEW ─────────────────────────────────────────────────────────
        with tab_ov:
            k1,k2,k3,k4,k5 = st.columns(5)
            pnl_col = TEAL if total_pnl>=0 else RED
            for col,(lbl,val,col_) in zip([k1,k2,k3,k4,k5],[
                ("Trades",      str(len(closed_pb)),              TEXT_H),
                ("Net P&L",     f"{'+'if total_pnl>=0 else ''}₹{abs(total_pnl):,.0f}", pnl_col),
                ("Win Rate",    f"{wr:.1f}%",                     TEAL if wr>=50 else AMBER),
                ("Profit Factor",f"{pf:.2f}",                     TEAL if pf>=1 else RED),
                ("Missed",      str(len(missed)),                  TEXT_MUTED),
            ]):
                col.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};
                    border-radius:10px;padding:14px 16px;box-shadow:{SHADOW_SM}">
                    <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;
                        letter-spacing:0.07em;margin-bottom:6px">{lbl}</div>
                    <div style="font-size:20px;font-weight:700;color:{col_}">{val}</div>
                </div>""", unsafe_allow_html=True)

            if pb_trades:
                import plotly.graph_objects as go
                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                cum=[]; running=0
                for t,_ in sorted(pb_trades, key=lambda x: str(x[0].get("exit_date","") or "")):
                    running+=float(t.get("pnl") or 0); cum.append(running)
                fig=go.Figure(go.Scatter(y=cum,mode="lines",
                    line=dict(color=TEAL,width=2,shape="spline"),
                    fill="tozeroy",fillcolor="rgba(16,185,129,0.1)",
                    showlegend=False,hovertemplate="₹%{y:,.0f}<extra></extra>"))
                l=chart_layout(height=200,title="Cumulative P&L — "+pb['name'])
                l["yaxis"]["tickprefix"]="₹"; l["margin"]=dict(l=70,r=12,t=30,b=20)
                fig.update_layout(**l)
                st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

        # ── PLAYBOOK RULES ────────────────────────────────────────────────────
        with tab_rules:
            TH_R = f"padding:10px 0;font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid {BORDER}"
            TD_R = f"padding:10px 0;font-size:13px;color:{TEXT_H};border-bottom:1px solid {BORDER_LIGHT}"

            def rule_stats(rule_id):
                if not pb_trades: return 0, 0.0, "N/A", "N/A"
                followed = [(t,tp) for t,tp in pb_trades if rule_id in json.loads(tp.get("rules_followed") or "[]")]
                fr = int(len(followed)/len(pb_trades)*100)
                fr_pnl = sum(float(t.get("pnl") or 0) for t,tp in followed)
                wins_f = [float(t.get("pnl") or 0) for t,tp in followed if float(t.get("pnl") or 0)>0]
                loss_f = [abs(float(t.get("pnl") or 0)) for t,tp in followed if float(t.get("pnl") or 0)<0]
                pf2 = f"{sum(wins_f)/sum(loss_f):.2f}" if loss_f else "N/A"
                wr_f = len(wins_f); tot_f = len(followed)
                wr2 = f"{wr_f/tot_f*100:.2f} %" if tot_f else "N/A"
                return fr, fr_pnl, pf2, wr2

            for section, rules_list, rtype in [
                ("Entry Rules", entry_r, "entry"),
                ("Exit Rules",  exit_r,  "exit")
            ]:
                # Section header with drag handle
                st.markdown(f"""<div style="display:flex;align-items:center;gap:8px;margin:18px 0 4px">
                    <span style="color:{TEXT_SUBTLE};font-size:16px;cursor:grab">⠿</span>
                    <span style="font-size:14px;font-weight:600;color:{TEXT_H}">{section}</span>
                </div>""", unsafe_allow_html=True)

                # Column headers
                st.markdown(f"""<div style="display:grid;grid-template-columns:3fr 1fr 1fr 1fr 1fr 0.3fr;
                    padding:8px 0;border-bottom:1px solid {BORDER};margin-bottom:2px">
                    <span style="font-size:10px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.06em"></span>
                    <span style="font-size:10px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.06em">Follow Rate</span>
                    <span style="font-size:10px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.06em">Net Profit / Loss</span>
                    <span style="font-size:10px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.06em">Profit Factor</span>
                    <span style="font-size:10px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.06em">Win Rate</span>
                    <span></span>
                </div>""", unsafe_allow_html=True)

                for r in rules_list:
                    fr, fr_pnl, pf2, wr2 = rule_stats(r["id"])
                    fc = RED if fr < 60 else AMBER if fr < 80 else TEAL
                    pnl_str = f"{'+'if fr_pnl>=0 else ''}₹{abs(fr_pnl):,.0f}" if pb_trades else "₹0"
                    pnl_col = TEAL if fr_pnl>=0 else RED
                    st.markdown(f"""<div style="display:grid;grid-template-columns:3fr 1fr 1fr 1fr 1fr 0.3fr;
                        padding:11px 0;border-bottom:1px solid {BORDER_LIGHT};align-items:center">
                        <div style="display:flex;align-items:center;gap:8px">
                            <span style="color:{TEXT_SUBTLE};cursor:grab">⠿</span>
                            <span style="font-size:13px;color:{TEXT_H}">{r["rule_text"]}</span>
                        </div>
                        <span style="font-size:13px;font-weight:600;color:{fc}">{fr} %</span>
                        <span style="font-size:13px;color:{pnl_col}">{pnl_str}</span>
                        <span style="font-size:13px;color:{TEXT_H}">{pf2}</span>
                        <span style="font-size:13px;color:{TEXT_H}">{wr2}</span>
                        <span style="font-size:12px;color:{TEXT_SUBTLE};cursor:pointer">···</span>
                    </div>""", unsafe_allow_html=True)

                # + Create new rule
                if st.button(f"＋  Create new rule", key=f"add_rule_{rtype}", use_container_width=False):
                    st.session_state[f"adding_rule_{rtype}"] = True
                if st.session_state.get(f"adding_rule_{rtype}"):
                    nr = st.text_input("Rule name", placeholder="e.g. Gap Up at open", key=f"new_rule_input_{rtype}", label_visibility="collapsed")
                    nc1,nc2 = st.columns([4,1])
                    with nc2:
                        if st.button("Add", key=f"confirm_rule_{rtype}") and nr:
                            existing_rules = get_playbook_rules(pb["id"])
                            existing_rules.append({"rule_type":rtype,"rule_text":nr,"show_when":"always"})
                            save_playbook_rules(pb["id"], existing_rules)
                            st.session_state[f"adding_rule_{rtype}"] = False; st.rerun()

        # ── EXECUTED TRADES ───────────────────────────────────────────────────
        with tab_exec:
            if not pb_trades:
                st.info("No trades tagged to this playbook yet. Tag a trade's playbook from Daily Plan.")
            else:
                sel_trade_key = f"sel_trade_{pb['id']}"
                if sel_trade_key not in st.session_state:
                    st.session_state[sel_trade_key] = None

                sel_t = st.session_state[sel_trade_key]

                if sel_t is not None:
                    # ── TRADE DETAIL: left=stats+rules, right=chart ────────
                    if st.button("← Back to trades", key="back_to_trades"):
                        st.session_state[sel_trade_key] = None; st.rerun()

                    t_data = next((t for t,_ in pb_trades if t.get("id")==sel_t), None)
                    tp_data = next((tp for t,tp in pb_trades if t.get("id")==sel_t), None)
                    if t_data:
                        p = float(t_data.get("pnl") or 0)
                        pc = TEAL if p>=0 else RED
                        rf = json.loads(tp_data.get("rules_followed") or "[]") if tp_data else []

                        det_l, det_r = st.columns([1, 1.8])
                        with det_l:
                            st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};
                                border-radius:10px;padding:16px;box-shadow:{SHADOW_SM}">
                                <div style="font-size:14px;font-weight:700;color:{TEXT_H}">{t_data.get('ticker','')}</div>
                                <div style="font-size:11px;color:{TEXT_MUTED};margin-bottom:12px">{str(t_data.get('exit_date','') or '')[:10]}</div>
                                <div style="font-size:11px;color:{TEXT_SUBTLE};margin-bottom:4px">NET P&L</div>
                                <div style="font-size:22px;font-weight:700;color:{pc};margin-bottom:14px">
                                    {'+'if p>=0 else ''}₹{abs(p):,.0f}</div>
                            </div>""", unsafe_allow_html=True)

                            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                            # Playbook rules checklist
                            n_followed = len(rf); n_total = len(rules)
                            bar_w = int(n_followed/n_total*100) if n_total else 0
                            st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};
                                border-radius:10px;padding:16px;box-shadow:{SHADOW_SM}">
                                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                                    <span style="font-size:12px;font-weight:600;color:{TEXT_H}">Rules Followed</span>
                                    <span style="font-size:11px;color:{TEXT_SUBTLE}">{n_followed}/{n_total}</span>
                                </div>
                                <div style="height:5px;background:{BORDER_LIGHT};border-radius:3px;overflow:hidden;margin-bottom:14px">
                                    <div style="width:{bar_w}%;height:100%;background:{TEAL};border-radius:3px"></div>
                                </div>
                            """, unsafe_allow_html=True)

                            for sect_name, sect_rules in [("ENTRY RULES", entry_r), ("EXIT RULES", exit_r)]:
                                if sect_rules:
                                    st.markdown(f'<div style="font-size:10px;font-weight:600;color:{TEXT_SUBTLE};letter-spacing:0.08em;margin:10px 0 6px">{sect_name}</div>', unsafe_allow_html=True)
                                    for r in sect_rules:
                                        checked = r["id"] in rf
                                        new_checked = st.checkbox(r["rule_text"], value=checked, key=f"rf_{sel_t}_{r['id']}")
                                        if new_checked != checked:
                                            if new_checked and r["id"] not in rf: rf.append(r["id"])
                                            elif not new_checked and r["id"] in rf: rf.remove(r["id"])
                                            save_trade_playbook(sel_t, pb["id"], rf)
                                            st.rerun()

                            st.markdown('</div>', unsafe_allow_html=True)

                        with det_r:
                            ticker = t_data.get("ticker","")
                            entry_date_str = str(t_data.get("entry_date","") or "")[:10]
                            exit_date_str  = str(t_data.get("exit_date","")  or "")[:10]
                            ep  = float(t_data.get("entry_price") or 0)
                            xp  = float(t_data.get("exit_price")  or 0)
                            sl  = float(t_data.get("stop_loss")   or 0)
                            mae = float(t_data.get("mae_price")   or 0)
                            mfe = float(t_data.get("mfe_price")   or 0)

                            # ── TradingView chart controls ───────────────────
                            INTERVALS_PB = {
                                "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
                                "1H":"60","2H":"120","4H":"240","1D":"D","1W":"W","1M":"M"
                            }
                            CHART_TYPES_PB = {
                                "Candles":"1","Bars":"0","Line":"2","Area":"3",
                                "Heikin Ashi":"8","Hollow Candles":"9"
                            }
                            pb_intv_key  = f"pb_tv_interval_{sel_t}"
                            pb_ctype_key = f"pb_tv_chart_type_{sel_t}"
                            if pb_intv_key  not in st.session_state: st.session_state[pb_intv_key]  = "D"
                            if pb_ctype_key not in st.session_state: st.session_state[pb_ctype_key] = "1"

                            _cc1, _cc2, _cc3 = st.columns([3, 1.5, 1.5])
                            with _cc1:
                                st.markdown(
                                    f'<div style="font-size:12px;font-weight:600;color:{TEXT_H};padding-top:6px">'
                                    f'📈 {ticker} — TradingView Chart</div>',
                                    unsafe_allow_html=True)
                            with _cc2:
                                _intv_label = st.selectbox(
                                    "Interval", list(INTERVALS_PB.keys()),
                                    index=8, key=f"pb_intv_{sel_t}",
                                    label_visibility="collapsed")
                                st.session_state[pb_intv_key] = INTERVALS_PB[_intv_label]
                            with _cc3:
                                _ctype_label = st.selectbox(
                                    "Chart Type", list(CHART_TYPES_PB.keys()),
                                    index=0, key=f"pb_ctype_{sel_t}",
                                    label_visibility="collapsed")
                                st.session_state[pb_ctype_key] = CHART_TYPES_PB[_ctype_label]

                            _pb_intv  = st.session_state[pb_intv_key]
                            _pb_ctype = st.session_state[pb_ctype_key]

                            # ── TradingView embed ─────────────────────────────
                            display_sym = f"BSE:{ticker}"
                            tv_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;padding:0;background:#ffffff;overflow:hidden;height:100%}}
  .tradingview-widget-container{{width:100%;height:600px}}
  .tradingview-widget-container__widget{{height:100%}}
</style></head>
<body>
<div class="tradingview-widget-container">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
    async>
  {{
    "autosize": true,
    "symbol": "{display_sym}",
    "interval": "{_pb_intv}",
    "timezone": "Asia/Kolkata",
    "theme": "light",
    "style": "{_pb_ctype}",
    "locale": "en",
    "allow_symbol_change": false,
    "calendar": false,
    "hide_volume": false,
    "support_host": "https://www.tradingview.com"
  }}
  </script>
</div>
</body></html>"""
                            components.html(tv_html, height=620, scrolling=False)

                            # ── Price level pills ────────────────────────────
                            def _pill(label, val, color):
                                if not val: return ""
                                return (f'<div style="display:flex;flex-direction:column;align-items:center;'
                                        f'background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;'
                                        f'padding:6px 14px;min-width:72px">'
                                        f'<span style="font-size:9px;color:#64748B;font-weight:600;'
                                        f'text-transform:uppercase;letter-spacing:0.07em;margin-bottom:2px">{label}</span>'
                                        f'<span style="font-size:13px;font-weight:700;color:{color}">₹{val:,.2f}</span>'
                                        f'</div>')
                            pills = (
                                _pill("Entry", ep,  "#10B981") +
                                _pill("Exit",  xp,  "#EF4444") +
                                _pill("SL",    sl,  "#F59E0B") +
                                _pill("MAE",   mae, "#FF6B6B") +
                                _pill("MFE",   mfe, "#34D399")
                            )
                            if pills:
                                st.markdown(
                                    f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">{pills}</div>',
                                    unsafe_allow_html=True
                                )



                else:
                    # ── TRADE LIST ─────────────────────────────────────────
                    # Header row
                    hc = st.columns([2, 1.8, 1.8, 1.5, 2])
                    for col, label in zip(hc, ["SYMBOL","DATE","STRATEGY","NET P&L","RULES"]):
                        col.markdown(f'<div style="font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;padding:6px 0;border-bottom:1px solid {BORDER}">{label}</div>', unsafe_allow_html=True)

                    for t,tp in sorted(pb_trades, key=lambda x: str(x[0].get("exit_date","") or ""), reverse=True):
                        p = float(t.get("pnl") or 0)
                        pc = TEAL if p > 0 else RED
                        rf = json.loads(tp.get("rules_followed") or "[]")
                        n_followed = len(rf); n_rules = len(rules)
                        bar_w = int(n_followed/n_rules*100) if n_rules else 0
                        c1,c2,c3,c4,c5 = st.columns([2, 1.8, 1.8, 1.5, 2])
                        # Ticker is the clickable element
                        with c1:
                            if st.button(f"**{t.get('ticker','')}**", key=f"open_trade_{t.get('id')}", use_container_width=True):
                                st.session_state[sel_trade_key] = t.get("id"); st.rerun()
                        c2.markdown(f'<div style="padding:8px 0;font-size:12px;color:{TEXT_MUTED};border-bottom:1px solid {BORDER_LIGHT}">{str(t.get("exit_date","") or "")[:10]}</div>', unsafe_allow_html=True)
                        c3.markdown(f'<div style="padding:8px 0;font-size:12px;color:{TEXT_MUTED};border-bottom:1px solid {BORDER_LIGHT}">{t.get("strategy","")}</div>', unsafe_allow_html=True)
                        c4.markdown(f'<div style="padding:8px 0;font-size:12px;font-weight:700;color:{pc};border-bottom:1px solid {BORDER_LIGHT}">{"+" if p>0 else ""}₹{abs(p):,.0f}</div>', unsafe_allow_html=True)
                        c5.markdown(f'''<div style="padding:8px 0;border-bottom:1px solid {BORDER_LIGHT}">
                            <div style="display:flex;align-items:center;gap:6px">
                                <div style="flex:1;height:5px;background:{BORDER_LIGHT};border-radius:3px;overflow:hidden">
                                    <div style="width:{bar_w}%;height:100%;background:{TEAL}"></div>
                                </div>
                                <span style="font-size:10px;color:{TEXT_MUTED}">{n_followed}/{n_rules}</span>
                            </div></div>''', unsafe_allow_html=True)

        # ── MISSED TRADES ─────────────────────────────────────────────────────
        with tab_missed:
            st.markdown(f'<p style="font-size:12px;font-weight:600;color:{TEXT_H};margin-bottom:10px">Missed / Logged Trades</p>', unsafe_allow_html=True)

            with st.expander("＋ Add missed trade"):
                mc1,mc2,mc3 = st.columns(3)
                with mc1: mt_ticker = st.text_input("Ticker", key="mt_ticker")
                with mc2: mt_date   = st.date_input("Date",   key="mt_date", value=date.today())
                with mc3: mt_notes  = st.text_input("Notes",  key="mt_notes")
                mc4,mc5,mc6 = st.columns(3)
                with mc4: mt_ep = st.number_input("Entry ₹", min_value=0.0, step=0.05, key="mt_ep", format="%.2f")
                with mc5: mt_xp = st.number_input("Exit ₹",  min_value=0.0, step=0.05, key="mt_xp", format="%.2f")
                with mc6: mt_qty = st.number_input("Qty",     min_value=0, step=1, key="mt_qty")
                if st.button("Add missed trade", type="primary", key="add_mt"):
                    if mt_ticker:
                        add_missed_trade(pb["id"], mt_ticker, str(mt_date), mt_ep, mt_xp, mt_qty, mt_notes)
                        st.success("Added!"); st.rerun()

            if missed:
                TH3=f"padding:9px 14px;font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;background:{TABLE_HEAD_BG};border-bottom:1px solid {BORDER}"
                TD3=f"padding:9px 14px;font-size:12.5px;border-bottom:1px solid {BORDER_LIGHT}"
                rows=""
                for m in missed:
                    ep=float(m.get("entry_price") or 0); xp=float(m.get("exit_price") or 0)
                    est_pnl=(xp-ep)*(m.get("qty") or 0)
                    pc2=TEAL if est_pnl>=0 else RED
                    rows+=f"""<tr>
                        <td style="{TD3};font-weight:600;color:{TEXT_H}">{m.get('ticker','')}</td>
                        <td style="{TD3};color:{TEXT_MUTED}">{m.get('trade_date','')}</td>
                        <td style="{TD3}">₹{ep:,.2f}</td>
                        <td style="{TD3}">₹{xp:,.2f}</td>
                        <td style="{TD3};color:{pc2}">{'+'if est_pnl>=0 else ''}₹{abs(est_pnl):,.0f}</td>
                        <td style="{TD3};color:{TEXT_MUTED}">{m.get('notes','')}</td>
                    </tr>"""
                st.markdown(f"""<table style="width:100%;border-collapse:collapse">
                    <thead><tr>
                        <th style="{TH3};text-align:left">Symbol</th>
                        <th style="{TH3}">Date</th>
                        <th style="{TH3}">Entry ₹</th>
                        <th style="{TH3}">Exit ₹</th>
                        <th style="{TH3}">Est P&L</th>
                        <th style="{TH3}">Notes</th>
                    </tr></thead><tbody>{rows}</tbody></table>""", unsafe_allow_html=True)
            else:
                st.info("No missed trades logged yet.")

        # ── NOTES ─────────────────────────────────────────────────────────────
        with tab_notes:
            note_key = f"pb_note_{pb['id']}"
            current  = pb.get("description","") or ""
            note_val = st.text_area("Playbook notes", value=current, height=300,
                placeholder="Document your setup: when it occurs, market conditions, key criteria, how to manage it…",
                key=note_key)
            if st.button("Save notes", type="primary"):
                update_playbook(pb["id"], pb["name"], pb["emoji"], pb["color"], note_val)
                st.success("✅ Saved!")
        return

    # ══════════════════════════════════════════════════════════════════════════
    # LIST VIEW (main page)
    # ══════════════════════════════════════════════════════════════════════════
    h1, h2 = st.columns([4,1])
    with h1:
        st.markdown("## Playbook")
        st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:14px;font-size:11px">Track your trading setups and strategies</p>', unsafe_allow_html=True)
    with h2:
        if st.button("＋ Create Playbook", type="primary", use_container_width=True):
            st.session_state.pb_view = "create"; st.rerun()

    if not playbooks:
        st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:12px;
            padding:48px;text-align:center;box-shadow:{SHADOW_SM}">
            <div style="font-size:40px;margin-bottom:12px">📋</div>
            <div style="font-size:16px;font-weight:600;color:{TEXT_H};margin-bottom:6px">No playbooks yet</div>
            <div style="font-size:13px;color:{TEXT_MUTED}">Create your first playbook to start tracking your trading setups</div>
        </div>""", unsafe_allow_html=True)
        return

    # ── Playbook list: pure st.columns rows ──────────────────────────────────
    # Header
    h1,h2,h3,h4,h5 = st.columns([3, 1, 1.5, 1, 1])
    for col, label in zip([h1,h2,h3,h4,h5], ["PLAYBOOK","TRADES","NET P&L","WIN RATE","MISSED"]):
        col.markdown(f'<div style="font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;padding:8px 0;border-bottom:2px solid {BORDER}">{label}</div>', unsafe_allow_html=True)

    for pb in playbooks:
        pb_trade_list = []
        for t in closed:
            tp = get_trade_playbook(t["id"]) if t.get("id") else None
            if tp and tp.get("playbook_id") == pb["id"]:
                pb_trade_list.append(t)

        n_trades  = len(pb_trade_list)
        total_pnl = sum(float(t.get("pnl") or 0) for t in pb_trade_list)
        wins      = sum(1 for t in pb_trade_list if float(t.get("pnl") or 0)>0)
        wr        = f"{wins/n_trades*100:.1f}%" if n_trades else "—"
        n_missed  = len(get_missed_trades(pb["id"]))
        pc        = TEAL if total_pnl>=0 else RED
        pnl_str   = f"{'+'if total_pnl>=0 else ''}₹{abs(total_pnl):,.0f}"
        wr_col    = TEAL if (n_trades > 0 and wins/n_trades >= 0.5) else TEXT_MUTED

        c1,c2,c3,c4,c5 = st.columns([3, 1, 1.5, 1, 1])
        # Full clickable name+icon button
        with c1:
            btn_label = f'''{pb['emoji']}  {pb['name']}'''
            if st.button(btn_label, key=f"open_pb_{pb['id']}", use_container_width=True,
                         help=f"Open {pb['name']}"):
                st.session_state.pb_view   = "detail"
                st.session_state.pb_sel_id = pb["id"]
                st.rerun()
        c2.markdown(f'<div style="padding:10px 0;font-size:13px;color:{TEXT_H};border-bottom:1px solid {BORDER_LIGHT}">{n_trades}</div>', unsafe_allow_html=True)
        c3.markdown(f'<div style="padding:10px 0;font-size:13px;font-weight:600;color:{pc};border-bottom:1px solid {BORDER_LIGHT}">{pnl_str}</div>', unsafe_allow_html=True)
        c4.markdown(f'<div style="padding:10px 0;font-size:13px;color:{wr_col};border-bottom:1px solid {BORDER_LIGHT}">{wr}</div>', unsafe_allow_html=True)
        c5.markdown(f'<div style="padding:10px 0;font-size:13px;color:{TEXT_MUTED};border-bottom:1px solid {BORDER_LIGHT}">{n_missed}</div>', unsafe_allow_html=True)
