import streamlit as st
import pandas as pd
from data.db import _sb
from theme import *

TIMEFRAMES = [
    ("ret_1d", "1D"), ("ret_1w", "1W"), ("ret_1m", "1M"),
    ("ret_3m", "3M"), ("ret_6m", "6M"), ("ret_12m", "12M"), ("ret_ytd", "YTD"),
]

def safe_float(v):
    try: return float(v) if v is not None else None
    except: return None

def heat_color(val):
    """Returns a background color on a red→green scale based on % return."""
    if val is None:
        return BORDER_LIGHT, TEXT_SUBTLE
    if val >= 15: return "#059669", "#FFFFFF"
    if val >= 5:  return "#A7F3D0", TEXT_H
    if val >= 0:  return "#ECFDF5", TEXT_H
    if val >= -5: return "#FEF2F2", TEXT_H
    if val >= -15:return "#FECACA", TEXT_H
    return "#EF4444", "#FFFFFF"


def render():
    st.markdown("## Thematic Heatmap")
    st.caption("Sector/industry % move grid across your tracked NSE universe. "
               "Data refreshes periodically via a background script, not live on page load.")

    try:
        uni = _sb().table("market_universe").select("*").execute().data or []
        rets = _sb().table("market_returns").select("*").execute().data or []
    except Exception as e:
        st.error(f"Could not load market data: {e}")
        return

    if not uni:
        st.info("Market universe is empty. Run `market_refresh.py` to seed and populate data.")
        return
    if not rets:
        st.info("No returns data yet. Run `market_refresh.py` on your Mac to populate market_returns.")
        return

    ret_by_ticker = {r["ticker"]: r for r in rets}
    as_of = rets[0].get("as_of_date", "—") if rets else "—"

    tf_key = st.selectbox("Timeframe", [tf[1] for tf in TIMEFRAMES], index=2, key="heatmap_tf")
    tf_col = next(c for c, label in TIMEFRAMES if label == tf_key)

    st.caption(f"As of: {as_of}")

    # Build sector → industry → [tickers] structure
    rows = []
    for u in uni:
        r = ret_by_ticker.get(u["ticker"])
        val = safe_float(r.get(tf_col)) if r else None
        rows.append({"ticker": u["ticker"], "sector": u["sector"], "industry": u["industry"], "ret": val})

    df = pd.DataFrame(rows)

    # ── Sector-level summary (avg return per sector) ─────────────────────
    sector_avg = df.groupby("sector")["ret"].mean().sort_values(ascending=False)

    st.markdown(section_label("Sector Overview"), unsafe_allow_html=True)
    cols = st.columns(len(sector_avg)) if len(sector_avg) <= 7 else st.columns(7)
    for i, (sector, avg) in enumerate(sector_avg.items()):
        bg, fg = heat_color(avg)
        with cols[i % len(cols)]:
            st.markdown(f"""<div style="background:{bg};border-radius:8px;padding:10px 8px;text-align:center;margin-bottom:8px">
                <div style="font-size:10px;color:{fg};opacity:0.85;font-weight:600;text-transform:uppercase;
                    letter-spacing:0.03em;line-height:1.2;margin-bottom:4px">{sector}</div>
                <div style="font-size:15px;font-weight:700;color:{fg}">{avg:+.1f}%</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Per-sector tabs: industry grid + stock detail ────────────────────
    st.markdown(section_label("Industry Breakdown"), unsafe_allow_html=True)
    sectors = sector_avg.index.tolist()
    tabs = st.tabs(sectors)

    for tab, sector in zip(tabs, sectors):
        with tab:
            plot_df = df[df["sector"] == sector]
            industry_avg = plot_df.groupby("industry")["ret"].agg(["mean", "count"]).sort_values("mean", ascending=False)

            n_cols = 4
            industries = industry_avg.index.tolist()
            for row_start in range(0, len(industries), n_cols):
                cols = st.columns(n_cols)
                for j, ind in enumerate(industries[row_start:row_start+n_cols]):
                    avg = industry_avg.loc[ind, "mean"]
                    cnt = int(industry_avg.loc[ind, "count"])
                    bg, fg = heat_color(avg)
                    with cols[j]:
                        st.markdown(f"""<div style="background:{bg};border-radius:8px;padding:10px;margin-bottom:8px;min-height:70px">
                            <div style="font-size:10px;color:{fg};opacity:0.85;font-weight:600;line-height:1.3">{ind} ({cnt})</div>
                            <div style="font-size:16px;font-weight:700;color:{fg};margin-top:4px">{avg:+.1f}%</div>
                        </div>""", unsafe_allow_html=True)

            # ── Stock-level table for this sector — color-coded by rating ──
            st.markdown(section_label(f"{sector} — Stock Detail"), unsafe_allow_html=True)
            detail_df = plot_df.dropna(subset=["ret"]).sort_values("ret", ascending=False).copy()
            detail_df = detail_df.rename(columns={"ticker": "Symbol", "sector": "Sector", "industry": "Industry", "ret": tf_key})
            detail_df = detail_df[["Symbol", "Industry", tf_key]]

            def style_rating(val):
                bg, fg = heat_color(val)
                return f"background-color:{bg};color:{fg};font-weight:600"

            styler = detail_df.style
            if hasattr(styler, "map"):
                styler = styler.map(style_rating, subset=[tf_key])
            else:
                styler = styler.applymap(style_rating, subset=[tf_key])
            styled = styler.format({tf_key: "{:+.2f}%"})
            st.dataframe(styled, use_container_width=True, hide_index=True)

    unmapped_in_rets = set(ret_by_ticker.keys()) - set(u["ticker"] for u in uni)
    if unmapped_in_rets:
        st.caption(f"Note: {len(unmapped_in_rets)} ticker(s) have return data but no sector mapping — they won't appear above.")
