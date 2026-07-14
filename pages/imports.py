"""
Imports page — centralized hub for all data uploads.
Tabs: Daily (Excel trades) | Weekly (Universe CSV) | Monthly (MTF List)
"""
import streamlit as st
import os, csv, io
from theme import *
from data.db import _sb, _use_supabase

def render():
    st.markdown("## ⬆️ Imports")
    st.markdown(f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:18px;font-size:12px">Centralized data import hub — Daily trades · Weekly universe · Monthly MTF list</p>', unsafe_allow_html=True)

    tab_daily, tab_weekly, tab_monthly = st.tabs([
        "📅 Daily — Trade Excel",
        "📆 Weekly — Universe CSV",
        "🏦 Monthly — MTF List"
    ])

    # ── DAILY: Excel Trade Import ─────────────────────────────────────────────
    with tab_daily:
        st.markdown("### 📅 Daily Trade Import")
        st.caption("Upload your Daily Plan .xlsx to bulk-import trades from your Excel journal")
        from pages.import_excel import render as _render_excel
        _render_excel()

    # ── WEEKLY: Universe CSV ──────────────────────────────────────────────────
    with tab_weekly:
        st.markdown("### 📆 Weekly Universe Upload")
        st.caption("Upload Chirag's universe CSV weekly to keep your screener universe updated")
        st.markdown(f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px;margin-bottom:12px;font-size:11px;color:{TEXT_SUBTLE}">Expected columns: <b>Stock Name, RS Rating, Basic Industry, % from 52W High, Returns since Earnings(%)</b></div>', unsafe_allow_html=True)

        uploaded_u = st.file_uploader("Choose Universe CSV", type="csv", key="imp_universe_csv")
        if uploaded_u is not None:
            try:
                csv_text = uploaded_u.read().decode("utf-8")
                rows = list(csv.DictReader(io.StringIO(csv_text)))
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
                    st.success(f"✅ File read: {len(records)} tickers")
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
                    prog.progress(min((i+50)/len(records),1.0), text=f"Uploading {min(i+50,len(records))}/{len(records)}...")
                prog.empty()
                st.success(f"✅ {success} tickers uploaded to universe!")
                st.session_state.pop("_imp_universe_records", None)
                st.cache_data.clear()

        # Last upload info
        try:
            count = _sb().table("market_universe").select("ticker", count="exact").execute().count
            st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE};margin-top:12px">Current universe: {count} tickers</p>', unsafe_allow_html=True)
        except: pass

    # ── MONTHLY: MTF List ─────────────────────────────────────────────────────
    with tab_monthly:
        st.markdown("### 🏦 Monthly MTF List Upload")
        st.caption("Download from Zerodha → zerodha.com/margin-calculator/MTF → Upload here")
        st.markdown(f'<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:12px 14px;margin-bottom:12px;font-size:11px;color:{TEXT_SUBTLE}">Zerodha CSV columns: <b>isin, tradingsymbol, category, margin, leverage</b><br>Map columns below after upload.</div>', unsafe_allow_html=True)

        mtf_up = st.file_uploader("Choose Zerodha MTF CSV", type="csv", key="imp_mtf_csv")
        if mtf_up is not None:
            try:
                mtf_text = mtf_up.read().decode("utf-8")
                mtf_rows = list(csv.DictReader(io.StringIO(mtf_text)))
                st.session_state["_imp_mtf_rows"] = mtf_rows
                st.success(f"✅ File read: {len(mtf_rows)} rows")
                st.write(f"Columns found: `{', '.join(mtf_rows[0].keys() if mtf_rows else [])}`")
            except Exception as e:
                st.error(f"❌ {e}")

        if st.session_state.get("_imp_mtf_rows"):
            mtf_rows = st.session_state["_imp_mtf_rows"]
            cols_m = list(mtf_rows[0].keys())
            mc1, mc2, mc3 = st.columns(3)
            sym_c = mc1.selectbox("Ticker column", cols_m,
                index=cols_m.index("tradingsymbol") if "tradingsymbol" in cols_m else 0,
                key="imp_mtf_sym")
            mar_c = mc2.selectbox("Margin% column", ["None"]+cols_m,
                index=cols_m.index("margin")+1 if "margin" in cols_m else 0,
                key="imp_mtf_mar")
            lev_c = mc3.selectbox("Leverage column", ["None"]+cols_m,
                index=cols_m.index("leverage")+1 if "leverage" in cols_m else 0,
                key="imp_mtf_lev")

            if st.button("⬆️ Upload MTF List", key="imp_mtf_btn", type="primary"):
                sb = _sb()
                # Clear existing
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
                    chunk = recs[i:i+50]
                    try:
                        sb.table("mtf_margins").upsert(chunk, on_conflict="ticker").execute()
                        success += len(chunk)
                    except Exception as e:
                        st.error(f"❌ {e}"); break
                    prog.progress(min((i+50)/len(recs),1.0), text=f"Uploading {min(i+50,len(recs))}/{len(recs)}...")
                prog.empty()
                st.success(f"✅ {success} MTF stocks uploaded!")
                st.session_state.pop("_imp_mtf_rows", None)
                st.cache_data.clear()

        # Current MTF count
        try:
            mtf_count = _sb().table("mtf_margins").select("ticker", count="exact").execute().count
            updated = _sb().table("mtf_margins").select("updated_at").order("updated_at", desc=True).limit(1).execute().data
            last_update = str(updated[0]["updated_at"])[:10] if updated else "never"
            st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE};margin-top:12px">Current MTF list: {mtf_count} stocks · Last updated: {last_update}</p>', unsafe_allow_html=True)
        except: pass
