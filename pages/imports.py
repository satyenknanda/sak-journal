"""
Imports page — Cohort 3 routine format
Weekly | Daily | Seasonal | Situational
"""
import streamlit as st
import os, csv, io
from theme import *
from data.db import _sb, _use_supabase

def render():
    st.markdown("## ⬆️ Imports")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:18px;font-size:12px">Cohort 3 Routine — Weekly · Daily · Seasonal · Situational</p>', unsafe_allow_html=True)

    tab_weekly, tab_daily, tab_seasonal, tab_sit, tab_excel = st.tabs([
        "📆 Weekly",
        "📅 Daily",
        "🌱 Seasonal",
        "⚡ Situational",
        "📊 Import Trades"
    ])

    # ═══════════════════════════════════════════════════════════════════════
    # WEEKLY
    # ═══════════════════════════════════════════════════════════════════════
    with tab_weekly:
        st.markdown("### 📆 Weekly Routine")
        st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE}">Run every weekend — update universe, MTF/MIS list, IPO list</p>', unsafe_allow_html=True)

        w1, w2, w3, w4, w5 = st.tabs([
            "1️⃣ Universe List",
            "2️⃣ New Universe Merge",
            "3️⃣ IPO List",
            "4️⃣ MTF / MIS List",
            "5️⃣ Circuit Filter"
        ])

        # 1. Total Universe List
        with w1:
            st.markdown("#### Total Universe List")
            st.caption("Upload Chirag's universe CSV — Stock Name, RS Rating, Basic Industry, % from 52W High, Returns since Earnings(%)")
            uploaded_u = st.file_uploader("Choose Universe CSV", type="csv", key="imp_universe_csv")
            if uploaded_u is not None:
                try:
                    rows = list(csv.DictReader(io.StringIO(uploaded_u.read().decode("utf-8"))))
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
                    if records:
                        st.session_state["_imp_universe_records"] = records
                        st.success(f"✅ {len(records)} tickers read")
                    else:
                        st.warning("No valid tickers found")
                except Exception as e:
                    st.error(f"❌ {e}")

            if st.session_state.get("_imp_universe_records"):
                records = st.session_state["_imp_universe_records"]
                if st.button("⬆️ Upload Universe", key="imp_universe_btn", type="primary"):
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
                        prog.progress(min((i+50)/len(records),1.0), text=f"{min(i+50,len(records))}/{len(records)}")
                    prog.empty()
                    st.success(f"✅ {success} tickers uploaded!")
                    st.session_state.pop("_imp_universe_records", None)
                    st.cache_data.clear()
            try:
                count = _sb().table("market_universe").select("ticker", count="exact").execute().count
                st.metric("Current Universe", f"{count} tickers")
            except: pass

        # 2. New Universe Merge
        with w2:
            st.markdown("#### New Universe List + Merge")
            st.caption("Upload a new/updated universe CSV — tickers are merged (upserted) into the total universe, not replaced")
            uploaded_new = st.file_uploader("Choose New Universe CSV", type="csv", key="imp_new_universe")
            if uploaded_new is not None:
                try:
                    rows = list(csv.DictReader(io.StringIO(uploaded_new.read().decode("utf-8"))))
                    # Handle TV export format (NSE:TICKER,) or plain ticker list
                    records = []
                    for row in rows:
                        # Try Stock Name column first
                        ticker = row.get("Stock Name", row.get("Symbol", list(row.values())[0] if row else "")).strip()
                        ticker = ticker.replace("NSE:","").rstrip(",").strip()
                        if not ticker: continue
                        records.append({"ticker": ticker})
                    if records:
                        st.session_state["_imp_new_universe"] = records
                        st.success(f"✅ {len(records)} tickers read — will be MERGED into universe")
                except Exception as e:
                    st.error(f"❌ {e}")

            if st.session_state.get("_imp_new_universe"):
                records = st.session_state["_imp_new_universe"]
                if st.button("⬆️ Merge into Universe", key="imp_merge_btn", type="primary"):
                    sb = _sb()
                    success = 0
                    prog = st.progress(0, text="Merging...")
                    for i in range(0, len(records), 50):
                        chunk = records[i:i+50]
                        try:
                            sb.table("market_universe").upsert(chunk, on_conflict="ticker").execute()
                            success += len(chunk)
                        except Exception as e:
                            st.error(f"❌ {e}"); break
                        prog.progress(min((i+50)/len(records),1.0))
                    prog.empty()
                    st.success(f"✅ {success} tickers merged!")
                    st.session_state.pop("_imp_new_universe", None)

        # 3. IPO List
        with w3:
            st.markdown("#### IPO List Update")
            st.caption("Upload IPO watchlist — columns: ticker, listing_date, listing_price, ipo_price")
            uploaded_ipo = st.file_uploader("Choose IPO CSV", type="csv", key="imp_ipo_csv")
            if uploaded_ipo is not None:
                try:
                    rows = list(csv.DictReader(io.StringIO(uploaded_ipo.read().decode("utf-8"))))
                    st.write(f"Columns: `{', '.join(rows[0].keys() if rows else [])}`")
                    st.write(f"Rows: {len(rows)}")
                    st.session_state["_imp_ipo_rows"] = rows
                    st.success(f"✅ {len(rows)} IPO stocks read")
                except Exception as e:
                    st.error(f"❌ {e}")

            if st.session_state.get("_imp_ipo_rows"):
                rows = st.session_state["_imp_ipo_rows"]
                cols = list(rows[0].keys())
                ic1, ic2, ic3 = st.columns(3)
                sym_c = ic1.selectbox("Ticker col", cols, key="ipo_sym")
                date_c = ic2.selectbox("Listing date col", ["None"]+cols, key="ipo_date")
                price_c = ic3.selectbox("Listing price col", ["None"]+cols, key="ipo_price")
                if st.button("⬆️ Upload IPO List", key="imp_ipo_btn", type="primary"):
                    sb = _sb()
                    records = []
                    for row in rows:
                        tk = str(row.get(sym_c,"") or "").strip().lstrip("﻿")
                        if not tk: continue
                        listing_date = None
                        if date_c != "None":
                            raw_date = str(row.get(date_c,"") or "").strip()
                            try:
                                from datetime import datetime
                                listing_date = datetime.strptime(raw_date, "%d-%b-%y").strftime("%Y-%m-%d")
                            except:
                                try: listing_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                                except: listing_date = raw_date
                        records.append({
                            "ticker": tk,
                            "is_ipo": True,
                            "listing_date": listing_date,
                        })
                    success = 0
                    for i in range(0, len(records), 50):
                        try:
                            sb.table("market_universe").upsert(records[i:i+50], on_conflict="ticker").execute()
                            success += len(records[i:i+50])
                        except Exception as e:
                            st.error(f"❌ {e}"); break
                    st.success(f"✅ {success} IPO stocks added to universe!")
                    st.session_state.pop("_imp_ipo_rows", None)

        # 4. MTF / MIS List
        with w4:
            st.markdown("#### MTF / MIS Stocks List")
            st.caption("Download from Zerodha → zerodha.com/margin-calculator/MTF → Upload here. Update monthly.")
            mtf_up = st.file_uploader("Choose Zerodha MTF CSV", type="csv", key="imp_mtf_csv")
            if mtf_up is not None:
                try:
                    mtf_rows = list(csv.DictReader(io.StringIO(mtf_up.read().decode("utf-8"))))
                    st.session_state["_imp_mtf_rows"] = mtf_rows
                    st.success(f"✅ {len(mtf_rows)} rows read")
                    st.write(f"Columns: `{', '.join(mtf_rows[0].keys() if mtf_rows else [])}`")
                except Exception as e:
                    st.error(f"❌ {e}")

            if st.session_state.get("_imp_mtf_rows"):
                mtf_rows = st.session_state["_imp_mtf_rows"]
                cols_m = list(mtf_rows[0].keys())
                mc1, mc2, mc3 = st.columns(3)
                sym_c = mc1.selectbox("Ticker col", cols_m,
                    index=cols_m.index("tradingsymbol") if "tradingsymbol" in cols_m else 0,
                    key="imp_mtf_sym")
                mar_c = mc2.selectbox("Margin% col", ["None"]+cols_m,
                    index=cols_m.index("margin")+1 if "margin" in cols_m else 0,
                    key="imp_mtf_mar")
                lev_c = mc3.selectbox("Leverage col", ["None"]+cols_m,
                    index=cols_m.index("leverage")+1 if "leverage" in cols_m else 0,
                    key="imp_mtf_lev")
                if st.button("⬆️ Upload MTF List", key="imp_mtf_btn", type="primary"):
                    sb = _sb()
                    try: sb.table("mtf_margins").delete().neq("id",0).execute()
                    except: pass
                    recs = []
                    for row in mtf_rows:
                        tk = str(row.get(sym_c,"") or "").strip().replace("NSE:","").replace("-EQ","")
                        if not tk: continue
                        mg = lv = None
                        if mar_c != "None":
                            try: mg = float(str(row.get(mar_c,"") or "").replace("%",""))
                            except: pass
                        if lev_c != "None":
                            try: lv = float(str(row.get(lev_c,"") or ""))
                            except: pass
                        recs.append({"ticker": tk, "margin_pct": mg, "leverage": lv})
                    success = 0
                    prog = st.progress(0, text="Uploading MTF list...")
                    for i in range(0, len(recs), 50):
                        try:
                            sb.table("mtf_margins").upsert(recs[i:i+50], on_conflict="ticker").execute()
                            success += len(recs[i:i+50])
                        except Exception as e:
                            st.error(f"❌ {e}"); break
                        prog.progress(min((i+50)/len(recs),1.0))
                    prog.empty()
                    st.success(f"✅ {success} MTF stocks uploaded!")
                    st.session_state.pop("_imp_mtf_rows", None)
                try:
                    mtf_count = _sb().table("mtf_margins").select("ticker", count="exact").execute().count
                    st.metric("Current MTF List", f"{mtf_count} stocks")
                except: pass

        # 5. Circuit Filter
        with w5:
            st.markdown("#### Circuit Filter Update")
            st.caption("Download from NSE → Home → All Reports → Daily Reports → Cash Markets → Price Band Complete List")
            st.info("Upload the NSE circuit filter CSV to exclude 5% circuit stocks from your universe scans.")
            cf_up = st.file_uploader("Choose Circuit Filter CSV", type="csv", key="imp_cf_csv")
            if cf_up is not None:
                try:
                    cf_rows = list(csv.DictReader(io.StringIO(cf_up.read().decode("utf-8"))))
                    st.write(f"Columns: `{', '.join(cf_rows[0].keys() if cf_rows else [])}`")
                    st.write(f"Rows: {len(cf_rows)}")
                    st.success(f"✅ {len(cf_rows)} circuit filter stocks read — feature coming soon")
                except Exception as e:
                    st.error(f"❌ {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # DAILY
    # ═══════════════════════════════════════════════════════════════════════
    with tab_daily:
        st.markdown("### 📅 Daily Routine")
        st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE}">Run every morning — Easy Money, High ADR, Stocks-in-Play are auto-updated via GitHub Actions at 4 PM IST</p>', unsafe_allow_html=True)

        d1, d2, d3 = st.columns(3)
        d1.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:20px">💰</div>
            <div style="font-size:12px;font-weight:700;color:{TEXT_H};margin:6px 0">Easy Money List</div>
            <div style="font-size:11px;color:{TEXT_SUBTLE}">Auto-updated daily<br>View in Screener → Cohort 3</div>
        </div>''', unsafe_allow_html=True)
        d2.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:20px">⚡</div>
            <div style="font-size:12px;font-weight:700;color:{TEXT_H};margin:6px 0">High ADR</div>
            <div style="font-size:11px;color:{TEXT_SUBTLE}">Auto-updated daily<br>View in Screener → Cohort 3</div>
        </div>''', unsafe_allow_html=True)
        d3.markdown(f'''<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:20px">🎯</div>
            <div style="font-size:12px;font-weight:700;color:{TEXT_H};margin:6px 0">Stocks-in-Play</div>
            <div style="font-size:11px;color:{TEXT_SUBTLE}">Auto-updated daily<br>View in Screener → Cohort 3</div>
        </div>''', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📊 Manual Daily Trade Import")
        st.caption("Upload Daily Plan Excel to import today's trades")
        import pandas as pd
        from pages.import_excel import parse_daily_plan_excel
        from data.db import add_trade, get_trades, update_trade

        uploaded_xl = st.file_uploader("Choose Daily Plan Excel", type=["xlsx","xls"], key="imp_excel_upload")
        if uploaded_xl:
            try:
                trades_parsed = parse_daily_plan_excel(uploaded_xl)
                if trades_parsed:
                    existing = get_trades()
                    existing_ids = {str(t.get("trade_no","") or ""): t for t in existing if t.get("trade_no")}
                    add_list = []; upd_list = []
                    for t in trades_parsed:
                        tid = str(t.get("trade_no","") or "")
                        if tid and tid in existing_ids:
                            upd_list.append((existing_ids[tid]["id"], t))
                        else:
                            add_list.append(t)
                    st.info(f"Found {len(trades_parsed)} trades — {len(add_list)} new, {len(upd_list)} updates")
                    if st.button(f"⬆️ Import All ({len(trades_parsed)})", key="imp_xl_all", type="primary"):
                        success = 0
                        for t in add_list:
                            try: add_trade(t); success += 1
                            except: pass
                        for tid, t in upd_list:
                            try: update_trade(tid, t); success += 1
                            except: pass
                        st.success(f"✅ {success} trades imported!")
                else:
                    st.warning("No trades found")
            except Exception as e:
                st.error(f"❌ {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SEASONAL
    # ═══════════════════════════════════════════════════════════════════════
    with tab_seasonal:
        st.markdown("### 🌱 Seasonal — Earnings Watchlist")
        st.caption("Upload upcoming earnings watchlist — stocks reporting results in the next 1-2 weeks")
        st.info("📌 Download from NSE Event Calendar → Filter by Financial Results → Upload here")

        earn_up = st.file_uploader("Choose Earnings CSV", type="csv", key="imp_earn_csv")
        if earn_up is not None:
            try:
                earn_rows = list(csv.DictReader(io.StringIO(earn_up.read().decode("utf-8"))))
                st.write(f"Columns: `{', '.join(earn_rows[0].keys() if earn_rows else [])}`")
                st.success(f"✅ {len(earn_rows)} earnings events read — Earnings Watchlist feature coming soon")
            except Exception as e:
                st.error(f"❌ {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SITUATIONAL
    # ═══════════════════════════════════════════════════════════════════════
    with tab_sit:
        st.markdown("### ⚡ Situational — Parabolic Longs")
        st.caption("Stocks in parabolic moves — use when market is in strong bull phase")
        st.info("📌 Parabolic Longs scan coming soon — will identify stocks up 3%+ for 3+ consecutive days with expanding volume")

        st.markdown("#### Manual Parabolic Watchlist")
        par_tickers = st.text_area("Enter tickers (one per line or comma separated)",
            placeholder="RELIANCE\nHDFCBANK\nICICIBANK",
            key="par_tickers", height=150)
        if st.button("💾 Save Parabolic Watchlist", key="par_save"):
            tickers = [t.strip() for t in par_tickers.replace(",","\n").split("\n") if t.strip()]
            st.session_state["parabolic_watchlist"] = tickers
            st.success(f"✅ {len(tickers)} stocks saved to Parabolic watchlist")
            st.write(tickers)

    # ═══════════════════════════════════════════════════════════════════════
    # EXCEL IMPORT
    # ═══════════════════════════════════════════════════════════════════════
    with tab_excel:
        st.markdown("### 📊 Excel Trade Import")
        st.caption("Full Excel import with preview and selective import options")
        from pages.import_excel import render as _xl_render
        _xl_render()
