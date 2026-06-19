# -*- coding: utf-8 -*-
"""
Excel Import page — upload Daily Plan format .xlsx and bulk-import to Supabase/SQLite.
Expected columns (in order):
Status | No | Entry Date | Side | Qty | Ticker | Strategy | Entry Price | Stop Loss |
Take Profit | Commission | TSL | Live Price | Change% | Exit Date | Qty | Exit Price |
Commission | Risk Status
"""
import streamlit as st
import pandas as pd
import os
from datetime import datetime, date

from theme import *
from data.db import add_trade, get_trades

G="#10B981"; R="#EF4444"; B="#3B82F6"; MUTED="#6B7280"; BORDER="#E5E7EB"

# Map Excel column names -> DB field names
COL_MAP = {
    "Status": "status",
    "No": "trade_no",
    "Entry Date": "entry_date",
    "Side": "side",
    "Qty": "qty",                 # first Qty = entry qty
    "Ticker": "ticker",
    "Strategy": "strategy",
    "Entry Price": "entry_price",
    "Stop Loss": "stop_loss",
    "Take Profit": "take_profit",
    "Commission": "commission_entry",   # first Commission = entry commission
    "TSL": "tsl",
    "Live Price": "live_price",
    "Change%": "change_pct",
    "Exit Date": "exit_date",
    "Exit Price": "exit_price",
    "Risk Status": "risk_status",
}

def _safe_float(v):
    try:
        if pd.isna(v) or v == "" or v is None: return None
        return float(v)
    except: return None

def _safe_date(v):
    if pd.isna(v) or v == "" or v is None: return None
    try:
        if isinstance(v, (datetime, date)):
            return v.strftime("%Y-%m-%d")
        return pd.to_datetime(v).strftime("%Y-%m-%d")
    except:
        return None

def _safe_str(v):
    if pd.isna(v) or v is None: return ""
    return str(v).strip()

def parse_daily_plan_excel(file):
    """Read the Daily Plan sheet and return list of trade dicts."""
    df = pd.read_excel(file, sheet_name="DailyPlan", header=25)
    df.columns = [str(c).strip() for c in df.columns]

    trades = []
    # Handle duplicate column names (Qty appears twice, Commission twice)
    cols = list(df.columns)

    # Find positional indices for duplicated columns
    qty_idxs = [i for i,c in enumerate(cols) if c=="Qty"]
    comm_idxs = [i for i,c in enumerate(cols) if c=="Commission"]

    for _, row in df.iterrows():
        ticker = _safe_str(row.get("Ticker",""))
        if not ticker:
            continue  # skip blank rows

        entry_qty = _safe_float(row.iloc[qty_idxs[0]]) if qty_idxs else None
        exit_qty  = _safe_float(row.iloc[qty_idxs[1]]) if len(qty_idxs)>1 else None
        entry_comm = _safe_float(row.iloc[comm_idxs[0]]) if comm_idxs else None
        exit_comm  = _safe_float(row.iloc[comm_idxs[1]]) if len(comm_idxs)>1 else None

        status_raw = _safe_str(row.get("Status","")).upper()
        exit_price = _safe_float(row.get("Exit Price"))
        exit_date  = _safe_date(row.get("Exit Date"))
        status = "CLOSED" if (exit_price and exit_date) else ("OPEN" if status_raw in ("","OPEN") else status_raw)
        if status not in ("OPEN","CLOSED"):
            status = "CLOSED" if exit_price else "OPEN"

        entry_price = _safe_float(row.get("Entry Price"))
        pnl = None
        r_mult = None
        if status=="CLOSED" and entry_price and exit_price and entry_qty:
            side = _safe_str(row.get("Side","")).upper()
            if side in ("BUY","LONG"):
                pnl = (exit_price - entry_price) * entry_qty
            else:
                pnl = (entry_price - exit_price) * entry_qty
            sl = _safe_float(row.get("Stop Loss"))
            if sl and entry_price:
                risk = abs(entry_price - sl) * entry_qty
                if risk: r_mult = pnl / risk

        trade = {
            "status": status,
            "trade_no": _safe_str(row.get("No","")),
            "entry_date": _safe_date(row.get("Entry Date")),
            "side": _safe_str(row.get("Side","")),
            "qty": entry_qty,
            "ticker": ticker,
            "strategy": _safe_str(row.get("Strategy","")),
            "entry_price": entry_price,
            "stop_loss": _safe_float(row.get("Stop Loss")),
            "take_profit": _safe_float(row.get("Take Profit")),
            "commission_entry": entry_comm,
            "tsl": _safe_float(row.get("TSL")),
            "live_price": _safe_float(row.get("Live Price")),
            "change_pct": _safe_float(row.get("Change%")),
            "exit_date": exit_date,
            "exit_qty": exit_qty,
            "exit_price": exit_price,
            "commission_exit": exit_comm,
            "risk_status": _safe_str(row.get("Risk Status","")),
        }
        if pnl is not None: trade["pnl"] = round(pnl, 2)
        if r_mult is not None: trade["r_multiple"] = round(r_mult, 3)

        # Remove None values (Supabase doesn't like them for some col types)
        trade = {k:v for k,v in trade.items() if v not in (None, "", "nan")}
        trades.append(trade)

    return trades

def render():
    st.markdown("## ⬆️ Import Trades from Excel")
    st.markdown(f'<p style="color:{MUTED};margin-top:-8px;margin-bottom:18px;font-size:12px">Upload your Daily Plan .xlsx file to bulk-import trades</p>', unsafe_allow_html=True)

    with st.expander("📋 Expected column format", expanded=False):
        st.code("""Status | No | Entry Date | Side | Qty | Ticker | Strategy |
Entry Price | Stop Loss | Take Profit | Commission | TSL |
Live Price | Change% | Exit Date | Qty | Exit Price |
Commission | Risk Status""", language=None)

    uploaded = st.file_uploader("Choose your Daily Plan Excel file", type=["xlsx","xls"], key="import_excel_upload")

    if uploaded:
        try:
            with st.spinner("Parsing Excel file..."):
                trades = parse_daily_plan_excel(uploaded)
            st.success(f"✅ Parsed {len(trades)} trades from the sheet.")

            if trades:
                # Preview
                preview_df = pd.DataFrame(trades)
                show_cols = [c for c in ["entry_date","ticker","strategy","side","qty","entry_price","exit_price","status","pnl"] if c in preview_df.columns]
                st.dataframe(preview_df[show_cols].head(20), use_container_width=True, hide_index=True)

                if len(trades) > 20:
                    st.caption(f"Showing first 20 of {len(trades)} trades")

                st.markdown("---")

                # Check for duplicates against existing trades
                existing = get_trades()
                existing_keys = {(t.get("ticker"), str(t.get("entry_date"))[:10], t.get("trade_no")) for t in existing}

                new_trades = []
                dup_trades = []
                for t in trades:
                    key = (t.get("ticker"), str(t.get("entry_date"))[:10], t.get("trade_no"))
                    if key in existing_keys:
                        dup_trades.append(t)
                    else:
                        new_trades.append(t)

                c1,c2,c3 = st.columns(3)
                c1.metric("Total Parsed", len(trades))
                c2.metric("New", len(new_trades))
                c3.metric("Duplicates (skip)", len(dup_trades))

                skip_dups = st.checkbox("Skip duplicates (matched by Ticker + Entry Date + Trade No)", value=True)
                to_import = new_trades if skip_dups else trades

                if st.button(f"⬆️ Import {len(to_import)} Trades", type="primary", use_container_width=True):
                    prog = st.progress(0, text="Importing...")
                    success = 0
                    errors = []
                    for i, t in enumerate(to_import):
                        try:
                            add_trade(t)
                            success += 1
                        except Exception as e:
                            errors.append(f"{t.get('ticker','?')}: {e}")
                        prog.progress((i+1)/len(to_import), text=f"Importing {i+1}/{len(to_import)}...")
                    prog.empty()

                    if success:
                        st.success(f"✅ Imported {success} trades successfully!")
                    if errors:
                        with st.expander(f"⚠️ {len(errors)} errors"):
                            for e in errors[:20]:
                                st.text(e)
                    st.balloons()
            else:
                st.warning("No valid trade rows found. Make sure Ticker column is populated.")
        except Exception as e:
            st.error(f"Error parsing file: {e}")
            import traceback
            st.code(traceback.format_exc())
