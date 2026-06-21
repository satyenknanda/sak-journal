import streamlit as st
import pandas as pd
from data.db import _sb
from theme import *
from thematic_clusters import get_cluster

SECTOR_COLORS = {
    "Financial Services": "#7C3AED", "Information Technology": "#3B82F6",
    "Healthcare": "#10B981", "Materials": "#F59E0B", "Industrials": "#EC4899",
    "Utilities": "#14B8A6", "Consumer Discretionary": "#F97316", "Energy": "#06B6D4",
}

CLUSTER_COLORS = {
    "Banking & Financial Services": "#7C3AED",
    "Information Technology & Software": "#3B82F6",
    "Healthcare & Pharma": "#10B981",
    "Metals & Mining": "#F59E0B",
    "Defense, Aerospace & Engineering": "#EC4899",
    "Energy & Utilities": "#14B8A6",
    "Automotive & Components": "#F97316",
    "Lifestyle & Retail": "#06B6D4",
    "Other": "#94A3B8",
}


def render():
    st.markdown("## Domain Vector")
    st.caption("Browsable directory of your tracked NSE universe — sector → industry → tickers. "
               "Export any selection as a TradingView-ready watchlist (copy/paste, no account sync).")

    try:
        uni = _sb().table("market_universe").select("*").execute().data or []
    except Exception as e:
        st.error(f"Could not load market universe: {e}")
        return

    if not uni:
        st.info("Market universe is empty. Run `market_refresh.py` on your Mac to populate it.")
        return

    uni_df = pd.DataFrame(uni)
    uni_df["cluster"] = uni_df["industry"].map(get_cluster)

    view_mode = st.radio("Group by", ["Sector", "Thematic Cluster"], key="domain_view_mode", horizontal=True)
    group_col = "sector" if view_mode == "Sector" else "cluster"
    color_map = SECTOR_COLORS if view_mode == "Sector" else CLUSTER_COLORS

    search = st.text_input("🔍 Search sectors, clusters, industries, or tickers", key="domain_search")

    if search:
        s = search.upper()
        filtered = uni_df[
            uni_df["ticker"].str.upper().str.contains(s) |
            uni_df["sector"].str.upper().str.contains(s) |
            uni_df["cluster"].str.upper().str.contains(s) |
            uni_df["industry"].str.upper().str.contains(s)
        ]
    else:
        filtered = uni_df

    if filtered.empty:
        st.info("No matches found.")
        return

    group_counts = filtered.groupby(group_col).agg(
        tickers=("ticker", "count"), industries=("industry", "nunique")
    ).reset_index().sort_values("tickers", ascending=False)

    st.markdown(section_label(f"{view_mode}s ({len(group_counts)})"), unsafe_allow_html=True)

    n_cols = 4
    groups = group_counts[group_col].tolist()
    for row_start in range(0, len(groups), n_cols):
        cols = st.columns(n_cols)
        for j, group_name in enumerate(groups[row_start:row_start+n_cols]):
            row = group_counts[group_counts[group_col] == group_name].iloc[0]
            color = color_map.get(group_name, TEXT_MUTED)
            with cols[j]:
                if st.button(f"{group_name}\n{int(row['tickers'])} tickers · {int(row['industries'])} industries",
                             key=f"group_btn_{view_mode}_{group_name}", use_container_width=True):
                    st.session_state["domain_selected_group"] = group_name
                    st.session_state["domain_selected_mode"] = view_mode
                st.markdown(f"""<div style="height:3px;background:{color};border-radius:2px;margin-top:-8px;margin-bottom:8px"></div>""",
                            unsafe_allow_html=True)

    selected_group = st.session_state.get("domain_selected_group")
    selected_mode = st.session_state.get("domain_selected_mode")

    if selected_group and selected_mode == view_mode and selected_group in groups:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(section_label(f"{selected_group} — Industries"), unsafe_allow_html=True)

        sec_df = filtered[filtered[group_col] == selected_group]
        industries = sorted(sec_df["industry"].unique())

        sel_industry = st.selectbox("Industry", ["All"] + industries, key="domain_industry_select")
        show_df = sec_df if sel_industry == "All" else sec_df[sec_df["industry"] == sel_industry]

        tickers = sorted(show_df["ticker"].unique())
        st.markdown(f"""<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px">
            {''.join(f'<span style="font-size:12px;padding:4px 10px;border-radius:14px;background:{TEAL_BG};color:{TEAL_DARK};border:1px solid {TEAL_BORDER}">{t}</span>' for t in tickers)}
        </div>""", unsafe_allow_html=True)

        # ── TradingView export ──────────────────────────────────────────
        st.markdown(section_label("Export to TradingView"), unsafe_allow_html=True)
        st.caption("Copy the text below, save as a .txt file, then in TradingView: Watchlist → ⋯ → "
                   "Import list → select your saved file.")

        tv_format = ",".join(f"NSE:{t}" for t in tickers)
        st.code(tv_format, language="text")

        st.download_button(
            "⬇️ Download as .txt",
            data=tv_format,
            file_name=f"{selected_group.replace(' ','_')}_{sel_industry.replace(' ','_') if sel_industry!='All' else 'all'}_watchlist.txt",
            mime="text/plain",
            key="domain_download_btn",
        )
    else:
        st.caption(f"Click a {view_mode.lower()} above to browse its industries and tickers.")
