import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data.db import _sb
from theme import *

PERIOD_DAYS = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "YTD": None}


def render():
    st.markdown("## Comparison Engine")
    st.caption("Overlay normalized return curves for sectors, industries, or individual stocks.")

    try:
        uni = _sb().table("market_universe").select("*").execute().data or []
    except Exception as e:
        st.error(f"Could not load market universe: {e}")
        return

    if not uni:
        st.info("Market universe is empty. Run `market_refresh.py` on your Mac to populate it.")
        return

    uni_df = pd.DataFrame(uni)
    sectors = sorted(uni_df["sector"].unique())

    c1, c2 = st.columns([1, 3])
    with c1:
        mode = st.radio("Compare by", ["Sector", "Stock"], key="compare_mode", horizontal=True)
        period = st.selectbox("Period", list(PERIOD_DAYS.keys()), index=3, key="compare_period")

    with c2:
        if mode == "Sector":
            selected = st.multiselect("Select sectors to compare", sectors,
                                       default=sectors[:3] if len(sectors) >= 3 else sectors,
                                       key="compare_sectors")
        else:
            tickers = sorted(uni_df["ticker"].unique())
            selected = st.multiselect("Select stocks to compare", tickers,
                                       default=tickers[:3] if len(tickers) >= 3 else tickers,
                                       key="compare_stocks")

    if not selected:
        st.info("Select at least one sector or stock to compare.")
        return

    # ── Determine which tickers' price history to pull ──────────────────
    if mode == "Sector":
        target_tickers = uni_df[uni_df["sector"].isin(selected)]["ticker"].tolist()
    else:
        target_tickers = selected

    if not target_tickers:
        st.info("No tickers found for the current selection.")
        return

    try:
        # Pull price history for all relevant tickers, batched by ticker count
        # AND paginated by row count — Supabase/PostgREST caps responses at
        # ~1000 rows by default, and a single ticker can have 250+ rows of
        # daily history, so a chunk of 40 tickers can easily exceed that cap
        # and silently truncate results without raising an error.
        ph = []
        chunk_size = 40
        page_size = 1000
        for i in range(0, len(target_tickers), chunk_size):
            chunk = target_tickers[i:i + chunk_size]
            offset = 0
            while True:
                ph_res = (_sb().table("price_history").select("*")
                          .in_("ticker", chunk)
                          .range(offset, offset + page_size - 1)
                          .execute())
                rows = ph_res.data or []
                ph.extend(rows)
                if len(rows) < page_size:
                    break
                offset += page_size
    except Exception as e:
        st.error(f"Could not load price history: {e}")
        return

    if not ph:
        st.info("No price history found. Run the updated `market_refresh.py` on your Mac to populate `price_history` "
                "(requires the new table — run `price_history_schema.sql` first).")
        return

    ph_df = pd.DataFrame(ph)
    ph_df["trade_date"] = pd.to_datetime(ph_df["trade_date"])

    # Trim to selected period
    if PERIOD_DAYS[period] is not None:
        cutoff = ph_df["trade_date"].max() - pd.Timedelta(days=int(PERIOD_DAYS[period] * 1.45))  # buffer for weekends
        ph_df = ph_df[ph_df["trade_date"] >= cutoff]
    else:  # YTD
        year_start = pd.Timestamp(year=ph_df["trade_date"].max().year, month=1, day=1)
        ph_df = ph_df[ph_df["trade_date"] >= year_start]

    if ph_df.empty:
        st.info("No price history in the selected period yet.")
        return

    # ── Build normalized series ──────────────────────────────────────────
    fig = go.Figure()
    colors = DNA_COLORS

    if mode == "Sector":
        for i, sector in enumerate(selected):
            sec_tickers = uni_df[uni_df["sector"] == sector]["ticker"].tolist()
            sec_ph = ph_df[ph_df["ticker"].isin(sec_tickers)]
            if sec_ph.empty:
                continue
            # average close per day across all tickers in this sector, then normalize
            daily_avg = sec_ph.groupby("trade_date")["close"].mean().sort_index()
            if daily_avg.empty or daily_avg.iloc[0] == 0:
                continue
            normalized = (daily_avg / daily_avg.iloc[0] - 1) * 100
            fig.add_trace(go.Scatter(
                x=normalized.index, y=normalized.values, mode="lines", name=sector,
                line=dict(color=colors[i % len(colors)], width=2),
                hovertemplate=f"{sector}<br>%{{y:.1f}}%<extra></extra>",
            ))
    else:
        for i, ticker in enumerate(selected):
            t_ph = ph_df[ph_df["ticker"] == ticker].sort_values("trade_date")
            if t_ph.empty or t_ph["close"].iloc[0] == 0:
                continue
            normalized = (t_ph["close"] / t_ph["close"].iloc[0] - 1) * 100
            fig.add_trace(go.Scatter(
                x=t_ph["trade_date"], y=normalized.values, mode="lines", name=ticker,
                line=dict(color=colors[i % len(colors)], width=2),
                hovertemplate=f"{ticker}<br>%{{y:.1f}}%<extra></extra>",
            ))

    if not fig.data:
        st.info("No data to plot for this selection.")
        return

    l = chart_layout(height=420, title=f"Normalized Return — {period}")
    l["showlegend"] = True
    l["legend"] = dict(orientation="h", y=-0.15, x=0, font=dict(size=11, color=TEXT_MUTED))
    l["yaxis"]["ticksuffix"] = "%"
    l["hovermode"] = "x unified"
    fig.update_layout(**l)
    fig.add_hline(y=0, line=dict(color=BORDER_MED, width=1, dash="dot"))

    st.plotly_chart(fig, use_container_width=True)

    # ── Summary table: final return per series ───────────────────────────
    st.markdown(section_label("Period Summary"), unsafe_allow_html=True)
    summary_rows = []
    for trace in fig.data:
        if len(trace.y) > 0:
            summary_rows.append({"Name": trace.name, f"Return ({period})": f"{trace.y[-1]:+.2f}%"})
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows).sort_values(f"Return ({period})", ascending=False)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
