import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import calendar as cal
from collections import defaultdict
from datetime import datetime
from data.db import get_journal_trades, get_playbooks, get_trade_playbook
from theme import *

# ── aliases ───────────────────────────────────────────────────────────────
kcard = kpi_card
G = TEAL; R = RED; B = BLUE; AM = AMBER
MUTED = TEXT_MUTED; TEXT = TEXT_H; TEXT2 = TEXT_BODY
DIM = BORDER_LIGHT; BG = PAGE_BG; CARD = CARD_BG; BORDER_C = BORDER

def safe_float(v):
    try: return float(v or 0)
    except: return 0.0

def pnl_color(v): return TEAL if v >= 0 else RED
def fmt_pnl(v): return f"{'+'if v>=0 else ''}₹{abs(v):,.0f}"

def stat_row(label, value):
    return (f'<div style="display:flex;justify-content:space-between;padding:8px 0;'
            f'border-bottom:1px solid {BORDER_LIGHT};font-size:13px">'
            f'<span style="color:{TEXT_MUTED}">{label}</span>'
            f'<span style="color:{TEXT_H};font-weight:500">{value}</span></div>')

def kpi_strip(items):
    html = '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">'
    for label, value, color in items:
        html += (f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;'
                 f'padding:12px 18px;flex:1;min-width:140px">'
                 f'<div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;'
                 f'letter-spacing:0.07em;margin-bottom:4px">{label}</div>'
                 f'<div style="font-size:20px;font-weight:700;color:{color}">{value}</div></div>')
    html += '</div>'
    return html

def line_area_chart(x, y_pnl, y_count=None, y_avg=None, height=260, title=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y_pnl, mode="lines+markers",
        line=dict(color=TEAL, width=2.5, shape="spline"),
        marker=dict(size=7, color=TEAL, line=dict(color="white", width=1.5)),
        fill="tozeroy", fillcolor="rgba(16,185,129,0.25)",
        name="Net P&L", hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"))
    neg = [min(v, 0) for v in y_pnl]
    fig.add_trace(go.Scatter(x=x, y=neg, mode="lines", line=dict(width=0),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.30)", showlegend=False, hoverinfo="skip"))
    if y_count:
        fig.add_trace(go.Scatter(x=x, y=y_count, mode="lines+markers",
            line=dict(color=BLUE, width=1.5, dash="dot"), marker=dict(size=5, color=BLUE),
            name="Trade count", yaxis="y2",
            hovertemplate="%{x}<br>%{y} trades<extra></extra>"))
    if y_avg:
        fig.add_trace(go.Scatter(x=x, y=y_avg, mode="lines+markers",
            line=dict(color=AMBER, width=1.5), marker=dict(size=5, color=AMBER),
            name="Avg win", hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"))
    l = chart_layout(height=height, title=title)
    l["yaxis"]["tickprefix"] = "₹"; l["yaxis"]["tickformat"] = ",.0f"
    if y_count:
        l["yaxis2"] = dict(overlaying="y", side="right", showgrid=False,
                           tickfont=dict(size=10, color=BLUE))
    l["legend"] = dict(orientation="h", y=-0.18, x=0, font=dict(size=10, color=TEXT_MUTED))
    fig.update_layout(**l)
    return fig

def win_rate_chart(x, wrs, height=220):
    fig = go.Figure()
    fig.add_hline(y=0.5, line=dict(color=BLUE, width=1, dash="dash"),
        annotation_text="50%", annotation_font=dict(color=BLUE, size=9))
    fig.add_trace(go.Scatter(x=x, y=wrs, mode="lines+markers",
        line=dict(color=TEAL, width=2.5, shape="spline"),
        marker=dict(size=7, color=[TEAL if w >= 0.5 else RED for w in wrs],
                   line=dict(color="white", width=1.5)),
        fill="tozeroy", fillcolor="rgba(16,185,129,0.20)",
        name="Win %", hovertemplate="%{x}<br>%{y:.1%}<extra></extra>"))
    l = chart_layout(height=height, title="Win Rate")
    l["yaxis"]["tickformat"] = ".0%"; l["yaxis"]["range"] = [0, 1]
    fig.update_layout(**l)
    return fig

def render_chart_pair(x, y_pnl, y_count, y_avg_win, y_wr, key_prefix, height=260):
    """
    Renders two customisable side-by-side charts with metric selector + chart type toggle.
    Left chart: P&L-based metrics. Right chart: Win%-based metrics.
    Both support switching primary metric, adding overlay metrics, and chart type.
    """
    EXTRA_COLORS = [AMBER, BLUE, RED, "#8B5CF6"]

    # ── Available metrics ────────────────────────────────────────────────
    LEFT_METRICS = {
        "Net P&L":        ("₹", y_pnl),
        "Trade count":    ("#", y_count),
        "Avg win":        ("₹", y_avg_win),
    }
    RIGHT_METRICS = {
        "Win %":          ("%", y_wr),
        "Net P&L":        ("₹", y_pnl),
        "Trade count":    ("#", y_count),
    }

    def _build(x, primary_key, extra_keys, chart_type, metrics_dict):
        pfx, y = metrics_dict[primary_key]
        fig = go.Figure()
        if chart_type == "Bar":
            fig.add_trace(go.Bar(x=x, y=y,
                marker=dict(color=[TEAL if v>=0 else RED for v in y], opacity=0.90, line=dict(width=0)),
                name=primary_key, hovertemplate=f"%{{x}}<br>{pfx}%{{y:,.2f}}<extra></extra>"))
        elif chart_type == "Scatter":
            fig.add_trace(go.Scatter(x=x, y=y, mode="markers",
                marker=dict(color=[TEAL if v>=0 else RED for v in y], size=6),
                name=primary_key, hovertemplate=f"%{{x}}<br>{pfx}%{{y:,.2f}}<extra></extra>"))
        else:  # Line
            if pfx == "%":
                fig.add_hline(y=0.5, line=dict(color=BLUE, width=1, dash="dash"),
                    annotation_text="50%", annotation_font=dict(color=BLUE, size=9))
                fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers",
                    line=dict(color=TEAL, width=2.5, shape="spline"),
                    marker=dict(size=6, color=[TEAL if v>=0.5 else RED for v in y],
                               line=dict(color="white", width=1.5)),
                    fill="tozeroy", fillcolor="rgba(16,185,129,0.20)",
                    name=primary_key, hovertemplate=f"%{{x}}<br>%{{y:.1%}}<extra></extra>"))
            else:
                fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers",
                    line=dict(color=TEAL, width=2.5),
                    marker=dict(size=6, color=TEAL, line=dict(color="white", width=1.5)),
                    fill="tozeroy", fillcolor="rgba(16,185,129,0.25)",
                    name=primary_key, hovertemplate=f"%{{x}}<br>{pfx}%{{y:,.2f}}<extra></extra>"))
                fig.add_trace(go.Scatter(x=x, y=[min(v,0) for v in y], mode="lines",
                    line=dict(width=0), fill="tozeroy",
                    fillcolor="rgba(239,68,68,0.30)", showlegend=False))
        # Extra overlays
        all_metrics = {**LEFT_METRICS, **RIGHT_METRICS}
        for i, em in enumerate(extra_keys[:3]):
            if em in all_metrics:
                epfx, ey = all_metrics[em]
                fig.add_trace(go.Scatter(x=x, y=ey, mode="lines",
                    line=dict(color=EXTRA_COLORS[i], width=1.5, dash="dot"),
                    name=em, yaxis="y2",
                    hovertemplate=f"%{{x}}<br>{epfx}%{{y:,.2f}}<extra></extra>"))
        l = chart_layout(height=height, title="")
        l["yaxis"]["tickprefix"] = pfx if pfx == "₹" else ""
        l["yaxis"]["tickformat"] = ".0%" if pfx == "%" else ",.0f"
        if pfx == "%": l["yaxis"]["range"] = [0, 1]
        if extra_keys:
            l["yaxis2"] = dict(overlaying="y", side="right", showgrid=False,
                               tickfont=dict(size=9, color=EXTRA_COLORS[0]))
        l["legend"] = dict(orientation="h", y=-0.2, x=0, font=dict(size=10))
        l["bargap"] = 0.25
        fig.update_layout(**l)
        return fig

    c1, c2 = st.columns(2)
    with c1:
        cc1, cc2, cc3 = st.columns([2, 2, 1])
        m1  = cc1.selectbox("Metric", list(LEFT_METRICS.keys()),
                             key=f"{key_prefix}_l_primary", label_visibility="collapsed")
        ex1 = cc2.multiselect("Add", [k for k in {**LEFT_METRICS,**RIGHT_METRICS} if k!=m1],
                               key=f"{key_prefix}_l_extra", placeholder="+ Add metric",
                               label_visibility="collapsed")
        ct1 = cc3.selectbox("Type", ["Line","Bar","Scatter"],
                             key=f"{key_prefix}_l_type", label_visibility="collapsed")
        st.plotly_chart(_build(x, m1, ex1, ct1, LEFT_METRICS),
                        use_container_width=True, config={"displayModeBar":False})
    with c2:
        cc4, cc5, cc6 = st.columns([2, 2, 1])
        m2  = cc4.selectbox("Metric", list(RIGHT_METRICS.keys()),
                             key=f"{key_prefix}_r_primary", label_visibility="collapsed")
        ex2 = cc5.multiselect("Add", [k for k in {**LEFT_METRICS,**RIGHT_METRICS} if k!=m2],
                               key=f"{key_prefix}_r_extra", placeholder="+ Add metric",
                               label_visibility="collapsed")
        ct2 = cc6.selectbox("Type", ["Line","Bar","Scatter"],
                             key=f"{key_prefix}_r_type", label_visibility="collapsed")
        st.plotly_chart(_build(x, m2, ex2, ct2, RIGHT_METRICS),
                        use_container_width=True, config={"displayModeBar":False})


def cross_heatmap(rows, cols, data_dict, metric="P&L", height=None):
    """
    data_dict: {row: {col: {"pnl":x, "wins":y, "count":z}}}
    metric: "P&L" | "Win %" | "Trades"
    """
    if not rows or not cols: return None
    z = []
    text = []
    for row in rows:
        z_row = []; t_row = []
        for col in cols:
            d = data_dict.get(row, {}).get(col, {"pnl":0,"wins":0,"count":0})
            if metric == "P&L":
                v = d["pnl"]; t_row.append(fmt_pnl(v))
            elif metric == "Win %":
                v = d["wins"]/d["count"] if d["count"] else 0; t_row.append(f"{v:.0%}")
            else:
                v = d["count"]; t_row.append(str(int(v)))
            z_row.append(v)
        z.append(z_row); text.append(t_row)

    zmax = max(abs(v) for row in z for v in row if v != 0) or 1
    zmid = 0.5 if metric == "Win %" else 0
    zmin_val = 0 if metric in ("Win %","Trades") else -zmax
    zmax_val = 1 if metric == "Win %" else zmax

    fig = go.Figure(go.Heatmap(
        z=z, x=cols, y=rows, text=text, texttemplate="%{text}",
        textfont=dict(size=10),
        colorscale=[[0,"#DC2626"],[0.35,"#FCA5A5"],[0.5,"#F9FAFB"],[0.65,"#6EE7B7"],[1,"#059669"]],
        zmid=zmid, zmin=zmin_val, zmax=zmax_val,
        showscale=False,
        hovertemplate="%{y} × %{x}<br>%{text}<extra></extra>"))
    h = height or max(260, len(rows)*44+80)
    l = chart_layout(height=h, title="")
    l["margin"] = dict(l=130, r=20, t=20, b=100)
    l["xaxis"]["tickangle"] = -40
    l["xaxis"]["tickfont"] = dict(size=10)
    l["yaxis"]["tickfont"] = dict(size=11)
    fig.update_layout(**l)
    return fig

def _get_cross_row_value(t, dimension):
    """Extract the row value for cross analysis based on selected dimension."""
    if dimension == "Playbook":
        return t.get("_pb_name","")
    elif dimension == "Symbols":
        return t.get("ticker","")
    elif dimension == "Strategy":
        return t.get("strategy","")
    elif dimension == "Day and time":
        return _get_dow(t)
    elif dimension == "Entry time by":
        entry = str(t.get("entry_date","") or "")
        try: return f"{int(entry[11:13]):02d}:00"
        except: return ""
    elif dimension == "Exit time by":
        exit_ = str(t.get("exit_date","") or "")
        try: return f"{int(exit_[11:13]):02d}:00"
        except: return ""
    elif dimension == "Risk & size":
        try:
            r = safe_float(t.get("r_multiple"))
            if r < 0: return "Loss"
            elif r < 1: return "<1R"
            elif r < 2: return "1-2R"
            elif r < 4: return "2-4R"
            else: return "4R+"
        except: return ""
    elif dimension == "Month":
        return _get_month(t)
    else:
        return t.get("strategy","")

def _get_cross_row_labels(trades_list, dimension):
    DOW_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    R_ORDER   = ["<1R","1-2R","2-4R","4R+","Loss"]
    if dimension == "Day and time":
        return DOW_ORDER
    elif dimension == "Risk & size":
        return R_ORDER
    elif dimension == "Entry time by" or dimension == "Exit time by":
        hours = sorted({_get_cross_row_value(t, dimension) for t in trades_list if _get_cross_row_value(t, dimension)})
        return hours
    else:
        vals = sorted({_get_cross_row_value(t, dimension) for t in trades_list if _get_cross_row_value(t, dimension)})
        return vals

def render_cross_analysis(trades_list, row_field, col_field, row_labels, col_labels, key_prefix):
    """Renders a cross-analysis section with row dimension selector + metric toggle."""
    st.markdown(
        f'<div style="margin:20px 0 10px">' 
        f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:0 0 8px">Cross Analysis</p>',
        unsafe_allow_html=True)

    ROW_DIMENSIONS = ["Strategy","Playbook","Symbols","Day and time",
                      "Entry time by","Risk & size","Month"]

    ca1, ca2 = st.columns([2, 3])
    row_dim  = ca1.selectbox("Row dimension", ROW_DIMENSIONS,
                              key=f"{key_prefix}_rowdim", label_visibility="collapsed")
    metric   = ca2.radio("Metric", ["P&L","Win %","Trades"],
                          horizontal=True, key=f"{key_prefix}_metric", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    # Use dynamic row dimension or fall back to passed-in row_labels
    if row_dim != "Strategy":
        dyn_row_labels = _get_cross_row_labels(trades_list, row_dim)
    else:
        dyn_row_labels = row_labels

    # Col labels stay as passed (strategies or symbols)
    data = defaultdict(lambda: defaultdict(lambda: {"pnl":0,"wins":0,"count":0}))
    for t in trades_list:
        r = _get_cross_row_value(t, row_dim) if row_dim != "Strategy" else (t.get(row_field,"") if row_field != "dow" else _get_dow(t))
        c = t.get(col_field,"") if col_field not in ("strategy","ticker") else t.get(col_field,"")
        if not r or not c: continue
        p = safe_float(t.get("pnl"))
        data[r][c]["pnl"]   += p
        data[r][c]["count"] += 1
        if p > 0: data[r][c]["wins"] += 1

    rows_f = [r for r in dyn_row_labels if r in data]
    cols_f = [c for c in col_labels if any(c in data[r] for r in rows_f)]
    if not rows_f or not cols_f:
        st.info("Not enough data for this combination."); return

    fig = cross_heatmap(rows_f, cols_f, data, metric)
    if fig: st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

def _get_dow(t):
    d = str(t.get("exit_date","") or "")[:10]
    try: return datetime.strptime(d, "%Y-%m-%d").strftime("%A")
    except: return ""

def _get_month(t):
    m = str(t.get("exit_date","") or "")[:7]
    if m and m != "nan":
        try: return cal.month_abbr[int(m[5:])] + " '" + m[2:4]
        except: return ""
    return ""

def fmt_month(m):
    try: return cal.month_abbr[int(m[5:])] + " '" + m[2:4]
    except: return m

def summary_df(rows, pnl_cols=("Net P&L","Avg Win","Avg Loss")):
    df = pd.DataFrame(rows)
    def sty(row):
        idx = df.columns.tolist(); styles = [""] * len(row)
        for col in pnl_cols:
            if col in idx:
                v = row.get(col, 0)
                if isinstance(v, (int, float)):
                    styles[idx.index(col)] = (f"color:{TEAL};font-weight:600" if v > 0
                                               else f"color:{RED};font-weight:600" if v < 0 else "")
        return styles
    fmt = {c: (lambda v: f"{'+'if v>=0 else ''}₹{abs(v):,.0f}" if isinstance(v,(int,float)) else v)
           for c in pnl_cols if c in df.columns}
    if "Win %" in df.columns: fmt["Win %"] = lambda v: v
    if "R-Mult" in df.columns: fmt["R-Mult"] = lambda v: f"{v:.2f}R" if isinstance(v,(int,float)) else v
    styled = df.style.apply(sty, axis=1)
    if fmt: styled = styled.format(fmt)
    return styled.set_properties(**{"font-size":"12.5px"}).set_table_styles(TABLE_STYLES)

def _max_consec(trades, wins=True):
    best = cur = 0
    for t in sorted(trades, key=lambda x: str(x.get("exit_date","") or "")):
        p = safe_float(t.get("pnl"))
        if (wins and p > 0) or (not wins and p < 0): cur += 1; best = max(best, cur)
        else: cur = 0
    return best


# ══════════════════════════════════════════════════════════════════════════════
def render():
    st.markdown("## Reports")
    st.markdown(f'<p style="color:{TEXT_MUTED};margin-top:-8px;margin-bottom:16px;font-size:0.85rem">'
                f'FY 2026-27 · Performance analytics</p>', unsafe_allow_html=True)

    trades = get_journal_trades()
    closed = [t for t in trades if t["status"] == "CLOSED"]
    if not closed: st.info("No closed trades yet."); return

    ALL_STRATEGIES = sorted({t.get("strategy","") for t in closed if t.get("strategy")})
    ALL_SYMBOLS    = sorted({t.get("ticker","") for t in closed if t.get("ticker")})
    DOW_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday"]

    # ════════════════════════════════════════════════════════════════════
    # PERFORMANCE
    # ════════════════════════════════════════════════════════════════════
    # ── TOP TABS ──────────────────────────────────────────────────────
    tab_perf, tab_ov, tab_reports, tab_cmp, tab_deep = st.tabs([
        "📈 Performance", "📊 Overview", "📊 Reports", "⚖️ Compare", "🔬 Deep Analytics"
    ])

    # ════════════════════════════════════════════════════════════════════
    # PERFORMANCE
    # ════════════════════════════════════════════════════════════════════
    with tab_perf:
        wins_p   = [t for t in closed if safe_float(t.get("pnl")) > 0]
        losses_p = [t for t in closed if safe_float(t.get("pnl")) < 0]
        total_p  = sum(safe_float(t.get("pnl")) for t in closed)
        wr_p     = len(wins_p)/len(closed)
        avg_w_p  = sum(safe_float(t.get("pnl")) for t in wins_p)/len(wins_p) if wins_p else 0
        avg_l_p  = sum(safe_float(t.get("pnl")) for t in losses_p)/len(losses_p) if losses_p else 0
        pf_p     = abs(sum(safe_float(t.get("pnl")) for t in wins_p)/
                      sum(safe_float(t.get("pnl")) for t in losses_p)) if losses_p else 0

        st.markdown(kpi_strip([
            ("Net P&L",       fmt_pnl(total_p),       pnl_color(total_p)),
            ("Win Rate",      f"{wr_p:.1%}",           TEAL if wr_p>=0.4 else RED),
            ("Profit Factor", f"{pf_p:.2f}",           TEAL if pf_p>=1 else RED),
            ("Avg Win",       fmt_pnl(avg_w_p),        TEAL),
            ("Avg Loss",      fmt_pnl(avg_l_p),        RED),
            ("Trades",        str(len(closed)),         TEXT_H),
        ]), unsafe_allow_html=True)

        # Cumulative by date
        by_date = defaultdict(float)
        for t in closed:
            d = str(t.get("exit_date","") or "")[:10]
            if d and d != "nan": by_date[d] += safe_float(t.get("pnl"))
        dates = sorted(by_date.keys())
        cum=[]; run=0
        for d in dates: run+=by_date[d]; cum.append(run)

        # Per-date win/loss ratio
        by_date_wins  = defaultdict(int)
        by_date_total = defaultdict(int)
        for t in closed:
            d = str(t.get("exit_date","") or "")[:10]
            if d and d!="nan":
                by_date_total[d]+=1
                if safe_float(t.get("pnl"))>0: by_date_wins[d]+=1
        daily_wr = [by_date_wins[d]/by_date_total[d] if by_date_total[d] else 0 for d in dates]
        daily_pnl_abs = [by_date[d] for d in dates]

        # Running drawdown
        peak=0; dd_series=[]
        for v in cum:
            if v>peak: peak=v
            dd_series.append(v-peak)

        # ── Compute all available metrics from trade data ──────────────────
        # Profitability
        daily_wins  = [by_date_wins[d] for d in dates]
        daily_total = [by_date_total[d] for d in dates]
        avg_daily_wl = [w/t if t else 0 for w,t in zip(daily_wins, daily_total)]

        # Cumulative trade count
        trade_count_cum = []; tc=0
        for d in dates: tc+=by_date_total[d]; trade_count_cum.append(tc)

        # Drawdown series
        # (already computed above as dd_series)

        # Consecutive wins/losses running
        consec_wins_series=[]; consec_loss_series=[]; cw=0; cl=0
        for t in sorted(closed, key=lambda x: str(x.get("exit_date","") or "")):
            p=safe_float(t.get("pnl"))
            if p>0: cw+=1; cl=0
            else: cl+=1; cw=0
            consec_wins_series.append(cw); consec_loss_series.append(cl)
        # Map to dates (simplified: last value per day)
        cw_by_date={}; cl_by_date={}; idx_t=0
        for t in sorted(closed, key=lambda x: str(x.get("exit_date","") or "")):
            d=str(t.get("exit_date","") or "")[:10]
            p=safe_float(t.get("pnl"))
            if d and d!="nan":
                cw_by_date[d]=consec_wins_series[idx_t]
                cl_by_date[d]=consec_loss_series[idx_t]
            idx_t+=1
        daily_cw=[cw_by_date.get(d,0) for d in dates]
        daily_cl=[cl_by_date.get(d,0) for d in dates]

        # Avg R per day
        r_by_date=defaultdict(list)
        for t in closed:
            d=str(t.get("exit_date","") or "")[:10]
            if d and d!="nan": r_by_date[d].append(safe_float(t.get("r_multiple")))
        daily_avg_r=[sum(r_by_date[d])/len(r_by_date[d]) if r_by_date[d] else 0 for d in dates]
        daily_avg_r_cum=[]; rr=0; rc=0
        for v in daily_avg_r: rc+=1; rr+=v; daily_avg_r_cum.append(rr/rc if rc else 0)

        # Win/loss per day
        win_pnl_by_date=defaultdict(float); loss_pnl_by_date=defaultdict(float)
        for t in closed:
            d=str(t.get("exit_date","") or "")[:10]; p=safe_float(t.get("pnl"))
            if d and d!="nan":
                if p>0: win_pnl_by_date[d]+=p
                else: loss_pnl_by_date[d]+=p
        daily_avg_win =[win_pnl_by_date[d]/by_date_wins[d] if by_date_wins[d] else 0 for d in dates]
        daily_avg_loss=[loss_pnl_by_date[d]/(by_date_total[d]-by_date_wins[d])
                        if (by_date_total[d]-by_date_wins[d])>0 else 0 for d in dates]

        # Cumulative avg win
        cum_avg_win=[]; wsum=0; wc=0
        for v in daily_avg_win:
            if v: wsum+=v; wc+=1
            cum_avg_win.append(wsum/wc if wc else 0)

        # ALL metric options — grouped for display
        METRIC_OPTIONS = {
            # Profitability
            "Net P&L — cumulative":          ("₹", cum),
            "Net P&L — daily":               ("₹", [by_date[d] for d in dates]),
            "Avg win — cumulative":           ("₹", cum_avg_win),
            "Avg daily win/loss ratio":       ("%", avg_daily_wl),
            # Risk & Drawdown
            "Drawdown":                       ("₹", dd_series),
            "Avg R — daily":                  ("R", daily_avg_r),
            "Avg R — cumulative":             ("R", daily_avg_r_cum),
            # Trading Activity
            "Trade count — cumulative":       ("#", trade_count_cum),
            "Winning trades/day":             ("#", daily_wins),
            # Streaks
            "Consecutive wins":               ("#", daily_cw),
            "Consecutive losses":             ("#", daily_cl),
        }

        EXTRA_COLORS = [AMBER, BLUE, RED, "#8B5CF6"]

        def build_chart(primary_key, extra_keys, chart_type, chart_num):
            pfx, y = METRIC_OPTIONS[primary_key]
            fig = go.Figure()
            # Primary trace
            if chart_type == "Bar":
                fig.add_trace(go.Bar(x=dates, y=y,
                    marker=dict(color=[TEAL if v>=0 else RED for v in y], opacity=0.90, line=dict(width=0)),
                    name=primary_key, hovertemplate=f"%{{x}}<br>{pfx}%{{y:,.2f}}<extra></extra>"))
            elif chart_type == "Scatter":
                fig.add_trace(go.Scatter(x=dates, y=y, mode="markers",
                    marker=dict(color=[TEAL if v>=0 else RED for v in y], size=5),
                    name=primary_key, hovertemplate=f"%{{x}}<br>{pfx}%{{y:,.2f}}<extra></extra>"))
            else:  # Line (default)
                fig.add_trace(go.Scatter(x=dates, y=y, mode="lines",
                    line=dict(color=TEAL, width=2.5),
                    fill="tozeroy", fillcolor="rgba(16,185,129,0.25)",
                    name=primary_key, hovertemplate=f"%{{x}}<br>{pfx}%{{y:,.2f}}<extra></extra>"))
                if pfx in ("₹","R"):
                    fig.add_trace(go.Scatter(x=dates, y=[min(v,0) for v in y], mode="lines",
                        line=dict(width=0), fill="tozeroy",
                        fillcolor="rgba(239,68,68,0.30)", showlegend=False))
                if pfx=="%":
                    fig.add_hline(y=0.5, line=dict(color=BLUE, width=1, dash="dash"),
                        annotation_text="50%", annotation_font=dict(color=BLUE, size=9))
            # Extra overlay traces
            for i, em in enumerate(extra_keys[:3]):
                epfx, ey = METRIC_OPTIONS[em]
                fig.add_trace(go.Scatter(x=dates, y=ey, mode="lines",
                    line=dict(color=EXTRA_COLORS[i], width=1.5, dash="dot"),
                    name=em, yaxis="y2",
                    hovertemplate=f"%{{x}}<br>{epfx}%{{y:,.2f}}<extra></extra>"))
            l = chart_layout(height=320, title=primary_key)
            l["yaxis"]["tickprefix"] = pfx if pfx=="₹" else ""
            l["yaxis"]["tickformat"] = ",.0f" if pfx in ("₹","R","#") else ".0%"
            if pfx=="%": l["yaxis"]["range"]=[0,1]
            if extra_keys:
                l["yaxis2"] = dict(overlaying="y", side="right", showgrid=False,
                                   tickfont=dict(size=9, color=EXTRA_COLORS[0]))
            l["legend"] = dict(orientation="h", y=-0.18, x=0, font=dict(size=10))
            l["bargap"] = 0.2
            fig.update_layout(**l)
            return fig

        pc1, pc2 = st.columns(2)

        with pc1:
            cc1, cc2, cc3 = st.columns([2, 2, 1])
            m1_primary = cc1.selectbox("Primary", list(METRIC_OPTIONS.keys()),
                                        index=0, key="perf_m1_primary", label_visibility="collapsed")
            m1_extra   = cc2.multiselect("Add metric", [k for k in METRIC_OPTIONS if k!=m1_primary],
                                          key="perf_m1_extra", placeholder="+ Add metric",
                                          label_visibility="collapsed")
            m1_type    = cc3.selectbox("Type", ["Line","Bar","Scatter"],
                                        key="perf_m1_type", label_visibility="collapsed")
            fig = build_chart(m1_primary, m1_extra, m1_type, 1)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

        with pc2:
            cc4, cc5, cc6 = st.columns([2, 2, 1])
            m2_primary = cc4.selectbox("Primary", list(METRIC_OPTIONS.keys()),
                                        index=3, key="perf_m2_primary", label_visibility="collapsed")
            m2_extra   = cc5.multiselect("Add metric", [k for k in METRIC_OPTIONS if k!=m2_primary],
                                          key="perf_m2_extra", placeholder="+ Add metric",
                                          label_visibility="collapsed")
            m2_type    = cc6.selectbox("Type", ["Line","Bar","Scatter"],
                                        key="perf_m2_type", label_visibility="collapsed")
            fig2 = build_chart(m2_primary, m2_extra, m2_type, 2)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

        # Summary
        by_date_p=by_date
        st.markdown(f'<p style="font-size:11px;font-weight:600;color:{TEXT_SUBTLE};text-transform:uppercase;'
                    f'letter-spacing:0.07em;margin:16px 0 8px">Summary</p>', unsafe_allow_html=True)
        sc1,sc2=st.columns(2)
        left=[("Net P&L",fmt_pnl(total_p)),("Win Rate",f"{wr_p:.1%}"),
              ("Profit Factor",f"{pf_p:.2f}"),("Avg Win",fmt_pnl(avg_w_p)),
              ("Avg Loss",fmt_pnl(avg_l_p)),("Total Trades",str(len(closed))),
              ("Winning Trades",str(len(wins_p))),("Losing Trades",str(len(losses_p))),
              ("Max Consec Wins",str(_max_consec(closed,True))),
              ("Max Consec Losses",str(_max_consec(closed,False)))]
        right=[("Avg Trade P&L",fmt_pnl(total_p/len(closed))),
               ("Largest Win",fmt_pnl(max((safe_float(t.get("pnl")) for t in wins_p),default=0))),
               ("Largest Loss",fmt_pnl(min((safe_float(t.get("pnl")) for t in losses_p),default=0))),
               ("Total R",f"{sum(safe_float(t.get('r_multiple')) for t in closed):.2f}R"),
               ("Best Day",fmt_pnl(max(by_date_p.values()) if by_date_p else 0)),
               ("Worst Day",fmt_pnl(min(by_date_p.values()) if by_date_p else 0)),
               ("Trading Days",str(len(by_date_p))),
               ("Winning Days",str(sum(1 for v in by_date_p.values() if v>0))),
               ("Losing Days",str(sum(1 for v in by_date_p.values() if v<0))),
               ("Avg Daily P&L",fmt_pnl(sum(by_date_p.values())/len(by_date_p) if by_date_p else 0))]
        with sc1: st.markdown("".join(stat_row(l,v) for l,v in left), unsafe_allow_html=True)
        with sc2: st.markdown("".join(stat_row(l,v) for l,v in right), unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # OVERVIEW
    # ════════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════════
    # OVERVIEW
    # ════════════════════════════════════════════════════════════════════
    with tab_ov:
        wins_o=[t for t in closed if safe_float(t.get("pnl"))>0]
        losses_o=[t for t in closed if safe_float(t.get("pnl"))<0]
        total_o=sum(safe_float(t.get("pnl")) for t in closed)
        wr_o=len(wins_o)/len(closed)
        avg_w_o=sum(safe_float(t.get("pnl")) for t in wins_o)/len(wins_o) if wins_o else 0
        avg_l_o=sum(safe_float(t.get("pnl")) for t in losses_o)/len(losses_o) if losses_o else 0
        pf_o=abs(sum(safe_float(t.get("pnl")) for t in wins_o)/
                 sum(safe_float(t.get("pnl")) for t in losses_o)) if losses_o else 0
        by_m_o=defaultdict(float)
        for t in closed:
            m=str(t.get("exit_date","") or "")[:7]
            if m and m!="nan": by_m_o[m]+=safe_float(t.get("pnl"))
        best_m=max(by_m_o,key=by_m_o.get) if by_m_o else "—"
        worst_m=min(by_m_o,key=by_m_o.get) if by_m_o else "—"
        avg_m=sum(by_m_o.values())/len(by_m_o) if by_m_o else 0
        by_d_o=defaultdict(float)
        for t in closed:
            d=str(t.get("exit_date","") or "")[:10]
            if d and d!="nan": by_d_o[d]+=safe_float(t.get("pnl"))

        st.markdown(f"""<div style="display:flex;gap:16px;margin-bottom:20px">
            <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 20px;flex:1">
                <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Best Month</div>
                <div style="font-size:22px;font-weight:700;color:{TEAL}">{fmt_month(best_m)}</div>
                <div style="font-size:12px;color:{TEXT_MUTED}">{fmt_pnl(by_m_o.get(best_m,0))}</div>
            </div>
            <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 20px;flex:1">
                <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Worst Month</div>
                <div style="font-size:22px;font-weight:700;color:{RED}">{fmt_month(worst_m)}</div>
                <div style="font-size:12px;color:{TEXT_MUTED}">{fmt_pnl(by_m_o.get(worst_m,0))}</div>
            </div>
            <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 20px;flex:1">
                <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Avg / Month</div>
                <div style="font-size:22px;font-weight:700;color:{pnl_color(avg_m)}">{fmt_pnl(avg_m)}</div>
            </div>
        </div>""", unsafe_allow_html=True)

        all_r=[safe_float(t.get("r_multiple")) for t in closed]
        ov_stats=[
            ("Total P&L",fmt_pnl(total_o)),("Win Rate",f"{wr_o:.1%}"),
            ("Profit Factor",f"{pf_o:.2f}"),("Total Trades",str(len(closed))),
            ("Winning Trades",str(len(wins_o))),("Losing Trades",str(len(losses_o))),
            ("Avg Win",fmt_pnl(avg_w_o)),("Avg Loss",fmt_pnl(avg_l_o)),
            ("Avg Win/Loss Ratio",f"{abs(avg_w_o/avg_l_o):.2f}" if avg_l_o else "—"),
            ("Largest Win",fmt_pnl(max((safe_float(t.get("pnl")) for t in wins_o),default=0))),
            ("Largest Loss",fmt_pnl(min((safe_float(t.get("pnl")) for t in losses_o),default=0))),
            ("Max Consec Wins",str(_max_consec(closed,True))),
            ("Max Consec Losses",str(_max_consec(closed,False))),
            ("Total R",f"{sum(all_r):.2f}R"),
            ("Avg R all trades",f"{sum(all_r)/len(all_r):.2f}R" if all_r else "—"),
            ("Avg R wins",f"{sum(safe_float(t.get('r_multiple')) for t in wins_o)/len(wins_o):.2f}R" if wins_o else "—"),
            ("Avg R losses",f"{sum(safe_float(t.get('r_multiple')) for t in losses_o)/len(losses_o):.2f}R" if losses_o else "—"),
            ("Trading Days",str(len(by_d_o))),
            ("Winning Days",str(sum(1 for v in by_d_o.values() if v>0))),
            ("Losing Days",str(sum(1 for v in by_d_o.values() if v<0))),
            ("Best Day",fmt_pnl(max(by_d_o.values()) if by_d_o else 0)),
            ("Worst Day",fmt_pnl(min(by_d_o.values()) if by_d_o else 0)),
            ("Avg Daily P&L",fmt_pnl(sum(by_d_o.values())/len(by_d_o) if by_d_o else 0)),
            ("Best Month",f"{fmt_month(best_m)} ({fmt_pnl(by_m_o.get(best_m,0))})"),
            ("Worst Month",f"{fmt_month(worst_m)} ({fmt_pnl(by_m_o.get(worst_m,0))})"),
        ]
        half=len(ov_stats)//2
        oc1,oc2=st.columns(2)
        with oc1: st.markdown("".join(stat_row(l,v) for l,v in ov_stats[:half]), unsafe_allow_html=True)
        with oc2: st.markdown("".join(stat_row(l,v) for l,v in ov_stats[half:]), unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # REPORTS — dropdown with Day & Time, Symbols, Risk, Playbooks
    # ════════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════════
    # REPORTS — selectbox controls sub-section
    # ════════════════════════════════════════════════════════════════════
    with tab_reports:
        report_section = st.selectbox(
            "Report type",
            ["📅 Day & Time", "🎯 Symbols", "⚠️ Risk", "📋 Playbooks", "🏷️ Tags", "⚡ Wins vs Losses"],
            key="report_section_select", label_visibility="collapsed"
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if report_section == "📅 Day & Time":
            dt_sub = st.tabs(["📆 Days", "🗓️ Months", "⏰ Trade Time", "⌛ Trade Duration"])

            # ── DAYS ─────────────────────────────────────────────────────────
            with dt_sub[0]:
                day_d=defaultdict(lambda:{"pnl":0,"wins":0,"losses":0,"count":0,"win_sum":0,"loss_sum":0})
                for t in closed:
                    dow=_get_dow(t)
                    if not dow: continue
                    p=safe_float(t.get("pnl")); dd=day_d[dow]
                    dd["pnl"]+=p; dd["count"]+=1
                    if p>0: dd["wins"]+=1; dd["win_sum"]+=p
                    else: dd["losses"]+=1; dd["loss_sum"]+=p

                days_x=[d for d in DOW_ORDER if d in day_d]
                dpnls=[day_d[d]["pnl"] for d in days_x]
                dwrs=[day_d[d]["wins"]/day_d[d]["count"] if day_d[d]["count"] else 0 for d in days_x]
                dcnts=[day_d[d]["count"] for d in days_x]
                davgw=[day_d[d]["win_sum"]/day_d[d]["wins"] if day_d[d]["wins"] else 0 for d in days_x]

                if days_x:
                    best_d=max(days_x,key=lambda d:day_d[d]["pnl"])
                    worst_d=min(days_x,key=lambda d:day_d[d]["pnl"])
                    most_d=max(days_x,key=lambda d:day_d[d]["count"])
                    bestwr_d=max(days_x,key=lambda d:day_d[d]["wins"]/day_d[d]["count"] if day_d[d]["count"] else 0)
                    st.markdown(kpi_strip([
                        ("Best Day",best_d,TEAL),("Worst Day",worst_d,RED),
                        ("Most Active",most_d,BLUE),("Best Win %",bestwr_d,TEAL),
                    ]), unsafe_allow_html=True)

                    # Summary table
                    drows=[{"Day":d,"Trades":day_d[d]["count"],
                        "Win %":f"{day_d[d]['wins']/day_d[d]['count']*100:.1f}%" if day_d[d]["count"] else "—",
                        "Net P&L":day_d[d]["pnl"],
                        "Avg Win":day_d[d]["win_sum"]/day_d[d]["wins"] if day_d[d]["wins"] else 0,
                        "Avg Loss":day_d[d]["loss_sum"]/day_d[d]["losses"] if day_d[d]["losses"] else 0}
                        for d in DOW_ORDER if d in day_d]
                    st.dataframe(summary_df(drows), use_container_width=True, hide_index=True)

                    # Cross analysis — Day × Strategy (with metric toggle)
                    render_cross_analysis(closed, "dow", "strategy", DOW_ORDER, ALL_STRATEGIES, "day_strat")

            # ── MONTHS ───────────────────────────────────────────────────────
            with dt_sub[1]:
                mon_d=defaultdict(lambda:{"pnl":0,"wins":0,"losses":0,"count":0,"win_sum":0,"loss_sum":0})
                for t in closed:
                    m=str(t.get("exit_date","") or "")[:7]
                    if not m or m=="nan": continue
                    p=safe_float(t.get("pnl")); md=mon_d[m]
                    md["pnl"]+=p; md["count"]+=1
                    if p>0: md["wins"]+=1; md["win_sum"]+=p
                    else: md["losses"]+=1; md["loss_sum"]+=p

                months_k=sorted(mon_d.keys())
                mlabels=[fmt_month(m) for m in months_k]
                mpnls=[mon_d[m]["pnl"] for m in months_k]
                mwrs=[mon_d[m]["wins"]/mon_d[m]["count"] if mon_d[m]["count"] else 0 for m in months_k]
                mcnts=[mon_d[m]["count"] for m in months_k]
                mavgw=[mon_d[m]["win_sum"]/mon_d[m]["wins"] if mon_d[m]["wins"] else 0 for m in months_k]

                if months_k:
                    best_m2=months_k[mpnls.index(max(mpnls))]
                    worst_m2=months_k[mpnls.index(min(mpnls))]
                    st.markdown(kpi_strip([
                        ("Best Month",fmt_month(best_m2),TEAL),
                        ("Worst Month",fmt_month(worst_m2),RED),
                        ("Total P&L",fmt_pnl(sum(mpnls)),pnl_color(sum(mpnls))),
                        ("Avg/Month",fmt_pnl(sum(mpnls)/len(mpnls)),TEXT_H),
                    ]), unsafe_allow_html=True)

                    mrows=[{"Month":fmt_month(m),"Trades":mon_d[m]["count"],
                        "Win %":f"{mon_d[m]['wins']/mon_d[m]['count']*100:.1f}%" if mon_d[m]["count"] else "—",
                        "Net P&L":mon_d[m]["pnl"],
                        "Avg Win":mon_d[m]["win_sum"]/mon_d[m]["wins"] if mon_d[m]["wins"] else 0,
                        "Avg Loss":mon_d[m]["loss_sum"]/mon_d[m]["losses"] if mon_d[m]["losses"] else 0}
                        for m in months_k]
                    st.dataframe(summary_df(mrows), use_container_width=True, hide_index=True)

                    # Cross analysis — Month × Strategy
                    month_labels_cross=[fmt_month(m) for m in months_k]

                    # Build using month label as key
                    def render_month_cross(trades_list, col_labels, key_prefix):
                        st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:20px 0 10px">Cross Analysis</p>', unsafe_allow_html=True)
                        metric=st.radio("Metric",["P&L","Win %","Trades"],horizontal=True,key=f"{key_prefix}_metric",label_visibility="collapsed")
                        data=defaultdict(lambda:defaultdict(lambda:{"pnl":0,"wins":0,"count":0}))
                        for t in trades_list:
                            row=_get_month(t); col=t.get("strategy","")
                            if not row or not col: continue
                            p=safe_float(t.get("pnl"))
                            data[row][col]["pnl"]+=p; data[row][col]["count"]+=1
                            if p>0: data[row][col]["wins"]+=1
                        rows_f=[r for r in month_labels_cross if r in data]
                        cols_f=[c for c in col_labels if any(c in data[r] for r in rows_f)]
                        if not rows_f or not cols_f: st.info("Not enough data."); return
                        fig=cross_heatmap(rows_f,cols_f,data,metric)
                        if fig: st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})

                    render_month_cross(closed, ALL_STRATEGIES, "month_strat")

            # ── TRADE TIME ───────────────────────────────────────────────────
            with dt_sub[2]:
                hr_d=defaultdict(lambda:{"pnl":0,"wins":0,"losses":0,"count":0,"win_sum":0,"loss_sum":0})
                for t in closed:
                    entry=str(t.get("entry_date","") or t.get("exit_date","") or "")
                    try: hr=int(entry[11:13])
                    except: continue
                    if hr<0 or hr>23: continue
                    p=safe_float(t.get("pnl")); hd=hr_d[hr]
                    hd["pnl"]+=p; hd["count"]+=1
                    if p>0: hd["wins"]+=1; hd["win_sum"]+=p
                    else: hd["losses"]+=1; hd["loss_sum"]+=p

                hrs=sorted(hr_d.keys())
                if hrs:
                    hlabels=[f"{h}:00" for h in hrs]
                    hpnls=[hr_d[h]["pnl"] for h in hrs]
                    hwrs=[hr_d[h]["wins"]/hr_d[h]["count"] if hr_d[h]["count"] else 0 for h in hrs]
                    hcnts=[hr_d[h]["count"] for h in hrs]
                    best_h=hrs[hpnls.index(max(hpnls))]
                    worst_h=hrs[hpnls.index(min(hpnls))]
                    most_h=max(hrs,key=lambda h:hr_d[h]["count"])
                    st.markdown(kpi_strip([
                        ("Best Hour",f"{best_h}:00",TEAL),
                        ("Worst Hour",f"{worst_h}:00",RED),
                        ("Most Active",f"{most_h}:00",BLUE),
                        ("Total Trades",str(len(closed)),TEXT_H),
                    ]), unsafe_allow_html=True)

                    hrows=[{"Hour":f"{h}:00","Trades":hr_d[h]["count"],
                        "Win %":f"{hr_d[h]['wins']/hr_d[h]['count']*100:.1f}%" if hr_d[h]["count"] else "—",
                        "Net P&L":hr_d[h]["pnl"],
                        "Avg Win":hr_d[h]["win_sum"]/hr_d[h]["wins"] if hr_d[h]["wins"] else 0,
                        "Avg Loss":hr_d[h]["loss_sum"]/hr_d[h]["losses"] if hr_d[h]["losses"] else 0}
                        for h in hrs]
                    st.dataframe(summary_df(hrows), use_container_width=True, hide_index=True)

                    # Cross analysis — Hour × Strategy
                    render_cross_analysis(closed,"dow","strategy",DOW_ORDER,ALL_STRATEGIES,"hour_strat")
                else:
                    st.info("No entry time data. Trades need a time component in entry_date.")

            # ── TRADE DURATION (R-multiple buckets) ──────────────────────────
            with dt_sub[3]:
                # Parse duration field: "5 days 0 hrs 0 mins" → number of days
                def parse_duration_days(dur_str):
                    if not dur_str: return None
                    try:
                        parts = str(dur_str).lower()
                        days = 0
                        import re
                        m = re.search(r"(\d+)\s*day", parts)
                        if m: days += int(m.group(1))
                        return days
                    except: return None

                # Duration buckets in days
                dur_def = [("<1 day",0,1),("1 day",1,2),("2-5 days",2,6),
                           ("1-2 weeks",6,15),("2-4 weeks",15,29),("1+ month",29,9999)]
                dur_d = {k:{"pnl":0,"wins":0,"losses":0,"count":0,"win_sum":0,"loss_sum":0}
                         for k,_,_ in dur_def}
                dur_d["Unknown"] = {"pnl":0,"wins":0,"losses":0,"count":0,"win_sum":0,"loss_sum":0}

                for t in closed:
                    p   = safe_float(t.get("pnl"))
                    dur = parse_duration_days(t.get("duration",""))
                    if dur is None:
                        # Fallback: compute from entry/exit date
                        try:
                            ed = datetime.strptime(str(t.get("entry_date",""))[:10], "%Y-%m-%d")
                            xd = datetime.strptime(str(t.get("exit_date",""))[:10],  "%Y-%m-%d")
                            dur = (xd - ed).days
                        except: dur = None
                    if dur is None:
                        k = "Unknown"
                    else:
                        k = next((lbl for lbl,lo,hi in dur_def if lo<=dur<hi), "1+ month")
                    bd = dur_d[k]; bd["pnl"]+=p; bd["count"]+=1
                    if p>0: bd["wins"]+=1; bd["win_sum"]+=p
                    else:   bd["losses"]+=1; bd["loss_sum"]+=p

                dur_order = [k for k,_,_ in dur_def] + ["Unknown"]
                blabels = [b for b in dur_order if dur_d[b]["count"]>0]
                bpnls   = [dur_d[b]["pnl"]   for b in blabels]
                bwrs    = [dur_d[b]["wins"]/dur_d[b]["count"] if dur_d[b]["count"] else 0 for b in blabels]
                bcnts   = [dur_d[b]["count"]  for b in blabels]

                if blabels:
                    best_b   = blabels[bpnls.index(max(bpnls))]
                    worst_b  = blabels[bpnls.index(min(bpnls))]
                    most_b   = blabels[bcnts.index(max(bcnts))]
                    bestwr_b = blabels[bwrs.index(max(bwrs))]
                    st.markdown(kpi_strip([
                        ("Best Duration",  best_b,   TEAL),
                        ("Worst Duration", worst_b,  RED),
                        ("Most Active",    most_b,   BLUE),
                        ("Best Win %",     bestwr_b, TEAL),
                    ]), unsafe_allow_html=True)
                    render_chart_pair(blabels, bpnls, bcnts, [0]*len(blabels), bwrs, "dur_chart")

                    brows=[{"Duration":b,"Trades":dur_d[b]["count"],
                        "Win %":f"{dur_d[b]['wins']/dur_d[b]['count']*100:.1f}%" if dur_d[b]["count"] else "—",
                        "Net P&L":dur_d[b]["pnl"],
                        "Avg Win":dur_d[b]["win_sum"]/dur_d[b]["wins"] if dur_d[b]["wins"] else 0,
                        "Avg Loss":dur_d[b]["loss_sum"]/dur_d[b]["losses"] if dur_d[b]["losses"] else 0}
                        for b in blabels]
                    st.dataframe(summary_df(brows), use_container_width=True, hide_index=True)

                    # Cross analysis — Duration × Strategy
                    render_cross_analysis(closed,"duration","strategy",blabels,ALL_STRATEGIES,"dur_strat")
                else:
                    st.info("No trade duration data available.")

        # ════════════════════════════════════════════════════════════════════
        # SYMBOLS (sub-tabs: Symbols | Instruments/Strategy | Prices)
        # ════════════════════════════════════════════════════════════════════

        elif report_section == "🎯 Symbols":
            sym_sub = st.tabs(["📊 Symbols", "📋 Instruments", "💲 Prices"])

            def _build_sym_stats(group_field, group_fn=None, price_buckets=None):
                """Build aggregated stats dict keyed by group value."""
                d = defaultdict(lambda:{
                    "pnl":0,"wins":0,"losses":0,"count":0,
                    "win_sum":0,"loss_sum":0,
                    "r_sum":0,"r_wins":0,"r_losses":0,
                    "r_planned_sum":0
                })
                for t in closed:
                    if group_fn:
                        k = group_fn(t)
                    elif price_buckets:
                        try:
                            ep = float(t.get("entry_price") or 0)
                            k = next((lbl for lbl,lo,hi in price_buckets if lo<=ep<hi), None)
                        except: k = None
                    else:
                        k = t.get(group_field,"") or "Unknown"
                    if not k: continue
                    p  = safe_float(t.get("pnl"))
                    r  = safe_float(t.get("r_multiple"))
                    rp = safe_float(t.get("max_rr") or t.get("one_r") or 0)
                    dd = d[k]
                    dd["pnl"]+=p; dd["count"]+=1; dd["r_sum"]+=r
                    if p>0: dd["wins"]+=1; dd["win_sum"]+=p; dd["r_wins"]+=r
                    else:   dd["losses"]+=1; dd["loss_sum"]+=p; dd["r_losses"]+=r
                    if rp: dd["r_planned_sum"]+=rp
                return d

            def _render_sym_section(d, group_label, key_pfx, group_field=None, cross_col_field="strategy", group_fn=None, price_buckets=None):
                keys = sorted(d.keys(), key=lambda k: d[k]["pnl"], reverse=True)
                if not keys: st.info("No data."); return

                pnls = [d[k]["pnl"]   for k in keys]
                cnts = [d[k]["count"] for k in keys]
                wrs  = [d[k]["wins"]/d[k]["count"] if d[k]["count"] else 0 for k in keys]
                avgw = [d[k]["win_sum"]/d[k]["wins"] if d[k]["wins"] else 0 for k in keys]

                best   = keys[0]; worst = keys[-1]
                most   = max(keys, key=lambda k: d[k]["count"])
                bestwr = max(keys, key=lambda k: d[k]["wins"]/d[k]["count"] if d[k]["count"] else 0)

                st.markdown(kpi_strip([
                    (f"Best {group_label}",  best,   TEAL),
                    (f"Least {group_label}", worst,  RED),
                    ("Most Active",          most,   BLUE),
                    ("Best Win Rate",        bestwr, TEAL),
                ]), unsafe_allow_html=True)

                render_chart_pair(keys, pnls, cnts, avgw, wrs, f"{key_pfx}_chart")

                # ── Rich summary table ───────────────────────────────────
                rows = []
                for k in keys:
                    dk = d[k]
                    cl = dk["wins"]+dk["losses"]
                    rows.append({
                        group_label:         k,
                        "Trades":            dk["count"],
                        "Win %":             f"{dk['wins']/cl*100:.1f}%" if cl else "—",
                        "Net P&L":           dk["pnl"],
                        "Avg Win":           dk["win_sum"]/dk["wins"] if dk["wins"] else 0,
                        "Avg Loss":          dk["loss_sum"]/dk["losses"] if dk["losses"] else 0,
                        "Avg R":             f"{dk['r_sum']/dk['count']:.2f}R" if dk["count"] else "—",
                        "Avg R (wins)":      f"{dk['r_wins']/dk['wins']:.2f}R" if dk["wins"] else "—",
                        "Avg R (losses)":    f"{dk['r_losses']/dk['losses']:.2f}R" if dk["losses"] else "—",
                        "Wins":              dk["wins"],
                        "Losses":            dk["losses"],
                        "Profit Factor":     f"{abs(dk['win_sum']/dk['loss_sum']):.2f}" if dk["loss_sum"] else "—",
                    })
                df_s = pd.DataFrame(rows)
                def _sty(row):
                    idx=df_s.columns.tolist(); styles=[""]*len(row)
                    for col in ("Net P&L","Avg Win","Avg Loss"):
                        if col in idx:
                            v=row.get(col,0)
                            if isinstance(v,(int,float)):
                                styles[idx.index(col)]=f"color:{TEAL};font-weight:600" if v>0 else f"color:{RED};font-weight:600" if v<0 else ""
                    return styles
                fmt = {
                    "Net P&L": lambda v: f"{'+'if v>=0 else ''}₹{abs(v):,.0f}" if isinstance(v,(int,float)) else v,
                    "Avg Win": lambda v: f"₹{v:,.0f}" if isinstance(v,(int,float)) else v,
                    "Avg Loss": lambda v: f"₹{v:,.0f}" if isinstance(v,(int,float)) else v,
                }
                st.dataframe(df_s.style.apply(_sty,axis=1).format(fmt)
                    .set_properties(**{"font-size":"12.5px"}).set_table_styles(TABLE_STYLES),
                    use_container_width=True, hide_index=True)

                # ── Cross analysis ───────────────────────────────────────
                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:20px 0 8px">Cross Analysis</p>', unsafe_allow_html=True)
                ca1,ca2,ca3 = st.columns([2,2,3])
                cross_col_opt = ca1.selectbox("Rows", keys[:20],
                                               key=f"{key_pfx}_cross_rows", label_visibility="collapsed")
                cross_dim = ca2.selectbox("Columns", [
                    "Strategy","Day of week","Month","Trade duration","R-Multiple","Position size"
                ], key=f"{key_pfx}_cross_dim", label_visibility="collapsed")
                metric = ca3.radio("Metric",["P&L","Win %","Trades"],
                                    horizontal=True, key=f"{key_pfx}_cross_metric",
                                    label_visibility="collapsed")

                # Map cross_dim to a value extractor
                def get_col_val(t):
                    if cross_dim=="Strategy": return t.get("strategy","")
                    elif cross_dim=="Day of week": return _get_dow(t)
                    elif cross_dim=="Month": return _get_month(t)
                    elif cross_dim=="Trade duration":
                        dur=t.get("duration","")
                        if dur:
                            import re as _re
                            m=_re.search(r"(\d+)\s*day",str(dur).lower())
                            days=int(m.group(1)) if m else 0
                        else:
                            try:
                                ed=datetime.strptime(str(t.get("entry_date",""))[:10],"%Y-%m-%d")
                                xd=datetime.strptime(str(t.get("exit_date",""))[:10],"%Y-%m-%d")
                                days=(xd-ed).days
                            except: days=0
                        if days<1: return "<1 day"
                        elif days<2: return "1 day"
                        elif days<6: return "2-5 days"
                        elif days<15: return "1-2 wks"
                        elif days<29: return "2-4 wks"
                        else: return "1+ month"
                    elif cross_dim=="R-Multiple":
                        r=safe_float(t.get("r_multiple"))
                        if r<0: return "<0R"
                        elif r<1: return "0-1R"
                        elif r<2: return "1-2R"
                        elif r<3: return "2-3R"
                        elif r<5: return "3-5R"
                        else: return "5R+"
                    elif cross_dim=="Position size":
                        try: ps=float(t.get("position_size") or 0) or float(t.get("entry_price") or 0)*float(t.get("qty") or 0)
                        except: ps=0
                        if ps<10000: return "<₹10K"
                        elif ps<25000: return "₹10-25K"
                        elif ps<50000: return "₹25-50K"
                        elif ps<100000: return "₹50-100K"
                        else: return "₹100K+"
                    return ""

                data_x = defaultdict(lambda: defaultdict(lambda: {"pnl":0,"wins":0,"count":0}))
                for t in closed:
                    if price_buckets:
                        try:
                            ep=float(t.get("entry_price") or 0)
                            row_v=next((lbl for lbl,lo,hi in (price_buckets or []) if lo<=ep<hi),None)
                        except: row_v=None
                    elif group_fn:
                        row_v=group_fn(t)
                    else:
                        row_v=t.get(group_field,"") or "Unknown"
                    col_v=get_col_val(t)
                    if not row_v or not col_v: continue
                    p=safe_float(t.get("pnl"))
                    data_x[row_v][col_v]["pnl"]+=p; data_x[row_v][col_v]["count"]+=1
                    if p>0: data_x[row_v][col_v]["wins"]+=1

                rows_f=[k for k in keys[:10] if k in data_x]
                # Limit to top 15 columns by total trade count to keep heatmap readable
                col_counts={c:sum(data_x[r].get(c,{}).get("count",0) for r in rows_f)
                            for c in {c for rv in data_x.values() for c in rv}}
                cols_f=sorted(col_counts,key=col_counts.get,reverse=True)[:15]
                cols_f=[c for c in cols_f if any(c in data_x[r] for r in rows_f)]
                if rows_f and cols_f:
                    fig=cross_heatmap(rows_f,cols_f,data_x,metric)
                    if fig: st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
                else:
                    st.info("Not enough data for cross analysis.")

            # ── SYMBOLS tab ──────────────────────────────────────────────
            with sym_sub[0]:
                d_sym = _build_sym_stats("ticker")
                _render_sym_section(d_sym, "Symbol", "sym", group_field="ticker", cross_col_field="strategy")

            # ── INSTRUMENTS tab (= Strategy in our schema) ───────────────
            with sym_sub[1]:
                d_inst = _build_sym_stats("strategy")
                _render_sym_section(d_inst, "Strategy", "inst", group_field="strategy", cross_col_field="ticker")

            # ── PRICES tab (entry price buckets) ─────────────────────────
            with sym_sub[2]:
                price_bkts = [
                    ("<₹50",    0,50),   ("₹50-100",50,100),  ("₹100-200",100,200),
                    ("₹200-500",200,500),("₹500-1K",500,1000),("₹1K-2K",1000,2000),
                    ("₹2K-5K",2000,5000),("₹5K+",5000,9999999)
                ]
                d_price = _build_sym_stats(None, price_buckets=price_bkts)
                _render_sym_section(d_price, "Price Range", "price", group_field=None, cross_col_field="strategy", price_buckets=price_bkts)

        # ════════════════════════════════════════════════════════════════════
        # RISK (sub-tabs: Volumes | Position Sizes | R-Multiples)
        # ════════════════════════════════════════════════════════════════════

        elif report_section == "⚠️ Risk":
            risk_sub = st.tabs(["📊 Volumes", "💰 Position Sizes", "📐 R-Multiples"])

            def _risk_render(buckets_def, get_key_fn, col_name, cross_key, description):
                """Full-spec risk section renderer."""
                # ── Aggregate ────────────────────────────────────────────
                bd = {k:{
                    "pnl":0,"wins":0,"losses":0,"count":0,
                    "win_sum":0,"loss_sum":0,
                    "r_sum":0,"r_wins":0,"r_losses":0,
                    "consec_wins":0,"consec_losses":0,"_cw":0,"_cl":0
                } for k,_,_ in buckets_def}

                for t in sorted(closed, key=lambda x: str(x.get("exit_date","") or "")):
                    k = get_key_fn(t, buckets_def)
                    if k is None: continue
                    p = safe_float(t.get("pnl"))
                    r = safe_float(t.get("r_multiple"))
                    d = bd[k]
                    d["pnl"]+=p; d["count"]+=1; d["r_sum"]+=r
                    if p>0:
                        d["wins"]+=1; d["win_sum"]+=p; d["r_wins"]+=r
                        d["_cw"]+=1; d["_cl"]=0
                        d["consec_wins"]=max(d["consec_wins"],d["_cw"])
                    else:
                        d["losses"]+=1; d["loss_sum"]+=p; d["r_losses"]+=r
                        d["_cl"]+=1; d["_cw"]=0
                        d["consec_losses"]=max(d["consec_losses"],d["_cl"])

                labels = [k for k,_,_ in buckets_def if bd[k]["count"]>0]
                if not labels:
                    st.info(f"No {description} data available."); return

                pnls  = [bd[k]["pnl"]   for k in labels]
                wrs   = [bd[k]["wins"]/bd[k]["count"] if bd[k]["count"] else 0 for k in labels]
                cnts  = [bd[k]["count"]  for k in labels]
                avgw  = [bd[k]["win_sum"]/bd[k]["wins"] if bd[k]["wins"] else 0 for k in labels]
                best  = labels[pnls.index(max(pnls))]
                worst = labels[pnls.index(min(pnls))]
                most  = labels[cnts.index(max(cnts))]
                bestwr= labels[wrs.index(max(wrs))] if any(wrs) else labels[0]

                # ── KPI strip ────────────────────────────────────────────
                st.markdown(kpi_strip([
                    (f"Best {description}",  best,   TEAL),
                    (f"Worst {description}", worst,  RED),
                    ("Most Active",          most,   BLUE),
                    ("Best Win Rate",        bestwr, TEAL),
                ]), unsafe_allow_html=True)

                # ── Customisable charts ──────────────────────────────────
                render_chart_pair(labels, pnls, cnts, avgw, wrs, f"risk_{cross_key}_chart")

                # ── Rich summary table ───────────────────────────────────
                rows = []
                for k in labels:
                    d = bd[k]; cl = d["wins"]+d["losses"]
                    pf = abs(d["win_sum"]/d["loss_sum"]) if d["loss_sum"] else 0
                    rows.append({
                        col_name:             k,
                        "Trades":             d["count"],
                        "Win %":              f"{d['wins']/cl*100:.1f}%" if cl else "—",
                        "Net P&L":            d["pnl"],
                        "Avg Win":            d["win_sum"]/d["wins"] if d["wins"] else 0,
                        "Avg Loss":           d["loss_sum"]/d["losses"] if d["losses"] else 0,
                        "Profit Factor":      f"{pf:.2f}" if pf else "—",
                        "Avg R":              f"{d['r_sum']/d['count']:.2f}R" if d["count"] else "—",
                        "Avg R (wins)":       f"{d['r_wins']/d['wins']:.2f}R" if d["wins"] else "—",
                        "Avg R (losses)":     f"{d['r_losses']/d['losses']:.2f}R" if d["losses"] else "—",
                        "Max Consec Wins":    d["consec_wins"],
                        "Max Consec Losses":  d["consec_losses"],
                        "Wins":               d["wins"],
                        "Losses":             d["losses"],
                    })
                df_r = pd.DataFrame(rows)
                def _rsty(row):
                    idx=df_r.columns.tolist(); styles=[""]*len(row)
                    for col in ("Net P&L","Avg Win","Avg Loss"):
                        if col in idx:
                            v=row.get(col,0)
                            if isinstance(v,(int,float)):
                                styles[idx.index(col)]=f"color:{TEAL};font-weight:600" if v>0 else f"color:{RED};font-weight:600" if v<0 else ""
                    return styles
                fmt_r = {
                    "Net P&L": lambda v: f"{'+'if v>=0 else ''}₹{abs(v):,.0f}" if isinstance(v,(int,float)) else v,
                    "Avg Win": lambda v: f"₹{v:,.0f}" if isinstance(v,(int,float)) and v else "—",
                    "Avg Loss": lambda v: f"₹{v:,.0f}" if isinstance(v,(int,float)) and v else "—",
                }
                st.dataframe(df_r.style.apply(_rsty,axis=1).format(fmt_r)
                    .set_properties(**{"font-size":"12.5px"}).set_table_styles(TABLE_STYLES),
                    use_container_width=True, hide_index=True)

                # ── Cross analysis ───────────────────────────────────────
                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:20px 0 8px">Cross Analysis</p>', unsafe_allow_html=True)
                ca1,ca2,ca3 = st.columns([2,2,3])
                cross_dim = ca1.selectbox("Columns", [
                    "Strategy","Symbol","Day of week","Month",
                    "Trade duration","R-Multiple","Position size"
                ], key=f"{cross_key}_dim", label_visibility="collapsed")
                metric = ca3.radio("Metric",["P&L","Win %","Trades"],
                                    horizontal=True, key=f"{cross_key}_metric",
                                    label_visibility="collapsed")

                def _get_col_v(t):
                    if cross_dim=="Strategy": return t.get("strategy","")
                    elif cross_dim=="Symbol": return t.get("ticker","")
                    elif cross_dim=="Day of week": return _get_dow(t)
                    elif cross_dim=="Month": return _get_month(t)
                    elif cross_dim=="Trade duration":
                        import re as _re
                        dur=str(t.get("duration","") or "")
                        m=_re.search(r"(\d+)\s*day",dur.lower())
                        days=int(m.group(1)) if m else 0
                        if days<1: return "<1d"
                        elif days<2: return "1d"
                        elif days<6: return "2-5d"
                        elif days<15: return "1-2wk"
                        else: return "2wk+"
                    elif cross_dim=="R-Multiple":
                        r=safe_float(t.get("r_multiple"))
                        if r<0: return "<0R"
                        elif r<1: return "0-1R"
                        elif r<2: return "1-2R"
                        elif r<3: return "2-3R"
                        else: return "3R+"
                    elif cross_dim=="Position size":
                        try: ps=float(t.get("position_size") or 0) or float(t.get("entry_price") or 0)*float(t.get("qty") or 0)
                        except: ps=0
                        if ps<10000: return "<₹10K"
                        elif ps<50000: return "₹10-50K"
                        elif ps<100000: return "₹50-100K"
                        else: return "₹100K+"
                    return ""

                data_x = defaultdict(lambda: defaultdict(lambda: {"pnl":0,"wins":0,"count":0}))
                for t in closed:
                    row_k=get_key_fn(t, buckets_def); col_v=_get_col_v(t)
                    if not row_k or not col_v: continue
                    p=safe_float(t.get("pnl"))
                    data_x[row_k][col_v]["pnl"]+=p; data_x[row_k][col_v]["count"]+=1
                    if p>0: data_x[row_k][col_v]["wins"]+=1

                rows_f=[k for k in labels if k in data_x]
                # Limit to top 15 columns by total trade count to keep heatmap readable
                col_counts={c:sum(data_x[r].get(c,{}).get("count",0) for r in rows_f)
                            for c in {c for rv in data_x.values() for c in rv}}
                cols_f=sorted(col_counts,key=col_counts.get,reverse=True)[:15]
                cols_f=[c for c in cols_f if any(c in data_x[r] for r in rows_f)]
                if rows_f and cols_f:
                    fig=cross_heatmap(rows_f, cols_f, data_x, metric)
                    if fig: st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
                else:
                    st.info("Not enough data for this cross analysis combination.")

            # ── VOLUMES ──────────────────────────────────────────────────
            with risk_sub[0]:
                st.markdown(f'<p style="color:{TEXT_MUTED};font-size:12px;margin-bottom:12px">Review how different trade volumes impact your performance.</p>', unsafe_allow_html=True)
                vol_buckets=[("1 to 4",1,5),("5 to 9",5,10),("10 to 19",10,20),
                             ("20 to 49",20,50),("50 to 99",50,100),("100+",100,9999)]
                def get_vol_key(t, buckets):
                    try: qty=int(float(t.get("qty") or 0))
                    except: return None
                    if qty<=0: return None
                    return next((lbl for lbl,lo,hi in buckets if lo<=qty<hi), None)
                _risk_render(vol_buckets, get_vol_key, "Volume", "vol", "Volume")

            # ── POSITION SIZES ───────────────────────────────────────────
            with risk_sub[1]:
                st.markdown(f'<p style="color:{TEXT_MUTED};font-size:12px;margin-bottom:12px">Assess the effect of position sizing on your outcomes.</p>', unsafe_allow_html=True)
                ps_buckets=[("<₹10K",0,10000),("₹10-25K",10000,25000),
                            ("₹25-50K",25000,50000),("₹50-100K",50000,100000),
                            ("₹100-250K",100000,250000),("₹250K+",250000,9999999)]
                def get_ps_key(t, buckets):
                    try: ps=float(t.get("position_size") or 0)
                    except: return None
                    if ps<=0:
                        try: ps=float(t.get("entry_price") or 0)*float(t.get("qty") or 0)
                        except: return None
                    if ps<=0: return None
                    return next((lbl for lbl,lo,hi in buckets if lo<=ps<hi), "₹250K+")
                _risk_render(ps_buckets, get_ps_key, "Position Size", "ps", "Position Size")

            # ── R-MULTIPLES ──────────────────────────────────────────────
            with risk_sub[2]:
                st.markdown(f'<p style="color:{TEXT_MUTED};font-size:12px;margin-bottom:12px">Analyze trades based on R-Multiple categories (risk-reward ratio).</p>', unsafe_allow_html=True)
                r_buckets=[("<0R",-999,0),("0-1R",0,1),("1-2R",1,2),
                           ("2-3R",2,3),("3-5R",3,5),("5R+",5,999)]
                def get_r_key(t, buckets):
                    r=safe_float(t.get("r_multiple"))
                    return next((lbl for lbl,lo,hi in buckets if lo<=r<hi), "5R+")
                _risk_render(r_buckets, get_r_key, "R-Multiple", "rmult", "R-Multiple")

        # ════════════════════════════════════════════════════════════════════
        # PLAYBOOKS
        # ════════════════════════════════════════════════════════════════════

        elif report_section == "📋 Playbooks":
            try: playbooks=get_playbooks()
            except: playbooks=[]

            # ── Aggregate per playbook ────────────────────────────────────
            pb_stats=[]
            for pb in playbooks:
                pb_trades=[t for t in closed
                           if (tp:=get_trade_playbook(t.get("id"))) and tp.get("playbook_id")==pb["id"]]
                n=len(pb_trades)
                if n==0:
                    pb_stats.append({"id":pb["id"],"name":pb["name"],"emoji":pb.get("emoji","📋"),
                        "color":pb.get("color","#64748B"),"n":0,"total":0,"wr":0,
                        "avg_w":0,"avg_l":0,"trades":[],"wins_n":0,"losses_n":0,
                        "r_sum":0,"pf":0,"consec_w":0,"consec_l":0})
                    continue
                total    = sum(safe_float(t.get("pnl")) for t in pb_trades)
                wins_pb  = [t for t in pb_trades if safe_float(t.get("pnl"))>0]
                losses_pb= [t for t in pb_trades if safe_float(t.get("pnl"))<0]
                wr       = len(wins_pb)/n
                avg_w    = sum(safe_float(t.get("pnl")) for t in wins_pb)/len(wins_pb) if wins_pb else 0
                avg_l    = sum(safe_float(t.get("pnl")) for t in losses_pb)/len(losses_pb) if losses_pb else 0
                pf       = abs(sum(safe_float(t.get("pnl")) for t in wins_pb)/
                              sum(safe_float(t.get("pnl")) for t in losses_pb)) if losses_pb else 0
                r_sum    = sum(safe_float(t.get("r_multiple")) for t in pb_trades)
                consec_w = _max_consec(pb_trades, True)
                consec_l = _max_consec(pb_trades, False)
                pb_stats.append({"id":pb["id"],"name":pb["name"],"emoji":pb.get("emoji","📋"),
                    "color":pb.get("color","#64748B"),"n":n,"total":total,"wr":wr,
                    "avg_w":avg_w,"avg_l":avg_l,"trades":pb_trades,
                    "wins_n":len(wins_pb),"losses_n":len(losses_pb),
                    "r_sum":r_sum,"pf":pf,"consec_w":consec_w,"consec_l":consec_l})

            pb_with=[p for p in pb_stats if p["n"]>0]

            # ── KPI strip ─────────────────────────────────────────────────
            if pb_with:
                best_pb  =max(pb_with,key=lambda p:p["total"])
                worst_pb =min(pb_with,key=lambda p:p["total"])
                most_pb  =max(pb_with,key=lambda p:p["n"])
                bestwr_pb=max(pb_with,key=lambda p:p["wr"])
                st.markdown(kpi_strip([
                    ("Best Playbook",  f"{best_pb['emoji']} {best_pb['name']}",   TEAL),
                    ("Worst Playbook", f"{worst_pb['emoji']} {worst_pb['name']}",  RED),
                    ("Most Active",    f"{most_pb['emoji']} {most_pb['name']}",    BLUE),
                    ("Best Win Rate",  f"{bestwr_pb['emoji']} {bestwr_pb['name']}", TEAL),
                ]), unsafe_allow_html=True)

                # ── Customisable charts ──────────────────────────────────
                pb_names=[f"{p['emoji']} {p['name']}" for p in pb_with]
                pb_pnls =[p["total"] for p in pb_with]
                pb_wrs  =[p["wr"]    for p in pb_with]
                pb_cnts =[p["n"]     for p in pb_with]
                pb_avgw =[p["avg_w"] for p in pb_with]
                render_chart_pair(pb_names, pb_pnls, pb_cnts, pb_avgw, pb_wrs, "pb_chart")

            # ── Rich summary table ────────────────────────────────────────
            pbrows=[]
            for p in pb_stats:
                cl=p["wins_n"]+p["losses_n"]
                pbrows.append({
                    "Playbook":      f"{p['emoji']} {p['name']}",
                    "Trades":        p["n"],
                    "Win %":         f"{p['wr']*100:.1f}%" if p["n"] else "—",
                    "Net P&L":       p["total"],
                    "Avg Win":       p["avg_w"],
                    "Avg Loss":      p["avg_l"],
                    "Profit Factor": f"{p['pf']:.2f}" if p["pf"] else "—",
                    "Avg R":         f"{p['r_sum']/p['n']:.2f}R" if p["n"] else "—",
                    "Max Consec W":  p["consec_w"],
                    "Max Consec L":  p["consec_l"],
                    "Wins":          p["wins_n"],
                    "Losses":        p["losses_n"],
                })
            df_pb = pd.DataFrame(pbrows)
            def _pbsty(row):
                idx=df_pb.columns.tolist(); styles=[""]*len(row)
                for col in ("Net P&L","Avg Win","Avg Loss"):
                    if col in idx:
                        v=row.get(col,0)
                        if isinstance(v,(int,float)):
                            styles[idx.index(col)]=f"color:{TEAL};font-weight:600" if v>0 else f"color:{RED};font-weight:600" if v<0 else ""
                return styles
            fmt_pb={
                "Net P&L": lambda v: f"{'+'if v>=0 else ''}₹{abs(v):,.0f}" if isinstance(v,(int,float)) else v,
                "Avg Win": lambda v: f"₹{v:,.0f}" if isinstance(v,(int,float)) and v else "—",
                "Avg Loss":lambda v: f"₹{v:,.0f}" if isinstance(v,(int,float)) and v else "—",
            }
            st.dataframe(df_pb.style.apply(_pbsty,axis=1).format(fmt_pb)
                .set_properties(**{"font-size":"12.5px"}).set_table_styles(TABLE_STYLES),
                use_container_width=True, hide_index=True)

            # ── Cross analysis ────────────────────────────────────────────
            if pb_with:
                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:20px 0 8px">Cross Analysis</p>', unsafe_allow_html=True)
                ca1,ca2,ca3=st.columns([2,2,3])
                cross_dim=ca1.selectbox("Columns",[
                    "Symbol","Day of week","Month","Trade duration","R-Multiple","Position size"
                ], key="pb_cross_dim", label_visibility="collapsed")
                metric=ca3.radio("Metric",["P&L","Win %","Trades"],
                                  horizontal=True,key="pb_cross_metric",label_visibility="collapsed")

                def _pb_col_val(t):
                    if cross_dim=="Symbol": return t.get("ticker","")
                    elif cross_dim=="Day of week": return _get_dow(t)
                    elif cross_dim=="Month": return _get_month(t)
                    elif cross_dim=="Trade duration":
                        import re as _re
                        dur=str(t.get("duration","") or "")
                        m=_re.search(r"(\d+)\s*day",dur.lower())
                        days=int(m.group(1)) if m else 0
                        if days<1: return "<1d"
                        elif days<2: return "1d"
                        elif days<6: return "2-5d"
                        elif days<15: return "1-2wk"
                        else: return "2wk+"
                    elif cross_dim=="R-Multiple":
                        r=safe_float(t.get("r_multiple"))
                        if r<0: return "<0R"
                        elif r<1: return "0-1R"
                        elif r<2: return "1-2R"
                        elif r<3: return "2-3R"
                        else: return "3R+"
                    elif cross_dim=="Position size":
                        try: ps=float(t.get("position_size") or 0) or float(t.get("entry_price") or 0)*float(t.get("qty") or 0)
                        except: ps=0
                        if ps<10000: return "<₹10K"
                        elif ps<50000: return "₹10-50K"
                        elif ps<100000: return "₹50-100K"
                        else: return "₹100K+"
                    return ""

                data_pb=defaultdict(lambda:defaultdict(lambda:{"pnl":0,"wins":0,"count":0}))
                for p in pb_with:
                    row=f"{p['emoji']} {p['name']}"
                    for t in p["trades"]:
                        col_v=_pb_col_val(t)
                        if not col_v: continue
                        pv=safe_float(t.get("pnl"))
                        data_pb[row][col_v]["pnl"]+=pv
                        data_pb[row][col_v]["count"]+=1
                        if pv>0: data_pb[row][col_v]["wins"]+=1

                rows_pb=[f"{p['emoji']} {p['name']}" for p in pb_with]
                col_counts3={c:sum(data_pb[r].get(c,{}).get("count",0) for r in rows_pb)
                             for c in {c for rv in data_pb.values() for c in rv}}
                cols_f=sorted(col_counts3,key=col_counts3.get,reverse=True)[:15]
                cols_f=[c for c in cols_f if any(c in data_pb[r] for r in rows_pb)]
                if rows_pb and cols_f:
                    fig=cross_heatmap(rows_pb, cols_f, data_pb, metric)
                    if fig: st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
                else:
                    st.info("Not enough data for cross analysis.")

        # ════════════════════════════════════════════════════════════════════
        # COMPARE
        # ════════════════════════════════════════════════════════════════════

        elif report_section == "🏷️ Tags":
            st.markdown(
                f'<p style="color:{TEXT_MUTED};font-size:12px;margin-bottom:12px">'
                f'Performance breakdown by tag category. Each tab shows a different tag group.</p>',
                unsafe_allow_html=True)

            # ── Tag categories — in your schema strategy = tag category ──
            # Each strategy is a "tag category", trades are tagged with it
            TAG_CATEGORIES = {
                "Strategies":  {"field":"strategy",  "trades": closed},
                "Symbols":     {"field":"ticker",    "trades": closed},
                "Win/Loss":    {"field":"win_loss",  "trades": closed},
            }
            cat_names = list(TAG_CATEGORIES.keys())
            tag_tabs  = st.tabs([f"📌 {c}" for c in cat_names])

            def _render_tag_section(field, trades_in, key_pfx):
                tag_d=defaultdict(lambda:{"pnl":0,"wins":0,"losses":0,"count":0,
                                          "win_sum":0,"loss_sum":0,"r_sum":0,
                                          "consec_w":0,"consec_l":0})
                for t in sorted(trades_in, key=lambda x: str(x.get("exit_date","") or "")):
                    tag=(t.get(field,"") or "Untagged")
                    p=safe_float(t.get("pnl")); r=safe_float(t.get("r_multiple"))
                    td=tag_d[tag]; td["pnl"]+=p; td["count"]+=1; td["r_sum"]+=r
                    if p>0: td["wins"]+=1; td["win_sum"]+=p
                    else:   td["losses"]+=1; td["loss_sum"]+=p

                # consec streaks per tag
                tag_cw=defaultdict(int); tag_cl=defaultdict(int)
                tag_cw_cur=defaultdict(int); tag_cl_cur=defaultdict(int)
                for t in sorted(trades_in, key=lambda x: str(x.get("exit_date","") or "")):
                    tag=(t.get(field,"") or "Untagged"); p=safe_float(t.get("pnl"))
                    if p>0:
                        tag_cw_cur[tag]+=1; tag_cl_cur[tag]=0
                        tag_cw[tag]=max(tag_cw[tag],tag_cw_cur[tag])
                    else:
                        tag_cl_cur[tag]+=1; tag_cw_cur[tag]=0
                        tag_cl[tag]=max(tag_cl[tag],tag_cl_cur[tag])
                for tag in tag_d:
                    tag_d[tag]["consec_w"]=tag_cw[tag]
                    tag_d[tag]["consec_l"]=tag_cl[tag]

                tags=sorted(tag_d.keys(),key=lambda s:tag_d[s]["pnl"],reverse=True)
                if not tags: st.info("No data."); return

                tpnls=[tag_d[s]["pnl"] for s in tags]
                twrs =[tag_d[s]["wins"]/tag_d[s]["count"] if tag_d[s]["count"] else 0 for s in tags]
                tcnts=[tag_d[s]["count"] for s in tags]
                tavgw=[tag_d[s]["win_sum"]/tag_d[s]["wins"] if tag_d[s]["wins"] else 0 for s in tags]

                best_t  =tags[0]; worst_t=tags[-1]
                most_t  =max(tags,key=lambda s:tag_d[s]["count"])
                bestwr_t=max(tags,key=lambda s:tag_d[s]["wins"]/tag_d[s]["count"] if tag_d[s]["count"] else 0)

                st.markdown(kpi_strip([
                    ("Best Tag",  best_t,   TEAL),
                    ("Worst Tag", worst_t,  RED),
                    ("Most Used", most_t,   BLUE),
                    ("Best Win %",bestwr_t, TEAL),
                ]), unsafe_allow_html=True)

                render_chart_pair(tags, tpnls, tcnts, tavgw, twrs, f"{key_pfx}_chart")

                # Rich summary table
                trows=[]
                for s in tags:
                    td=tag_d[s]; cl=td["wins"]+td["losses"]
                    pf=abs(td["win_sum"]/td["loss_sum"]) if td["loss_sum"] else 0
                    trows.append({
                        "Tag":           s,
                        "Trades":        td["count"],
                        "Win %":         f"{td['wins']/cl*100:.1f}%" if cl else "—",
                        "Net P&L":       td["pnl"],
                        "Avg Win":       td["win_sum"]/td["wins"] if td["wins"] else 0,
                        "Avg Loss":      td["loss_sum"]/td["losses"] if td["losses"] else 0,
                        "Profit Factor": f"{pf:.2f}" if pf else "—",
                        "Avg R":         f"{td['r_sum']/td['count']:.2f}R" if td["count"] else "—",
                        "Max Consec W":  td["consec_w"],
                        "Max Consec L":  td["consec_l"],
                        "Wins":          td["wins"],
                        "Losses":        td["losses"],
                    })
                df_t=pd.DataFrame(trows)
                def _tsty(row):
                    idx=df_t.columns.tolist(); styles=[""]*len(row)
                    for col in ("Net P&L","Avg Win","Avg Loss"):
                        if col in idx:
                            v=row.get(col,0)
                            if isinstance(v,(int,float)):
                                styles[idx.index(col)]=f"color:{TEAL};font-weight:600" if v>0 else f"color:{RED};font-weight:600" if v<0 else ""
                    return styles
                fmt_t={
                    "Net P&L": lambda v: f"{'+'if v>=0 else ''}₹{abs(v):,.0f}" if isinstance(v,(int,float)) else v,
                    "Avg Win": lambda v: f"₹{v:,.0f}" if isinstance(v,(int,float)) and v else "—",
                    "Avg Loss":lambda v: f"₹{v:,.0f}" if isinstance(v,(int,float)) and v else "—",
                }
                st.dataframe(df_t.style.apply(_tsty,axis=1).format(fmt_t)
                    .set_properties(**{"font-size":"12.5px"}).set_table_styles(TABLE_STYLES),
                    use_container_width=True, hide_index=True)

                # Cross analysis
                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:20px 0 8px">Cross Analysis</p>', unsafe_allow_html=True)
                ca1,ca2,ca3=st.columns([2,2,3])
                cross_dim=ca1.selectbox("Columns",[
                    "Symbol","Strategy","Day of week","Month",
                    "Trade duration","R-Multiple","Position size"
                ], key=f"{key_pfx}_cross_dim", label_visibility="collapsed")
                metric=ca3.radio("Metric",["P&L","Win %","Trades"],
                                  horizontal=True,key=f"{key_pfx}_cross_metric",
                                  label_visibility="collapsed")

                def _tcol(t):
                    if cross_dim=="Symbol": return t.get("ticker","")
                    elif cross_dim=="Strategy": return t.get("strategy","")
                    elif cross_dim=="Day of week": return _get_dow(t)
                    elif cross_dim=="Month": return _get_month(t)
                    elif cross_dim=="Trade duration":
                        import re as _re
                        dur=str(t.get("duration","") or "")
                        m=_re.search(r"(\d+)\s*day",dur.lower())
                        days=int(m.group(1)) if m else 0
                        if days<1: return "<1d"
                        elif days<2: return "1d"
                        elif days<6: return "2-5d"
                        else: return "1wk+"
                    elif cross_dim=="R-Multiple":
                        r=safe_float(t.get("r_multiple"))
                        if r<0: return "<0R"
                        elif r<1: return "0-1R"
                        elif r<2: return "1-2R"
                        else: return "2R+"
                    elif cross_dim=="Position size":
                        try: ps=float(t.get("position_size") or 0) or float(t.get("entry_price") or 0)*float(t.get("qty") or 0)
                        except: ps=0
                        if ps<25000: return "<₹25K"
                        elif ps<100000: return "₹25-100K"
                        else: return "₹100K+"
                    return ""

                data_t=defaultdict(lambda:defaultdict(lambda:{"pnl":0,"wins":0,"count":0}))
                for t in trades_in:
                    row_v=(t.get(field,"") or "Untagged"); col_v=_tcol(t)
                    if not row_v or not col_v: continue
                    p=safe_float(t.get("pnl"))
                    data_t[row_v][col_v]["pnl"]+=p; data_t[row_v][col_v]["count"]+=1
                    if p>0: data_t[row_v][col_v]["wins"]+=1

                rows_f=[k for k in tags if k in data_t]
                col_counts={c:sum(data_t[r].get(c,{}).get("count",0) for r in rows_f)
                            for c in {c for rv in data_t.values() for c in rv}}
                cols_f=sorted(col_counts,key=col_counts.get,reverse=True)[:15]
                cols_f=[c for c in cols_f if any(c in data_t[r] for r in rows_f)]
                if rows_f and cols_f:
                    fig=cross_heatmap(rows_f,cols_f,data_t,metric)
                    if fig: st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
                else:
                    st.info("Not enough data for cross analysis.")

            for tab, (cat_name, cat_cfg) in zip(tag_tabs, TAG_CATEGORIES.items()):
                with tab:
                    _render_tag_section(cat_cfg["field"], cat_cfg["trades"], f"tag_{cat_name.lower()}")

        elif report_section == "⚡ Wins vs Losses":
            # P&L metric selector — matches Tradezella "P&L SHOWING" control
            wvl_pc1, wvl_pc2 = st.columns([1, 11])
            wvl_pc1.markdown(
                f'<p style="font-size:10px;font-weight:700;color:{TEXT_SUBTLE};'
                f'text-transform:uppercase;letter-spacing:0.06em;padding-top:10px;'
                f'white-space:nowrap">P&L SHOWING</p>',
                unsafe_allow_html=True)
            wvl_metric = wvl_pc2.selectbox(
                "P&L metric", ["Net P&L", "Gross P&L", "Net P&L (%)"],
                key="wvl_pnl_metric", label_visibility="collapsed")

            # Wire wvl_metric to actual P&L field
            def _get_pnl(t):
                p = safe_float(t.get("pnl"))
                if wvl_metric == "Gross P&L":
                    comm = safe_float(t.get("commission_entry",0)) + safe_float(t.get("commission_exit",0))
                    return p + comm  # add back commissions to get gross
                elif wvl_metric == "Net P&L (%)":
                    ep = safe_float(t.get("entry_price") or 1)
                    qty = safe_float(t.get("qty") or 1)
                    cost = ep * qty
                    return (p / cost * 100) if cost else 0
                return p  # Net P&L (default)

            wins_g   = [t for t in closed if _get_pnl(t)>0]
            losses_g = [t for t in closed if _get_pnl(t)<=0]

            pnl_prefix = "%" if wvl_metric == "Net P&L (%)" else "₹"

            def _grp_stats_wl(grp):
                if not grp: return {}
                total   = sum(_get_pnl(t) for t in grp)
                wins_n  = sum(1 for t in grp if _get_pnl(t)>0)
                losses_n= len(grp)-wins_n
                avg_w   = sum(_get_pnl(t) for t in grp if _get_pnl(t)>0)/wins_n if wins_n else 0
                avg_l   = sum(_get_pnl(t) for t in grp if _get_pnl(t)<0)/losses_n if losses_n else 0
                avg_vol = sum(safe_float(t.get("qty")) for t in grp)/len(grp)
                comm    = sum(safe_float(t.get("commission_entry",0))+safe_float(t.get("commission_exit",0)) for t in grp)
                return {
                    "Total P&L":              total,
                    "Average Daily Volume":   avg_vol,
                    "Average Winning Trade":  avg_w if wins_n else "N/A",
                    "Average Losing Trade":   avg_l if losses_n else "N/A",
                    "Number of Winning Trades": wins_n,
                    "Number of Losing Trades":  losses_n,
                    "Max Consecutive Wins":   _max_consec(grp, True),
                    "Total Commissions":      comm,
                }

            def _cum_chart_wl(grp, color):
                by_d=defaultdict(float)
                for t in grp:
                    d=str(t.get("exit_date","") or "")[:10]
                    if d and d!="nan": by_d[d]+=_get_pnl(t)
                if not by_d: return None
                ds=sorted(by_d.keys()); cm=[]; rn=0
                for d in ds: rn+=by_d[d]; cm.append(rn)
                fill_col="rgba(16,185,129,0.30)" if color==TEAL else "rgba(239,68,68,0.30)"
                fig=go.Figure()
                fig.add_trace(go.Scatter(x=ds,y=cm,mode="lines",
                    line=dict(color=color,width=2.5),
                    fill="tozeroy",fillcolor=fill_col))
                l=chart_layout(height=280,title="")
                l["yaxis"]["tickprefix"]=pnl_prefix if pnl_prefix=="₹" else ""
                l["yaxis"]["ticksuffix"]=pnl_prefix if pnl_prefix=="%" else ""
                l["margin"]=dict(l=70,r=20,t=10,b=40)
                fig.update_layout(**l); return fig

            wl_c1,wl_c2=st.columns(2)
            for col,grp,label,color in [(wl_c1,wins_g,"WINS",TEAL),(wl_c2,losses_g,"LOSSES",RED)]:
                with col:
                    bg=f"rgba(16,185,129,0.04)" if color==TEAL else f"rgba(239,68,68,0.04)"
                    st.markdown(
                        f'<div style="background:{bg};border:1px solid {BORDER};border-radius:10px;padding:10px 16px;margin-bottom:12px">'
                        f'<p style="font-size:12px;font-weight:700;color:{color};margin:0">{label} ({len(grp)} Trades Matched)</p></div>',
                        unsafe_allow_html=True)
                    stats=_grp_stats_wl(grp)
                    st.markdown(
                        f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:16px 20px;margin-bottom:12px">'
                        f'<p style="font-size:10px;font-weight:700;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:4px">STATISTICS ({label})</p>'
                        f'<p style="font-size:10px;color:{TEXT_SUBTLE};margin-bottom:12px">(ALL DATES)</p>',
                        unsafe_allow_html=True)
                    rows_html=""
                    for k,v in stats.items():
                        if k=="Total P&L": fv=fmt_pnl(v); fc=pnl_color(v)
                        elif k in("Average Winning Trade","Average Losing Trade"):
                            if v=="N/A": fv="N/A"; fc=TEXT_MUTED
                            else: fv=fmt_pnl(v); fc=TEAL if v>=0 else RED
                        elif k=="Total Commissions": fv=fmt_pnl(v); fc=TEXT_MUTED
                        elif k=="Average Daily Volume": fv=f"{v:.2f}"; fc=TEXT_H
                        else: fv=str(int(v)) if isinstance(v,(int,float)) else str(v); fc=TEXT_H
                        rows_html+=(f'<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid {BORDER_LIGHT};font-size:13px"><span style="color:{TEXT_MUTED}">{k}</span><span style="color:{fc};font-weight:500">{fv}</span></div>')
                    st.markdown(rows_html+"</div>",unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:16px 20px">'
                        f'<p style="font-size:10px;font-weight:700;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:4px">DAILY NET CUMULATIVE P&L ({label})</p>'
                        f'<p style="font-size:10px;color:{TEXT_SUBTLE};margin-bottom:4px">(ALL DATES)</p>',
                        unsafe_allow_html=True)
                    fig_c=_cum_chart_wl(grp,color)
                    if fig_c: st.plotly_chart(fig_c,use_container_width=True,config={"displayModeBar":False})
                    st.markdown("</div>",unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # DEEP ANALYTICS — sub-tabbed: Position & P&L | Streaks | Risk & Expectancy
    # ════════════════════════════════════════════════════════════════════
    with tab_deep:
        import numpy as np

        if not closed:
            st.info("No closed trades yet.")
        else:
            da_sub1, da_sub2, da_sub3, da_sub4, da_sub5, da_sub6, da_sub7, da_sub8, da_sub9, da_sub10 = st.tabs(["📊 Position & P&L", "🔥 Streaks", "⚖️ Risk & Expectancy", "📈 Pareto / Asymmetry", "⏱ Duration Matrix", "🏭 Sector & Industry", "🎨 Visual Analytics", "🎯 Performance Attribution", "🧬 Multi-Dimension", "📰 Learning Feed"])

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 1: POSITION & P&L (existing content)
            # ════════════════════════════════════════════════════════════
            with da_sub1:
                pnls_d = [safe_float(t.get("pnl")) for t in closed]
                wins_d = [p for p in pnls_d if p > 0]
                losses_d = [p for p in pnls_d if p < 0]

                by_date_d = defaultdict(float)
                for t in closed:
                    d = str(t.get("exit_date","") or "")[:10]
                    if d and d != "nan":
                        by_date_d[d] += safe_float(t.get("pnl"))
                daily_vals = list(by_date_d.values())

                if len(daily_vals) > 1 and np.std(daily_vals) > 0:
                    sharpe = np.mean(daily_vals) / np.std(daily_vals)
                else:
                    sharpe = 0.0

                avg_pnl_day = np.mean(daily_vals) if daily_vals else 0
                expectancy_inr = np.mean(pnls_d) if pnls_d else 0

                sorted_closed = sorted(closed, key=lambda x: str(x.get("exit_date","") or ""))
                win_streak = loss_streak = cur_w = cur_l = 0
                for t in sorted_closed:
                    p = safe_float(t.get("pnl"))
                    if p > 0: cur_w += 1; cur_l = 0; win_streak = max(win_streak, cur_w)
                    else: cur_l += 1; cur_w = 0; loss_streak = max(loss_streak, cur_l)

                avg_win_inr = np.mean(wins_d) if wins_d else 0
                avg_loss_inr = np.mean(losses_d) if losses_d else 0

                risks = []
                for t in closed:
                    ep = safe_float(t.get("entry_price"))
                    sl = safe_float(t.get("stop_loss"))
                    qty = safe_float(t.get("qty"))
                    if ep and sl and qty:
                        risks.append(abs(ep - sl) * qty)
                avg_risk_inr = np.mean(risks) if risks else 0

                avg_pf_risk_pct = []
                for t in closed:
                    ep = safe_float(t.get("entry_price"))
                    sl = safe_float(t.get("stop_loss"))
                    if ep and sl:
                        avg_pf_risk_pct.append(abs(ep - sl) / ep * 100)
                avg_pf_risk = np.mean(avg_pf_risk_pct) if avg_pf_risk_pct else 0

                best_trade = max(pnls_d) if pnls_d else 0
                worst_trade = min(pnls_d) if pnls_d else 0

                r_vals = [safe_float(t.get("r_multiple")) for t in closed if t.get("r_multiple")]
                highest_r = max(r_vals) if r_vals else 0
                lowest_r = min(r_vals) if r_vals else 0
                avg_r = np.mean(r_vals) if r_vals else 0

                def kpi_card_accent(label, value, color, sub=None):
                    """KPI card with a colored top-border accent (Nexus multi-color style)."""
                    sub_html = f'<div style="font-size:11px;color:{TEXT_SUBTLE};margin-top:3px">{sub}</div>' if sub else ""
                    return f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-top:3px solid {color};
                        border-radius:10px;padding:14px 16px;box-shadow:{SHADOW_SM};min-height:78px">
                        <div style="font-size:10.5px;color:{TEXT_SUBTLE};text-transform:uppercase;
                            letter-spacing:0.07em;font-weight:500;margin-bottom:6px">{label}</div>
                        <div style="font-size:1.35rem;font-weight:700;color:{TEXT_H};letter-spacing:-0.02em;
                            font-variant-numeric:tabular-nums;line-height:1.2">{value}</div>
                        {sub_html}
                    </div>"""

                AC = DNA_COLORS  # 12-color accent cycle

                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Key Performance Metrics</p>', unsafe_allow_html=True)
                d1, d2, d3, d4 = st.columns(4)
                d1.markdown(kpi_card_accent("Avg PnL/Day", fmt_pnl(avg_pnl_day), AC[0],
                                      sub="Average daily profit/loss"), unsafe_allow_html=True)
                d2.markdown(kpi_card_accent("Sharpe Ratio", f"{sharpe:.2f}", AC[1],
                                      sub="Risk-adjusted return (daily)"), unsafe_allow_html=True)
                d3.markdown(kpi_card_accent("Expectancy", fmt_pnl(expectancy_inr), AC[2],
                                      sub="Expected profit per trade"), unsafe_allow_html=True)
                d4.markdown(kpi_card_accent("Avg Risk/Trade", fmt_pnl(avg_risk_inr), AC[3], sub="Average initial rupee risk"), unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                d5, d6, d7, d8 = st.columns(4)
                d5.markdown(kpi_card_accent("Win Streak", str(win_streak), AC[4], sub=f"Avg Win: {fmt_pnl(avg_win_inr)}"), unsafe_allow_html=True)
                d6.markdown(kpi_card_accent("Loss Streak", str(loss_streak), AC[5], sub=f"Avg Loss: {fmt_pnl(avg_loss_inr)}"), unsafe_allow_html=True)
                d7.markdown(kpi_card_accent("Avg PF Risk/Trade", f"{avg_pf_risk:.2f}%", AC[6], sub="Average risk vs entry price"), unsafe_allow_html=True)
                d8.markdown(kpi_card_accent("Best / Worst Trade", f"{fmt_pnl(best_trade)} / {fmt_pnl(worst_trade)}", AC[7],
                                      sub="Highest profit / Biggest loss"), unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                d9, d10, d11 = st.columns(3)
                d9.markdown(kpi_card_accent("Highest R", f"{highest_r:.2f}R", AC[8], sub="Best risk:reward"), unsafe_allow_html=True)
                d10.markdown(kpi_card_accent("Lowest R", f"{lowest_r:.2f}R", AC[9], sub="Worst risk:reward"), unsafe_allow_html=True)
                d11.markdown(kpi_card_accent("Avg R", f"{avg_r:.2f}R", AC[10], sub="Average risk:reward"), unsafe_allow_html=True)

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Aggregate PnL vs Day — Weekday Distribution</p>', unsafe_allow_html=True)
                DOW_FULL = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                dow_pnl = defaultdict(float)
                dow_count = defaultdict(int)
                for t in closed:
                    dow = _get_dow(t)
                    if dow:
                        dow_pnl[dow] += safe_float(t.get("pnl"))
                        dow_count[dow] += 1
                dow_x = [d for d in DOW_FULL if d in dow_pnl]
                dow_y = [dow_pnl[d] for d in dow_x]
                if dow_x:
                    fig_dow = go.Figure()
                    fig_dow.add_trace(go.Bar(x=dow_x, y=dow_y,
                        marker=dict(color=[TEAL if v>=0 else RED for v in dow_y], opacity=0.85, line=dict(width=0)),
                        text=[f"{c} trades" for c in [dow_count[d] for d in dow_x]],
                        textposition="outside", textfont=dict(size=9, color=TEXT_MUTED),
                        hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"))
                    l_dow = chart_layout(height=260, title="")
                    l_dow["yaxis"]["tickprefix"] = "₹"
                    fig_dow.update_layout(**l_dow)
                    st.plotly_chart(fig_dow, use_container_width=True, config={"displayModeBar":False})
                else:
                    st.info("No weekday data available.")

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Aggregate PnL vs Symbol</p>', unsafe_allow_html=True)
                sym_pnl = defaultdict(float)
                sym_count = defaultdict(int)
                for t in closed:
                    sym = t.get("ticker","")
                    if sym:
                        sym_pnl[sym] += safe_float(t.get("pnl"))
                        sym_count[sym] += 1
                top_syms = sorted(sym_pnl.items(), key=lambda x: x[1], reverse=True)[:15]
                if top_syms:
                    sym_x = [s for s,_ in top_syms]
                    sym_y = [v for _,v in top_syms]
                    fig_sym = go.Figure()
                    fig_sym.add_trace(go.Bar(x=sym_x, y=sym_y,
                        marker=dict(color=[TEAL if v>=0 else RED for v in sym_y], opacity=0.85, line=dict(width=0)),
                        hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"))
                    l_sym = chart_layout(height=280, title="Top 15 Symbols by Net P&L")
                    l_sym["yaxis"]["tickprefix"] = "₹"
                    l_sym["xaxis"]["tickangle"] = -40
                    fig_sym.update_layout(**l_sym)
                    st.plotly_chart(fig_sym, use_container_width=True, config={"displayModeBar":False})

                st.markdown(f'<p style="font-size:12px;color:{TEXT_MUTED};margin:12px 0 4px">Realized P&L Distribution — frequency spread of trade P&L size</p>', unsafe_allow_html=True)
                if pnls_d:
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(x=pnls_d, nbinsx=25,
                        marker=dict(color=TEAL, opacity=0.7),
                        hovertemplate="₹%{x:,.0f}<br>%{y} trades<extra></extra>"))
                    fig_dist.add_vline(x=0, line=dict(color=RED, width=1, dash="dash"))
                    l_dist = chart_layout(height=240, title="")
                    l_dist["xaxis"]["tickprefix"] = "₹"
                    l_dist["xaxis"]["title"] = dict(text="Trade P&L (₹)", font=dict(size=10, color=TEXT_SUBTLE))
                    fig_dist.update_layout(**l_dist)
                    st.plotly_chart(fig_dist, use_container_width=True, config={"displayModeBar":False})

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Stock Move % — Average Underlying Movement</p>', unsafe_allow_html=True)
                st.caption("% move of the underlying stock from entry to exit (not P&L% — the raw price move), bucketed by exit period.")

                move_period = st.radio("Period", ["Daily","Weekly","Monthly"], index=2, horizontal=True, key="deep_move_period")

                def stock_move_pct(t):
                    ep = safe_float(t.get("entry_price"))
                    xp = safe_float(t.get("exit_price"))
                    if ep <= 0: return None
                    side = str(t.get("side","") or "").upper()
                    raw = (xp - ep) / ep * 100
                    return raw if side not in ("SHORT","SELL") else -raw

                move_data = []
                for t in closed:
                    m = stock_move_pct(t)
                    ed = str(t.get("exit_date","") or "")[:10]
                    if m is not None and ed and ed != "nan":
                        move_data.append({"date": ed, "move": m})

                if move_data:
                    mdf = pd.DataFrame(move_data)
                    mdf["date"] = pd.to_datetime(mdf["date"])
                    if move_period == "Daily":
                        mdf["period"] = mdf["date"].dt.strftime("%Y-%m-%d")
                    elif move_period == "Weekly":
                        mdf["period"] = mdf["date"].dt.to_period("W").astype(str)
                    else:
                        mdf["period"] = mdf["date"].dt.strftime("%Y-%m")
                    grp = mdf.groupby("period")["move"].mean().reset_index().sort_values("period")

                    fig_move = go.Figure()
                    fig_move.add_trace(go.Scatter(x=grp["period"], y=grp["move"], mode="lines+markers",
                        line=dict(color=BLUE, width=2.5, shape="spline"),
                        marker=dict(size=6, color=BLUE),
                        fill="tozeroy", fillcolor="rgba(59,130,246,0.15)",
                        hovertemplate="%{x}<br>%{y:+.2f}%<extra></extra>"))
                    fig_move.add_hline(y=0, line=dict(color=BORDER_LIGHT, width=1))
                    l_move = chart_layout(height=260, title="")
                    l_move["yaxis"]["ticksuffix"] = "%"
                    fig_move.update_layout(**l_move)
                    st.plotly_chart(fig_move, use_container_width=True, config={"displayModeBar":False})
                else:
                    st.info("No entry/exit price data available to compute stock move %.")

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 2: STREAKS
            # ════════════════════════════════════════════════════════════
            with da_sub2:
                sorted_closed2 = sorted(closed, key=lambda x: str(x.get("exit_date","") or ""))

                cur_streak_n = 0
                cur_streak_type = None
                run_type = None
                run_pnl = 0.0
                run_n = 0
                run_syms = []

                best_streak_pnl = 0.0
                best_streak_label = ""
                worst_streak_pnl = 0.0
                worst_streak_label = ""

                streaks_list = []

                for t in sorted_closed2:
                    p = safe_float(t.get("pnl"))
                    ttype = "W" if p > 0 else "L"
                    sym = t.get("ticker","")
                    if ttype == run_type:
                        run_pnl += p
                        run_n += 1
                        run_syms.append(sym)
                    else:
                        if run_type is not None:
                            streaks_list.append((run_type, run_n, run_pnl, run_syms[0] if run_syms else "", run_syms[-1] if run_syms else ""))
                        run_type = ttype
                        run_pnl = p
                        run_n = 1
                        run_syms = [sym]
                if run_type is not None:
                    streaks_list.append((run_type, run_n, run_pnl, run_syms[0] if run_syms else "", run_syms[-1] if run_syms else ""))

                if streaks_list:
                    last_type, last_n, last_pnl, _, _ = streaks_list[-1]
                    cur_streak_type = "WINNING" if last_type == "W" else "LOSING"
                    cur_streak_n = last_n

                    win_streaks_pnl = [(n, pnl, s1, s2) for ty,n,pnl,s1,s2 in streaks_list if ty=="W"]
                    loss_streaks_pnl = [(n, pnl, s1, s2) for ty,n,pnl,s1,s2 in streaks_list if ty=="L"]

                    if win_streaks_pnl:
                        best = max(win_streaks_pnl, key=lambda x: x[1])
                        best_streak_pnl = best[1]
                        best_streak_label = f"RECORD: W{best[0]} · {best[2]}, {best[3]}"
                    if loss_streaks_pnl:
                        worst = min(loss_streaks_pnl, key=lambda x: x[1])
                        worst_streak_pnl = worst[1]
                        worst_streak_label = f"WORST: L{worst[0]}"

                cs_col = RED if cur_streak_type == "LOSING" else TEAL
                sc1, sc2, sc3 = st.columns(3)
                sc1.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
                    padding:16px;text-align:center">
                    <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Current</div>
                    <div style="font-size:24px;font-weight:800;color:{cs_col};margin:4px 0">{('L' if cur_streak_type=='LOSING' else 'W')}{cur_streak_n}</div>
                    <div style="font-size:10px;color:{TEXT_SUBTLE};text-transform:uppercase">{cur_streak_type or '—'}</div>
                </div>""", unsafe_allow_html=True)
                sc2.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
                    padding:16px;text-align:center">
                    <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Best Streak</div>
                    <div style="font-size:20px;font-weight:800;color:{TEAL};margin:4px 0">{fmt_pnl(best_streak_pnl)}</div>
                    <div style="font-size:9px;color:{TEXT_SUBTLE}">{best_streak_label}</div>
                </div>""", unsafe_allow_html=True)
                sc3.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
                    padding:16px;text-align:center">
                    <div style="font-size:9.5px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.07em">Worst Streak</div>
                    <div style="font-size:20px;font-weight:800;color:{RED};margin:4px 0">{fmt_pnl(worst_streak_pnl)}</div>
                    <div style="font-size:9px;color:{TEXT_SUBTLE}">{worst_streak_label}</div>
                </div>""", unsafe_allow_html=True)

                st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

                st.markdown(f'<p style="font-size:12px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:8px">Trade-by-Trade Move %</p>', unsafe_allow_html=True)

                def stock_move_pct2(t):
                    ep = safe_float(t.get("entry_price"))
                    xp = safe_float(t.get("exit_price"))
                    if ep <= 0: return None
                    side = str(t.get("side","") or "").upper()
                    raw = (xp - ep) / ep * 100
                    return raw if side not in ("SHORT","SELL") else -raw

                grid_trades = sorted_closed2[-70:]
                n_grid_cols = 7
                for row_start in range(0, len(grid_trades), n_grid_cols):
                    row = grid_trades[row_start:row_start+n_grid_cols]
                    gcols = st.columns(n_grid_cols)
                    for gc, t in zip(gcols, row):
                        mv = stock_move_pct2(t)
                        sym = t.get("ticker","")
                        if mv is None:
                            continue
                        bg = TEAL_BG if mv >= 0 else RED_BG
                        fg = TEAL if mv >= 0 else RED
                        gc.markdown(f"""<div style="background:{bg};border-radius:6px;padding:6px 4px;
                            text-align:center;margin-bottom:4px">
                            <div style="font-size:9px;color:{fg};font-weight:700;white-space:nowrap;
                                overflow:hidden;text-overflow:ellipsis">{sym}</div>
                            <div style="font-size:11px;color:{fg};font-weight:700">{mv:+.1f}%</div>
                        </div>""", unsafe_allow_html=True)

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Trading Calendar Heatmap</p>', unsafe_allow_html=True)
                st.caption("Realized P&L spread mapped on a calendar view")

                cal_pnl = defaultdict(float)
                for t in closed:
                    d = str(t.get("exit_date","") or "")[:10]
                    if d and d != "nan":
                        cal_pnl[d] += safe_float(t.get("pnl"))

                if cal_pnl:
                    cal_df = pd.DataFrame([{"date": d, "pnl": v} for d, v in cal_pnl.items()])
                    cal_df["date"] = pd.to_datetime(cal_df["date"])
                    cal_df["year"] = cal_df["date"].dt.year
                    years_avail = sorted(cal_df["year"].unique(), reverse=True)
                    sel_year = st.selectbox("Year", years_avail, key="deep_streak_cal_year")
                    ydf = cal_df[cal_df["year"] == sel_year].copy()
                    ydf["week"] = ydf["date"].dt.isocalendar().week
                    ydf["dow"] = ydf["date"].dt.dayofweek

                    max_abs = ydf["pnl"].abs().max() if not ydf.empty else 1

                    def cal_color(v):
                        if v is None: return BORDER_LIGHT
                        intensity = min(abs(v) / max_abs, 1.0) if max_abs else 0
                        if v >= 0:
                            return f"rgba(16,185,129,{0.15 + intensity*0.6:.2f})"
                        return f"rgba(239,68,68,{0.15 + intensity*0.6:.2f})"

                    pivot = ydf.pivot_table(index="dow", columns="week", values="pnl", aggfunc="sum")
                    weeks_sorted = sorted(pivot.columns)
                    months_for_weeks = ydf.groupby("week")["date"].first().dt.strftime("%b")

                    html = '<div style="overflow-x:auto"><table style="border-collapse:separate;border-spacing:2px">'
                    html += "<tr><td></td>"
                    last_mo = ""
                    for wk in weeks_sorted:
                        mo = months_for_weeks.get(wk, "")
                        html += f'<td style="font-size:8px;color:{TEXT_MUTED};text-align:center">{"" if mo==last_mo else mo}</td>'
                        last_mo = mo
                    html += "</tr>"
                    DOW_LABELS = ["M","T","W","T","F","S","S"]
                    for dow in range(7):
                        html += f'<tr><td style="font-size:8px;color:{TEXT_MUTED};padding-right:3px">{DOW_LABELS[dow]}</td>'
                        for wk in weeks_sorted:
                            v = pivot.loc[dow, wk] if (dow in pivot.index and wk in pivot.columns and not pd.isna(pivot.loc[dow, wk])) else None
                            bg = cal_color(v)
                            tip = f"₹{v:,.0f}" if v is not None else "No trades"
                            html += f'<td title="{tip}" style="width:12px;height:12px;background:{bg};border-radius:2px"></td>'
                        html += "</tr>"
                    html += "</table></div>"
                    st.markdown(html, unsafe_allow_html=True)

                    total_for_year = ydf["pnl"].sum()
                    st.markdown(f"""<div style="display:flex;gap:14px;align-items:center;margin-top:8px;font-size:10px;color:{TEXT_SUBTLE}">
                        <span>⚪ No trades</span>
                        <span style="color:{RED}">🔴 Loss</span>
                        <span style="color:{TEAL}">🟢 Profit</span>
                        <span style="margin-left:auto;color:{TEXT_H};font-weight:700">Total: {fmt_pnl(total_for_year)}</span>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.info("No trade data for calendar heatmap.")

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 3: RISK & EXPECTANCY (Month-on-Month matrix)
            # ════════════════════════════════════════════════════════════
            with da_sub3:
                st.markdown(f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin:8px 0">Month-on-Month Risk & Expectancy Matrix</p>', unsafe_allow_html=True)

                by_month = defaultdict(list)
                for t in closed:
                    m = str(t.get("exit_date","") or "")[:7]
                    if m and m != "nan":
                        by_month[m].append(t)
                open_by_month = defaultdict(list)
                for t in trades:
                    if t.get("status") == "OPEN":
                        m = str(t.get("entry_date","") or "")[:7]
                        if m and m != "nan":
                            open_by_month[m].append(t)

                all_months_sorted = sorted(set(list(by_month.keys()) + list(open_by_month.keys())), reverse=True)[:6]

                if not all_months_sorted:
                    st.info("Not enough data for month-on-month matrix.")
                else:
                    def fmt_month_label(m):
                        try:
                            return pd.to_datetime(m + "-01").strftime("%b %Y").upper()
                        except Exception:
                            return m

                    month_stats = {}
                    for m in all_months_sorted:
                        ct = by_month.get(m, [])
                        ot = open_by_month.get(m, [])
                        pnls_m = [safe_float(t.get("pnl")) for t in ct]
                        wins_m = [p for p in pnls_m if p > 0]
                        losses_m = [p for p in pnls_m if p < 0]
                        be_m = [p for p in pnls_m if p == 0]
                        wr_m = len(wins_m) / len(pnls_m) * 100 if pnls_m else 0
                        avg_loss_m = np.mean(losses_m) if losses_m else 0
                        avg_gain_m = np.mean(wins_m) if wins_m else 0
                        r_vals_m = [safe_float(t.get("r_multiple")) for t in ct if t.get("r_multiple")]
                        r_wins_m = [r for r in r_vals_m if r > 0]
                        r_losses_m = [r for r in r_vals_m if r <= 0]
                        avg_r_loss = np.mean(r_losses_m) if r_losses_m else 0
                        avg_r_gain = np.mean(r_wins_m) if r_wins_m else 0
                        expectancy_r = (wr_m/100 * avg_r_gain) + ((1 - wr_m/100) * avg_r_loss) if r_vals_m else 0
                        total_r = sum(r_vals_m)
                        total_profit_entry = sum(safe_float(t.get("pnl")) for t in ct
                                                  if str(t.get("entry_date",""))[:7] == m)
                        total_profit_close = sum(pnls_m)

                        month_stats[m] = {
                            "entered": len(ct) + len(ot), "open": len(ot), "closed": len(ct),
                            "be": len(be_m), "winners": len(wins_m), "losers": len(losses_m),
                            "win_rate": wr_m, "avg_loss": avg_loss_m, "avg_gain": avg_gain_m,
                            "avg_r_loss": avg_r_loss, "avg_r_gain": avg_r_gain,
                            "arr": (avg_r_gain / abs(avg_r_loss)) if avg_r_loss else 0,
                            "expectancy_r": expectancy_r, "total_r": total_r,
                            "avg_risk_r": np.mean([abs(r) for r in r_vals_m]) if r_vals_m else 0,
                            "profit_entry": total_profit_entry, "profit_close": total_profit_close,
                        }

                    ROWS = [
                        ("1. TRADES", None, None),
                        ("Trades Entered", "entered", "int"),
                        ("Open Till Date", "open", "bracket"),
                        ("Trades Closed", "closed", "int"),
                        ("Breakeven", "be", "bracket"),
                        ("Winners", "winners", "int_green"),
                        ("Losers", "losers", "int_red"),
                        ("Win Rate", "win_rate", "pct"),
                        ("2. AVERAGES", None, None),
                        ("Avg Loss (Losers)", "avg_loss", "inr_red"),
                        ("Avg Gain (Winners)", "avg_gain", "inr_green"),
                        ("3. RISK/REWARD", None, None),
                        ("Avg R Loss (Losers)", "avg_r_loss", "r_red"),
                        ("Avg R Gain (Winners)", "avg_r_gain", "r_green"),
                        ("ARR", "arr", "num"),
                        ("4. EXPECTANCY", None, None),
                        ("Trade Expectancy (in R)", "expectancy_r", "r_signed"),
                        ("Trades Closed", "closed", "int"),
                        ("Total R Gained", "total_r", "r_signed"),
                        ("5. PROFITABILITY", None, None),
                        ("Avg Risk (R)", "avg_risk_r", "r"),
                        ("Total Profit (By Entry Date)", "profit_entry", "inr_signed"),
                        ("Total Profit (By Close Date)", "profit_close", "inr_signed"),
                    ]

                    def fmt_cell(val, kind):
                        if kind is None:
                            return ""
                        if kind == "int":
                            return str(int(val))
                        if kind == "int_green":
                            return f'<span style="color:{TEAL};font-weight:700">{int(val)}</span>'
                        if kind == "int_red":
                            return f'<span style="color:{RED};font-weight:700">{int(val)}</span>'
                        if kind == "bracket":
                            return f'<span style="color:{BLUE}">[{int(val)}]</span>'
                        if kind == "pct":
                            return f"{val:.0f}%"
                        if kind == "inr_red":
                            return f'<span style="color:{RED}">{fmt_pnl(val) if val else "₹0"}</span>'
                        if kind == "inr_green":
                            return f'<span style="color:{TEAL}">{fmt_pnl(val) if val else "₹0"}</span>'
                        if kind == "inr_signed":
                            return f'<span style="color:{pnl_color(val)};font-weight:700">{fmt_pnl(val)}</span>'
                        if kind == "r_red":
                            return f'<span style="color:{RED}">{val:.0f}R</span>'
                        if kind == "r_green":
                            return f'<span style="color:{TEAL}">+{val:.0f}R</span>'
                        if kind == "r":
                            return f"{val:.0f}R"
                        if kind == "r_signed":
                            return f'<span style="color:{pnl_color(val)}">{val:+.0f}R</span>'
                        if kind == "num":
                            return f"{val:.0f}"
                        return str(val)

                    th_style = f"padding:9px 14px;text-align:left;color:{TEXT_SUBTLE};font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;border-bottom:2px solid {BORDER};background:{CARD_BG};white-space:nowrap"
                    td_style = f"padding:8px 14px;font-size:13px;border-bottom:1px solid {BORDER_LIGHT};white-space:nowrap"
                    section_style = f"padding:10px 14px;font-size:11px;font-weight:700;font-style:italic;color:{TEXT_H};background:{PAGE_BG}"

                    rows_html = ""
                    for label, key, kind in ROWS:
                        if key is None:
                            rows_html += f'<tr><td colspan="{len(all_months_sorted)+1}" style="{section_style}">{label}</td></tr>'
                        else:
                            rows_html += f'<tr><td style="{td_style};color:{TEXT_MUTED}">{label}</td>'
                            for m in all_months_sorted:
                                val = month_stats[m].get(key, 0)
                                rows_html += f'<td style="{td_style};text-align:center">{fmt_cell(val, kind)}</td>'
                            rows_html += "</tr>"

                    header_html = f'<th style="{th_style}">Matrix Metrics</th>' + "".join(
                        f'<th style="{th_style};text-align:center">{fmt_month_label(m)}</th>' for m in all_months_sorted)

                    st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER};box-shadow:{SHADOW_SM}">
                        <table style="width:100%;border-collapse:collapse">
                        <thead><tr>{header_html}</tr></thead>
                        <tbody>{rows_html}</tbody>
                        </table>
                    </div>""", unsafe_allow_html=True)
            # ════════════════════════════════════════════════════════════
            # SUB-TAB 4: PARETO / ASYMMETRY
            # ════════════════════════════════════════════════════════════
            with da_sub4:
                st.caption("How concentrated is your profit? This is the structural-asymmetry lens on your MFE-capture problem.")

                def stock_move_pct_pareto(t):
                    ep = safe_float(t.get("entry_price"))
                    xp = safe_float(t.get("exit_price"))
                    if ep <= 0:
                        return 0.0
                    side = str(t.get("side","") or "").upper()
                    raw = (xp - ep) / ep * 100
                    return raw if side != "SHORT" else -raw

                pc1, pc2 = st.columns([1,3])
                with pc1:
                    pareto_strat_opts = ["All Strategies"] + sorted({t.get("strategy","") for t in closed if t.get("strategy")})
                    pareto_strat_sel = st.selectbox("Strategy", pareto_strat_opts, key="deep_pareto_strat")
                pareto_closed = closed if pareto_strat_sel == "All Strategies" else [t for t in closed if t.get("strategy") == pareto_strat_sel]

                pareto_wins = [t for t in pareto_closed if safe_float(t.get("pnl")) > 0]
                pareto_total_gross = sum(safe_float(t.get("pnl")) for t in pareto_wins)

                if not pareto_wins or pareto_total_gross <= 0:
                    st.info("No winning trades yet to analyze.")
                else:
                    pareto_wins_sorted = sorted(pareto_wins, key=lambda t: safe_float(t.get("pnl")), reverse=True)

                    pareto_cum_pct = []
                    pareto_running = 0.0
                    for t in pareto_wins_sorted:
                        pareto_running += safe_float(t.get("pnl"))
                        pareto_cum_pct.append(pareto_running / pareto_total_gross * 100)

                    pn = len(pareto_wins_sorted)
                    p_top1 = pareto_cum_pct[0] if pn >= 1 else 0
                    p_top3 = pareto_cum_pct[min(2, pn-1)] if pn >= 1 else 0
                    p_top5 = pareto_cum_pct[min(4, pn-1)] if pn >= 1 else 0

                    pareto_n = next((i+1 for i, c in enumerate(pareto_cum_pct) if c >= 80), pn)
                    pareto_share = pareto_cum_pct[pareto_n-1] if pareto_n <= pn else 100.0

                    pleft, pright = st.columns([1, 2])
                    with pleft:
                        st.markdown(f"""<div style="background:{TEAL_BG};border:1px solid {TEAL_BORDER};border-radius:12px;padding:18px 20px;">
                            <div style="display:inline-flex;align-items:center;gap:6px;background:{CARD_BG};border:1px solid {TEAL_BORDER};
                                border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600;color:{TEAL_DARK};margin-bottom:10px">
                                ⚡ ASYMMETRY {"FOUND" if pareto_share >= 70 else "MODERATE"}
                            </div>
                            <div style="font-size:11px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;font-weight:500;margin-bottom:6px">
                                Statistical Narrative
                            </div>
                            <div style="font-size:14px;color:{TEXT_BODY};line-height:1.5">
                                A significant <b style="color:{TEXT_H};font-size:16px">{pareto_share:.1f}%</b> of your gross profit comes
                                from just <b style="color:{TEXT_H};font-size:16px">{pareto_n}</b> trades (out of {pn} winners, {len(pareto_closed)} closed total).
                            </div>
                        </div>""", unsafe_allow_html=True)

                        st.markdown("<br>", unsafe_allow_html=True)
                        pk1, pk2, pk3 = st.columns(3)
                        pk1.markdown(kpi_card("TOP 1", f"{p_top1:.0f}%"), unsafe_allow_html=True)
                        pk2.markdown(kpi_card("TOP 3", f"{p_top3:.0f}%"), unsafe_allow_html=True)
                        pk3.markdown(kpi_card("TOP 5", f"{p_top5:.0f}%"), unsafe_allow_html=True)

                    with pright:
                        fig_pareto = go.Figure()
                        px = list(range(1, pn+1))
                        fig_pareto.add_trace(go.Scatter(
                            x=px, y=pareto_cum_pct, mode="lines+markers", fill="tozeroy",
                            fillcolor="rgba(16,185,129,0.20)",
                            line=dict(color=TEAL, width=2.5, shape="spline"),
                            marker=dict(size=5, color=TEAL),
                            hovertemplate="Top %{x} trades<br>%{y:.1f}% of profit<extra></extra>",
                        ))
                        fig_pareto.add_hline(y=80, line=dict(color=AMBER, width=1, dash="dash"),
                                       annotation_text="80%", annotation_font=dict(color=AMBER, size=9))
                        l_pareto = chart_layout(height=280, title="Cumulative Gross Profit Share — Top N Winners")
                        l_pareto["yaxis"]["range"] = [0, 105]
                        l_pareto["yaxis"]["ticksuffix"] = "%"
                        l_pareto["xaxis"]["title"] = dict(text="N winning trades", font=dict(size=10, color=TEXT_SUBTLE))
                        fig_pareto.update_layout(**l_pareto)
                        st.plotly_chart(fig_pareto, use_container_width=True)

                    st.markdown(section_label("Top Winners Breakdown"), unsafe_allow_html=True)

                    pareto_rows = []
                    for i, t in enumerate(pareto_wins_sorted[:15]):
                        p = safe_float(t.get("pnl"))
                        pareto_rows.append({
                            "#": f"#{i+1}",
                            "Symbol": t.get("ticker",""),
                            "Strategy": t.get("strategy",""),
                            "Stock Move %": f"{stock_move_pct_pareto(t):+.1f}%",
                            "P&L": fmt_pnl(p),
                            "PF Impact %": f"{p/pareto_total_gross*100:+.1f}%",
                            "Exit Date": str(t.get("exit_date",""))[:10],
                        })
                    pareto_df = pd.DataFrame(pareto_rows)
                    st.dataframe(pareto_df, use_container_width=True, hide_index=True)

                    st.markdown(section_label("What this means"), unsafe_allow_html=True)
                    st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 18px;font-size:13px;color:{TEXT_BODY};line-height:1.6">
                        If a small number of trades drive most of your profit, your exit execution on the <i>rest</i> of your winners is likely
                        cutting them short — i.e. an MFE-capture problem, not a stop-loss problem. The fix is usually trailing/scale-out discipline
                        on trades that are already working, not finding more setups.
                    </div>""", unsafe_allow_html=True)
            # ════════════════════════════════════════════════════════════
            # SUB-TAB 5: DURATION MATRIX
            # ════════════════════════════════════════════════════════════
            with da_sub5:
                from plotly.subplots import make_subplots
                from datetime import datetime as _dt

                st.caption("Correlation between holding period and profitability — sharpens stop/exit timing across strategies.")

                DUR_BUCKETS = ["Intraday", "1-3 Days", "4-7 Days", "1-2 Weeks", "2-4 Weeks", "1-2 Months", "2+ Months"]

                def dur_holding_days(t):
                    try:
                        ed = _dt.strptime(str(t.get("entry_date",""))[:10], "%Y-%m-%d")
                        xd = _dt.strptime(str(t.get("exit_date",""))[:10], "%Y-%m-%d")
                        return (xd - ed).days
                    except Exception:
                        return None

                def dur_bucket_for(days):
                    if days is None: return None
                    if days <= 0: return "Intraday"
                    if days <= 3: return "1-3 Days"
                    if days <= 7: return "4-7 Days"
                    if days <= 14: return "1-2 Weeks"
                    if days <= 28: return "2-4 Weeks"
                    if days <= 60: return "1-2 Months"
                    return "2+ Months"

                dc1, dc2 = st.columns([1,3])
                with dc1:
                    dur_strat_opts = ["All Strategies"] + sorted({t.get("strategy","") for t in closed if t.get("strategy")})
                    dur_strat_sel = st.selectbox("Strategy", dur_strat_opts, key="deep_dur_strat")
                dur_closed = closed if dur_strat_sel == "All Strategies" else [t for t in closed if t.get("strategy") == dur_strat_sel]

                dur_data = []
                for t in dur_closed:
                    d = dur_holding_days(t)
                    b = dur_bucket_for(d)
                    if b is None: continue
                    dur_data.append({"bucket": b, "pnl": safe_float(t.get("pnl")), "days": d})

                if not dur_data:
                    st.info("No closed trades with valid entry/exit dates found.")
                else:
                    dur_df = pd.DataFrame(dur_data)
                    dur_df["bucket"] = pd.Categorical(dur_df["bucket"], categories=DUR_BUCKETS, ordered=True)
                    dur_grp = dur_df.groupby("bucket", observed=True).agg(
                        trades=("pnl","count"),
                        avg_pnl=("pnl","mean"),
                        total_pnl=("pnl","sum"),
                        win_rate=("pnl", lambda s: (s>0).mean()*100),
                    ).reindex(DUR_BUCKETS).fillna(0)

                    dur_best_bucket = dur_grp["avg_pnl"].idxmax() if dur_grp["trades"].sum() > 0 else "—"
                    dur_worst_bucket = dur_grp["avg_pnl"].idxmin() if dur_grp["trades"].sum() > 0 else "—"
                    dk1, dk2, dk3, dk4 = st.columns(4)
                    dk1.markdown(kpi_card("TOTAL CLOSED TRADES", f"{int(dur_grp['trades'].sum())}"), unsafe_allow_html=True)
                    dk2.markdown(kpi_card("BEST AVG P/L BUCKET", dur_best_bucket, color=TEAL), unsafe_allow_html=True)
                    dk3.markdown(kpi_card("WORST AVG P/L BUCKET", dur_worst_bucket, color=RED), unsafe_allow_html=True)
                    dk4.markdown(kpi_card("MEDIAN HOLDING DAYS", f"{dur_df['days'].median():.0f}d"), unsafe_allow_html=True)

                    st.markdown("<br>", unsafe_allow_html=True)

                    ducol1, ducol2 = st.columns(2)
                    with ducol1:
                        st.markdown(section_label("Volume by Duration"), unsafe_allow_html=True)
                        fig_vol = go.Figure()
                        fig_vol.add_trace(go.Bar(x=DUR_BUCKETS, y=dur_grp["trades"], marker=dict(color=BLUE, opacity=0.85),
                                              hovertemplate="%{x}<br>%{y} trades<extra></extra>"))
                        l_vol = chart_layout(height=260)
                        l_vol["yaxis"]["title"] = dict(text="Trades", font=dict(size=10, color=TEXT_SUBTLE))
                        fig_vol.update_layout(**l_vol)
                        st.plotly_chart(fig_vol, use_container_width=True)

                    with ducol2:
                        st.markdown(section_label("Returns by Duration"), unsafe_allow_html=True)
                        fig_ret = go.Figure()
                        dur_colors = [TEAL if v>=0 else RED for v in dur_grp["avg_pnl"]]
                        fig_ret.add_trace(go.Bar(x=DUR_BUCKETS, y=dur_grp["avg_pnl"], marker=dict(color=dur_colors, opacity=0.9),
                                              hovertemplate="%{x}<br>₹%{y:,.0f} avg<extra></extra>"))
                        l_ret = chart_layout(height=260)
                        l_ret["yaxis"]["title"] = dict(text="Avg P/L (₹)", font=dict(size=10, color=TEXT_SUBTLE))
                        l_ret["yaxis"]["tickprefix"] = "₹"
                        fig_ret.update_layout(**l_ret)
                        st.plotly_chart(fig_ret, use_container_width=True)

                    st.markdown(section_label("Duration Performance Matrix — Correlation Between Frequency & Profitability"), unsafe_allow_html=True)
                    fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_combo.add_trace(go.Bar(x=DUR_BUCKETS, y=dur_grp["trades"], name="# Trades",
                                          marker=dict(color=BLUE, opacity=0.55),
                                          hovertemplate="%{x}<br>%{y} trades<extra></extra>"), secondary_y=False)
                    fig_combo.add_trace(go.Scatter(x=DUR_BUCKETS, y=dur_grp["avg_pnl"], name="Avg P/L", mode="lines+markers",
                                              line=dict(color=TEAL, width=2.5, shape="spline"),
                                              marker=dict(size=7, color=TEAL, line=dict(color="white", width=1.5)),
                                              hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"), secondary_y=True)
                    l_combo = chart_layout(height=320, title="")
                    l_combo["legend"] = dict(orientation="h", y=-0.18, x=0, font=dict(size=10, color=TEXT_MUTED))
                    l_combo["showlegend"] = True
                    fig_combo.update_layout(**l_combo)
                    fig_combo.update_yaxes(title_text="# Trades", secondary_y=False, gridcolor=CHART_GRID,
                                      tickfont=dict(size=10, color=TEXT_SUBTLE))
                    fig_combo.update_yaxes(title_text="Avg P/L (₹)", secondary_y=True, showgrid=False,
                                      tickfont=dict(size=10, color=TEAL), tickprefix="₹")
                    st.plotly_chart(fig_combo, use_container_width=True)

                    st.markdown(section_label("Bucket Detail"), unsafe_allow_html=True)
                    dur_out = dur_grp.reset_index().rename(columns={"bucket": "Duration"})
                    dur_out["Trades"] = dur_out["trades"].astype(int)
                    dur_out["Win Rate"] = dur_out["win_rate"].map(lambda v: f"{v:.1f}%")
                    dur_out["Avg P/L"] = dur_out["avg_pnl"].map(fmt_pnl)
                    dur_out["Total P/L"] = dur_out["total_pnl"].map(fmt_pnl)
                    st.dataframe(dur_out[["Duration","Trades","Win Rate","Avg P/L","Total P/L"]],
                                 use_container_width=True, hide_index=True)

                    if dur_strat_sel in ("VCP", "REVERSAL", "All Strategies"):
                        st.markdown(section_label("Notes"), unsafe_allow_html=True)
                        st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px 18px;font-size:13px;color:{TEXT_BODY};line-height:1.6">
                            Use this to sanity-check your strategy-specific stop levels: VCP at 2.5–3% and REVERSAL at technical stop with a 2.5% floor
                            should show their best Avg P/L in the 4-7 Day to 2-4 Week buckets if exits are working as designed. If the Intraday or 1-3 Day
                            buckets are dragging the average down, that's premature stop-outs rather than the setup failing.
                        </div>""", unsafe_allow_html=True)

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 6: SECTOR & INDUSTRY
            # ════════════════════════════════════════════════════════════
            with da_sub6:
                st.caption("Sector / industry concentration and performance across your trades.")
                try:
                    from pages.portfolio_dna import _get_sector_map
                    sector_map = _get_sector_map()
                except Exception:
                    sector_map = {}

                sec_d = defaultdict(lambda: {"pnl":0,"wins":0,"count":0})
                ind_d = defaultdict(lambda: {"pnl":0,"wins":0,"count":0})
                for t in closed:
                    tk = t.get("ticker","")
                    info = sector_map.get(tk, {"sector":"Unclassified","industry":"Unclassified"})
                    p = safe_float(t.get("pnl"))
                    s = info.get("sector","Unclassified") or "Unclassified"
                    i = info.get("industry","Unclassified") or "Unclassified"
                    sec_d[s]["pnl"] += p; sec_d[s]["count"] += 1
                    if p > 0: sec_d[s]["wins"] += 1
                    ind_d[i]["pnl"] += p; ind_d[i]["count"] += 1
                    if p > 0: ind_d[i]["wins"] += 1

                if not sec_d:
                    st.info("No sector data available.")
                else:
                    sectors_sorted = sorted(sec_d.keys(), key=lambda k: sec_d[k]["count"], reverse=True)
                    industries_sorted = sorted(ind_d.keys(), key=lambda k: ind_d[k]["count"], reverse=True)
                    top_sector = max(sec_d, key=lambda k: sec_d[k]["count"])
                    least_sector = min(sec_d, key=lambda k: sec_d[k]["count"])
                    top_industry = max(ind_d, key=lambda k: ind_d[k]["count"])
                    least_industry = min(ind_d, key=lambda k: ind_d[k]["count"])

                    sk1, sk2, sk3, sk4 = st.columns(4)
                    sk1.markdown(kpi_card("TOP SECTOR", top_sector, color=TEAL), unsafe_allow_html=True)
                    sk2.markdown(kpi_card("LEAST SECTOR", least_sector, color=RED), unsafe_allow_html=True)
                    sk3.markdown(kpi_card("TOP INDUSTRY", top_industry, color=TEAL), unsafe_allow_html=True)
                    sk4.markdown(kpi_card("LEAST INDUSTRY", least_industry, color=RED), unsafe_allow_html=True)

                    st.markdown("<div style=\'height:14px\'></div>", unsafe_allow_html=True)
                    st.markdown(section_label(f"Sector Allocation Distribution — {len(closed)} Trades"), unsafe_allow_html=True)

                    sc1, sc2 = st.columns(2)
                    with sc1:
                        fig_sec_pie = go.Figure(go.Pie(
                            labels=sectors_sorted, values=[sec_d[s]["count"] for s in sectors_sorted],
                            hole=0.55, marker=dict(colors=[DNA_COLORS[i % len(DNA_COLORS)] for i in range(len(sectors_sorted))]),
                            textinfo="percent", textfont=dict(size=10),
                            hovertemplate="%{label}<br>%{value} trades (%{percent})<extra></extra>"))
                        l_sp = chart_layout(height=300, title="")
                        l_sp["showlegend"] = True
                        l_sp["legend"] = dict(orientation="v", x=1.0, y=0.5, font=dict(size=10))
                        fig_sec_pie.update_layout(**l_sp)
                        st.plotly_chart(fig_sec_pie, use_container_width=True, config={"displayModeBar":False})
                    with sc2:
                        sec_pnls = [sec_d[s]["pnl"] for s in sectors_sorted]
                        fig_sec_bar = go.Figure(go.Bar(
                            x=sec_pnls, y=sectors_sorted, orientation="h",
                            marker=dict(color=[TEAL if v>=0 else RED for v in sec_pnls], opacity=0.85),
                            hovertemplate="%{y}<br>₹%{x:,.0f}<extra></extra>"))
                        l_sb = chart_layout(height=300, title="Sector Performance (Net P&L)")
                        l_sb["xaxis"]["tickprefix"] = "₹"
                        fig_sec_bar.update_layout(**l_sb)
                        st.plotly_chart(fig_sec_bar, use_container_width=True, config={"displayModeBar":False})

                    st.markdown("<div style=\'height:14px\'></div>", unsafe_allow_html=True)
                    st.markdown(section_label(f"Industry Allocation Distribution — {len(closed)} Trades"), unsafe_allow_html=True)
                    ic1, ic2 = st.columns(2)
                    with ic1:
                        fig_ind_pie = go.Figure(go.Pie(
                            labels=industries_sorted, values=[ind_d[s]["count"] for s in industries_sorted],
                            hole=0.55, marker=dict(colors=[DNA_COLORS[i % len(DNA_COLORS)] for i in range(len(industries_sorted))]),
                            textinfo="percent", textfont=dict(size=9),
                            hovertemplate="%{label}<br>%{value} trades (%{percent})<extra></extra>"))
                        l_ip = chart_layout(height=300, title="")
                        l_ip["showlegend"] = True
                        l_ip["legend"] = dict(orientation="v", x=1.0, y=0.5, font=dict(size=9))
                        fig_ind_pie.update_layout(**l_ip)
                        st.plotly_chart(fig_ind_pie, use_container_width=True, config={"displayModeBar":False})
                    with ic2:
                        ind_pnls = [ind_d[s]["pnl"] for s in industries_sorted]
                        fig_ind_bar = go.Figure(go.Bar(
                            x=ind_pnls, y=industries_sorted, orientation="h",
                            marker=dict(color=[TEAL if v>=0 else RED for v in ind_pnls], opacity=0.85),
                            hovertemplate="%{y}<br>₹%{x:,.0f}<extra></extra>"))
                        l_ib = chart_layout(height=300, title="Industry Performance (Net P&L)")
                        l_ib["xaxis"]["tickprefix"] = "₹"
                        fig_ind_bar.update_layout(**l_ib)
                        st.plotly_chart(fig_ind_bar, use_container_width=True, config={"displayModeBar":False})

                    st.markdown(section_label("Sector Detail Table"), unsafe_allow_html=True)
                    sec_rows = [{"Sector":s,"Trades":sec_d[s]["count"],
                                 "Win %":f"{sec_d[s][\'wins\']/sec_d[s][\'count\']*100:.1f}%" if sec_d[s]["count"] else "—",
                                 "Net P&L":sec_d[s]["pnl"]} for s in sectors_sorted]
                    st.dataframe(summary_df(sec_rows, pnl_cols=("Net P&L",)), use_container_width=True, hide_index=True)

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 7: VISUAL ANALYTICS
            # ════════════════════════════════════════════════════════════
            with da_sub7:
                st.caption("Distribution of setups, entry types, growth areas, and exit triggers across your trades.")

                def _explode_field(trades_list, field):
                    d = defaultdict(lambda: {"pnl":0,"wins":0,"count":0})
                    for t in trades_list:
                        raw = t.get(field,"") or ""
                        tags = [s.strip() for s in str(raw).split(",") if s.strip()]
                        if not tags: continue
                        p = safe_float(t.get("pnl"))
                        for tag in tags:
                            d[tag]["pnl"] += p; d[tag]["count"] += 1
                            if p > 0: d[tag]["wins"] += 1
                    return d

                playbook_d = defaultdict(lambda: {"pnl":0,"wins":0,"count":0})
                for t in closed:
                    pb = t.get("playbook","") or "Untagged"
                    p = safe_float(t.get("pnl"))
                    playbook_d[pb]["pnl"] += p; playbook_d[pb]["count"] += 1
                    if p > 0: playbook_d[pb]["wins"] += 1

                entry_type_d = _explode_field(closed, "entry_type")
                growth_d     = _explode_field(closed, "mistakes")
                exit_trig_d  = _explode_field(closed, "exit_trigger")

                def _donut_block(d, title, key):
                    if not d:
                        st.markdown(f\'<p style="font-size:12px;font-weight:600;color:{TEXT_H};margin-bottom:6px">{title}</p>\', unsafe_allow_html=True)
                        st.info("No data yet — start tagging trades.")
                        return
                    labels = sorted(d.keys(), key=lambda k: d[k]["count"], reverse=True)
                    vals = [d[k]["count"] for k in labels]
                    fig = go.Figure(go.Pie(labels=labels, values=vals, hole=0.6,
                        marker=dict(colors=[DNA_COLORS[i % len(DNA_COLORS)] for i in range(len(labels))]),
                        textinfo="percent", textfont=dict(size=9),
                        hovertemplate="%{label}<br>%{value} trades (%{percent})<extra></extra>"))
                    l = chart_layout(height=260, title=title)
                    l["showlegend"] = True
                    l["legend"] = dict(orientation="v", x=1.0, y=0.5, font=dict(size=9))
                    fig.update_layout(**l)
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False}, key=f"viz_{key}")

                vc1, vc2 = st.columns(2)
                with vc1: _donut_block(playbook_d, "Setup Distribution (Playbook)", "setup")
                with vc2: _donut_block(entry_type_d, "Entry Type Distribution", "entry")

                vc3, vc4 = st.columns(2)
                with vc3: _donut_block(growth_d, "Growth Areas (Behavioral Issues)", "growth")
                with vc4: _donut_block(exit_trig_d, "Exit Trigger Frequency", "exit")

                st.markdown("<div style=\'height:16px\'></div>", unsafe_allow_html=True)
                st.markdown(section_label("Monthly Trading Performance"), unsafe_allow_html=True)

                mon_perf = defaultdict(lambda: {"count":0,"wins":0,"pos_size_sum":0})
                for t in closed:
                    m = str(t.get("exit_date","") or "")[:7]
                    if not m or m == "nan": continue
                    p = safe_float(t.get("pnl"))
                    try:
                        ps = float(t.get("position_size") or 0) or float(t.get("entry_price") or 0)*float(t.get("qty") or 0)
                    except: ps = 0
                    mon_perf[m]["count"] += 1
                    if p > 0: mon_perf[m]["wins"] += 1
                    mon_perf[m]["pos_size_sum"] += ps

                months_mp = sorted(mon_perf.keys())
                if months_mp:
                    from plotly.subplots import make_subplots
                    mp_labels = [fmt_month(m) for m in months_mp]
                    mp_counts = [mon_perf[m]["count"] for m in months_mp]
                    mp_wr = [mon_perf[m]["wins"]/mon_perf[m]["count"]*100 if mon_perf[m]["count"] else 0 for m in months_mp]
                    mp_avgpos = [mon_perf[m]["pos_size_sum"]/mon_perf[m]["count"] if mon_perf[m]["count"] else 0 for m in months_mp]

                    fig_mp = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_mp.add_trace(go.Bar(x=mp_labels, y=mp_counts, name="Trade Count",
                        marker=dict(color=BLUE, opacity=0.55),
                        hovertemplate="%{x}<br>%{y} trades<extra></extra>"), secondary_y=False)
                    fig_mp.add_trace(go.Scatter(x=mp_labels, y=mp_wr, name="Win Rate (%)", mode="lines+markers",
                        line=dict(color=TEAL, width=2.5, shape="spline"),
                        marker=dict(size=7, color=TEAL, line=dict(color="white", width=1.5)),
                        hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>"), secondary_y=True)
                    fig_mp.add_trace(go.Scatter(x=mp_labels, y=mp_avgpos, name="Avg Pos. Size", mode="lines",
                        line=dict(color=AMBER, width=1.5, dash="dot"),
                        hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>"), secondary_y=False)
                    l_mp = chart_layout(height=320, title="")
                    l_mp["legend"] = dict(orientation="h", y=-0.18, x=0, font=dict(size=10, color=TEXT_MUTED))
                    l_mp["showlegend"] = True
                    fig_mp.update_layout(**l_mp)
                    fig_mp.update_yaxes(title_text="Trades / Avg Pos. (₹)", secondary_y=False, gridcolor=CHART_GRID, tickfont=dict(size=10, color=TEXT_SUBTLE))
                    fig_mp.update_yaxes(title_text="Win Rate (%)", secondary_y=True, showgrid=False, tickfont=dict(size=10, color=TEAL), ticksuffix="%")
                    st.plotly_chart(fig_mp, use_container_width=True, config={"displayModeBar":False})
                else:
                    st.info("No monthly data available.")

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 8: PERFORMANCE ATTRIBUTION
            # ════════════════════════════════════════════════════════════
            with da_sub8:
                st.caption("Attributed metrics aggregated by execution attributes — Setup, Entry Type, Exit Trigger, Growth Areas.")

                def _attr_table(d, label, total_pnl_all):
                    if not d:
                        st.info(f"No {label} data yet.")
                        return
                    rows = []
                    for k in sorted(d.keys(), key=lambda x: d[x]["pnl"], reverse=True):
                        v = d[k]
                        wr = v["wins"]/v["count"]*100 if v["count"] else 0
                        pf_impact = (v["pnl"]/total_pnl_all*100) if total_pnl_all else 0
                        rows.append({
                            label: k, "Trades": v["count"], "Win Rate": f"{wr:.1f}%",
                            "Net P&L": v["pnl"], "PF Impact %": f"{pf_impact:+.1f}%",
                        })
                    df_a = pd.DataFrame(rows)
                    def _asty(row):
                        idx = df_a.columns.tolist(); styles = [""]*len(row)
                        if "Net P&L" in idx:
                            v = row.get("Net P&L", 0)
                            if isinstance(v,(int,float)):
                                styles[idx.index("Net P&L")] = f"color:{TEAL};font-weight:600" if v>0 else f"color:{RED};font-weight:600" if v<0 else ""
                        return styles
                    fmt_a = {"Net P&L": lambda v: f"{\'+\'if v>=0 else \'\'}₹{abs(v):,.0f}" if isinstance(v,(int,float)) else v}
                    st.dataframe(df_a.style.apply(_asty, axis=1).format(fmt_a)
                        .set_properties(**{"font-size":"12.5px"}).set_table_styles(TABLE_STYLES),
                        use_container_width=True, hide_index=True)

                total_pnl_all = sum(safe_float(t.get("pnl")) for t in closed)

                playbook_d2 = defaultdict(lambda: {"pnl":0,"wins":0,"count":0})
                for t in closed:
                    pb = t.get("playbook","") or "Untagged"
                    p = safe_float(t.get("pnl"))
                    playbook_d2[pb]["pnl"] += p; playbook_d2[pb]["count"] += 1
                    if p > 0: playbook_d2[pb]["wins"] += 1

                def _explode_field2(trades_list, field):
                    d = defaultdict(lambda: {"pnl":0,"wins":0,"count":0})
                    for t in trades_list:
                        raw = t.get(field,"") or ""
                        tags = [s.strip() for s in str(raw).split(",") if s.strip()]
                        p = safe_float(t.get("pnl"))
                        for tag in tags:
                            d[tag]["pnl"] += p; d[tag]["count"] += 1
                            if p > 0: d[tag]["wins"] += 1
                    return d

                entry_type_d2 = _explode_field2(closed, "entry_type")
                growth_d2     = _explode_field2(closed, "mistakes")
                exit_trig_d2  = _explode_field2(closed, "exit_trigger")

                at1, at2 = st.columns(2)
                with at1:
                    st.markdown(section_label("Performance by Setup (Playbook)"), unsafe_allow_html=True)
                    _attr_table(playbook_d2, "Setup", total_pnl_all)
                with at2:
                    st.markdown(section_label("Performance by Entry Type"), unsafe_allow_html=True)
                    _attr_table(entry_type_d2, "Entry Type", total_pnl_all)

                at3, at4 = st.columns(2)
                with at3:
                    st.markdown(section_label("Performance by Exit Trigger"), unsafe_allow_html=True)
                    _attr_table(exit_trig_d2, "Exit Trigger", total_pnl_all)
                with at4:
                    st.markdown(section_label("Performance by Growth Area"), unsafe_allow_html=True)
                    _attr_table(growth_d2, "Growth Area", total_pnl_all)

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 9: MULTI-DIMENSION COMBINATIONS
            # ════════════════════════════════════════════════════════════
            with da_sub9:
                st.caption("Attributed performance matrix matching multiple tag dimensions at once.")

                def _tags_of(t, field):
                    raw = t.get(field,"") or ""
                    return [s.strip() for s in str(raw).split(",") if s.strip()] or ["—"]

                DIM_OPTS = {
                    "Setup (Playbook)": lambda t: [t.get("playbook","") or "—"],
                    "Entry Type": lambda t: _tags_of(t, "entry_type"),
                    "Exit Trigger": lambda t: _tags_of(t, "exit_trigger"),
                    "Growth Area": lambda t: _tags_of(t, "mistakes"),
                    "Strategy": lambda t: [t.get("strategy","") or "—"],
                }

                mc1, mc2 = st.columns(2)
                dim_a = mc1.selectbox("Dimension 1", list(DIM_OPTS.keys()), index=0, key="mdim_a")
                dim_b = mc2.selectbox("Dimension 2", list(DIM_OPTS.keys()), index=1, key="mdim_b")

                combo_d = defaultdict(lambda: {"pnl":0,"wins":0,"count":0,"r_sum":0})
                for t in closed:
                    a_tags = DIM_OPTS[dim_a](t)
                    b_tags = DIM_OPTS[dim_b](t)
                    p = safe_float(t.get("pnl")); r = safe_float(t.get("r_multiple"))
                    for a in a_tags:
                        for b in b_tags:
                            key = f"{a} • {b}"
                            combo_d[key]["pnl"] += p; combo_d[key]["count"] += 1; combo_d[key]["r_sum"] += r
                            if p > 0: combo_d[key]["wins"] += 1

                if not combo_d:
                    st.info("No combination data available yet.")
                else:
                    total_pnl_combo = sum(safe_float(t.get("pnl")) for t in closed)

                    mcc1, mcc2 = st.columns(2)
                    with mcc1:
                        st.markdown(section_label("Top Combos by Win Rate %"), unsafe_allow_html=True)
                        wr_rows = sorted(combo_d.items(), key=lambda kv: kv[1]["wins"]/kv[1]["count"] if kv[1]["count"] else 0, reverse=True)[:10]
                        wr_df = pd.DataFrame([{"Combination":k,"Trades":v["count"],
                                                "Win Rate":f"{v[\'wins\']/v[\'count\']*100:.1f}%" if v["count"] else "—"}
                                               for k,v in wr_rows])
                        st.dataframe(wr_df, use_container_width=True, hide_index=True)
                    with mcc2:
                        st.markdown(section_label("Top Combos by Avg R"), unsafe_allow_html=True)
                        r_rows = sorted(combo_d.items(), key=lambda kv: kv[1]["r_sum"]/kv[1]["count"] if kv[1]["count"] else 0, reverse=True)[:10]
                        r_df = pd.DataFrame([{"Combination":k,"Trades":v["count"],
                                               "Avg R":f"{v[\'r_sum\']/v[\'count\']:.2f}R" if v["count"] else "—"}
                                              for k,v in r_rows])
                        st.dataframe(r_df, use_container_width=True, hide_index=True)

                    mcc3, mcc4 = st.columns(2)
                    with mcc3:
                        st.markdown(section_label("Top Combos by Total PF Impact %"), unsafe_allow_html=True)
                        pf_rows = sorted(combo_d.items(), key=lambda kv: kv[1]["pnl"], reverse=True)[:10]
                        pf_df = pd.DataFrame([{"Combination":k,"Trades":v["count"],
                                                "PF Impact %":f"{v[\'pnl\']/total_pnl_combo*100:+.1f}%" if total_pnl_combo else "—"}
                                               for k,v in pf_rows])
                        st.dataframe(pf_df, use_container_width=True, hide_index=True)
                    with mcc4:
                        st.markdown(section_label("Top Combos by Realized P&L"), unsafe_allow_html=True)
                        pl_rows = sorted(combo_d.items(), key=lambda kv: kv[1]["pnl"], reverse=True)[:10]
                        pl_df = pd.DataFrame([{"Combination":k,"Trades":v["count"],"Total P&L":fmt_pnl(v["pnl"])}
                                               for k,v in pl_rows])
                        st.dataframe(pl_df, use_container_width=True, hide_index=True)

            # ════════════════════════════════════════════════════════════
            # SUB-TAB 10: LEARNING FEED
            # ════════════════════════════════════════════════════════════
            with da_sub10:
                st.caption("Highlights from your selected timeframe — what's working, what's not.")

                lf_period = st.selectbox("Period", ["Last 7 days","Last 30 days","Last 90 days","All time"], index=1, key="lf_period")
                days_map = {"Last 7 days":7,"Last 30 days":30,"Last 90 days":90,"All time":99999}
                ndays = days_map[lf_period]
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=ndays)
                prior_cutoff = cutoff - pd.Timedelta(days=ndays)

                def _in_window(t, start, end=None):
                    d = str(t.get("exit_date","") or "")[:10]
                    if not d or d == "nan": return False
                    try: dt = pd.Timestamp(d)
                    except: return False
                    if end is not None: return start <= dt < end
                    return dt >= start

                recent_trades  = [t for t in closed if _in_window(t, cutoff)]
                prior_trades   = [t for t in closed if _in_window(t, prior_cutoff, cutoff)]

                def _best_combo(trades_list):
                    d = defaultdict(lambda: {"pnl":0,"wins":0,"count":0})
                    for t in trades_list:
                        pb = t.get("playbook","") or "—"
                        p = safe_float(t.get("pnl"))
                        d[pb]["pnl"] += p; d[pb]["count"] += 1
                        if p > 0: d[pb]["wins"] += 1
                    if not d: return None
                    best_k = max(d, key=lambda k: d[k]["wins"]/d[k]["count"] if d[k]["count"] else 0)
                    v = d[best_k]
                    wr = v["wins"]/v["count"]*100 if v["count"] else 0
                    pf = v["pnl"]
                    return best_k, wr, pf

                recent_best = _best_combo(recent_trades)

                if recent_best:
                    k, wr, pf = recent_best
                    prior_pf_for_same = 0
                    if prior_trades:
                        prior_pf_for_same = sum(safe_float(t.get("pnl")) for t in prior_trades if (t.get("playbook","") or "—") == k)
                    st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:16px 20px;margin-bottom:16px">
                        <p style="font-size:13px;color:{TEXT_BODY};line-height:1.6;margin:0">
                        In the <b>{lf_period.lower()}</b> your best setup was <b style="color:{TEAL}">{k}</b> with
                        <b>{wr:.1f}% win rate</b> and <b style="color:{pnl_color(pf)}">{fmt_pnl(pf)}</b> net P&L,
                        vs <b style="color:{pnl_color(prior_pf_for_same)}">{fmt_pnl(prior_pf_for_same)}</b> in the prior {lf_period.lower().replace(\'last \',\'\')}.
                        </p>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.info("Not enough trade data in this window for a learning summary.")

                st.markdown(section_label("What's Working For You"), unsafe_allow_html=True)

                def _tags_of2(t, field):
                    raw = t.get(field,"") or ""
                    return [s.strip() for s in str(raw).split(",") if s.strip()]

                def _factor_stats(trades_list, getter):
                    d = defaultdict(lambda: {"pnl":0,"wins":0,"count":0,"r_sum":0})
                    for t in trades_list:
                        vals = getter(t)
                        p = safe_float(t.get("pnl")); r = safe_float(t.get("r_multiple"))
                        for v in vals:
                            d[v]["pnl"] += p; d[v]["count"] += 1; d[v]["r_sum"] += r
                            if p > 0: d[v]["wins"] += 1
                    return d

                setup_stats = defaultdict(lambda: {"pnl":0,"wins":0,"count":0,"r_sum":0})
                for t in recent_trades:
                    pb = t.get("playbook","") or "—"
                    p = safe_float(t.get("pnl")); r = safe_float(t.get("r_multiple"))
                    setup_stats[pb]["pnl"] += p; setup_stats[pb]["count"] += 1; setup_stats[pb]["r_sum"] += r
                    if p > 0: setup_stats[pb]["wins"] += 1

                entry_stats  = _factor_stats(recent_trades, lambda t: _tags_of2(t,"entry_type"))
                exit_stats   = _factor_stats(recent_trades, lambda t: _tags_of2(t,"exit_trigger"))
                growth_stats = _factor_stats(recent_trades, lambda t: _tags_of2(t,"mistakes"))

                def _top_factor_card(d, label):
                    if not d:
                        return kpi_card(label, "—", sub="no data")
                    best_k = max(d, key=lambda k: d[k]["wins"]/d[k]["count"] if d[k]["count"] else 0)
                    v = d[best_k]
                    wr = v["wins"]/v["count"]*100 if v["count"] else 0
                    avg_r = v["r_sum"]/v["count"] if v["count"] else 0
                    return kpi_card(f"{label}: {best_k}", f"{wr:.1f}% WR",
                                     sub=f"{fmt_pnl(v[\'pnl\'])} · {avg_r:.2f}R · {v[\'count\']} trades",
                                     color=TEAL if v["pnl"]>=0 else RED)

                f1, f2, f3, f4 = st.columns(4)
                f1.markdown(_top_factor_card(setup_stats, "Setup"), unsafe_allow_html=True)
                f2.markdown(_top_factor_card(entry_stats, "Entry"), unsafe_allow_html=True)
                f3.markdown(_top_factor_card(exit_stats, "Exit"), unsafe_allow_html=True)
                f4.markdown(_top_factor_card(growth_stats, "Growth"), unsafe_allow_html=True)

    with tab_cmp:
        st.markdown(
            f'<p style="color:{TEXT_MUTED};font-size:13px;margin-bottom:16px">'
            f'Generate reports comparing two sets of trades. Example: same symbol — long vs short, '
            f'or two different strategies side by side.</p>',
            unsafe_allow_html=True)

        # ── Filter forms ─────────────────────────────────────────────────
        def group_form(label, key):
            st.markdown(
                f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;'
                f'padding:14px 16px;margin-bottom:4px">'
                f'<p style="font-size:12px;font-weight:700;color:{TEXT_H};text-transform:uppercase;'
                f'letter-spacing:0.06em;margin-bottom:10px">{label}</p>',
                unsafe_allow_html=True)
            c1,c2,c3 = st.columns(3)
            sym   = c1.selectbox("Symbol",   ["All"]+ALL_SYMBOLS,    key=f"{key}_sym")
            strat = c2.selectbox("Strategy", ["All"]+ALL_STRATEGIES, key=f"{key}_strat")
            wl    = c3.selectbox("Win/Loss", ["All","Win","Loss"],    key=f"{key}_wl")
            d1,d2 = st.columns(2)
            date_from = d1.date_input("From", value=None, key=f"{key}_from")
            date_to   = d2.date_input("To",   value=None, key=f"{key}_to")
            st.markdown("</div>", unsafe_allow_html=True)
            return sym, strat, wl, date_from, date_to

        cg1, cg2 = st.columns(2)
        with cg1: g1 = group_form("Group #1", "g1")
        with cg2: g2 = group_form("Group #2", "g2")

        _, btn_col, _ = st.columns([3,1,3])
        run = btn_col.button("Generate Report", type="primary", use_container_width=True)

        def filter_group(sym, strat, wl, df, dt):
            res = closed[:]
            if sym   != "All": res=[t for t in res if t.get("ticker","")==sym]
            if strat != "All": res=[t for t in res if t.get("strategy","")==strat]
            if wl    == "Win":  res=[t for t in res if safe_float(t.get("pnl"))>0]
            if wl    == "Loss": res=[t for t in res if safe_float(t.get("pnl"))<0]
            if df: res=[t for t in res if str(t.get("exit_date","") or "")[:10]>=str(df)]
            if dt: res=[t for t in res if str(t.get("exit_date","") or "")[:10]<=str(dt)]
            return res

        def grp_stats(trades):
            if not trades: return None
            wins_g   = [t for t in trades if safe_float(t.get("pnl"))>0]
            losses_g = [t for t in trades if safe_float(t.get("pnl"))<0]
            total    = sum(safe_float(t.get("pnl")) for t in trades)
            wr       = len(wins_g)/len(trades)
            avg_w    = sum(safe_float(t.get("pnl")) for t in wins_g)/len(wins_g) if wins_g else 0
            avg_l    = sum(safe_float(t.get("pnl")) for t in losses_g)/len(losses_g) if losses_g else 0
            pf_g     = abs(sum(safe_float(t.get("pnl")) for t in wins_g)/
                          sum(safe_float(t.get("pnl")) for t in losses_g)) if losses_g else 0
            avg_r    = sum(safe_float(t.get("r_multiple")) for t in trades)/len(trades)
            avg_vol  = sum(safe_float(t.get("qty")) for t in trades)/len(trades)
            return {
                "Total P&L":          total,
                "Average Winning Trade": avg_w,
                "Average Losing Trade":  avg_l,
                "Number of Winning Trades": len(wins_g),
                "Number of Losing Trades":  len(losses_g),
                "Max Consecutive Wins":  _max_consec(trades, True),
                "Max Consecutive Losses":_max_consec(trades, False),
                "Profit Factor":         pf_g,
                "Avg R-Multiple":        avg_r,
                "Avg Daily Volume":      avg_vol,
                "_wr": wr, "_wins": len(wins_g), "_losses": len(losses_g),
            }

        def donut_chart(wr, wins, losses):
            fig = go.Figure(go.Pie(
                values=[wins, losses],
                labels=["Winners","Losers"],
                hole=0.65,
                marker=dict(colors=[TEAL, RED]),
                textinfo="none",
                hovertemplate="%{label}: %{value}<extra></extra>"
            ))
            fig.add_annotation(
                text=f"<b>{wr:.0%}</b><br><span style='font-size:10px'>WINRATE</span>",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=18, color=TEAL),
                align="center"
            )
            l = chart_layout(height=220, title="")
            l["showlegend"] = True
            l["legend"] = dict(x=0.75, y=0.5, font=dict(size=12))
            l["margin"] = dict(l=10, r=10, t=10, b=10)
            fig.update_layout(**l)
            return fig

        if run:
            r1 = filter_group(*g1); r2 = filter_group(*g2)
            s1 = grp_stats(r1);     s2 = grp_stats(r2)

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            # ── STATISTICS side by side ──────────────────────────────────
            comp_c1, comp_c2 = st.columns(2)
            for col, stats, label, grp in [(comp_c1,s1,"Group #1",r1),(comp_c2,s2,"Group #2",r2)]:
                with col:
                    st.markdown(
                        f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:16px 20px;margin-bottom:12px">'
                        f'<p style="font-size:10px;font-weight:700;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:4px">STATISTICS ({label})</p>'
                        f'<p style="font-size:10px;color:{TEXT_SUBTLE};margin-bottom:12px">(ALL DATES)</p>',
                        unsafe_allow_html=True)
                    if stats:
                        display_stats = {k:v for k,v in stats.items() if not k.startswith("_")}
                        rows_html = ""
                        for k,v in display_stats.items():
                            if k=="Total P&L":             fv=fmt_pnl(v); fc=pnl_color(v)
                            elif k in("Average Winning Trade","Average Losing Trade"):
                                fv=fmt_pnl(v); fc=TEAL if v>=0 else RED
                            elif k=="Profit Factor":       fv=f"{v:.2f}"; fc=TEAL if v>=1 else RED
                            elif k=="Avg R-Multiple":      fv=f"{v:.2f}R"; fc=TEAL if v>=0 else RED
                            elif k=="Avg Daily Volume":    fv=f"{v:.1f}"; fc=TEXT_H
                            else: fv=str(int(v)) if isinstance(v,(int,float)) else str(v); fc=TEXT_H
                            rows_html += (
                                f'<div style="display:flex;justify-content:space-between;'
                                f'padding:8px 0;border-bottom:1px solid {BORDER_LIGHT};font-size:13px">'
                                f'<span style="color:{TEXT_MUTED}">{k}</span>'
                                f'<span style="color:{fc};font-weight:500">{fv}</span></div>')
                        st.markdown(rows_html+"</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("</div>", unsafe_allow_html=True)
                        st.info("No trades match this filter.")

            # ── OVERALL EVALUATION (donut charts) ────────────────────────
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            ev_c1, ev_c2 = st.columns(2)
            for col, stats, label, grp in [(ev_c1,s1,"Group #1",r1),(ev_c2,s2,"Group #2",r2)]:
                with col:
                    st.markdown(
                        f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:16px 20px;margin-bottom:12px">'
                        f'<p style="font-size:10px;font-weight:700;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:4px">OVERALL EVALUATION ({label})</p>'
                        f'<p style="font-size:10px;color:{TEXT_SUBTLE};margin-bottom:4px">(ALL DATES)</p>',
                        unsafe_allow_html=True)
                    if stats:
                        wr=stats["_wr"]; wins=stats["_wins"]; losses=stats["_losses"]
                        fig_d = donut_chart(wr, wins, losses)
                        st.plotly_chart(fig_d, use_container_width=True, config={"displayModeBar":False})
                    else:
                        st.info("No data.")
                    st.markdown("</div>", unsafe_allow_html=True)

            # ── DAILY NET CUMULATIVE P&L ─────────────────────────────────
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            pnl_c1, pnl_c2 = st.columns(2)
            for col, stats, label, grp in [(pnl_c1,s1,"Group #1",r1),(pnl_c2,s2,"Group #2",r2)]:
                with col:
                    st.markdown(
                        f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:16px 20px">'
                        f'<p style="font-size:10px;font-weight:700;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:4px">DAILY NET CUMULATIVE P&L ({label})</p>'
                        f'<p style="font-size:10px;color:{TEXT_SUBTLE};margin-bottom:4px">(ALL DATES)</p>',
                        unsafe_allow_html=True)
                    if grp:
                        by_d = defaultdict(float)
                        for t in grp:
                            d = str(t.get("exit_date","") or "")[:10]
                            if d and d!="nan": by_d[d]+=safe_float(t.get("pnl"))
                        if by_d:
                            ds=sorted(by_d.keys()); cm=[]; rn=0
                            for d in ds: rn+=by_d[d]; cm.append(rn)
                            is_pos = cm[-1]>=0 if cm else True
                            line_col = TEAL if is_pos else RED
                            fill_col = "rgba(16,185,129,0.25)" if is_pos else "rgba(239,68,68,0.25)"
                            fig_c = go.Figure()
                            fig_c.add_trace(go.Scatter(
                                x=ds, y=cm, mode="lines",
                                line=dict(color=line_col, width=2.5),
                                fill="tozeroy", fillcolor=fill_col,
                                name="Cumulative P&L"))
                            # Negative underwater area
                            fig_c.add_trace(go.Scatter(
                                x=ds, y=[min(v,0) for v in cm], mode="lines",
                                line=dict(width=0), fill="tozeroy",
                                fillcolor="rgba(239,68,68,0.30)", showlegend=False))
                            lc = chart_layout(height=260, title="")
                            lc["yaxis"]["tickprefix"]="₹"
                            lc["margin"]=dict(l=60,r=20,t=10,b=40)
                            fig_c.update_layout(**lc)
                            st.plotly_chart(fig_c, use_container_width=True, config={"displayModeBar":False})
                    else:
                        st.info("No trades match this filter.")
                    st.markdown("</div>", unsafe_allow_html=True)
