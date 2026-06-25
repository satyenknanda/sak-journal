import streamlit as st
import plotly.graph_objects as go
import numpy as np
import io
from theme import *

def render():
    st.markdown("## 🔍 Scanner")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:18px;font-size:11px">NSE Universe · Pradeep Bonde + Cohort 3 · v3 — Easy Money sub-tabs</p>', unsafe_allow_html=True)

    from data.db import _sb

    # ── Cache clear ──────────────────────────────────────────────────────────
    if st.button("🗑️ Clear Cache", key="clear_cache"):
        st.cache_data.clear()
        st.rerun()

    def _do_refresh_signals():
        import sys; sys.path.insert(0, ".")
        from market_universe.market_refresh import refresh_bonde_signals
        refresh_bonde_signals()
        st.cache_data.clear()

    def _do_refresh_returns():
        import sys; sys.path.insert(0, ".")
        from market_universe.refresh_scans import refresh_returns_only
        refresh_returns_only()
        st.cache_data.clear()

    # ── Upload Universe CSV ───────────────────────────────────────────────────
    with st.expander("⬆️ Upload Universe CSV", expanded=False):
        import csv, io as _io
        st.caption("CSV columns: Stock Name, RS Rating, Basic Industry, % from 52W High, Returns since Earnings(%)")
        uploaded = st.file_uploader("Choose CSV", type="csv", key="universe_csv")
        if uploaded is not None:
            csv_text = uploaded.read().decode("utf-8")
            rows = list(csv.DictReader(_io.StringIO(csv_text)))
            records = []
            for row in rows:
                ticker = row.get("Stock Name","").strip()
                if not ticker: continue
                rs = row.get("RS Rating","").strip()
                industry = row.get("Basic Industry","").strip()
                pct52 = row.get("% from 52W High","").strip()
                ret_earn = row.get("Returns since Earnings(%)","").strip()
                records.append({
                    "ticker": ticker, "sector": industry, "industry": industry,
                    "rs_rating": int(rs) if rs.lstrip("-").isdigit() else None,
                    "pct_from_52w_high": float(pct52) if pct52 not in ("","NA") else None,
                    "returns_since_earnings": float(ret_earn) if ret_earn not in ("","NA") else None,
                })
            st.session_state["_universe_records"] = records
            st.info(f"Found {len(records)} tickers")

        if st.session_state.get("_universe_records"):
            records = st.session_state["_universe_records"]
            if st.button("⬆️ Upload to Universe", key="upload_universe_btn", type="primary"):
                sb = _sb()
                success = 0
                prog = st.progress(0, text="Uploading...")
                for i in range(0, len(records), 50):
                    chunk = records[i:i+50]
                    try:
                        sb.table("market_universe").upsert(chunk, on_conflict="ticker").execute()
                        success += len(chunk)
                    except Exception as e:
                        st.error(f"❌ {e}"); break
                    prog.progress(min((i+50)/len(records),1.0), text=f"Uploading {min(i+50,len(records))}/{len(records)}...")
                prog.empty()
                st.success(f"✅ {success} tickers uploaded!")
                st.session_state.pop("_universe_records", None)
                st.cache_data.clear()

    @st.cache_data(ttl=300)
    def _load_signals():
        r = _sb().table("bonde_signals").select("*").order("ret_1d", desc=True).execute()
        return r.data or []

    @st.cache_data(ttl=300)
    def _load_returns():
        r = _sb().table("market_returns").select("*").execute()
        return r.data or []

    signals = _load_signals()
    returns = _load_returns()

    if not signals:
        st.info("No signals. Click Refresh Signals."); return

    as_of = signals[0].get("as_of_date","") if signals else ""
    total = len(signals)

    # ── Helpers ───────────────────────────────────────────────────────────────
    TH = f"padding:10px 14px;font-size:10px;color:white;font-weight:500;text-transform:uppercase;letter-spacing:0.06em;background:#1E293B;border-bottom:1px solid {BORDER}"
    TD = f"padding:9px 14px;font-size:12.5px;border-bottom:1px solid {BORDER_LIGHT}"

    def csv_download(rows, filename, cols):
        import csv, io as _io
        buf = _io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c,"") for c in cols})
        st.download_button(f"⬇️ Download CSV", buf.getvalue().encode(),
            file_name=filename, mime="text/csv", key=f"dl_{filename}")

    def tv_copy(rows, key):
        tv = ",".join([f"NSE:{r['ticker']}" for r in rows if r.get('ticker')])
        st.code(tv, language=None)
        st.caption("👆 Copy above → TradingView → Watchlist → Import")

    def signal_table(rows, scanner_name, description, dl_file, show_tv=True):
        st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE};margin-bottom:8px">{description}</p>', unsafe_allow_html=True)

        if not rows:
            st.info(f"No stocks triggered {scanner_name} today")
            return

        # Download + TV copy
        dc1, dc2 = st.columns([1,3])
        with dc1:
            csv_download(rows, dl_file, ["ticker","sector","close","ret_1d","ret_5d","volume_ratio","ti65","pct_from_52w_high","atr_20d"])
        with dc2:
            with st.expander("📋 TradingView Import List"):
                tv_copy(rows, dl_file)

        # KPIs
        k1,k2,k3,k4 = st.columns(4)
        avg_ret = sum(float(r.get("ret_1d") or 0) for r in rows)/len(rows)
        avg_vol = sum(float(r.get("volume_ratio") or 0) for r in rows)/len(rows)
        avg_ti  = sum(float(r.get("ti65") or 0) for r in rows if r.get("ti65"))/max(1,sum(1 for r in rows if r.get("ti65")))
        for col,(label,val,color) in zip([k1,k2,k3,k4],[
            ("Triggered", str(len(rows)), TEAL),
            ("Avg 1D",    f"{avg_ret:+.1f}%", TEAL if avg_ret>=0 else RED),
            ("Avg Vol",   f"{avg_vol:.1f}x",  TEAL if avg_vol>=1.5 else AMBER),
            ("Avg TI65",  f"{avg_ti:.1f}%",   TEAL if avg_ti>=55 else AMBER),
        ]):
            col.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px;margin-bottom:10px">
                <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px">{label}</div>
                <div style="font-size:20px;font-weight:700;color:{color}">{val}</div>
            </div>''', unsafe_allow_html=True)

        rows_html = ""
        for s in rows:
            r1d = float(s.get("ret_1d") or 0); r5d = float(s.get("ret_5d") or 0)
            vr  = float(s.get("volume_ratio") or 0); ti = s.get("ti65")
            p52 = float(s.get("pct_from_52w_high") or 0)
            rows_html += f"""<tr>
                <td style="{TD};font-weight:700;color:{TEXT_H}">{s['ticker']}</td>
                <td style="{TD};color:{TEXT_SUBTLE};font-size:11px">{s.get('sector','')[:18]}</td>
                <td style="{TD};text-align:right">₹{float(s.get('close') or 0):,.2f}</td>
                <td style="{TD};text-align:right;color:{'#10B981' if r1d>=0 else RED};font-weight:600">{r1d:+.2f}%</td>
                <td style="{TD};text-align:right;color:{'#10B981' if r5d>=0 else RED}">{r5d:+.2f}%</td>
                <td style="{TD};text-align:right;color:{'#10B981' if vr>=1.5 else AMBER if vr>=1 else TEXT_SUBTLE}">{vr:.2f}x</td>
                <td style="{TD};text-align:right;color:{'#10B981' if (ti or 0)>=55 else AMBER}">{ti or '—'}%</td>
                <td style="{TD};text-align:right;color:{TEXT_SUBTLE}">{p52:+.1f}%</td>
            </tr>"""

        st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER}">
        <table style="width:100%;border-collapse:collapse">
            <thead><tr>
                <th style="{TH};text-align:left">Ticker</th>
                <th style="{TH};text-align:left">Sector</th>
                <th style="{TH};text-align:right">Close</th>
                <th style="{TH};text-align:right">1D%</th>
                <th style="{TH};text-align:right">5D%</th>
                <th style="{TH};text-align:right">Vol</th>
                <th style="{TH};text-align:right">TI65</th>
                <th style="{TH};text-align:right">vs 52W</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table></div>""", unsafe_allow_html=True)
        st.markdown(f'<p style="font-size:10px;color:{TEXT_SUBTLE};margin-top:6px">As of {as_of} · {total} tickers scanned</p>', unsafe_allow_html=True)

    # ── MAIN TABS ─────────────────────────────────────────────────────────────
    main1, main2, main3 = st.tabs(["🎯 Bonde Scans", "💰 Cohort 3 Scans", "📊 Full Universe"])

    # ═══════════════════════════════════════════════════════════════════════════
    # BONDE SCANS
    # ═══════════════════════════════════════════════════════════════════════════
    with main1:
        b1, b2, b3, b4 = st.tabs(["🚀 Momentum Burst", "🔵 TTT", "⚡ 20% in 5D", "🔥 50% in 2M"])

        with b1:
            if st.button("🔄 Refresh Momentum Burst", key="ref_burst", type="primary"):
                with st.spinner("Refreshing signals (~15 mins)..."):
                    _do_refresh_signals()
                    st.success("✅ Done!")
                    st.rerun()
            burst = sorted([s for s in signals if s.get("momentum_burst")], key=lambda x: -(float(x.get("volume_ratio") or 0)))
            signal_table(burst, "Momentum Burst",
                "📌 +4% single day + volume > previous day — Bonde primary scan — institutional range expansion",
                "bonde_momentum_burst.csv")

        with b2:
            if st.button("🔄 Refresh TTT", key="ref_ttt", type="primary"):
                with st.spinner("Refreshing signals (~15 mins)..."):
                    _do_refresh_signals()
                    st.success("✅ Done!"); st.rerun()
            ttt = sorted([s for s in signals if s.get("ttt")], key=lambda x: float(x.get("range_3d_pct") or 99))
            signal_table(ttt, "TTT",
                "📌 3-bar range ≤1.5%, today ≤0.8% — quiet before the storm — institutional accumulation",
                "bonde_ttt.csv")

        with b3:
            if st.button("🔄 Refresh 20% in 5D", key="ref_r20", type="primary"):
                with st.spinner("Refreshing signals (~15 mins)..."):
                    _do_refresh_signals()
                    st.success("✅ Done!"); st.rerun()
            r20 = sorted([s for s in signals if s.get("ret_20pct_5d")], key=lambda x: -(float(x.get("ret_5d") or 0)))
            signal_table(r20, "20% in 5 Days",
                "📌 20%+ gain in last 5 days — study the catalyst — explosive momentum",
                "bonde_20pct_5d.csv")

        with b4:
            if st.button("🔄 Refresh 50% in 2M", key="ref_r50", type="primary"):
                with st.spinner("Refreshing signals (~15 mins)..."):
                    _do_refresh_signals()
                    st.success("✅ Done!"); st.rerun()
            r50 = sorted([s for s in signals if s.get("ret_50pct_2m")], key=lambda x: -(float(x.get("ret_5d") or 0)))
            signal_table(r50, "50% in 2 Months",
                "📌 50%+ in 2 months — weekend deep dive — what was the catalyst",
                "bonde_50pct_2m.csv")

    # ═══════════════════════════════════════════════════════════════════════════
    # COHORT 3 SCANS
    # ═══════════════════════════════════════════════════════════════════════════
    with main2:
        c1, c2, c3, c4, c5 = st.tabs(["💰 Easy Money", "🏔️ ATH Scan", "⚡ High ADR", "🎯 Stocks in Play", "🔄 Reversals"])

        # Easy Money
        with c1:
            st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE};margin-bottom:8px">Top 20% weekly AND Top 25% monthly AND Top 35% quarterly AND Top 50% semi-annual</p>', unsafe_allow_html=True)
            if not returns:
                st.info("No returns data. Run Refresh Signals.")
            else:
                # Easy Money — sub-tabs with independent % per timeframe
                all_r = [r for r in returns if r.get("ret_1w") is not None]
                sig_map = {s["ticker"]: s for s in signals}

                def _enrich(r):
                    s = sig_map.get(r["ticker"], {})
                    return {**r, "close": s.get("close",0), "sector": s.get("sector","")}

                # Rank-based — top % of universe by each timeframe
                s1 = sorted(all_r, key=lambda x: -(float(x.get("ret_1w") or 0)))
                s1 = [_enrich(r) for r in s1[:max(1,int(len(s1)*0.20))]]
                s2 = sorted(all_r, key=lambda x: -(float(x.get("ret_1m") or 0)))
                s2 = [_enrich(r) for r in s2[:max(1,int(len(s2)*0.25))]]
                s3 = sorted(all_r, key=lambda x: -(float(x.get("ret_3m") or 0)))
                s3 = [_enrich(r) for r in s3[:max(1,int(len(s3)*0.35))]]
                s4 = sorted(all_r, key=lambda x: -(float(x.get("ret_6m") or 0)))
                s4 = [_enrich(r) for r in s4[:max(1,int(len(s4)*0.50))]]
                min_1w = float(s1[-1].get("ret_1w") or 0) if s1 else 0
                min_1m = float(s2[-1].get("ret_1m") or 0) if s2 else 0
                min_3m = float(s3[-1].get("ret_3m") or 0) if s3 else 0
                min_6m = float(s4[-1].get("ret_6m") or 0) if s4 else 0

                # Union for TV export
                seen = set(); all_easy = []
                for sec in [s1,s2,s3,s4]:
                    for r in sec:
                        if r["ticker"] not in seen:
                            seen.add(r["ticker"]); all_easy.append(r)

                # TV copy + CSV
                tv_str = ",".join([f"NSE:{e['ticker']}" for e in all_easy])
                dc1e, dc2e = st.columns([1,3])
                with dc1e:
                    import csv, io as _io2
                    buf = _io2.StringIO()
                    w2 = csv.DictWriter(buf, fieldnames=["ticker","ret_1w","ret_1m","ret_3m","ret_6m"])
                    w2.writeheader()
                    for e in all_easy: w2.writerow({k: e.get(k,"") for k in ["ticker","ret_1w","ret_1m","ret_3m","ret_6m"]})
                    st.download_button("⬇️ Download All CSV", buf.getvalue().encode(), "easy_money.csv", "text/csv", key="dl_easy")
                with dc2e:
                    with st.expander("📋 TradingView Import (All)"):
                        st.code(tv_str, language=None)
                        st.caption("👆 Copy → TradingView → Watchlist → Import")

                # KPI strip
                em1,em2,em3,em4,em5 = st.columns(5)
                for col,(label,val,color) in zip([em1,em2,em3,em4,em5],[
                    ("Total Unique", str(len(all_easy)), TEAL),
                    (f"1W Top 20% (≥{min_1w:.1f}%)",  str(len(s1)), BLUE),
                    (f"1M Top 25% (≥{min_1m:.1f}%)",  str(len(s2)), BLUE),
                    (f"3M Top 35% (≥{min_3m:.1f}%)",  str(len(s3)), BLUE),
                    (f"6M Top 50% (≥{min_6m:.1f}%)",  str(len(s4)), BLUE),
                ]):
                    col.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px;margin-bottom:10px">
                        <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px">{label}</div>
                        <div style="font-size:20px;font-weight:700;color:{color}">{val}</div>
                    </div>''', unsafe_allow_html=True)

                # Section selector — radio instead of nested tabs (Streamlit limitation)
                em_section = st.radio("Section", [
                    f"📅 1W — Top 20% ({len(s1)} stocks)",
                    f"📅 1M — Top 25% ({len(s2)} stocks)",
                    f"📅 3M — Top 35% ({len(s3)} stocks)",
                    f"📅 6M — Top 50% ({len(s4)} stocks)",
                ], horizontal=True, key="em_section_sel", label_visibility="collapsed")

                sec_map = {
                    f"📅 1W — Top 20% ({len(s1)} stocks)": (s1, "1w"),
                    f"📅 1M — Top 25% ({len(s2)} stocks)": (s2, "1m"),
                    f"📅 3M — Top 35% ({len(s3)} stocks)": (s3, "3m"),
                    f"📅 6M — Top 50% ({len(s4)} stocks)": (s4, "6m"),
                }
                active_sec, active_key = sec_map[em_section]

                def _em_table(sec, sort_key, tab_key):
                    # TV + CSV per section
                    tv_sec = ",".join([f"NSE:{e['ticker']}" for e in sec])
                    dl1, dl2 = st.columns([1,3])
                    with dl1:
                        import csv, io as _io3
                        buf2 = _io3.StringIO()
                        w3 = csv.DictWriter(buf2, fieldnames=["ticker","ret_1w","ret_1m","ret_3m","ret_6m","ret_ytd"])
                        w3.writeheader()
                        for e in sec: w3.writerow({k: e.get(k,"") for k in ["ticker","ret_1w","ret_1m","ret_3m","ret_6m","ret_ytd"]})
                        st.download_button("⬇️ Download CSV", buf2.getvalue().encode(),
                            f"easy_{tab_key}.csv", "text/csv", key=f"dl_em_{tab_key}")
                    with dl2:
                        with st.expander("📋 TradingView Import"):
                            st.code(tv_sec, language=None)
                            st.caption("👆 Copy → TradingView → Watchlist → Import")

                    rhtml = ""
                    for e in sec:
                        rhtml += f"""<tr>
                            <td style="{TD};font-weight:700;color:{TEXT_H}">{e['ticker']}</td>
                            <td style="{TD};color:{TEXT_SUBTLE};font-size:11px">{str(e.get('sector',''))[:18]}</td>
                            <td style="{TD};text-align:right">₹{float(e.get('close') or 0):,.2f}</td>
                            <td style="{TD};text-align:right;color:{'#10B981' if float(e.get('ret_1w') or 0)>=0 else RED}">{float(e.get('ret_1w') or 0):+.1f}%</td>
                            <td style="{TD};text-align:right;color:{'#10B981' if float(e.get('ret_1m') or 0)>=0 else RED}">{float(e.get('ret_1m') or 0):+.1f}%</td>
                            <td style="{TD};text-align:right;color:{'#10B981' if float(e.get('ret_3m') or 0)>=0 else RED}">{float(e.get('ret_3m') or 0):+.1f}%</td>
                            <td style="{TD};text-align:right;color:{'#10B981' if float(e.get('ret_6m') or 0)>=0 else RED}">{float(e.get('ret_6m') or 0):+.1f}%</td>
                            <td style="{TD};text-align:right;color:{'#10B981' if float(e.get('ret_ytd') or 0)>=0 else RED}">{float(e.get('ret_ytd') or 0):+.1f}%</td>
                        </tr>"""
                    st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER}">
                    <table style="width:100%;border-collapse:collapse">
                        <thead><tr>
                            <th style="{TH};text-align:left">Ticker</th>
                            <th style="{TH};text-align:left">Sector</th>
                            <th style="{TH};text-align:right">Close</th>
                            <th style="{TH};text-align:right">1W%</th>
                            <th style="{TH};text-align:right">1M%</th>
                            <th style="{TH};text-align:right">3M%</th>
                            <th style="{TH};text-align:right">6M%</th>
                            <th style="{TH};text-align:right">YTD%</th>
                        </tr></thead>
                        <tbody>{rhtml}</tbody>
                    </table></div>""", unsafe_allow_html=True)

                _em_table(active_sec, f"ret_{active_key}", active_key)
        # ATH Scan — within 10% of 52W high
        with c2:
            if st.button("🔄 Refresh ATH Scan", key="ref_ath", type="primary"):
                with st.spinner("Refreshing signals (~15 mins)..."):
                    _do_refresh_signals()
                    st.success("✅ Done!"); st.rerun()
            ath = sorted([s for s in signals if s.get("pct_from_52w_high") is not None
                         and float(s.get("pct_from_52w_high") or -99) >= -10],
                        key=lambda x: -(float(x.get("pct_from_52w_high") or -99)))
            signal_table(ath, "ATH Scan",
                "📌 Within 10% of 52-week high — near-breakout candidates — sort by closest to ATH",
                "cohort3_ath.csv")

        # High ADR
        with c3:
            if st.button("🔄 Refresh High ADR", key="ref_adr", type="primary"):
                with st.spinner("Refreshing signals (~15 mins)..."):
                    _do_refresh_signals()
                    st.success("✅ Done!"); st.rerun()
            adr_min = st.number_input("Min ADR %", value=5.0, step=0.5, key="adr_min")
            # ADR = (High - Low) / Close * 100 averaged — approximated by ATR/Close
            high_adr = []
            for s in signals:
                close = float(s.get("close") or 0)
                atr = float(s.get("atr_20d") or 0)
                if close > 0 and atr > 0:
                    adr = round(atr / close * 100, 2)
                    if adr >= adr_min:
                        high_adr.append({**s, "_adr": adr})
            high_adr = sorted(high_adr, key=lambda x: -x["_adr"])
            st.caption(f"Showing {len(high_adr)} stocks with ADR ≥ {adr_min}% · Reference: 93 stocks at ADR ≥ 5%")
            signal_table(high_adr, "High ADR",
                f"📌 ADR >{adr_min}% — fast movers — momentum expansion — trade quickly",
                "cohort3_high_adr.csv")

        # Stocks in Play
        with c4:
            if st.button("🔄 Refresh Stocks in Play", key="ref_sip", type="primary"):
                with st.spinner("Refreshing signals (~15 mins)..."):
                    _do_refresh_signals()
                    st.success("✅ Done!"); st.rerun()
            sip = sorted([s for s in signals
                         if float(s.get("volume_ratio") or 0) >= 3.0
                         and float(s.get("ret_1d") or 0) >= 3.0],
                        key=lambda x: -(float(x.get("volume_ratio") or 0)))
            signal_table(sip, "Stocks in Play",
                "📌 Volume 3x+ normal AND price 3%+ today — today's actionable names — highest conviction",
                "cohort3_stocks_in_play.csv")

        # Reversals — top weekly losers
        with c5:
            if st.button("🔄 Refresh Reversals", key="ref_rev", type="primary"):
                with st.spinner("Refreshing signals (~15 mins)..."):
                    _do_refresh_signals()
                    st.success("✅ Done!"); st.rerun()
            rev = sorted([s for s in signals if float(s.get("ret_5d") or 0) <= -10],
                        key=lambda x: float(x.get("ret_5d") or 0))
            signal_table(rev, "Reversals",
                "📌 Down 10%+ in last week — potential bounce setups — use in weak market conditions",
                "cohort3_reversals.csv")

    # ═══════════════════════════════════════════════════════════════════════════
    # FULL UNIVERSE
    # ═══════════════════════════════════════════════════════════════════════════
    with main3:
        full = sorted(signals, key=lambda x: -(x.get("ti65") or 0))
        sectors = sorted({s.get("sector","") for s in full if s.get("sector")})
        sel = st.selectbox("Filter by sector", ["All"] + sectors, key="screener_sector")
        if sel != "All":
            full = [s for s in full if s.get("sector") == sel]
        signal_table(full, "Universe", f"📌 {len(full)} stocks ranked by TI65 (Trend Intensity)", "full_universe.csv")
