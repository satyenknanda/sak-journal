import streamlit as st
import plotly.graph_objects as go
import numpy as np
import io
from theme import *

def render():
    st.markdown("## 🔍 Scanner")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:18px;font-size:11px">NSE Universe · Pradeep Bonde + Cohort 3 Methodology</p>', unsafe_allow_html=True)

    from data.db import _sb

    # ── Refresh + Cache controls ──────────────────────────────────────────────
    col_r1, col_r2, col_r3 = st.columns([1,1,4])
    with col_r1:
        if st.button("🔄 Refresh Signals", key="refresh_signals", type="primary"):
            with st.spinner("Fetching data for all tickers... ~15 mins"):
                try:
                    import sys; sys.path.insert(0, ".")
                    from market_universe.market_refresh import refresh_bonde_signals
                    refresh_bonde_signals()
                    st.cache_data.clear()
                    st.success("✅ Signals refreshed!")
                except Exception as e:
                    st.error(f"❌ {e}")
    with col_r2:
        if st.button("🗑️ Clear Cache", key="clear_cache"):
            st.cache_data.clear()
            st.rerun()

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
            burst = sorted([s for s in signals if s.get("momentum_burst")], key=lambda x: -(float(x.get("volume_ratio") or 0)))
            signal_table(burst, "Momentum Burst",
                "📌 +4% single day + volume > previous day — Bonde primary scan — institutional range expansion",
                "bonde_momentum_burst.csv")

        with b2:
            ttt = sorted([s for s in signals if s.get("ttt")], key=lambda x: float(x.get("range_3d_pct") or 99))
            signal_table(ttt, "TTT",
                "📌 3-bar range ≤1.5%, today ≤0.8% — quiet before the storm — institutional accumulation",
                "bonde_ttt.csv")

        with b3:
            r20 = sorted([s for s in signals if s.get("ret_20pct_5d")], key=lambda x: -(float(x.get("ret_5d") or 0)))
            signal_table(r20, "20% in 5 Days",
                "📌 20%+ gain in last 5 days — study the catalyst — explosive momentum",
                "bonde_20pct_5d.csv")

        with b4:
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
                r1w = [float(r.get("ret_1w") or 0) for r in returns]
                r1m = [float(r.get("ret_1m") or 0) for r in returns]
                r3m = [float(r.get("ret_3m") or 0) for r in returns]
                r6m = [float(r.get("ret_6m") or 0) for r in returns]
                p80 = np.percentile(r1w, 80); p75 = np.percentile(r1m, 75)
                p65 = np.percentile(r3m, 65); p50 = np.percentile(r6m, 50)

                easy = []
                for r in returns:
                    w = float(r.get("ret_1w") or 0); m = float(r.get("ret_1m") or 0)
                    q = float(r.get("ret_3m") or 0); s = float(r.get("ret_6m") or 0)
                    if w >= p80 and m >= p75 and q >= p65 and s >= p50:
                        score = (w/max(p80,0.01)+m/max(p75,0.01)+q/max(p65,0.01)+s/max(p50,0.01))/4
                        easy.append({**r, "_score": score, "ret_1d": 0, "volume_ratio": 0, "ti65": None,
                                     "close": 0, "pct_from_52w_high": 0, "sector": ""})
                easy = sorted(easy, key=lambda x: -x["_score"])

                # Merge with signals for close price
                sig_map = {s["ticker"]: s for s in signals}
                for e in easy:
                    if e["ticker"] in sig_map:
                        e.update({k: sig_map[e["ticker"]].get(k, e.get(k)) 
                                  for k in ["close","ret_1d","volume_ratio","ti65","pct_from_52w_high","sector"]})

                # TV copy
                tv_str = ",".join([f"NSE:{e['ticker']}" for e in easy])
                dc1, dc2 = st.columns([1,3])
                with dc1:
                    import csv, io as _io2
                    buf = _io2.StringIO()
                    w2 = csv.DictWriter(buf, fieldnames=["ticker","ret_1w","ret_1m","ret_3m","ret_6m","ret_ytd","_score"])
                    w2.writeheader()
                    for e in easy: w2.writerow({k: e.get(k,"") for k in ["ticker","ret_1w","ret_1m","ret_3m","ret_6m","ret_ytd","_score"]})
                    st.download_button("⬇️ Download CSV", buf.getvalue().encode(), "cohort3_easy_money.csv", "text/csv", key="dl_easy")
                with dc2:
                    with st.expander("📋 TradingView Import"):
                        st.code(tv_str, language=None)
                        st.caption("👆 Copy → TradingView → Watchlist → Import")

                # KPIs
                em1,em2,em3,em4 = st.columns(4)
                for col,(label,val,color) in zip([em1,em2,em3,em4],[
                    ("Easy Money Stocks", str(len(easy)), TEAL),
                    (f"Min 1W (top 20%)", f"{p80:+.1f}%", TEAL),
                    (f"Min 1M (top 25%)", f"{p75:+.1f}%", TEAL),
                    (f"Min 3M (top 35%)", f"{p65:+.1f}%", TEAL),
                ]):
                    col.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px;margin-bottom:10px">
                        <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px">{label}</div>
                        <div style="font-size:20px;font-weight:700;color:{color}">{val}</div>
                    </div>''', unsafe_allow_html=True)

                rows_em = ""
                for e in easy:
                    rows_em += f"""<tr>
                        <td style="{TD};font-weight:700;color:{TEXT_H}">{e['ticker']}</td>
                        <td style="{TD};text-align:right;color:#10B981">{float(e.get('ret_1w') or 0):+.1f}%</td>
                        <td style="{TD};text-align:right;color:#10B981">{float(e.get('ret_1m') or 0):+.1f}%</td>
                        <td style="{TD};text-align:right;color:#10B981">{float(e.get('ret_3m') or 0):+.1f}%</td>
                        <td style="{TD};text-align:right;color:#10B981">{float(e.get('ret_6m') or 0):+.1f}%</td>
                        <td style="{TD};text-align:right;color:#10B981">{float(e.get('ret_ytd') or 0):+.1f}%</td>
                        <td style="{TD};text-align:right;font-weight:700;color:{TEAL}">{e['_score']:.2f}</td>
                    </tr>"""
                st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER}">
                <table style="width:100%;border-collapse:collapse">
                    <thead><tr>
                        <th style="{TH};text-align:left">Ticker</th>
                        <th style="{TH};text-align:right">1W%</th>
                        <th style="{TH};text-align:right">1M%</th>
                        <th style="{TH};text-align:right">3M%</th>
                        <th style="{TH};text-align:right">6M%</th>
                        <th style="{TH};text-align:right">YTD%</th>
                        <th style="{TH};text-align:right">Score</th>
                    </tr></thead>
                    <tbody>{rows_em}</tbody>
                </table></div>""", unsafe_allow_html=True)

        # ATH Scan — within 10% of 52W high
        with c2:
            ath = sorted([s for s in signals if s.get("pct_from_52w_high") is not None
                         and float(s.get("pct_from_52w_high") or -99) >= -10],
                        key=lambda x: -(float(x.get("pct_from_52w_high") or -99)))
            signal_table(ath, "ATH Scan",
                "📌 Within 10% of 52-week high — near-breakout candidates — sort by closest to ATH",
                "cohort3_ath.csv")

        # High ADR
        with c3:
            # ADR = ATR20 / close * 100
            high_adr = []
            for s in signals:
                close = float(s.get("close") or 0)
                atr = float(s.get("atr_20d") or 0)
                if close > 0 and atr > 0:
                    adr = atr / close * 100
                    if adr >= 5:
                        high_adr.append({**s, "_adr": round(adr, 2)})
            high_adr = sorted(high_adr, key=lambda x: -x["_adr"])
            signal_table(high_adr, "High ADR",
                "📌 ADR >5% — fast movers — momentum expansion candidates — trade quickly",
                "cohort3_high_adr.csv")

        # Stocks in Play
        with c4:
            sip = sorted([s for s in signals
                         if float(s.get("volume_ratio") or 0) >= 3.0
                         and float(s.get("ret_1d") or 0) >= 3.0],
                        key=lambda x: -(float(x.get("volume_ratio") or 0)))
            signal_table(sip, "Stocks in Play",
                "📌 Volume 3x+ normal AND price 3%+ today — today's actionable names — highest conviction",
                "cohort3_stocks_in_play.csv")

        # Reversals — top weekly losers
        with c5:
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
