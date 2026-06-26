def render():
    import streamlit as st
    import pandas as pd
    from supabase import create_client
    from datetime import datetime, date
    import os
    
    # ── Supabase ────────────────────────────────────────────────────────────────
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://dvfxkcjugpvvpijxgnow.supabase.co")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
    
    @st.cache_resource
    def get_supabase():
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # ── DNA Colours (match existing palette) ────────────────────────────────────
    VERDICT_COLORS = {
        "STRONG BUY": "#00C896",
        "BUY":        "#4CAF50",
        "WATCH":      "#FFC107",
        "AVOID":      "#F44336",
    }
    
    SETUP_COLORS = {
        "VCP":      "#4A90D9",
        "REVERSAL": "#9B59B6",
        "SVRO":     "#E67E22",
        "EP":       "#E74C3C",
        "MARS":     "#1ABC9C",
        "TS":       "#3498DB",
        "None":     "#95A5A6",
    }
    
    BONDE_ICONS = {
        "MATCH":   "✅",
        "PARTIAL": "⚠️",
        "NO":      "❌",
    }
    
    # ── Page ────────────────────────────────────────────────────────────────────
    st.title("🔬 Trade Research")
    st.caption("Analyses from /trade-analyze — powered by SAK Trade Analyst (Claude Code)")
    
    supabase = get_supabase()
    
    # ── Filters ─────────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        filter_verdict = st.multiselect(
            "Verdict",
            ["STRONG BUY", "BUY", "WATCH", "AVOID"],
            default=["STRONG BUY", "BUY"]
        )
    
    with col2:
        filter_setup = st.multiselect(
            "Setup",
            ["VCP", "REVERSAL", "SVRO", "EP", "MARS", "TS", "None"],
            default=[]
        )
    
    with col3:
        filter_bonde = st.multiselect(
            "Bonde",
            ["MATCH", "PARTIAL", "NO"],
            default=[]
        )
    
    with col4:
        filter_taken = st.selectbox(
            "Trade taken",
            ["All", "Yes", "No"],
            index=0
        )
    
    # ── Fetch data ───────────────────────────────────────────────────────────────
    @st.cache_data(ttl=60)
    def fetch_research():
        res = supabase.table("trade_research") \
            .select("*") \
            .order("analysis_date", desc=True) \
            .order("created_at", desc=True) \
            .execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    
    df = fetch_research()
    
    if df.empty:
        st.info("No research saved yet. Run `/trade-analyze TICKER` then `/trade-save TICKER` in Claude Code.")
        st.stop()
    
    # ── Apply filters ────────────────────────────────────────────────────────────
    if filter_verdict:
        df = df[df["verdict"].isin(filter_verdict)]
    if filter_setup:
        df = df[df["setup"].isin(filter_setup)]
    if filter_bonde:
        df = df[df["bonde_match"].isin(filter_bonde)]
    if filter_taken == "Yes":
        df = df[df["trade_taken"] == True]
    elif filter_taken == "No":
        df = df[df["trade_taken"] == False]
    
    st.divider()
    
    # ── Summary metrics ──────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total", len(df))
    m2.metric("Strong Buy / Buy", len(df[df["verdict"].isin(["STRONG BUY", "BUY"])]))
    m3.metric("Bonde Match", len(df[df["bonde_match"] == "MATCH"]))
    m4.metric("Trade Taken", len(df[df["trade_taken"] == True]))
    avg_score = df["score_total"].mean() if "score_total" in df.columns and not df["score_total"].isna().all() else 0
    m5.metric("Avg Score", f"{avg_score:.1f}/10")
    
    st.divider()
    
    # ── Research cards ───────────────────────────────────────────────────────────
    for _, row in df.iterrows():
        verdict_color = VERDICT_COLORS.get(row.get("verdict", ""), "#666")
        setup_color = SETUP_COLORS.get(row.get("setup", "None"), "#666")
        bonde_icon = BONDE_ICONS.get(row.get("bonde_match", "NO"), "❌")
    
        with st.expander(
            f"{row.get('ticker','—')}  ·  "
            f"{row.get('setup','—')}  ·  "
            f"{row.get('verdict','—')}  ·  "
            f"Score: {row.get('score_total','—')}/10  ·  "
            f"{bonde_icon} Bonde  ·  "
            f"{row.get('analysis_date','—')}",
            expanded=False
        ):
            # Header row
            c1, c2, c3 = st.columns([2, 2, 2])
    
            with c1:
                st.markdown(f"### {row.get('ticker','—')}")
                st.caption(row.get("company_name", ""))
                st.markdown(
                    f"<span style='background:{verdict_color};color:white;"
                    f"padding:2px 10px;border-radius:4px;font-weight:bold'>"
                    f"{row.get('verdict','—')}</span>&nbsp;&nbsp;"
                    f"<span style='background:{setup_color};color:white;"
                    f"padding:2px 10px;border-radius:4px'>"
                    f"{row.get('setup','—')} · {row.get('setup_confidence','—')}</span>",
                    unsafe_allow_html=True
                )
    
            with c2:
                st.markdown("**Price Levels**")
                st.markdown(f"Current: ₹{row.get('price_current','—')}")
                st.markdown(f"Entry: ₹{row.get('price_entry','—')}")
                st.markdown(f"Stop: ₹{row.get('price_stop','—')}")
                st.markdown(f"T1: ₹{row.get('price_t1','—')} · T2: ₹{row.get('price_t2','—')} · T3: ₹{row.get('price_t3','—')}")
    
            with c3:
                st.markdown("**Van Tharp Sizing**")
                st.markdown(f"Shares: {row.get('position_size','—')}")
                st.markdown(f"Value: ₹{row.get('position_value','—'):,.0f}" if row.get('position_value') else "Value: —")
                st.markdown(f"% Portfolio: {row.get('pct_of_portfolio','—')}%")
                st.markdown(f"Risk/share: ₹{row.get('risk_per_share','—')}")
    
            st.divider()
    
            # Scores
            s1, s2, s3, s4, s5 = st.columns(5)
            s1.metric("Technical", f"{row.get('score_technical','—')}/10")
            s2.metric("Fundamental", f"{row.get('score_fundamental','—')}/10")
            s3.metric("Sentiment", f"{row.get('score_sentiment','—')}/10")
            s4.metric("Risk", f"{row.get('score_risk','—')}/10")
            s5.metric("Total", f"{row.get('score_total','—')}/10")
    
            st.divider()
    
            # SA format
            st.markdown("**Situational Analysis**")
            sa1, sa2 = st.columns(2)
            with sa1:
                st.markdown("**1. Bias**")
                st.write(row.get("bias", "—"))
                st.markdown("**2. Volume**")
                st.write(row.get("volume_analysis", "—"))
            with sa2:
                st.markdown("**3. Events**")
                st.write(row.get("events", "—"))
                st.markdown("**4. Strategy**")
                st.write(row.get("strategy", "—"))
    
            st.divider()
    
            # Full report toggle
            if row.get("full_report"):
                if st.checkbox("Show full report", key=f"report_{row.get('id','')}"):
                    st.markdown(row["full_report"])
    
            # Mark as trade taken
            taken = row.get("trade_taken", False)
            if st.button(
                "✅ Mark trade taken" if not taken else "↩️ Unmark trade taken",
                key=f"taken_{row.get('id','')}"
            ):
                supabase.table("trade_research") \
                    .update({"trade_taken": not taken}) \
                    .eq("id", row["id"]) \
                    .execute()
                st.cache_data.clear()
                st.rerun()
    