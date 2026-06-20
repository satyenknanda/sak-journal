import streamlit as st
import pandas as pd
import re
from data.db import _sb
from theme import *


def parse_tickers(raw_text):
    """Split on commas, whitespace, or newlines; uppercase; dedupe; preserve order."""
    tokens = re.split(r'[,\s]+', raw_text.strip())
    seen = set()
    out = []
    for t in tokens:
        t = t.upper().strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def render():
    st.markdown("## Stock Niche Mapper")
    st.caption("Translate tickers into sector/industry classification using your tracked NSE universe.")

    try:
        uni = _sb().table("market_universe").select("*").execute().data or []
    except Exception as e:
        st.error(f"Could not load market universe: {e}")
        return

    if not uni:
        st.info("Market universe is empty. Run `market_refresh.py` on your Mac to populate it.")
        return

    uni_map = {u["ticker"]: u for u in uni}

    raw = st.text_area(
        "Paste tickers (comma, space, or newline separated)",
        placeholder="RELIANCE, TCS, HDFCBANK...",
        height=120, key="niche_mapper_input",
    )

    c1, c2 = st.columns([1, 4])
    with c1:
        process = st.button("Process Selection →", type="primary", key="niche_mapper_process")

    tokens = parse_tickers(raw) if raw else []
    st.caption(f"{len(tokens)} ticker(s) detected")

    if not process or not tokens:
        if not process:
            st.info("Paste tickers above and click Process Selection.")
        return

    rows = []
    unmapped = []
    for t in tokens:
        if t in uni_map:
            u = uni_map[t]
            rows.append({"Symbol": t, "Sector": u["sector"], "Industry": u["industry"], "Status": "✅ Mapped"})
        else:
            unmapped.append(t)
            rows.append({"Symbol": t, "Sector": "—", "Industry": "—", "Status": "⚠️ Unmapped"})

    df = pd.DataFrame(rows)

    # ── Summary KPIs ─────────────────────────────────────────────────────
    k1, k2, k3 = st.columns(3)
    k1.markdown(kpi_card("TICKERS PROCESSED", f"{len(tokens)}"), unsafe_allow_html=True)
    k2.markdown(kpi_card("MAPPED", f"{len(tokens) - len(unmapped)}", color=TEAL), unsafe_allow_html=True)
    k3.markdown(kpi_card("UNMAPPED", f"{len(unmapped)}", color=(AMBER if unmapped else TEAL)), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if unmapped:
        st.markdown(f"""<div style="background:{AMBER_BG};border:1px solid {AMBER_BORDER};border-radius:8px;
            padding:10px 14px;font-size:12px;color:{TEXT_BODY};margin-bottom:14px">
            ⚠️ {len(unmapped)} ticker(s) not in your tracked universe: <b>{', '.join(unmapped)}</b>.
            Add them to <code>market_universe/universe_seed.py</code> and re-run <code>market_refresh.py</code> to classify.
        </div>""", unsafe_allow_html=True)

    # ── Result table ─────────────────────────────────────────────────────
    st.markdown(section_label("Industry-Aware List"), unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Grouped view ─────────────────────────────────────────────────────
    mapped_df = df[df["Status"] == "✅ Mapped"]
    if not mapped_df.empty:
        st.markdown(section_label("Grouped by Sector"), unsafe_allow_html=True)
        for sector in sorted(mapped_df["Sector"].unique()):
            sub = mapped_df[mapped_df["Sector"] == sector]
            symbols = ", ".join(sub["Symbol"].tolist())
            st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:8px;
                padding:10px 14px;margin-bottom:8px">
                <div style="font-size:12px;font-weight:600;color:{TEXT_H};margin-bottom:4px">{sector} ({len(sub)})</div>
                <div style="font-size:12px;color:{TEXT_MUTED}">{symbols}</div>
            </div>""", unsafe_allow_html=True)

    # ── Copy-paste friendly output ───────────────────────────────────────
    st.markdown(section_label("Copy as CSV"), unsafe_allow_html=True)
    csv_text = df.to_csv(index=False)
    st.code(csv_text, language="text")
