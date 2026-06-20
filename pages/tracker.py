import streamlit as st
import pandas as pd
from data.db import _sb
from theme import *

TIMEFRAMES = [
    ("ret_1d", "1D"), ("ret_1w", "1W"), ("ret_1m", "1M"),
    ("ret_3m", "3M"), ("ret_6m", "6M"), ("ret_ytd", "YTD"), ("ret_12m", "1Y"),
]

def safe_float(v):
    try: return float(v) if v is not None else None
    except: return None

def bar_color(val):
    if val is None: return TEXT_SUBTLE
    return TEAL if val >= 0 else RED


def render():
    st.markdown("## Tracker")
    st.caption("Ranked sector and industry leaderboard across your tracked NSE universe.")

    try:
        uni = _sb().table("market_universe").select("*").execute().data or []
        rets = _sb().table("market_returns").select("*").execute().data or []
    except Exception as e:
        st.error(f"Could not load market data: {e}")
        return

    if not uni or not rets:
        st.info("No market data yet. Run `market_refresh.py` on your Mac to populate the universe and returns.")
        return

    ret_by_ticker = {r["ticker"]: r for r in rets}
    as_of = rets[0].get("as_of_date", "—") if rets else "—"

    tf_label = st.selectbox("Timeframe", [tf[1] for tf in TIMEFRAMES], index=2, key="tracker_tf")
    tf_col = next(c for c, label in TIMEFRAMES if label == tf_label)
    st.caption(f"As of: {as_of}")

    rows = []
    for u in uni:
        r = ret_by_ticker.get(u["ticker"])
        val = safe_float(r.get(tf_col)) if r else None
        rows.append({"ticker": u["ticker"], "sector": u["sector"], "industry": u["industry"], "ret": val})

    df = pd.DataFrame(rows).dropna(subset=["ret"])

    if df.empty:
        st.info("No return data available for this timeframe yet.")
        return

    col1, col2 = st.columns(2)

    # ── Sector Rankings ──────────────────────────────────────────────────
    with col1:
        st.markdown(section_label("Sector Rankings"), unsafe_allow_html=True)
        sector_stats = df.groupby("sector").agg(avg_ret=("ret", "mean"), n=("ticker", "count")).reset_index()
        sector_stats = sector_stats.sort_values("avg_ret", ascending=False)
        max_abs = sector_stats["avg_ret"].abs().max() or 1

        for _, row in sector_stats.iterrows():
            pct_width = min(abs(row["avg_ret"]) / max_abs * 100, 100)
            color = bar_color(row["avg_ret"])
            st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
                padding:8px 0;border-bottom:1px solid {BORDER_LIGHT}">
                <div style="flex:1;min-width:0">
                    <div style="font-size:12px;color:{TEXT_BODY};font-weight:500;white-space:nowrap;
                        overflow:hidden;text-overflow:ellipsis">{row['sector']} <span style="color:{TEXT_SUBTLE}">({int(row['n'])})</span></div>
                    <div style="background:{BORDER_LIGHT};border-radius:4px;height:5px;margin-top:4px;width:100%;max-width:140px">
                        <div style="background:{color};border-radius:4px;height:5px;width:{pct_width}%"></div>
                    </div>
                </div>
                <span style="font-size:13px;font-weight:700;color:{color};margin-left:10px;white-space:nowrap">{row['avg_ret']:+.1f}%</span>
            </div>""", unsafe_allow_html=True)

    # ── Industry / Theme Alpha Rankings ──────────────────────────────────
    with col2:
        st.markdown(section_label("Industry Theme Alpha"), unsafe_allow_html=True)
        industry_stats = df.groupby("industry").agg(avg_ret=("ret", "mean"), n=("ticker", "count")).reset_index()
        industry_stats = industry_stats.sort_values("avg_ret", ascending=False).head(20)
        max_abs_i = industry_stats["avg_ret"].abs().max() or 1

        for _, row in industry_stats.iterrows():
            pct_width = min(abs(row["avg_ret"]) / max_abs_i * 100, 100)
            color = bar_color(row["avg_ret"])
            st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
                padding:8px 0;border-bottom:1px solid {BORDER_LIGHT}">
                <div style="flex:1;min-width:0">
                    <div style="font-size:12px;color:{TEXT_BODY};font-weight:500;white-space:nowrap;
                        overflow:hidden;text-overflow:ellipsis">{row['industry']} <span style="color:{TEXT_SUBTLE}">({int(row['n'])})</span></div>
                    <div style="background:{BORDER_LIGHT};border-radius:4px;height:5px;margin-top:4px;width:100%;max-width:140px">
                        <div style="background:{color};border-radius:4px;height:5px;width:{pct_width}%"></div>
                    </div>
                </div>
                <span style="font-size:13px;font-weight:700;color:{color};margin-left:10px;white-space:nowrap">{row['avg_ret']:+.1f}%</span>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Top/Bottom individual stocks ─────────────────────────────────────
    st.markdown(section_label("Top & Bottom Movers"), unsafe_allow_html=True)
    tcol, bcol = st.columns(2)
    stock_sorted = df.sort_values("ret", ascending=False)

    with tcol:
        st.caption("🟢 Top 10")
        top = stock_sorted.head(10).copy()
        top["ret"] = top["ret"].map(lambda v: f"{v:+.2f}%")
        top = top.rename(columns={"ticker": "Symbol", "sector": "Sector", "ret": tf_label})
        st.dataframe(top[["Symbol", "Sector", tf_label]], use_container_width=True, hide_index=True)

    with bcol:
        st.caption("🔴 Bottom 10")
        bottom = stock_sorted.tail(10).sort_values("ret").copy()
        bottom["ret"] = bottom["ret"].map(lambda v: f"{v:+.2f}%")
        bottom = bottom.rename(columns={"ticker": "Symbol", "sector": "Sector", "ret": tf_label})
        st.dataframe(bottom[["Symbol", "Sector", tf_label]], use_container_width=True, hide_index=True)
