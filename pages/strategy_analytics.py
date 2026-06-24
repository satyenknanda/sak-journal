import streamlit as st
import plotly.graph_objects as go
import numpy as np
from theme import *

def _get_strategy_stats(trades):
    strategies = {}
    for t in trades:
        s = t.get("strategy","Unknown") or "Unknown"
        r = float(t.get("r_multiple") or 0)
        ep = float(t.get("entry_price") or 0)
        xp = float(t.get("exit_price") or 0)
        pnl = float(t.get("pnl") or 0)
        mae = float(t.get("mae_price") or 0)
        mfe = float(t.get("mfe_price") or 0)
        side = str(t.get("side","")).upper()
        if s not in strategies:
            strategies[s] = {"rs":[],"pnls":[],"eps":[],"xps":[],"maes":[],"mfes":[],"sides":[]}
        strategies[s]["rs"].append(r)
        strategies[s]["pnls"].append(pnl)
        strategies[s]["eps"].append(ep)
        strategies[s]["xps"].append(xp)
        strategies[s]["maes"].append(mae)
        strategies[s]["mfes"].append(mfe)
        strategies[s]["sides"].append(side)
    result = {}
    for s, d in strategies.items():
        rs = d["rs"]
        wins = [r for r in rs if r > 0]
        losses = [r for r in rs if r < 0]
        wr = len(wins)/len(rs) if rs else 0
        exp = float(np.mean(rs)) if rs else 0
        avg_win = float(np.mean(wins)) if wins else 0
        avg_loss = float(np.mean(losses)) if losses else 0
        rr = abs(avg_win/avg_loss) if avg_loss else 0
        # MFE-based available R
        avail_rs = []
        for ep, mfe, sl, side in zip(d["eps"], d["mfes"], 
            [0]*len(d["eps"]), d["sides"]):
            if ep > 0 and mfe > 0:
                risk = ep * 0.025  # approx 2.5% risk
                if side in ("LONG","BUY"):
                    avail_r = (mfe - ep) / risk if risk else 0
                else:
                    avail_r = (ep - mfe) / risk if risk else 0
                avail_rs.append(avail_r)
        avg_avail = float(np.mean(avail_rs)) if avail_rs else 0
        result[s] = {
            "n": len(rs), "rs": rs, "wins": wins, "losses": losses,
            "wr": wr, "exp": exp, "avg_win": avg_win, "avg_loss": avg_loss,
            "rr": rr, "pnls": d["pnls"], "avg_avail": avg_avail,
            "avail_rs": avail_rs,
        }
    return result

VERDICTS = [
    ("Best edge",    lambda s: s["exp"] >= 3.0 and s["wr"] >= 0.5,  "#10B981", "#D1FAE5"),
    ("Strong edge",  lambda s: s["exp"] >= 1.5 and s["wr"] >= 0.4,  "#3B82F6", "#DBEAFE"),
    ("Active",       lambda s: s["exp"] >= 0.5,                      "#6366F1", "#EDE9FE"),
    ("Marginal",     lambda s: s["exp"] >= 0.0,                      "#F59E0B", "#FEF3C7"),
    ("Negative",     lambda s: s["exp"] < 0.0 and s["n"] >= 10,     "#EF4444", "#FEE2E2"),
    ("Small sample", lambda s: s["n"] < 10,                          "#94A3B8", "#F1F5F9"),
    ("Early stage",  lambda s: True,                                  "#64748B", "#F8FAFC"),
]

def _verdict(st_data):
    for label, fn, color, bg in VERDICTS:
        if fn(st_data):
            return label, color, bg
    return "Early stage", "#64748B", "#F8FAFC"

STRAT_COLORS = {
    "VCP": "#10B981", "REVERSAL": "#3B82F6", "EP": "#F59E0B",
    "SVRO": "#8B5CF6", "NR 1HR": "#EC4899", "Chirag Reversal": "#06B6D4",
    "1M ORB": "#EF4444", "Oops Reversal": "#F97316", "RANDOM": "#94A3B8",
    "EP PULLBACKS": "#6366F1",
}

def _strat_color(s):
    return STRAT_COLORS.get(s, "#64748B")

def render():
    st.markdown("## Strategy Analytics")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:18px;font-size:11px">Van Tharp System · FY 2026-27</p>', unsafe_allow_html=True)

    from data.db import get_trades
    all_trades = get_trades()
    closed = [t for t in all_trades if t.get("status")=="CLOSED" and t.get("r_multiple")]
    if not closed:
        st.info("No closed trades with R-multiple data."); return

    stats = _get_strategy_stats(closed)
    # Sort by expectancy desc
    sorted_strats = sorted(stats.items(), key=lambda x: -x[1]["exp"])

    sub1, sub2, sub3, sub4, sub5 = st.tabs(["📊 Overview", "📈 Running Expectancy", "🚀 Growth Simulator", "📉 R Capture", "🎯 MAE / MFE"])

    # ═══════════════════════════════════════════════════════
    # SUB-TAB 1: OVERVIEW
    # ═══════════════════════════════════════════════════════
    with sub1:
        # KPIs
        total_exp = float(np.mean([float(t.get("r_multiple") or 0) for t in closed]))
        total_wr  = sum(1 for t in closed if float(t.get("r_multiple") or 0) > 0) / len(closed) * 100
        wins_all  = sum(1 for t in closed if float(t.get("r_multiple") or 0) > 0)
        total_pnl = sum(float(t.get("pnl") or 0) for t in closed)

        k1, k2, k3, k4 = st.columns(4)
        for col, (label, val, color) in zip([k1,k2,k3,k4], [
            ("Combined Expectancy", f"{total_exp:+.2f}R", TEAL if total_exp>=0 else RED),
            ("System Win Rate",     f"{total_wr:.1f}%",   TEAL if total_wr>=40 else AMBER),
            ("Total Trades",        f"{wins_all}W / {len(closed)-wins_all}L of {len(closed)}", TEXT_H),
            ("Strategies Tracked",  str(len(stats)),       TEXT_H),
        ]):
            col.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 16px;box-shadow:{SHADOW_SM}">
                <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:6px">{label}</div>
                <div style="font-size:22px;font-weight:700;color:{color}">{val}</div>
            </div>''', unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        ch1, ch2 = st.columns([1.6, 1])
        with ch1:
            # RR vs Achievable Win Rate chart
            st.markdown(f'<p style="font-size:11px;font-weight:600;color:{TEXT_H};margin-bottom:4px">RR vs Achievable Win Rate</p>', unsafe_allow_html=True)
            st.caption("Sweet spot 3R–6R · Triangles = your strategies")

            fig_rr = go.Figure()
            # Break-even curve
            rr_vals = np.array([1,2,3,4,5,6,8,10])
            be_wr   = 1 / (1 + rr_vals) * 100
            fig_rr.add_trace(go.Scatter(x=rr_vals, y=be_wr, mode="lines+markers",
                line=dict(color=TEXT_H, width=2),
                marker=dict(size=7, color=TEXT_H),
                name="Break-even WR", hovertemplate="RR: %{x}R<br>Need WR: %{y:.1f}%<extra></extra>"))

            # Sweet spot shading
            fig_rr.add_vrect(x0=3, x1=6, fillcolor="rgba(16,185,129,0.08)",
                line_width=0, annotation_text="sweet spot",
                annotation_position="top left",
                annotation_font=dict(color=TEAL, size=10))

            # Strategy triangles
            for s, d in sorted_strats:
                if d["n"] < 3: continue
                fig_rr.add_trace(go.Scatter(
                    x=[d["rr"]], y=[d["wr"]*100],
                    mode="markers+text",
                    marker=dict(symbol="triangle-up", size=14, color=_strat_color(s),
                                line=dict(color="white", width=1)),
                    text=[s], textposition="top center",
                    textfont=dict(size=9, color=_strat_color(s)),
                    name=s, showlegend=False,
                    hovertemplate=f"<b>{s}</b><br>RR: {d['rr']:.2f}:1<br>WR: {d['wr']*100:.1f}%<br>Exp: {d['exp']:+.2f}R<extra></extra>"))

            l_rr = chart_layout(height=340, title="")
            l_rr["paper_bgcolor"] = "#FFFFFF"
            l_rr["plot_bgcolor"]  = "#FFFFFF"
            l_rr["xaxis"] = dict(title=dict(text="Reward:Risk Ratio", font=dict(size=10)),
                tickvals=[1,2,3,4,5,6,8,10],
                ticktext=["1R","2R","3R","4R","5R","6R","8R","10R"],
                gridcolor=BORDER_LIGHT, showgrid=True)
            l_rr["yaxis"] = dict(title=dict(text="Win Rate %", font=dict(size=10)),
                ticksuffix="%", gridcolor=BORDER_LIGHT, showgrid=True, range=[0,85])
            l_rr["showlegend"] = False
            fig_rr.update_layout(**l_rr)
            st.plotly_chart(fig_rr, use_container_width=True, config={"displayModeBar":False}, key="strat_rr_chart")

        with ch2:
            # Strategy Map bubble chart (Win Rate vs RR, bubble = |expectancy|)
            st.markdown(f'<p style="font-size:11px;font-weight:600;color:{TEXT_H};margin-bottom:4px">Strategy Map</p>', unsafe_allow_html=True)
            st.caption("Bubble size = |expectancy| · top-right = ideal")

            fig_map = go.Figure()
            for s, d in sorted_strats:
                if d["n"] < 2: continue
                fig_map.add_trace(go.Scatter(
                    x=[d["wr"]*100], y=[d["rr"]],
                    mode="markers+text",
                    marker=dict(size=max(12, min(50, abs(d["exp"])*8)),
                                color=_strat_color(s), opacity=0.8,
                                line=dict(color="white", width=1.5)),
                    text=[s[:3]], textposition="middle center",
                    textfont=dict(size=8, color="white", family="Inter"),
                    name=s,
                    hovertemplate=f"<b>{s}</b><br>WR: {d['wr']*100:.1f}%<br>RR: {d['rr']:.2f}:1<br>Exp: {d['exp']:+.2f}R<extra></extra>"))

            l_map = chart_layout(height=340, title="")
            l_map["paper_bgcolor"] = "#FFFFFF"
            l_map["plot_bgcolor"]  = "#FFFFFF"
            l_map["xaxis"] = dict(title=dict(text="Win Rate", font=dict(size=10)),
                ticksuffix="%", gridcolor=BORDER_LIGHT, showgrid=True)
            l_map["yaxis"] = dict(title=dict(text="RR Ratio", font=dict(size=10)),
                ticksuffix="R", gridcolor=BORDER_LIGHT, showgrid=True)
            l_map["showlegend"] = False
            fig_map.update_layout(**l_map)
            st.plotly_chart(fig_map, use_container_width=True, config={"displayModeBar":False}, key="strat_map_chart")

        # Strategy Performance Summary table
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:10px;font-weight:600;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">Strategy Performance Summary</p>', unsafe_allow_html=True)

        TH = f"padding:10px 14px;font-size:10px;color:white;font-weight:500;text-transform:uppercase;letter-spacing:0.06em;background:#1E293B;border-bottom:1px solid {BORDER}"
        TD = f"padding:9px 14px;font-size:12.5px;border-bottom:1px solid {BORDER_LIGHT}"

        rows_html = ""
        for s, d in sorted_strats:
            verdict, vc, vbg = _verdict(d)
            dot = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{_strat_color(s)};margin-right:6px"></span>'
            rows_html += f"""<tr>
                <td style="{TD};font-weight:600;color:{TEXT_H}">{dot}{s}</td>
                <td style="{TD};text-align:center">{d['n']}</td>
                <td style="{TD};text-align:center;color:{'#10B981' if d['wr']>=0.4 else '#F59E0B'}">{d['wr']*100:.1f}%</td>
                <td style="{TD};text-align:center;color:#10B981">{d['avg_win']:+.2f}R</td>
                <td style="{TD};text-align:center;color:#EF4444">{d['avg_loss']:+.2f}R</td>
                <td style="{TD};text-align:center;font-weight:600;color:{'#10B981' if d['exp']>=0 else '#EF4444'}">{d['exp']:+.2f}R</td>
                <td style="{TD};text-align:center">{d['rr']:.2f}:1</td>
                <td style="{TD};text-align:center"><span style="background:{vbg};color:{vc};padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600">{verdict}</span></td>
            </tr>"""

        st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER}">
        <table style="width:100%;border-collapse:collapse">
            <thead><tr>
                <th style="{TH};text-align:left">Strategy</th>
                <th style="{TH};text-align:center">Trades</th>
                <th style="{TH};text-align:center">Win Rate</th>
                <th style="{TH};text-align:center">Avg Win R</th>
                <th style="{TH};text-align:center">Avg Loss R</th>
                <th style="{TH};text-align:center">Expectancy</th>
                <th style="{TH};text-align:center">RR</th>
                <th style="{TH};text-align:center">Verdict</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table></div>""", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════
    # SUB-TAB 2: RUNNING EXPECTANCY
    # ═══════════════════════════════════════════════════════
    with sub2:
        st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE};margin-bottom:12px">Running expectancy (cumR ÷ N) vs theoretical. Green dashed = theoretical · Red = actual</p>', unsafe_allow_html=True)

        cols_per_row = 2
        strats_with_data = [(s,d) for s,d in sorted_strats if d["n"] >= 2]
        for i in range(0, len(strats_with_data), cols_per_row):
            row_cols = st.columns(cols_per_row)
            for j, (s, d) in enumerate(strats_with_data[i:i+cols_per_row]):
                with row_cols[j]:
                    rs = d["rs"]
                    cum_exp = [sum(rs[:k+1])/(k+1) for k in range(len(rs))]
                    theory  = [d["exp"]] * len(rs)
                    fig_re = go.Figure()
                    fig_re.add_trace(go.Scatter(
                        x=list(range(1, len(rs)+1)), y=theory,
                        mode="lines", line=dict(color=TEAL, width=1.5, dash="dash"),
                        name="Theory Expectancy"))
                    fig_re.add_trace(go.Scatter(
                        x=list(range(1, len(rs)+1)), y=cum_exp,
                        mode="lines", line=dict(color=RED, width=2),
                        name="Actual Expectancy",
                        fill="tozeroy", fillcolor="rgba(239,68,68,0.08)"))
                    l_re = chart_layout(height=220, title="")
                    l_re["paper_bgcolor"] = "#FFFFFF"
                    l_re["plot_bgcolor"]  = "#FFFFFF"
                    l_re["xaxis"]["title"] = dict(text="Trades", font=dict(size=9))
                    l_re["yaxis"]["ticksuffix"] = "R"
                    l_re["showlegend"] = True
                    l_re["legend"] = dict(orientation="h", y=-0.25, x=0.5, xanchor="center",
                        font=dict(size=9), bgcolor="rgba(0,0,0,0)")
                    l_re["margin"] = dict(l=50, r=20, t=30, b=50)
                    fig_re.update_layout(**l_re)
                    st.markdown(f'<p style="font-size:11px;font-weight:600;color:{_strat_color(s)};margin-bottom:2px">{s} — Running Expectancy · Final: {d["exp"]:+.2f}R · {d["n"]} trades</p>', unsafe_allow_html=True)
                    st.plotly_chart(fig_re, use_container_width=True, config={"displayModeBar":False}, key=f"re_{s}")

    # ═══════════════════════════════════════════════════════
    # SUB-TAB 3: GROWTH SIMULATOR
    # ═══════════════════════════════════════════════════════
    with sub3:
        st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE};margin-bottom:4px">Account balance growth simulation · 0.4% risk per trade · Actual avg win/loss R from journal</p>', unsafe_allow_html=True)
        n_trades = st.slider("Trades to simulate", 50, 500, 200, 10, key="growth_sim_slider")

        risk_pct = 0.004  # 0.4% per trade
        fig_gs = go.Figure()

        for s, d in sorted_strats:
            if d["n"] < 3: continue
            balance = 100.0
            curve = [balance]
            wr = d["wr"]
            avg_win = d["avg_win"]
            avg_loss = d["avg_loss"]
            np.random.seed(42)
            for _ in range(n_trades):
                win = np.random.random() < wr
                r = avg_win if win else avg_loss
                balance = balance * (1 + risk_pct * r)
                curve.append(balance)
            pct_curve = [(v/100 - 1)*100 for v in curve]
            fig_gs.add_trace(go.Scatter(
                x=list(range(n_trades+1)), y=pct_curve,
                mode="lines", name=f"{s} ({d['exp']:+.2f}R)",
                line=dict(color=_strat_color(s), width=2),
                hovertemplate=f"<b>{s}</b><br>Trade: %{{x}}<br>Balance: %{{y:+.1f}}%<extra></extra>"))

        l_gs = chart_layout(height=380, title="Account Balance Growth Simulation")
        l_gs["paper_bgcolor"] = "#FFFFFF"
        l_gs["plot_bgcolor"]  = "#FFFFFF"
        l_gs["xaxis"]["title"] = dict(text="Number of trades", font=dict(size=10))
        l_gs["yaxis"]["title"] = dict(text="Account balance (%)", font=dict(size=10))
        l_gs["yaxis"]["ticksuffix"] = "%"
        l_gs["showlegend"] = True
        l_gs["legend"] = dict(orientation="h", y=-0.18, x=0.5, xanchor="center",
            font=dict(size=10), bgcolor="rgba(0,0,0,0)")
        fig_gs.update_layout(**l_gs)
        st.plotly_chart(fig_gs, use_container_width=True, config={"displayModeBar":False}, key="growth_sim_chart")

        # Strategy summary cards
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        card_cols = st.columns(min(5, len([s for s,d in sorted_strats if d["n"]>=3])))
        for i, (s, d) in enumerate([x for x in sorted_strats if x[1]["n"]>=3][:5]):
            balance = 100.0
            np.random.seed(42)
            for _ in range(n_trades):
                win = np.random.random() < d["wr"]
                r = d["avg_win"] if win else d["avg_loss"]
                balance = balance * (1 + risk_pct * r)
            final_pct = (balance/100 - 1)*100
            color = TEAL if final_pct >= 0 else RED
            card_cols[i].markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-left:3px solid {_strat_color(s)};border-radius:10px;padding:14px 16px">
                <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px">{s}</div>
                <div style="font-size:22px;font-weight:700;color:{color}">{final_pct:+.0f}%</div>
                <div style="font-size:11px;color:{TEXT_SUBTLE}">{d["exp"]:+.2f}R/trade</div>
            </div>''', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════
    # SUB-TAB 4: MAE / MFE
    # ═══════════════════════════════════════════════════════
    with sub5:
        mae_trades = [t for t in closed if t.get("mae_price") and t.get("mfe_price") and t.get("entry_price")]
        if not mae_trades:
            st.info("No MAE/MFE data available."); return

        # KPIs
        def calc_avail_r(t):
            ep = float(t.get("entry_price") or 0)
            sl = float(t.get("stop_loss") or 0)
            mfe = float(t.get("mfe_price") or 0)
            side = str(t.get("side","")).upper()
            if ep <= 0: return 0
            risk = abs(ep - sl) if sl else ep * 0.025
            if risk == 0: return 0
            return (mfe - ep) / risk if side in ("LONG","BUY") else (ep - mfe) / risk

        def calc_cap_r(t):
            return float(t.get("r_multiple") or 0)

        avail_rs = [calc_avail_r(t) for t in mae_trades]
        cap_rs   = [calc_cap_r(t) for t in mae_trades]
        cap_pcts = [cap/avail*100 if avail > 0 else 0 for cap, avail in zip(cap_rs, avail_rs)]

        avg_avail = float(np.mean(avail_rs))
        avg_cap   = float(np.mean(cap_rs))
        avg_cap_pct = float(np.mean([p for p in cap_pcts if abs(p) < 500]))
        r_left    = avg_avail - avg_cap

        m1,m2,m3,m4,m5,m6 = st.columns(6)
        for col, (label, val, color) in zip([m1,m2,m3,m4,m5,m6], [
            ("Trades Tracked",    str(len(mae_trades)),        TEXT_H),
            ("Avg R Avail",       f"{avg_avail:+.2f}R",        TEAL),
            ("Avg R Captured",    f"{avg_cap:+.2f}R",          TEAL if avg_cap>=0 else RED),
            ("Avg MFE Capture",   f"{avg_cap_pct:.1f}%",       TEAL if avg_cap_pct>=50 else AMBER),
            ("Efficiency",        f"{avg_cap_pct:.1f}%",       TEAL if avg_cap_pct>=50 else RED),
            ("R Left/Trade",      f"{r_left:+.2f}R",           RED if r_left > 0 else TEAL),
        ]):
            col.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px">
                <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px">{label}</div>
                <div style="font-size:17px;font-weight:700;color:{color}">{val}</div>
            </div>''', unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        mf1, mf2 = st.columns([1.5, 1])
        with mf1:
            # Exit quality buckets
            st.markdown(f'<p style="font-size:11px;font-weight:600;color:{TEXT_H};margin-bottom:4px">Exit Quality — R Captured Buckets</p>', unsafe_allow_html=True)
            buckets = {"< 1R": 0, "1–2R": 0, "2–4R": 0, "> 4R": 0}
            for r in cap_rs:
                if r < 1: buckets["< 1R"] += 1
                elif r < 2: buckets["1–2R"] += 1
                elif r < 4: buckets["2–4R"] += 1
                else: buckets["> 4R"] += 1
            bk = list(buckets.keys()); bv = list(buckets.values())
            bcolors = [RED, AMBER, TEAL, "#10B981"]
            bcolors_fill = ["rgba(239,68,68,0.2)", "rgba(245,158,11,0.2)", "rgba(16,185,129,0.2)", "rgba(16,185,129,0.35)"]
            fig_bkt = go.Figure(go.Bar(x=bk, y=bv,
                marker=dict(color=bcolors_fill, line=dict(color=bcolors, width=2)),
                text=bv, textposition="outside"))
            l_bkt = chart_layout(height=260, title="")
            l_bkt["paper_bgcolor"] = "#FFFFFF"
            l_bkt["plot_bgcolor"]  = "#FFFFFF"
            l_bkt["yaxis"]["title"] = dict(text="Trades", font=dict(size=10))
            fig_bkt.update_layout(**l_bkt)
            st.plotly_chart(fig_bkt, use_container_width=True, config={"displayModeBar":False}, key="mfe_buckets")

        with mf2:
            # MFE capture % donut
            st.markdown(f'<p style="font-size:11px;font-weight:600;color:{TEXT_H};margin-bottom:4px">MFE Capture % Distribution</p>', unsafe_allow_html=True)
            pct_buckets = {"< 20%": 0, "20–40%": 0, "40–60%": 0, "60–80%": 0, "> 80%": 0}
            for p in cap_pcts:
                if p < 0: pct_buckets["< 20%"] += 1
                elif p < 20: pct_buckets["< 20%"] += 1
                elif p < 40: pct_buckets["20–40%"] += 1
                elif p < 60: pct_buckets["40–60%"] += 1
                elif p < 80: pct_buckets["60–80%"] += 1
                else: pct_buckets["> 80%"] += 1
            fig_donut = go.Figure(go.Pie(
                labels=list(pct_buckets.keys()), values=list(pct_buckets.values()),
                hole=0.55, marker=dict(colors=[RED, AMBER, "#6366F1", TEAL, "#10B981"]),
                textinfo="label+percent", textfont=dict(size=10)))
            l_d = chart_layout(height=260, title="")
            l_d["paper_bgcolor"] = "#FFFFFF"
            l_d["plot_bgcolor"]  = "#FFFFFF"
            l_d["showlegend"] = False
            fig_donut.update_layout(**l_d)
            st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar":False}, key="mfe_donut")

        # By strategy table
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:10px;font-weight:600;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">By Strategy — R Available vs Captured</p>', unsafe_allow_html=True)

        TH2 = f"padding:10px 14px;font-size:10px;color:white;font-weight:500;text-transform:uppercase;letter-spacing:0.06em;background:#1E293B;border-bottom:1px solid {BORDER}"
        TD2 = f"padding:9px 14px;font-size:12.5px;border-bottom:1px solid {BORDER_LIGHT}"

        strat_mae = {}
        for t in mae_trades:
            s = t.get("strategy","Unknown") or "Unknown"
            if s not in strat_mae:
                strat_mae[s] = {"avail":[], "cap":[], "pct":[]}
            av = calc_avail_r(t); cp = calc_cap_r(t)
            strat_mae[s]["avail"].append(av)
            strat_mae[s]["cap"].append(cp)
            if av > 0: strat_mae[s]["pct"].append(cp/av*100)

        rows2 = ""
        for s in sorted(strat_mae.keys(), key=lambda x: -len(strat_mae[x]["avail"])):
            d2 = strat_mae[s]
            avg_av = float(np.mean(d2["avail"]))
            avg_cp = float(np.mean(d2["cap"]))
            avg_pt = float(np.mean(d2["pct"])) if d2["pct"] else 0
            r_left2 = avg_av - avg_cp
            dot = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{_strat_color(s)};margin-right:6px"></span>'
            rows2 += f"""<tr>
                <td style="{TD2};font-weight:600">{dot}{s}</td>
                <td style="{TD2};text-align:center">{len(d2['avail'])}</td>
                <td style="{TD2};text-align:center;color:{TEAL}">{avg_av:+.2f}R</td>
                <td style="{TD2};text-align:center;color:{'#10B981' if avg_cp>=0 else RED}">{avg_cp:+.2f}R</td>
                <td style="{TD2};text-align:center;color:{'#10B981' if avg_pt>=50 else AMBER}">{avg_pt:.1f}%</td>
                <td style="{TD2};text-align:center;color:{RED}">{r_left2:+.2f}R</td>
            </tr>"""

        st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER}">
        <table style="width:100%;border-collapse:collapse">
            <thead><tr>
                <th style="{TH2};text-align:left">Strategy</th>
                <th style="{TH2};text-align:center">Trades</th>
                <th style="{TH2};text-align:center">Avg R Avail</th>
                <th style="{TH2};text-align:center">Avg R Captured</th>
                <th style="{TH2};text-align:center">Capture %</th>
                <th style="{TH2};text-align:center">R Left on Table</th>
            </tr></thead>
            <tbody>{rows2}</tbody>
        </table></div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    with sub4:
        st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE};margin-bottom:12px">Cumulative R — available vs captured · Green area = total available R · Red line = actual R captured · gap = R left on table</p>', unsafe_allow_html=True)

        mae_trades2 = [t for t in closed if t.get("mae_price") and t.get("mfe_price") and t.get("entry_price")]
        def calc_avail_r2(t):
            ep = float(t.get("entry_price") or 0)
            sl = float(t.get("stop_loss") or 0)
            mfe = float(t.get("mfe_price") or 0)
            side = str(t.get("side","")).upper()
            if ep <= 0: return 0
            risk = abs(ep - sl) if sl else ep * 0.025
            if risk == 0: return 0
            return (mfe - ep) / risk if side in ("LONG","BUY") else (ep - mfe) / risk

        strat_mae2 = {}
        for t in mae_trades2:
            s = t.get("strategy","Unknown") or "Unknown"
            if s not in strat_mae2:
                strat_mae2[s] = {"avail":[], "cap":[]}
            strat_mae2[s]["avail"].append(calc_avail_r2(t))
            strat_mae2[s]["cap"].append(float(t.get("r_multiple") or 0))

        strats_mfe = [(s,d) for s,d in sorted_strats if s in strat_mae2 and strat_mae2[s]["avail"]]
        for i in range(0, len(strats_mfe), 2):
            row_c = st.columns(2)
            for j, (s, d) in enumerate(strats_mfe[i:i+2]):
                with row_c[j]:
                    sm = strat_mae2[s]
                    n = len(sm["avail"])
                    cum_avail = np.cumsum(sm["avail"]).tolist()
                    cum_cap   = np.cumsum(sm["cap"]).tolist()
                    fig_mc = go.Figure()
                    fig_mc.add_trace(go.Scatter(
                        x=list(range(1,n+1)), y=cum_avail,
                        mode="lines", name="Available R",
                        line=dict(color="#4CAF50", width=2),
                        fill="tozeroy", fillcolor="rgba(76,175,80,0.15)"))
                    fig_mc.add_trace(go.Scatter(
                        x=list(range(1,n+1)), y=cum_cap,
                        mode="lines", name="Actual R",
                        line=dict(color="#8B1A1A", width=2)))
                    fig_mc.add_hline(y=0, line=dict(color="#CCCCCC", width=1, dash="dot"))
                    l_mc = chart_layout(height=280, title="")
                    l_mc["paper_bgcolor"] = "#FFFFFF"
                    l_mc["plot_bgcolor"]  = "#FFFFFF"
                    l_mc["xaxis"] = dict(showgrid=True, gridcolor="#F0F0F0",
                        title=dict(text="Trades", font=dict(size=9, color="#666")),
                        tickfont=dict(color="#666", size=9))
                    l_mc["yaxis"] = dict(showgrid=True, gridcolor="#F0F0F0",
                        ticksuffix="R", tickfont=dict(color="#666", size=9),
                        tickprefix="+", zeroline=False)
                    l_mc["showlegend"] = True
                    l_mc["legend"] = dict(orientation="h", y=-0.25, x=0.5, xanchor="center",
                        font=dict(size=9, color="#666"), bgcolor="rgba(0,0,0,0)")
                    l_mc["margin"] = dict(l=55, r=20, t=10, b=55)
                    fig_mc.update_layout(**l_mc)
                    st.markdown(f'<p style="font-size:11px;font-weight:600;color:{_strat_color(s)};margin-bottom:2px">{s} — {n} trades · {d["wr"]*100:.1f}% WR · {d["exp"]:+.2f}R</p>', unsafe_allow_html=True)
                    st.caption("Green area = cumulative available R · Red = actual R captured · gap = left on table")
                    st.plotly_chart(fig_mc, use_container_width=True, config={"displayModeBar":False}, key=f"mfe_chart_{s}")
