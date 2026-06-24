import streamlit as st
import plotly.graph_objects as go
from theme import *

def render():
    st.markdown("## 🔍 Bonde Scanner")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:18px;font-size:11px">Pradeep Bonde · Stockbee Methodology · NSE Universe · {166} tickers</p>', unsafe_allow_html=True)

    from data.db import _sb
    from datetime import date

    # ── Upload Universe CSV ───────────────────────────────────────────────────
    with st.expander("⬆️ Upload Universe CSV", expanded=True):
        import csv, io
        st.caption("Upload CSV: Stock Name, RS Rating, Basic Industry, % from 52W High, Returns since Earnings(%)")
        uploaded = st.file_uploader("Choose CSV", type="csv", key="universe_csv")
        if uploaded is not None:
            csv_text = uploaded.read().decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(csv_text)))
            st.write(f"✅ File read: {len(rows)} rows. First ticker: {rows[0].get('Stock Name','?') if rows else '?'}")
            if st.button("⬆️ Upload to Universe", key="upload_universe_btn", type="primary"):
                sb = _sb()
                records = []
                for row in rows:
                    ticker = row.get("Stock Name","").strip()
                    if not ticker: continue
                    rs = row.get("RS Rating","").strip()
                    industry = row.get("Basic Industry","").strip()
                    pct52 = row.get("% from 52W High","").strip()
                    ret_earn = row.get("Returns since Earnings(%)","").strip()
                    records.append({
                        "ticker": ticker,
                        "sector": industry,
                        "industry": industry,
                        "rs_rating": int(rs) if rs.lstrip("-").isdigit() else None,
                        "pct_from_52w_high": float(pct52) if pct52 not in ("","NA") else None,
                        "returns_since_earnings": float(ret_earn) if ret_earn not in ("","NA") else None,
                    })
                # Batch upsert in chunks of 100
                prog = st.progress(0, text="Uploading tickers...")
                success = 0
                chunk_size = 100
                for i in range(0, len(records), chunk_size):
                    chunk = records[i:i+chunk_size]
                    try:
                        sb.table("market_universe").upsert(chunk, on_conflict="ticker").execute()
                        success += len(chunk)
                    except Exception as e:
                        st.warning(f"Chunk {i//chunk_size+1} error: {e}")
                    prog.progress(min((i+chunk_size)/len(records), 1.0),
                        text=f"Uploading... {min(i+chunk_size, len(records))}/{len(records)}")
                prog.empty()
                st.success(f"✅ {success} tickers uploaded to universe!")
                st.cache_data.clear()

    @st.cache_data(ttl=300)
    def _load_signals():
        r = _sb().table("bonde_signals").select("*").order("ret_1d", desc=True).execute()
        return r.data or []

    signals = _load_signals()
    if not signals:
        st.info("No signals loaded. Run market refresh first.")
        return

    as_of = signals[0].get("as_of_date","") if signals else ""
    total = len(signals)

    # ── SCANNER TABS ──────────────────────────────────────────────────────────
    t1, t2, t3, t4, t5 = st.tabs([
        "🚀 Momentum Burst",
        "🔵 TTT — Tight Tight Tight",
        "⚡ 20% in 5 Days",
        "🔥 50% in 2 Months",
        "📊 Full Universe"
    ])

    TH = f"padding:10px 14px;font-size:10px;color:white;font-weight:500;text-transform:uppercase;letter-spacing:0.06em;background:#1E293B;border-bottom:1px solid {BORDER}"
    TD = f"padding:9px 14px;font-size:12.5px;border-bottom:1px solid {BORDER_LIGHT}"

    def signal_table(rows, scanner_name, description):
        st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE};margin-bottom:12px">{description}</p>', unsafe_allow_html=True)
        if not rows:
            st.markdown(f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:32px;text-align:center;color:{TEXT_SUBTLE}">No stocks triggered {scanner_name} today</div>', unsafe_allow_html=True)
            return

        # KPI strip
        k1, k2, k3, k4 = st.columns(4)
        avg_ret = sum(float(r.get("ret_1d") or 0) for r in rows) / len(rows)
        avg_vol = sum(float(r.get("volume_ratio") or 0) for r in rows) / len(rows)
        avg_ti  = sum(float(r.get("ti65") or 0) for r in rows if r.get("ti65")) / max(1, sum(1 for r in rows if r.get("ti65")))
        for col, (label, val, color) in zip([k1,k2,k3,k4], [
            ("Stocks Triggered", str(len(rows)), TEAL),
            ("Avg 1D Return",    f"{avg_ret:+.1f}%", TEAL if avg_ret>=0 else RED),
            ("Avg Volume Ratio", f"{avg_vol:.1f}x",  TEAL if avg_vol>=1.5 else AMBER),
            ("Avg TI65",         f"{avg_ti:.1f}%",   TEAL if avg_ti>=55 else AMBER),
        ]):
            col.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px;margin-bottom:12px">
                <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px">{label}</div>
                <div style="font-size:20px;font-weight:700;color:{color}">{val}</div>
            </div>''', unsafe_allow_html=True)

        # Table
        rows_html = ""
        for s in rows:
            ret1d = float(s.get("ret_1d") or 0)
            ret5d = float(s.get("ret_5d") or 0)
            vr    = float(s.get("volume_ratio") or 0)
            ti65  = s.get("ti65")
            pct52 = float(s.get("pct_from_52w_high") or 0)
            ret_color = TEAL if ret1d >= 0 else RED
            vr_color  = TEAL if vr >= 1.5 else (AMBER if vr >= 1.0 else TEXT_SUBTLE)
            ti_color  = TEAL if (ti65 or 0) >= 55 else AMBER
            rows_html += f"""<tr>
                <td style="{TD};font-weight:700;color:{TEXT_H}">{s['ticker']}</td>
                <td style="{TD};color:{TEXT_SUBTLE};font-size:11px">{s.get('sector','')[:15]}</td>
                <td style="{TD};text-align:right;font-weight:600">₹{float(s.get('close') or 0):,.2f}</td>
                <td style="{TD};text-align:right;color:{ret_color};font-weight:600">{ret1d:+.2f}%</td>
                <td style="{TD};text-align:right;color:{'#10B981' if ret5d>=0 else RED}">{ret5d:+.2f}%</td>
                <td style="{TD};text-align:right;color:{vr_color};font-weight:600">{vr:.2f}x</td>
                <td style="{TD};text-align:right;color:{ti_color}">{ti65 or '—'}%</td>
                <td style="{TD};text-align:right;color:{TEXT_SUBTLE}">{pct52:+.1f}%</td>
                <td style="{TD};text-align:right;font-size:11px;color:{TEXT_SUBTLE}">{float(s.get('atr_20d') or 0):.1f}</td>
            </tr>"""

        st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER}">
        <table style="width:100%;border-collapse:collapse">
            <thead><tr>
                <th style="{TH};text-align:left">Ticker</th>
                <th style="{TH};text-align:left">Sector</th>
                <th style="{TH};text-align:right">Close</th>
                <th style="{TH};text-align:right">1D %</th>
                <th style="{TH};text-align:right">5D %</th>
                <th style="{TH};text-align:right">Vol Ratio</th>
                <th style="{TH};text-align:right">TI65</th>
                <th style="{TH};text-align:right">vs 52W High</th>
                <th style="{TH};text-align:right">ATR 20D</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table></div>""", unsafe_allow_html=True)

        st.markdown(f'<p style="font-size:10px;color:{TEXT_SUBTLE};margin-top:8px">As of {as_of} · {total} tickers scanned · 2Lynch qualifying criteria: linear prior move, volume confirmation, near-high close</p>', unsafe_allow_html=True)

    with t1:
        burst = [s for s in signals if s.get("momentum_burst")]
        burst_sorted = sorted(burst, key=lambda x: -(float(x.get("volume_ratio") or 0)))
        signal_table(burst_sorted, "Momentum Burst",
            "📌 Pradeep Bonde primary scan — +4% single day gain with volume > previous day · Signals institutional range expansion on day 1")

    with t2:
        ttt = [s for s in signals if s.get("ttt")]
        ttt_sorted = sorted(ttt, key=lambda x: float(x.get("range_3d_pct") or 99))
        signal_table(ttt_sorted, "TTT",
            "📌 Tight-Tight-Tight — 3-bar range ≤1.5%, today's range ≤0.8% · Quiet before the storm · Institutional accumulation pattern")

    with t3:
        r20 = [s for s in signals if s.get("ret_20pct_5d")]
        r20_sorted = sorted(r20, key=lambda x: -(float(x.get("ret_5d") or 0)))
        signal_table(r20_sorted, "20% in 5 Days",
            "📌 Explosive momentum — 20%+ gain in last 5 trading days · Study what caused the move · Catalyst + volume")

    with t4:
        r50 = [s for s in signals if s.get("ret_50pct_2m")]
        r50_sorted = sorted(r50, key=lambda x: -(float(x.get("ret_5d") or 0)))
        signal_table(r50_sorted, "50% in 2 Months",
            "📌 Weekend scan — 50%+ gain in last 2 months · Deep dive: what was the catalyst, market cap, how did the move start")

    with t5:
        # Full universe sorted by TI65
        full_sorted = sorted(signals, key=lambda x: -(x.get("ti65") or 0))

        # Sector filter
        sectors = sorted({s.get("sector","") for s in signals if s.get("sector")})
        sel_sector = st.selectbox("Filter by sector", ["All"] + sectors, key="screener_sector")
        if sel_sector != "All":
            full_sorted = [s for s in full_sorted if s.get("sector") == sel_sector]

        signal_table(full_sorted, "Universe",
            f"📌 Full NSE universe ranked by TI65 (Trend Intensity) · {len(full_sorted)} stocks")

