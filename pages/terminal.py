# -*- coding: utf-8 -*-
"""
Terminal page — draggable/resizable multi-panel trading dashboard
using streamlit-elements (react-grid-layout under the hood).
"""
import streamlit as st
from datetime import date, datetime
import pandas as pd

from theme import *
from data.db import get_trades, get_kpi_summary_extended as get_kpi

G="#10B981"; R="#EF4444"; B="#3B82F6"; AM="#F59E0B"; MUTED="#6B7280"

try:
    from streamlit_elements import elements, mui, html, dashboard, nivo
    HAS_ELEMENTS = True
except ImportError:
    HAS_ELEMENTS = False


def render():
    st.markdown("## 🖥️ Terminal")
    st.markdown(f'<p style="color:{MUTED};margin-top:-10px;margin-bottom:14px;font-size:0.85rem">Drag panels by their title bar · Resize from the bottom-right corner</p>', unsafe_allow_html=True)

    if not HAS_ELEMENTS:
        st.error("`streamlit-elements` is not installed. Add `streamlit-elements` to requirements.txt and redeploy.")
        st.code("pip install streamlit-elements", language="bash")
        return

    # ── Load data ────────────────────────────────────────────────────────────
    all_trades = get_trades()
    open_trades = [t for t in all_trades if t.get("status") == "OPEN"]
    closed_trades = [t for t in all_trades if t.get("status") == "CLOSED"]
    kpi = get_kpi() or {}

    unrealized = 0.0
    for t in open_trades:
        live = t.get("live_price"); ep = t.get("entry_price")
        if live and ep:
            qty = float(t.get("qty") or 0)
            side = str(t.get("side","")).upper()
            lp, epf = float(live), float(ep)
            pnl = (lp-epf)*qty if side in ("BUY","LONG") else (epf-lp)*qty
            unrealized += pnl

    total_pnl = kpi.get("total_pnl", 0)
    win_rate = kpi.get("win_rate", 0)  # already a percentage from get_kpi_summary_extended

    # Cumulative P&L curve from closed trades — aggregate by exit DATE
    # (avoids duplicate x-axis points when multiple trades close same day)
    sorted_closed = sorted(closed_trades, key=lambda x: str(x.get("exit_date") or ""))
    from collections import defaultdict
    daily_pnl = defaultdict(float)
    for t in sorted_closed:
        d = str(t.get("exit_date",""))[:10]
        if d:
            daily_pnl[d] += float(t.get("pnl") or 0)

    cum = 0
    curve = []
    for d in sorted(daily_pnl.keys())[-30:]:  # last 30 trading days
        cum += daily_pnl[d]
        curve.append({"x": d, "y": round(cum,0)})

    # Streak calculation
    streak = 0
    streak_type = None
    for t in reversed(sorted_closed):
        p = float(t.get("pnl") or 0)
        if p == 0: continue
        this_type = "win" if p>0 else "loss"
        if streak_type is None:
            streak_type = this_type; streak = 1
        elif this_type == streak_type:
            streak += 1
        else:
            break

    # ── Layout definition (x, y, w, h in grid units) ────────────────────────
    layout = [
        dashboard.Item("holdings", 0, 0, 4, 4),
        dashboard.Item("performance", 4, 0, 5, 4),
        dashboard.Item("streak", 9, 0, 3, 4),
        dashboard.Item("openpos", 0, 4, 6, 4),
        dashboard.Item("strategy", 6, 4, 6, 4),
    ]

    with elements("terminal_grid"):
        with dashboard.Grid(layout, draggableHandle=".drag-handle"):

            # ── Panel: Portfolio Holdings ────────────────────────────────
            with mui.Paper(key="holdings", sx={"display":"flex","flexDirection":"column","height":"100%","borderRadius":"12px","overflow":"hidden"}):
                with mui.Box(className="drag-handle", sx={"bgcolor":"#111827","color":"white","px":2,"py":1,"cursor":"move","fontSize":"12px","fontWeight":700,"letterSpacing":"0.05em"}):
                    mui.Typography("📊 OPEN POSITIONS", variant="caption", sx={"fontWeight":700})
                with mui.Box(sx={"p":2,"overflowY":"auto","flex":1}):
                    # Combine same-ticker open positions for display (sum P&L, sum qty)
                    _combined = {}
                    for t in open_trades:
                        tk = t.get("ticker","")
                        pnl = 0
                        live=t.get("live_price"); ep=t.get("entry_price")
                        if live and ep:
                            qty=float(t.get("qty") or 0); side=str(t.get("side","")).upper()
                            lp,epf=float(live),float(ep)
                            pnl=(lp-epf)*qty if side in ("BUY","LONG") else (epf-lp)*qty
                        if tk not in _combined:
                            _combined[tk] = {"pnl":0.0,"qty":0.0}
                        _combined[tk]["pnl"] += pnl
                        _combined[tk]["qty"] += float(t.get("qty") or 0)

                    mui.Typography(f"{len(_combined)} Active", variant="h6", sx={"fontWeight":700,"mb":1})
                    for tk, agg in list(_combined.items())[:6]:
                        color = "#10B981" if agg["pnl"]>=0 else "#EF4444"
                        with mui.Box(sx={"display":"flex","justifyContent":"space-between","py":0.7,"borderBottom":"1px solid #F3F4F6"}):
                            mui.Typography(tk, sx={"fontWeight":700,"fontSize":"13px"})
                            mui.Typography(f"{'+' if agg['pnl']>=0 else ''}₹{agg['pnl']:,.0f}", sx={"color":color,"fontWeight":700,"fontSize":"13px"})

            # ── Panel: Performance Chart ─────────────────────────────────
            with mui.Paper(key="performance", sx={"display":"flex","flexDirection":"column","height":"100%","borderRadius":"12px","overflow":"hidden"}):
                with mui.Box(className="drag-handle", sx={"bgcolor":"#111827","color":"white","px":2,"py":1,"cursor":"move","fontSize":"12px","fontWeight":700,"letterSpacing":"0.05em"}):
                    mui.Typography("📈 PORTFOLIO PERFORMANCE", variant="caption", sx={"fontWeight":700})
                with mui.Box(sx={"p":1,"flex":1}):
                    if curve:
                        nivo.Line(
                            data=[{"id":"P&L","data":curve}],
                            margin={"top":20,"right":20,"bottom":40,"left":50},
                            xScale={"type":"point"},
                            yScale={"type":"linear","min":"auto","max":"auto"},
                            curve="monotoneX",
                            axisBottom={"tickRotation":-30,"tickSize":0},
                            axisLeft={"tickSize":0},
                            enableArea=True,
                            areaOpacity=0.15,
                            colors=["#10B981" if total_pnl>=0 else "#EF4444"],
                            lineWidth=2,
                            pointSize=0,
                            enableGridX=False,
                            theme={"axis":{"ticks":{"text":{"fontSize":10}}}},
                        )
                    else:
                        mui.Typography("No closed trades yet", sx={"p":2,"color":"#9CA3AF"})

            # ── Panel: Streak Analysis ────────────────────────────────────
            with mui.Paper(key="streak", sx={"display":"flex","flexDirection":"column","height":"100%","borderRadius":"12px","overflow":"hidden"}):
                with mui.Box(className="drag-handle", sx={"bgcolor":"#111827","color":"white","px":2,"py":1,"cursor":"move","fontSize":"12px","fontWeight":700,"letterSpacing":"0.05em"}):
                    mui.Typography("🔥 STREAK", variant="caption", sx={"fontWeight":700})
                with mui.Box(sx={"p":2,"textAlign":"center","flex":1,"display":"flex","flexDirection":"column","justifyContent":"center"}):
                    color = "#10B981" if streak_type=="win" else "#EF4444"
                    label = "WINNING" if streak_type=="win" else "LOSING" if streak_type=="loss" else "—"
                    mui.Typography(f"W{streak}" if streak_type=="win" else f"L{streak}" if streak_type=="loss" else "—",
                                    sx={"fontSize":"42px","fontWeight":800,"color":color})
                    mui.Typography(label, variant="caption", sx={"color":"#6B7280","fontWeight":600,"letterSpacing":"0.1em"})
                    mui.Typography(f"Win Rate: {win_rate:.1f}%", sx={"mt":2,"fontSize":"13px","fontWeight":600})

            # ── Panel: Open Positions Table ────────────────────────────────
            with mui.Paper(key="openpos", sx={"display":"flex","flexDirection":"column","height":"100%","borderRadius":"12px","overflow":"hidden"}):
                with mui.Box(className="drag-handle", sx={"bgcolor":"#111827","color":"white","px":2,"py":1,"cursor":"move","fontSize":"12px","fontWeight":700,"letterSpacing":"0.05em"}):
                    mui.Typography("💼 ALL OPEN POSITIONS", variant="caption", sx={"fontWeight":700})
                with mui.Box(sx={"p":1,"overflowY":"auto","flex":1}):
                    with mui.Table(size="small"):
                        with mui.TableHead():
                            with mui.TableRow():
                                for h in ["Ticker","Strategy","Entry","Live","P&L"]:
                                    mui.TableCell(h, sx={"fontWeight":700,"fontSize":"11px","color":"#6B7280"})
                        with mui.TableBody():
                            for t in open_trades:
                                live=t.get("live_price"); ep=t.get("entry_price")
                                pnl=0
                                if live and ep:
                                    qty=float(t.get("qty") or 0); side=str(t.get("side","")).upper()
                                    lp,epf=float(live),float(ep)
                                    pnl=(lp-epf)*qty if side in ("BUY","LONG") else (epf-lp)*qty
                                color = "#10B981" if pnl>=0 else "#EF4444"
                                with mui.TableRow():
                                    mui.TableCell(t.get("ticker",""), sx={"fontWeight":700,"fontSize":"12px"})
                                    mui.TableCell(t.get("strategy",""), sx={"fontSize":"12px"})
                                    mui.TableCell(f"₹{float(ep or 0):,.2f}", sx={"fontSize":"12px"})
                                    mui.TableCell(f"₹{float(live or 0):,.2f}" if live else "—", sx={"fontSize":"12px"})
                                    mui.TableCell(f"{'+' if pnl>=0 else ''}₹{pnl:,.0f}", sx={"fontSize":"12px","color":color,"fontWeight":700})

            # ── Panel: Strategy Breakdown ───────────────────────────────
            with mui.Paper(key="strategy", sx={"display":"flex","flexDirection":"column","height":"100%","borderRadius":"12px","overflow":"hidden"}):
                with mui.Box(className="drag-handle", sx={"bgcolor":"#111827","color":"white","px":2,"py":1,"cursor":"move","fontSize":"12px","fontWeight":700,"letterSpacing":"0.05em"}):
                    mui.Typography("🎯 STRATEGY P&L", variant="caption", sx={"fontWeight":700})
                with mui.Box(sx={"p":2,"flex":1,"overflowY":"auto"}):
                    from collections import defaultdict
                    sm = defaultdict(float)
                    for t in closed_trades:
                        sm[t.get("strategy","")] += float(t.get("pnl") or 0)
                    for s, pnl in sorted(sm.items(), key=lambda x: -abs(x[1]))[:8]:
                        color = "#10B981" if pnl>=0 else "#EF4444"
                        with mui.Box(sx={"display":"flex","justifyContent":"space-between","alignItems":"center","py":0.8,"borderBottom":"1px solid #F3F4F6"}):
                            mui.Typography(s or "—", sx={"fontSize":"13px","fontWeight":600})
                            mui.Typography(f"{'+' if pnl>=0 else ''}₹{pnl:,.0f}", sx={"fontSize":"13px","fontWeight":700,"color":color})

    st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')} · Click anywhere and re-run to refresh data")
