import streamlit as st
from theme import *
from clean_theme import metric_card_group, metric_row
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

import pandas as pd
from datetime import date
from data.db import get_trades, get_strategies, delete_trade, get_kpi_summary_extended as get_kpi, get_setting
from data.prices import fetch_prices_bulk
from components.trade_modals import render_add_trade_modal, render_exit_trade_modal, render_edit_trade_modal
from collections import defaultdict
import numpy as np

# ── Light theme colours ────────────────────────────────────────────────────
G = "#10B981"; R = "#EF4444"; B = "#3B82F6"; AM = "#F59E0B"
TEXT = "#111827"; MUTED = "#6B7280"; DIM = "#D1D5DB"
BG = "#FFFFFF"; BORDER = "#E5E7EB"; HEADER_BG = "#F9FAFB"
ROW_HOVER = "#F9FAFB"; ROW_WIN = "#F0FDF4"; ROW_LOSS = "#FEF2F2"; ROW_OPEN = "#EFF6FF"


@st.dialog("Add Trade", width="large")
def add_trade_dialog(): render_add_trade_modal()

@st.dialog("Edit Trade", width="large")
def edit_trade_dialog(trade): render_edit_trade_modal(trade)

@st.dialog("Exit Trade", width="large")
def exit_trade_dialog(trade): render_exit_trade_modal(trade)


def _p(v, d=2):
    try:
        f = float(v)
        return f"₹{f:,.{d}f}" if f else "—"
    except: return "—"

def _pct(v):
    try:
        f = float(v)
        return f"{'+' if f>0 else ''}{f:.2f}%"
    except: return "—"

def kcard_local(label, value, color="neutral", fs="1.2rem"):
    c = {"green":G,"red":R,"blue":B,"amber":AM,"neutral":MUTED}.get(color,MUTED)
    return f"""<div style="background:{BG};border:1px solid {BORDER};border-top:3px solid {c};
        border-radius:10px;padding:14px 16px;min-height:76px;box-shadow:0 1px 3px rgba(0,0,0,0.06)">
        <div style="font-size:0.65rem;color:{MUTED};text-transform:uppercase;letter-spacing:0.08em;font-weight:600;margin-bottom:6px">{label}</div>
        <div style="font-size:{fs};font-weight:700;color:{TEXT};font-family:'SF Mono','Fira Code',monospace;white-space:nowrap">{value}</div>
    </div>"""

def _calc_running(t):
    """Returns (pnl, r_mult) — running for OPEN trades using live price, actual for CLOSED."""
    pnl = t.get("pnl")
    r   = t.get("r_multiple")
    live = t.get("live_price")
    ep   = t.get("entry_price", 0)
    if t["status"] == "OPEN" and live and ep:
        qty = float(t.get("qty") or 0)
        side = str(t.get("side","")).upper()
        lp = float(live); epf = float(ep)
        if side in ("BUY","LONG"):
            pnl = (lp - epf) * qty
        else:
            pnl = (epf - lp) * qty
        sl = t.get("stop_loss")
        if sl:
            risk = abs(epf - float(sl)) * qty
            if risk:
                r = pnl / risk
    return pnl, r


def render():
    st.markdown("## Daily Plan")
    st.markdown(f'<p style="color:{MUTED};margin-top:-10px;margin-bottom:18px;font-size:0.88rem">FY 2026-27 · NSE Equity</p>', unsafe_allow_html=True)

    # ── Load all trades once, compute running P&L for open ones ────────────
    all_trades_raw = get_trades()
    open_all = [t for t in all_trades_raw if t["status"] == "OPEN"]
    closed_all = [t for t in all_trades_raw if t["status"] == "CLOSED"]

    # Refresh live prices for open trades (best-effort; falls back to stored value)
    if open_all:
        with st.spinner("Refreshing prices…"):
            price_data = fetch_prices_bulk(list({t["ticker"] for t in open_all}))
        for t in open_all:
            if t["ticker"] in price_data:
                p = price_data[t["ticker"]]
                if p.get("price"):
                    t["live_price"] = p["price"]; t["change_pct"] = p["change_pct"]
    else:
        price_data = {}

    # ── Combine same-ticker open positions for KPI purposes only ────────────
    # (individual trade rows in the table below stay separate; this only affects
    #  the Open Positions / Unrealized P&L / At Risk / In Profit cockpit cards)
    combined_by_ticker = {}
    for t in open_all:
        tk = t.get("ticker","")
        pnl, _ = _calc_running(t)
        rs = (t.get("risk_status") or "")
        if tk not in combined_by_ticker:
            combined_by_ticker[tk] = {"pnl": 0.0, "qty": 0.0, "rs_flags": set()}
        combined_by_ticker[tk]["pnl"] += pnl or 0
        combined_by_ticker[tk]["qty"] += float(t.get("qty") or 0)
        if "SL Breached" in rs or "Open Risk" in rs:
            combined_by_ticker[tk]["rs_flags"].add("at_risk")
        if "Profit" in rs or (pnl is not None and pnl > 0):
            combined_by_ticker[tk]["rs_flags"].add("in_profit")

    # ── Focused cockpit strip — 4 cards about OPEN positions (ticker-combined) ──
    unrealized_pnl = 0.0
    at_risk = 0
    in_profit = 0
    for tk, agg in combined_by_ticker.items():
        unrealized_pnl += agg["pnl"]
        if "at_risk" in agg["rs_flags"]:
            at_risk += 1
        elif agg["pnl"] > 0 or "in_profit" in agg["rs_flags"]:
            in_profit += 1

    n_positions = len(combined_by_ticker)  # unique tickers, not individual trade rows

    cockpit_rows = [
        metric_row("Open Positions", str(n_positions), f"{len(open_all)} trade rows" if len(open_all)!=n_positions else "", icon="📂", icon_color="blue"),
        metric_row("Unrealized P&L", f"{'+' if unrealized_pnl>=0 else ''}₹{unrealized_pnl:,.0f}",
                   icon="💰", icon_color="green" if unrealized_pnl>=0 else "red"),
        metric_row("At Risk", str(at_risk), icon="⚠️", icon_color="red" if at_risk else "blue"),
        metric_row("In Profit", str(in_profit), icon="📈", icon_color="green"),
    ]
    st.markdown(metric_card_group(cockpit_rows), unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Filter bar ─────────────────────────────────────────────────────────
    fc = st.columns([1, 1.4, 1.4, 1.4, 1.4, 1.4, 1])
    with fc[0]: status_f  = st.selectbox("Status",   ["OPEN","All","CLOSED"], label_visibility="collapsed")
    with fc[1]:
        strats = ["All"] + get_strategies()
        strat_f = st.selectbox("Strategy", strats, label_visibility="collapsed")
    with fc[2]: ticker_f  = st.text_input("Ticker", placeholder="🔍 Search ticker…", label_visibility="collapsed")
    with fc[3]: date_from = st.date_input("From", value=date(2026,4,1), label_visibility="collapsed")
    with fc[4]: date_to   = st.date_input("To",   value=date.today(),   label_visibility="collapsed")
    with fc[5]: pnl_f     = st.selectbox("P&L", ["All","Winners","Losers","Open only"], label_visibility="collapsed")
    with fc[6]:
        if st.button("＋ Add Trade", type="primary", use_container_width=True):
            add_trade_dialog()

    # Auto-open if triggered from sidebar button
    if st.session_state.pop("show_add_trade", False):
        add_trade_dialog()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Load & filter ──────────────────────────────────────────────────────
    trades = get_trades(status=status_f, strategy=strat_f, ticker=ticker_f,
                        date_from=date_from, date_to=date_to)
    if pnl_f == "Winners":   trades = [t for t in trades if (t.get("pnl") or 0)>0]
    elif pnl_f == "Losers":  trades = [t for t in trades if (t.get("pnl") or 0)<0]
    elif pnl_f == "Open only": trades = [t for t in trades if t["status"]=="OPEN"]

    if not trades:
        st.info("No trades match the current filters."); return

    # Apply refreshed live prices to filtered trade list too
    for t in trades:
        if t["status"] == "OPEN" and t["ticker"] in price_data:
            p = price_data[t["ticker"]]
            if p.get("price"):
                t["live_price"] = p["price"]; t["change_pct"] = p["change_pct"]

    fetched_at = next((v["fetched_at"] for v in price_data.values() if v.get("fetched_at")), None)
    st.caption(f"{len(trades)} trades{f' · prices as of {fetched_at}' if fetched_at else ''}")

    # ── More Stats (unchanged) ──────────────────────────────────────────────
    kpi = get_kpi()
    with st.expander("📊  More Stats"):
        acct_bal    = kpi.get("account_balance", 10_000_000)

        above = sum(1 for t in open_all if (t.get("live_price") or 0)>(t.get("entry_price") or 0))
        below = sum(1 for t in open_all if 0<(t.get("live_price") or 0)<(t.get("entry_price") or 0))
        sl_br = sum(1 for t in open_all if "SL Breached" in (t.get("risk_status") or ""))
        in_pr = sum(1 for t in open_all if "In Profits" in (t.get("risk_status") or ""))
        tot_ps= sum(float(t.get("entry_price",0))*float(t.get("qty",0)) for t in open_all)
        open_risk=sum(abs(float(t.get("entry_price",0))-float(t.get("stop_loss",0)))*float(t.get("qty",0))
                      for t in open_all if t.get("stop_loss"))

        st.markdown("#### 📈 Position Health")
        ph = st.columns(6)
        for col,(l,v,c) in zip(ph,[
            ("Above Entry",str(above),"green"),("Below Entry",str(below),"red"),
            ("SL Breached",str(sl_br),"red"),("In Profits",str(in_pr),"green"),
            ("Pos Value",f"₹{tot_ps:,.0f}","blue"),("Open Risk",f"₹{open_risk:,.0f}","amber"),
        ]): col.markdown(kcard(l,v,c,"1.3rem"), unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Top 3 open positions
        top3 = sorted(open_all, key=lambda x: float(x.get("entry_price",0))*float(x.get("qty",0)), reverse=True)[:3]
        if top3:
            st.markdown("#### 🏆 Top 3 Open Positions")
            t3c = st.columns(3)
            for col, t in zip(t3c, top3):
                ps   = float(t.get("entry_price",0))*float(t.get("qty",0))
                alloc= ps/acct_bal*100 if acct_bal else 0
                lp   = t.get("live_price") or 0
                ep   = t.get("entry_price") or 0
                unr  = (float(lp)-float(ep))*float(t.get("qty",0)) if lp and ep else 0
                unr_c= G if unr>=0 else R
                col.markdown(f"""
                <div style="background:{BG};border:1px solid {BORDER};border-radius:12px;
                    padding:16px;box-shadow:0 1px 4px rgba(0,0,0,0.06)">
                    <div style="font-size:1.05rem;font-weight:800;color:{TEXT}">{t['ticker']}</div>
                    <div style="font-size:0.75rem;color:{MUTED};margin:2px 0 10px">{t['strategy']}</div>
                    <div style="font-size:1rem;font-weight:700;color:{TEXT};font-family:monospace">₹{ps:,.0f}</div>
                    <div style="font-size:0.75rem;color:{MUTED}">{alloc:.1f}% of capital</div>
                    <div style="font-size:0.85rem;font-weight:600;color:{unr_c};margin-top:8px">
                        {"▲" if unr>=0 else "▼"} ₹{abs(unr):,.0f} unrealised
                    </div>
                    <div style="font-size:0.72rem;color:{MUTED}">Entry ₹{float(ep):,.2f} · {int(t.get('qty',0)):,} shares</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Trade outcomes
        st.markdown("#### 🎯 Trade Outcomes")
        th = sum(1 for t in closed_all if t.get("risk_status")=="Target Hit")
        ts = sum(1 for t in closed_all if t.get("risk_status")=="TSL Hit")
        sh = sum(1 for t in closed_all if t.get("risk_status")=="SL Hit")
        mc = sum(1 for t in closed_all if t.get("risk_status")=="Manually Closed")
        oc = st.columns(4)
        for col,(l,v,c) in zip(oc,[("Target Hit",str(th),"green"),("TSL Hit",str(ts),"amber"),
            ("SL Hit",str(sh),"red"),("Manual",str(mc),"neutral")]):
            col.markdown(kcard(l,v,c,"1.4rem"), unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Daily stats
        today_str = date.today().strftime("%Y-%m-%d")
        t_closed  = [t for t in closed_all if str(t.get("exit_date",""))[:10]==today_str]
        t_open    = [t for t in open_all   if str(t.get("entry_date",""))[:10]==today_str]
        t_pnl     = sum(float(t.get("pnl") or 0) for t in t_closed)
        st.markdown(f"#### 📅 Daily Stats — {date.today().strftime('%d %b %Y')}")
        dc = st.columns(5)
        for col,(l,v,c) in zip(dc,[
            ("New Entries",str(len(t_open)),"blue"),
            ("Closed Today",str(len(t_closed)),"neutral"),
            ("P&L Today",f"{'+' if t_pnl>=0 else ''}₹{t_pnl:,.0f}","green" if t_pnl>=0 else "red"),
            ("Best",f"₹{max((float(t.get('pnl') or 0) for t in t_closed),default=0):,.0f}","green"),
            ("Worst",f"₹{min((float(t.get('pnl') or 0) for t in t_closed),default=0):,.0f}","red"),
        ]): col.markdown(kcard(l,v,c,"1.1rem"), unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Strategy breakdown
        st.markdown("#### 📋 Strategy Breakdown")
        sm = defaultdict(lambda:{"trades":0,"closed":0,"wins":0,"pnl":0.0,"r":[]})
        for t in all_trades_raw:
            s=t.get("strategy",""); sm[s]["trades"]+=1
            if t["status"]=="CLOSED":
                sm[s]["closed"]+=1; p=float(t.get("pnl") or 0); sm[s]["pnl"]+=p
                if p>0: sm[s]["wins"]+=1
                r=t.get("r_multiple")
                if r: sm[s]["r"].append(float(r))
        srows=[]
        for s,d in sorted(sm.items()):
            cl=d["closed"]; wr=d["wins"]/cl if cl else 0
            pos_r=[r for r in d["r"] if r>0]; neg_r=[r for r in d["r"] if r<=0]
            aw=float(np.mean(pos_r)) if pos_r else 0; al=float(np.mean(neg_r)) if neg_r else 0
            exp=wr*aw+(1-wr)*al if cl else 0
            srows.append({"Strategy":s,"Trades":d["trades"],"Closed":cl,
                "Win Rate":f"{wr*100:.1f}%","Total P&L":d["pnl"],"Expectancy":f"{exp:.2f}R",
                "Avg Win R":f"{aw:.2f}R","Avg Loss R":f"{al:.2f}R"})
        if srows:
            sdf=pd.DataFrame(srows)
            def ss(row):
                idx=sdf.columns.tolist(); styles=[""]*len(row)
                p=row.get("Total P&L",0)
                if "Total P&L" in idx:
                    styles[idx.index("Total P&L")]=f"color:{G};font-weight:600" if p>0 else f"color:{R};font-weight:600" if p<0 else ""
                return styles
            TS=[{"selector":"thead th","props":[("background-color",HEADER_BG),("color",MUTED),
                ("font-size","10.5px"),("text-transform","uppercase"),("letter-spacing","0.07em"),
                ("border-bottom",f"1px solid {BORDER}"),("padding","9px 14px")]},
                {"selector":"td","props":[("padding","9px 14px"),("border-bottom",f"1px solid {BORDER}"),("font-size","13px")]}]
            st.dataframe(sdf.style.apply(ss,axis=1)
                .format({"Total P&L":lambda v:f"{'+' if v>=0 else ''}₹{v:,.0f}"})
                .set_properties(**{"font-size":"13px"}).set_table_styles(TS),
                use_container_width=True, hide_index=True)

    # ── Table — exact DailyPlan column order, light Tradezella style ───────
    def status_chip(status, risk_status=""):
        if status == "OPEN":
            label = risk_status if risk_status else "OPEN"
            # colour by risk status
            if "SL Breached" in label:
                bg,fg = "#FEF2F2", R
            elif "In Profits" in label:
                bg,fg = "#F0FDF4", G
            elif "Risk Free" in label or "At Cost" in label:
                bg,fg = "#FFF7ED", AM
            else:
                bg,fg = "#EFF6FF", B
        else:
            bg,fg = "#F3F4F6", MUTED
            label = "CLOSED"
        return f'<span style="background:{bg};color:{fg};padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;white-space:nowrap;border:1px solid {fg}22">{label}</span>'

    def pnl_chip(pnl, r_mult=None, is_open=False):
        if pnl is None: return '<span style="color:#9CA3AF">—</span>'
        color = G if pnl>0 else R if pnl<0 else MUTED
        bg    = "#F0FDF4" if pnl>0 else "#FEF2F2" if pnl<0 else "#F3F4F6"
        r_str = f'<span style="font-size:0.68rem;opacity:0.75;margin-left:3px">({r_mult:+.1f}R)</span>' if r_mult else ""
        prefix = "~" if is_open else ""
        return f'<span style="background:{bg};color:{color};padding:2px 8px;border-radius:12px;font-size:0.78rem;font-weight:700;border:1px solid {color}22;white-space:nowrap">{prefix}{"+₹" if pnl>0 else "₹"}{abs(pnl):,.0f}{r_str}</span>'

    def live_cell(live, entry, chg):
        if not live: return '<span style="color:#9CA3AF">—</span>'
        lf = float(live); ef = float(entry or 0)
        price_color = G if lf >= ef else R
        chg_color   = G if (chg or 0)>0 else R
        chg_str     = f'<span style="color:{chg_color};font-size:0.72rem;display:block">{_pct(chg)}</span>' if chg else ""
        return f'<span style="color:{price_color};font-weight:600">₹{lf:,.2f}</span>{chg_str}'

    def num(v): return f'<span style="color:#9CA3AF">—</span>' if not v else str(int(float(v)))

    headers = [
        "Status","No","Entry Date","Side","Qty","Ticker","Strategy",
        "Entry ₹","Stop Loss","Target ₹","Comm","TSL",
        "Live ₹","Chg %","Exit Date","Exit Qty","Exit ₹","Comm(X)","Risk Status","P&L","R-Mult"
    ]

    rows_html = []
    for t in trades:
        live = t.get("live_price")
        chg  = t.get("change_pct")
        ep   = t.get("entry_price",0)
        rs   = t.get("risk_status","") or ""

        pnl, r = _calc_running(t)

        if t["status"] == "OPEN":
            row_bg = "#EFF6FF" if not rs else ("#FEF2F2" if "SL" in rs else "#F0FDF4" if "Profit" in rs else "#EFF6FF")
        elif pnl and pnl > 0:
            row_bg = ROW_WIN
        elif pnl and pnl < 0:
            row_bg = ROW_LOSS
        else:
            row_bg = BG

        def td(content, align="left", mono=False, bold=False):
            style = f"padding:8px 12px;white-space:nowrap;text-align:{align};"
            if mono: style += "font-family:'SF Mono','Fira Code',monospace;font-size:0.82rem;"
            else: style += "font-size:0.82rem;"
            if bold: style += "font-weight:700;"
            return f'<td style="{style}">{content}</td>'

        rows_html.append(f"""
        <tr style="background:{row_bg};border-bottom:1px solid {BORDER};transition:background 0.1s"
            onmouseover="this.style.background='{ROW_HOVER}'"
            onmouseout="this.style.background='{row_bg}'">
            {td(status_chip(t['status'], rs))}
            {td(str(t.get('trade_no') or ''), mono=True)}
            {td(str(t.get('entry_date','') or '')[:10])}
            {td(t.get('side',''))}
            {td(f"{int(t.get('qty') or 0):,}", mono=True)}
            {td(f'<span style="font-weight:700;color:{TEXT}">{t.get("ticker","")}</span>')}
            {td(t.get('strategy',''))}
            {td(_p(ep), mono=True)}
            {td(f'<span style="color:{R};font-family:SF Mono,monospace">{_p(t.get("stop_loss"))}</span>')}
            {td(_p(t.get('take_profit')), mono=True)}
            {td(_p(t.get('commission_entry'), 0) if t.get('commission_entry') else '—', mono=True)}
            {td(_p(t.get('tsl')) if t.get('tsl') else '—', mono=True)}
            {td(live_cell(live, ep, chg))}
            {td(str(t.get('exit_date','') or '')[:10] or '—')}
            {td(num(t.get('exit_qty')), mono=True)}
            {td(_p(t.get('exit_price')) if t.get('exit_price') else '—', mono=True)}
            {td(_p(t.get('commission_exit'), 0) if t.get('commission_exit') else '—', mono=True)}
            {td(rs or '—')}
            {td(pnl_chip(pnl, r, is_open=(t["status"]=="OPEN")), align="right")}
        </tr>""")

    th_style = f"padding:9px 12px;text-align:left;color:{MUTED};font-size:0.68rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:600;white-space:nowrap;border-bottom:2px solid {BORDER};background:{HEADER_BG}"

    table_html = f"""
    <div style="overflow-x:auto;border-radius:12px;border:1px solid {BORDER};
        box-shadow:0 1px 4px rgba(0,0,0,0.06);background:{BG}">
    <table style="width:100%;border-collapse:collapse;font-size:0.82rem">
        <thead>
        <tr>{"".join(f'<th style="{th_style}">{h}</th>' for h in headers)}</tr>
        </thead>
        <tbody>{"".join(rows_html)}</tbody>
    </table>
    </div>"""

    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Trade Actions ──────────────────────────────────────────────────────
    a1, a2, a3 = st.columns(3)
    with a1:
        open_opts=[f"#{t['id']} {t['ticker']} ({t['strategy']})" for t in trades if t["status"]=="OPEN"]
        if open_opts:
            sel=st.selectbox("Exit trade",open_opts)
            if st.button("Exit Selected →", type="primary", use_container_width=True):
                tid=int(sel.split("#")[1].split(" ")[0])
                trade=next((t for t in trades if t["id"]==tid),None)
                if trade: exit_trade_dialog(trade)
        else: st.caption("No open trades.")
    with a2:
        # Edit any trade
        all_opts=[f"#{t['id']} {t['ticker']} {str(t.get('entry_date',''))[:10]}" for t in trades]
        if all_opts:
            sel_edit=st.selectbox("Edit trade", all_opts, key="edit_sel")
            if st.button("✏️ Edit", type="secondary", use_container_width=True):
                tid=int(sel_edit.split("#")[1].split(" ")[0])
                trade=next((t for t in trades if t["id"]==tid),None)
                if trade: edit_trade_dialog(trade)
    with a3:
        all_opts2=[f"#{t['id']} {t['ticker']} {str(t.get('entry_date',''))[:10]}" for t in trades]
        if all_opts2:
            sel_del=st.selectbox("Delete trade", all_opts2, key="del_sel")
            if st.button("🗑 Delete", type="secondary", use_container_width=True):
                tid=int(sel_del.split("#")[1].split(" ")[0])
                delete_trade(tid); st.success("Deleted."); st.rerun()
