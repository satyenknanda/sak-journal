import streamlit as st
import pandas as pd
from datetime import datetime
from data.db import get_journal_trades, get_trades
from theme import *

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def safe_float(v):
    try: return float(v or 0)
    except: return 0.0

def fmt_pnl(v):
    return f"{'+' if v>=0 else ''}₹{abs(v):,.0f}" if v>=0 else f"-₹{abs(v):,.0f}"

def fmt_inr(v):
    return f"₹{v:,.2f}"

def pnl_color(v):
    return TEAL if v >= 0 else RED


def render():
    st.markdown("## Fund Management")
    st.caption("Track month-over-month capital flows, growth attribution, and own-funds vs MTF (leverage) exposure.")

    from data.db import get_capital_flows, save_capital_flow, save_ledger_balance, get_ledger_balance as _get_ledger_balance_raw
    from position_utils import get_cash_balance

    trades = get_journal_trades()
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    open_trades = [t for t in trades if t.get("status") == "OPEN"]

    # ── Cash Balance (available to deploy right now) ─────────────────────
    try:
        _cb = get_cash_balance()
    except Exception:
        _cb = {"total_capital": 0.0, "deployed_capital": 0.0, "available_cash": 0.0, "source": "estimate",
               "as_of": None, "same_day_settled": 0.0, "pending_settlement": 0.0,
               "new_positions_since_ledger": 0.0, "available_cash_projected": 0.0}
    _avail_col = TEAL if _cb["available_cash"] >= 0 else RED
    _pending = _cb.get("pending_settlement", 0.0)
    _new_positions = _cb.get("new_positions_since_ledger", 0.0)
    cb1, cb2, cb3 = st.columns(3)
    cb1.markdown(kpi_card("TOTAL TRADING CAPITAL", fmt_inr(_cb["total_capital"])), unsafe_allow_html=True)
    cb2.markdown(kpi_card("DEPLOYED IN OPEN POSITIONS", fmt_inr(_cb["deployed_capital"])), unsafe_allow_html=True)
    cb3.markdown(kpi_card("💰 CASH BALANCE (AVAILABLE)", fmt_inr(_cb["available_cash"]), color=_avail_col,
                           sub="Free to deploy into new trades"), unsafe_allow_html=True)
    if _cb.get("source") == "ledger":
        _same_day = _cb.get("same_day_settled", 0.0)
        st.caption(f"✅ Cash Balance is your actual broker ledger balance as of {_cb.get('as_of','')}"
                   f"{', plus MTF same-day square-offs' if abs(_same_day) > 0.01 else ''}"
                   f"{', minus new positions opened since then' if abs(_new_positions) > 0.01 else ''}. "
                   f"Re-upload a fresh ledger for the exact up-to-date figure.")
        if abs(_new_positions) > 0.01:
            st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:8px;
                padding:10px 14px;margin-top:8px;display:flex;justify-content:space-between;align-items:center">
                <span style="font-size:12px;color:{TEXT_MUTED}">🛒 New positions opened since ledger date (cash already spent)</span>
                <span style="font-size:14px;font-weight:700;color:{RED}">-{fmt_inr(_new_positions)}</span>
            </div>""", unsafe_allow_html=True)
        with st.expander("🔎 See every open position and why it is/isn't deducted"):
            try:
                _ldt_op = datetime.strptime(str(_cb.get('as_of',''))[:10], "%Y-%m-%d").date()
                _op_rows = ""
                for _t in open_trades:
                    _tk_op = _t.get("ticker","")
                    _entd_op = str(_t.get("entry_date","") or "")[:10]
                    _ft_op = str(_t.get("funding_type","CASH") or "CASH").upper()
                    _q_op = _t.get("qty"); _ep_op = _t.get("entry_price")
                    try:
                        _entdt_op = datetime.strptime(_entd_op, "%Y-%m-%d").date()
                        _parse_ok = True
                    except Exception:
                        _entdt_op = None
                        _parse_ok = False
                    if not _parse_ok:
                        _reason = f"⚠️ entry_date '{_entd_op or '(blank)'}' couldn't be parsed — not counted"
                        _amt_op = 0.0
                    elif _entdt_op <= _ldt_op:
                        _reason = f"Entry on/before ledger date ({_cb.get('as_of','')}) — already reflected in ledger"
                        _amt_op = 0.0
                    else:
                        _qf = float(_q_op or 0); _epf = float(_ep_op or 0)
                        if _ft_op == "MTF":
                            _mp_op = float(_t.get("mtf_margin_pct") or 50.0)
                            _amt_op = _qf * _epf * _mp_op / 100
                        else:
                            _amt_op = _qf * _epf
                        _reason = "✅ Deducted from Cash Balance" if _amt_op > 0 else "⚠️ qty or entry_price is 0/missing"
                    _op_rows += (f'<tr><td style="padding:5px 8px">{_tk_op}</td>'
                                 f'<td style="padding:5px 8px">{_entd_op or "(blank)"}</td>'
                                 f'<td style="padding:5px 8px">{_ft_op}</td>'
                                 f'<td style="padding:5px 8px">{_q_op}</td>'
                                 f'<td style="padding:5px 8px">{_ep_op}</td>'
                                 f'<td style="padding:5px 8px;text-align:right">{fmt_inr(_amt_op)}</td>'
                                 f'<td style="padding:5px 8px">{_reason}</td></tr>')
                if _op_rows:
                    st.markdown(f"""<table style="width:100%;border-collapse:collapse;font-size:12px">
                        <thead><tr style="color:{TEXT_SUBTLE}">
                            <th style="padding:5px 8px;text-align:left">SYMBOL</th>
                            <th style="padding:5px 8px;text-align:left">ENTRY DATE</th>
                            <th style="padding:5px 8px;text-align:left">FUNDING</th>
                            <th style="padding:5px 8px;text-align:left">QTY</th>
                            <th style="padding:5px 8px;text-align:left">ENTRY PRICE</th>
                            <th style="padding:5px 8px;text-align:right">AMOUNT</th>
                            <th style="padding:5px 8px;text-align:left">STATUS</th>
                        </tr></thead><tbody>{_op_rows}</tbody></table>""", unsafe_allow_html=True)
                else:
                    st.caption("No open positions found in the journal at all.")
            except Exception as _e_op:
                st.caption(f"Couldn't build breakdown: {_e_op}")
        if abs(_same_day) > 0.01:
            _sd_col = TEAL if _same_day >= 0 else RED
            st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:8px;
                padding:10px 14px;margin-top:8px;display:flex;justify-content:space-between;align-items:center">
                <span style="font-size:12px;color:{TEXT_MUTED}">⚡ MTF same-day square-offs (credited instantly, no T+1 lag)</span>
                <span style="font-size:14px;font-weight:700;color:{_sd_col}">{fmt_pnl(_same_day)}</span>
            </div>""", unsafe_allow_html=True)
        if abs(_pending) > 0.01:
            _pend_col = TEAL if _pending >= 0 else RED
            st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:8px;
                padding:10px 14px;margin-top:6px;display:flex;justify-content:space-between;align-items:center">
                <span style="font-size:12px;color:{TEXT_MUTED}">⏳ Pending (not yet reflected in ledger — awaiting settlement)</span>
                <span style="font-size:14px;font-weight:700;color:{_pend_col}">{fmt_pnl(_pending)}</span>
            </div>
            <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:8px;
                padding:10px 14px;margin-top:6px;display:flex;justify-content:space-between;align-items:center">
                <span style="font-size:12px;color:{TEXT_MUTED}">📅 If all pending trades were settled today</span>
                <span style="font-size:16px;font-weight:800;color:{TEAL if _cb['available_cash_projected']>=0 else RED}">
                    {fmt_inr(_cb['available_cash_projected'])}</span>
            </div>""", unsafe_allow_html=True)
        if abs(_same_day) > 0.01 or abs(_pending) > 0.01:
            with st.expander("🔎 See which trades feed these numbers"):
                try:
                    _ldt = datetime.strptime(str(_cb.get('as_of',''))[:10], "%Y-%m-%d").date()
                    _bd_rows = ""
                    for _t in closed:
                        _exd = str(_t.get("exit_date",""))[:10]
                        try:
                            _exdt = datetime.strptime(_exd, "%Y-%m-%d").date()
                        except Exception:
                            continue
                        if _exdt <= _ldt:
                            continue  # already reflected in the ledger's closing balance
                        _entd = str(_t.get("entry_date",""))[:10]
                        try:
                            _entdt = datetime.strptime(_entd, "%Y-%m-%d").date()
                        except Exception:
                            _entdt = None
                        _is_mtf_bd = str(_t.get("funding_type","CASH") or "CASH").upper() == "MTF"
                        _q = float(_t.get("qty") or 0); _ep = float(_t.get("entry_price") or 0)
                        _pn = float(_t.get("pnl") or 0)
                        if _is_mtf_bd:
                            _mp = float(_t.get("mtf_margin_pct") or 50.0)
                            _lc = _q*_ep*_mp/100
                        else:
                            _lc = _q*_ep
                        _amt = _lc + _pn
                        _bucket = "Same-day (MTF)" if (_is_mtf_bd and _entdt is not None and _entdt == _exdt) else "Pending"
                        _bd_rows += (f'<tr><td style="padding:5px 8px">{_t.get("ticker","")}</td>'
                                     f'<td style="padding:5px 8px">{_entd}</td>'
                                     f'<td style="padding:5px 8px">{_exd}</td>'
                                     f'<td style="padding:5px 8px">{_bucket}</td>'
                                     f'<td style="padding:5px 8px;text-align:right">{fmt_inr(_lc)}</td>'
                                     f'<td style="padding:5px 8px;text-align:right;color:{TEAL if _pn>=0 else RED}">{fmt_pnl(_pn)}</td>'
                                     f'<td style="padding:5px 8px;text-align:right;font-weight:700">{fmt_inr(_amt)}</td></tr>')
                    if _bd_rows:
                        st.markdown(f"""<table style="width:100%;border-collapse:collapse;font-size:12px">
                            <thead><tr style="color:{TEXT_SUBTLE}">
                                <th style="padding:5px 8px;text-align:left">SYMBOL</th>
                                <th style="padding:5px 8px;text-align:left">ENTRY</th>
                                <th style="padding:5px 8px;text-align:left">EXIT</th>
                                <th style="padding:5px 8px;text-align:left">BUCKET</th>
                                <th style="padding:5px 8px;text-align:right">CAPITAL BACK</th>
                                <th style="padding:5px 8px;text-align:right">P&L</th>
                                <th style="padding:5px 8px;text-align:right">TOTAL</th>
                            </tr></thead><tbody>{_bd_rows}</tbody></table>""", unsafe_allow_html=True)
                    else:
                        st.caption("No trades to show.")
                except Exception as _e:
                    st.caption(f"Couldn't build breakdown: {_e}")
    else:
        st.caption("⚠️ Cash Balance is an estimate (no broker ledger imported yet) — upload one below for the real figure.")

    with st.expander("📄 Upload Broker Ledger — get your real Cash Balance"):
        st.caption("Upload your broker's ledger/statement export — plain CSV or the Excel (.xlsx) download both "
                   "work. The Closing Balance row becomes your Cash Balance everywhere in the app, replacing the estimate.")
        ledger_file = st.file_uploader("Choose ledger file", type=["csv", "xlsx", "xls"], key="ledger_upload")
        if ledger_file is not None:
            try:
                _fname = (ledger_file.name or "").lower()
                if _fname.endswith((".xlsx", ".xls")):
                    _raw = pd.read_excel(ledger_file, header=None)
                else:
                    _raw = pd.read_csv(ledger_file, header=None)

                # Find the real header row — the one containing "Particulars"
                # (broker Excel exports have metadata rows like Client ID and
                # a date-range title above the actual table).
                _header_row_idx = None
                for _i in range(min(len(_raw), 30)):
                    _row_vals = [str(v).strip().lower() for v in _raw.iloc[_i].tolist()]
                    if "particulars" in _row_vals:
                        _header_row_idx = _i
                        break
                if _header_row_idx is None:
                    _header_row_idx = 0  # assume already a clean header (e.g. the plain CSV format)

                _ldf = _raw.iloc[_header_row_idx + 1:].copy()
                _ldf.columns = [str(c).strip().lower().replace(" ", "_") for c in _raw.iloc[_header_row_idx]]
                _ldf = _ldf.dropna(how="all")
                _ldf = _ldf.loc[:, ~_ldf.columns.duplicated()]
                _ldf = _ldf[[c for c in _ldf.columns if c and c != "nan"]]

                _last_row = _ldf.iloc[-1]
                _closing_balance = float(_last_row["net_balance"])
                _dated = _ldf[_ldf["posting_date"].notna() & (_ldf["posting_date"].astype(str).str.strip() != "")
                              & (_ldf["posting_date"].astype(str).str.strip().str.lower() != "nan")]
                _as_of_raw = str(_dated.iloc[-1]["posting_date"]) if not _dated.empty else ""
                _as_of = _as_of_raw[:10] if _as_of_raw else ""
                lp1, lp2 = st.columns(2)
                lp1.metric("Closing Balance", fmt_inr(_closing_balance))
                lp2.metric("As of", _as_of or "—")
                if st.button("💾 Save as Cash Balance", key="save_ledger_btn", type="primary"):
                    save_ledger_balance(_closing_balance, _as_of)
                    _verify_bal, _verify_dt = _get_ledger_balance_raw()
                    if _verify_bal is not None and abs(_verify_bal - _closing_balance) < 0.01 and str(_verify_dt) == str(_as_of):
                        st.success(f"✅ Cash Balance updated to {fmt_inr(_closing_balance)} as of {_as_of} — verified saved.")
                        st.rerun()
                    else:
                        st.error(f"⚠️ Save may not have persisted correctly — wrote {fmt_inr(_closing_balance)} "
                                 f"as of {_as_of}, but reading it back shows "
                                 f"{fmt_inr(_verify_bal) if _verify_bal is not None else 'nothing'} as of {_verify_dt}. "
                                 f"This usually means a database permissions issue — check the app logs (Manage app → Logs) "
                                 f"for 'set_setting' or 'get_setting' error messages.")

                # ── Reconcile ledger totals against app's trades/capital_flows ──
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(section_label("🔍 Reconcile with Trades"), unsafe_allow_html=True)
                try:
                    _dated_all = _ldf[_ldf["posting_date"].notna() & (_ldf["posting_date"].astype(str).str.strip() != "")
                                       & (_ldf["posting_date"].astype(str).str.strip().str.lower() != "nan")].copy()
                    _dated_all["posting_date"] = pd.to_datetime(_dated_all["posting_date"])
                    _ledger_start = _dated_all["posting_date"].min().date()
                    _ledger_end = _dated_all["posting_date"].max().date()

                    _deposits_ledger = float(_dated_all[_dated_all["voucher_type"] == "Bank Receipts"]["credit"].sum())
                    _withdrawals_ledger = float(_dated_all[_dated_all["voucher_type"] == "Bank Payments"]["debit"].sum())
                    _mtf_interest_ledger = float(
                        _dated_all[_dated_all["particulars"].astype(str).str.contains("Interest for MTF", na=False)]["debit"].sum())
                    _settlements_ledger = int(
                        _dated_all["particulars"].astype(str).str.contains("Net settlement for Equity", na=False).sum())

                    st.caption(f"Ledger spans {_ledger_start} to {_ledger_end}. Comparing against your trades and "
                               f"capital flows in that same window.")

                    # App-side totals scoped to the ledger's own date range
                    import calendar as _cal_rc
                    _years_span = sorted({_ledger_start.year, _ledger_end.year})
                    _deposits_app = _withdrawn_app = 0.0
                    for _y in _years_span:
                        _flows_y = get_capital_flows(_y)
                        for _m in range(1, 13):
                            _f = _flows_y.get(_m, {})
                            _month_start = datetime(_y, _m, 1).date()
                            _month_end = datetime(_y, _m, _cal_rc.monthrange(_y, _m)[1]).date()
                            if _month_start <= _ledger_end and _month_end >= _ledger_start:
                                _deposits_app += float(_f.get("added", 0) or 0)
                                _withdrawn_app += float(_f.get("withdrawn", 0) or 0)

                    _mtf_interest_app = 0.0
                    ZERODHA_MTF_DAILY_RATE_RC = 0.0004
                    for _t in trades:
                        if str(_t.get("funding_type", "CASH") or "CASH").upper() != "MTF":
                            continue
                        _qty = float(_t.get("qty") or 0); _price = float(_t.get("entry_price") or 0)
                        _margin_pct = float(_t.get("mtf_margin_pct") or 50.0)
                        _borrowed = _qty * _price * (1 - _margin_pct / 100)
                        if _borrowed <= 0:
                            continue
                        try:
                            _entry_dt = datetime.strptime(str(_t.get("entry_date", ""))[:10], "%Y-%m-%d").date()
                        except Exception:
                            continue
                        if _t.get("status") == "CLOSED" and _t.get("exit_date"):
                            try:
                                _exit_dt = datetime.strptime(str(_t.get("exit_date", ""))[:10], "%Y-%m-%d").date()
                            except Exception:
                                _exit_dt = _ledger_end
                        else:
                            _exit_dt = _ledger_end
                        from datetime import timedelta as _td_rc
                        _start = max(_entry_dt + _td_rc(days=1), _ledger_start)
                        _end = min(_exit_dt, _ledger_end)
                        if _start > _end:
                            continue
                        _days = (_end - _start).days + 1
                        _mtf_interest_app += _borrowed * ZERODHA_MTF_DAILY_RATE_RC * _days

                    _closed_in_range = [t for t in closed if t.get("exit_date") and
                                         _ledger_start <= datetime.strptime(str(t.get("exit_date"))[:10], "%Y-%m-%d").date() <= _ledger_end]

                    def _diff_row(label, ledger_val, app_val, tol=100.0):
                        diff = ledger_val - app_val
                        ok = abs(diff) <= tol
                        icon = "✅" if ok else "⚠️"
                        return f'<tr><td style="padding:6px 10px">{label}</td>' \
                               f'<td style="padding:6px 10px;text-align:right">{fmt_inr(ledger_val)}</td>' \
                               f'<td style="padding:6px 10px;text-align:right">{fmt_inr(app_val)}</td>' \
                               f'<td style="padding:6px 10px;text-align:right;color:{TEAL if ok else RED}">{icon} {fmt_inr(diff)}</td></tr>'

                    _rows_html = ""
                    _rows_html += _diff_row("Deposits", _deposits_ledger, _deposits_app)
                    _rows_html += _diff_row("Withdrawals", _withdrawals_ledger, _withdrawn_app)
                    _rows_html += _diff_row("MTF Interest", _mtf_interest_ledger, _mtf_interest_app)

                    st.markdown(f"""<table style="width:100%;border-collapse:collapse">
                        <thead><tr>
                            <th style="padding:6px 10px;text-align:left;font-size:11px;color:{TEXT_SUBTLE}">METRIC</th>
                            <th style="padding:6px 10px;text-align:right;font-size:11px">LEDGER</th>
                            <th style="padding:6px 10px;text-align:right;font-size:11px">APP</th>
                            <th style="padding:6px 10px;text-align:right;font-size:11px">DIFFERENCE</th>
                        </tr></thead><tbody>{_rows_html}</tbody></table>""", unsafe_allow_html=True)

                    st.caption(f"📋 Ledger shows {_settlements_ledger} settlement entries · App shows {len(_closed_in_range)} "
                               f"closed trades exiting in this window. Settlements often bundle multiple trades and lag "
                               f"T+1, so these two counts won't match exactly — a big gap is what's worth investigating.")

                    # ── Match individual MTF buy/sell to ledger pledge/unpledge ──
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown(section_label("🔗 Match Buy/Sell (MTF) to Ledger"), unsafe_allow_html=True)
                    st.caption("MTF pledge/unpledge lines in the ledger name the ticker directly — this matches each "
                               "MTF trade's entry date to its pledge, and exit date to its unpledge, one ticker at a time.")

                    import re as _re_rc
                    def _extract_ticker_rc(text, prefix):
                        m = _re_rc.search(prefix + r"\s+(\S+)", str(text))
                        return m.group(1).upper() if m else None

                    _pledge_df = _dated_all[_dated_all["particulars"].astype(str).str.contains("MTF pledge charges for", na=False)].copy()
                    _unpledge_df = _dated_all[_dated_all["particulars"].astype(str).str.contains("MTF unpledge charges for", na=False)].copy()
                    _pledge_df["ticker"] = _pledge_df["particulars"].apply(lambda x: _extract_ticker_rc(x, "MTF pledge charges for"))
                    _unpledge_df["ticker"] = _unpledge_df["particulars"].apply(lambda x: _extract_ticker_rc(x, "MTF unpledge charges for"))

                    _pledge_by_ticker = {}
                    for _tk, _grp in _pledge_df.groupby("ticker"):
                        _pledge_by_ticker[_tk] = sorted(_grp["posting_date"].dt.date.tolist())
                    _unpledge_by_ticker = {}
                    for _tk, _grp in _unpledge_df.groupby("ticker"):
                        _unpledge_by_ticker[_tk] = sorted(_grp["posting_date"].dt.date.tolist())

                    _mtf_trades = [t for t in trades if str(t.get("funding_type","CASH") or "CASH").upper() == "MTF"]
                    _mtf_by_ticker = {}
                    for _t in _mtf_trades:
                        _tk = str(_t.get("ticker","")).upper().strip()
                        if not _tk:
                            continue
                        _mtf_by_ticker.setdefault(_tk, []).append(_t)
                    for _tk in _mtf_by_ticker:
                        _mtf_by_ticker[_tk].sort(key=lambda t: str(t.get("entry_date","")))

                    _all_tickers = sorted(set(_mtf_by_ticker.keys()) | set(_pledge_by_ticker.keys()) | set(_unpledge_by_ticker.keys()))
                    _match_rows = ""
                    _mismatch_count = 0
                    for _tk in _all_tickers:
                        _jt = _mtf_by_ticker.get(_tk, [])
                        _pl = _pledge_by_ticker.get(_tk, [])
                        _up = _unpledge_by_ticker.get(_tk, [])
                        if not _jt and (_pl or _up):
                            _match_rows += (f'<tr><td style="padding:5px 8px">{_tk}</td>'
                                f'<td style="padding:5px 8px" colspan="5">⚠️ Ledger shows MTF pledge/unpledge activity '
                                f'but no matching MTF trade found in the journal — possible missing trade</td></tr>')
                            _mismatch_count += 1
                            continue
                        if _jt and not _pl:
                            _match_rows += (f'<tr><td style="padding:5px 8px">{_tk}</td>'
                                f'<td style="padding:5px 8px" colspan="5">⚠️ {len(_jt)} MTF trade(s) in journal but no '
                                f'pledge charge found in ledger — check funding type or ticker spelling</td></tr>')
                            _mismatch_count += 1
                            continue
                        _n = max(len(_jt), len(_pl))
                        for _i in range(_n):
                            _trade = _jt[_i] if _i < len(_jt) else None
                            _pledge_d = _pl[_i] if _i < len(_pl) else None
                            _unpledge_d = _up[_i] if _i < len(_up) else None
                            _j_entry = str(_trade.get("entry_date",""))[:10] if _trade else "—"
                            _is_closed = bool(_trade and _trade.get("status")=="CLOSED")
                            _j_exit = str(_trade.get("exit_date",""))[:10] if _is_closed else ("open" if _trade else "—")
                            try:
                                _j_entry_dt = datetime.strptime(_j_entry, "%Y-%m-%d").date() if _trade else None
                            except Exception:
                                _j_entry_dt = None
                            try:
                                _j_exit_dt = datetime.strptime(_j_exit, "%Y-%m-%d").date() if _is_closed else None
                            except Exception:
                                _j_exit_dt = None

                            _entry_ok = (_trade is not None) and (_pledge_d is not None) and (_j_entry_dt == _pledge_d)
                            if _trade is not None and not _is_closed:
                                _exit_ok = (_unpledge_d is None)  # still open — correctly no unpledge yet
                            elif _trade is not None:
                                _exit_ok = (_unpledge_d is not None) and (_j_exit_dt == _unpledge_d)
                            else:
                                _exit_ok = False  # ledger event with no journal counterpart at all
                            if not _entry_ok or not _exit_ok:
                                _mismatch_count += 1
                            _icon_e = "✅" if _entry_ok else "⚠️"
                            _icon_x = "✅" if _exit_ok else "⚠️"
                            _match_rows += (f'<tr><td style="padding:5px 8px">{_tk}</td>'
                                f'<td style="padding:5px 8px">{_j_entry}</td>'
                                f'<td style="padding:5px 8px">{_pledge_d if _pledge_d else "—"}</td>'
                                f'<td style="padding:5px 8px;color:{TEAL if _entry_ok else RED}">{_icon_e}</td>'
                                f'<td style="padding:5px 8px">{_j_exit}</td>'
                                f'<td style="padding:5px 8px">{_unpledge_d if _unpledge_d else "—"}</td>'
                                f'<td style="padding:5px 8px;color:{TEAL if _exit_ok else RED}">{_icon_x}</td></tr>')

                    if _match_rows:
                        st.markdown(f"""<table style="width:100%;border-collapse:collapse;font-size:12px">
                            <thead><tr style="color:{TEXT_SUBTLE}">
                                <th style="padding:5px 8px;text-align:left">TICKER</th>
                                <th style="padding:5px 8px;text-align:left">JOURNAL ENTRY</th>
                                <th style="padding:5px 8px;text-align:left">LEDGER PLEDGE</th>
                                <th style="padding:5px 8px;text-align:left"></th>
                                <th style="padding:5px 8px;text-align:left">JOURNAL EXIT</th>
                                <th style="padding:5px 8px;text-align:left">LEDGER UNPLEDGE</th>
                                <th style="padding:5px 8px;text-align:left"></th>
                            </tr></thead><tbody>{_match_rows}</tbody></table>""", unsafe_allow_html=True)
                        if _mismatch_count:
                            st.warning(f"⚠️ {_mismatch_count} ticker(s) show a date mismatch or missing counterpart — "
                                       f"worth checking these trades' entry/exit dates in Trade Detail.")
                        else:
                            st.success("✅ All MTF trades match their ledger pledge/unpledge dates.")
                    else:
                        st.caption("No MTF trades or ledger MTF activity to match in this window.")
                except Exception as _e:
                    st.warning(f"Couldn't run reconciliation: {_e}")
                    st.rerun()
            except Exception as e:
                st.error(f"Couldn't parse this file as a ledger export: {e}")

    st.markdown("<br>", unsafe_allow_html=True)

    years = sorted({int(str(t.get("exit_date",""))[:4]) for t in closed if str(t.get("exit_date",""))[:4].isdigit()}, reverse=True)
    if not years:
        years = [datetime.now().year]
    year_sel = st.selectbox("Year", years, key="fund_year")

    flows = get_capital_flows(year_sel)  # {month_num: {"added": x, "withdrawn": y, "mtf_interest": z}}

    # ── Auto-calculated MTF interest (Zerodha formula: 0.04%/day on borrowed
    # amount, T+1 to exit/today) — computed once here, used by both the
    # Monthly Flows table below AND the MTF Analytics section further down. ──
    from datetime import date as _date, timedelta as _timedelta
    ZERODHA_MTF_DAILY_RATE = 0.0004  # 0.04% per day = ₹40 per lakh, per Zerodha's published MTF rate

    def calc_mtf_interest_for_trade(t, year_filter=None):
        """Per-trade MTF interest, split by month. See ZERODHA_MTF_DAILY_RATE above."""
        if str(t.get("funding_type", "CASH") or "CASH").upper() != "MTF":
            return {}
        qty = safe_float(t.get("qty"))
        price = safe_float(t.get("entry_price"))
        margin_pct = safe_float(t.get("mtf_margin_pct")) or 50.0
        position_value = qty * price
        borrowed = position_value * (1 - margin_pct / 100)
        if borrowed <= 0:
            return {}
        try:
            entry_dt = datetime.strptime(str(t.get("entry_date", ""))[:10], "%Y-%m-%d").date()
        except Exception:
            return {}
        if t.get("status") == "CLOSED" and t.get("exit_date"):
            try:
                exit_dt = datetime.strptime(str(t.get("exit_date", ""))[:10], "%Y-%m-%d").date()
            except Exception:
                exit_dt = _date.today()
        else:
            exit_dt = _date.today()
        start = entry_dt + _timedelta(days=1)
        if start > exit_dt:
            return {}
        daily_interest = borrowed * ZERODHA_MTF_DAILY_RATE
        by_month = {}
        cur = start
        while cur <= exit_dt:
            if year_filter is None or cur.year == year_filter:
                by_month[cur.month] = by_month.get(cur.month, 0.0) + daily_interest
            cur += _timedelta(days=1)
        return by_month

    auto_interest_by_month = {m: 0.0 for m in range(1, 13)}
    for t in trades:
        per_trade = calc_mtf_interest_for_trade(t, year_filter=year_sel)
        for m, amt in per_trade.items():
            auto_interest_by_month[m] += amt
    total_mtf_interest_auto = sum(auto_interest_by_month.values())


    # ── Own Capital vs MTF Exposure (current open positions) ────────────
    st.markdown(section_label("Current Exposure — Own Capital vs MTF"), unsafe_allow_html=True)

    cash_value = 0.0
    mtf_own_value = 0.0
    mtf_borrowed_value = 0.0
    cash_count = mtf_count = 0
    for t in open_trades:
        qty = safe_float(t.get("qty"))
        price = safe_float(t.get("entry_price")) or safe_float(t.get("live_price"))
        value = qty * price
        funding = str(t.get("funding_type", "CASH") or "CASH").upper()
        if funding == "MTF":
            margin_pct = safe_float(t.get("mtf_margin_pct")) or 50.0
            mtf_own_value += value * margin_pct / 100
            mtf_borrowed_value += value * (1 - margin_pct / 100)
            mtf_count += 1
        else:
            cash_value += value
            cash_count += 1

    mtf_value = mtf_own_value + mtf_borrowed_value  # total MTF position value
    own_capital_total = cash_value + mtf_own_value   # your actual money across both
    total_exposure = cash_value + mtf_value
    leverage_pct = (mtf_borrowed_value / total_exposure * 100) if total_exposure > 0 else 0

    e1, e2, e3, e4 = st.columns(4)
    e1.markdown(kpi_card("YOUR CAPITAL DEPLOYED", fmt_inr(own_capital_total),
                          sub=f"Cash {fmt_inr(cash_value)} + MTF margin {fmt_inr(mtf_own_value)}"), unsafe_allow_html=True)
    e2.markdown(kpi_card("ZERODHA-BORROWED (MTF)", fmt_inr(mtf_borrowed_value), color=AMBER,
                          sub=f"{mtf_count} MTF position(s)"), unsafe_allow_html=True)
    e3.markdown(kpi_card("TOTAL EXPOSURE", fmt_inr(total_exposure), sub=f"{cash_count+mtf_count} open positions"), unsafe_allow_html=True)
    e4.markdown(kpi_card("LEVERAGE %", f"{leverage_pct:.1f}%",
                          color=(RED if leverage_pct > 30 else AMBER if leverage_pct > 15 else TEAL),
                          sub="borrowed ÷ total exposure"), unsafe_allow_html=True)

    if leverage_pct > 0:
        st.markdown(f"""<div style="background:{AMBER_BG};border:1px solid {AMBER_BORDER};border-radius:8px;
            padding:10px 14px;font-size:12px;color:{TEXT_BODY};margin:10px 0">
            ⚡ {leverage_pct:.1f}% of your total exposure is Zerodha-funded (borrowed) via MTF — based on the margin %
            you entered per trade. This amplifies both gains and losses, and accrues daily interest — tracked below as
            a monthly expense against P&L. Margin % per trade isn't pulled live from Zerodha; verify against Kite's
            order screen at entry time, since rates vary by stock and can change.
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── MTF Margin Lookup (collapsible) ──────────────────────────────────
    from data.db import get_mtf_margins, save_mtf_margin, delete_mtf_margin

    with st.expander("⚡ MTF Margin Lookup — paste Zerodha margin % per ticker"):
        st.caption("Paste margin % from Zerodha's MTF page (zerodha.com/mtf-approved-securities) once per ticker. "
                   "Edit Trade will auto-fill from here instead of asking you to look it up every time. "
                   "Still editable per trade if Zerodha revises a stock's margin requirement.")

        margins = get_mtf_margins()

        if margins:
            mdf = pd.DataFrame([{
                "Symbol": m["ticker"],
                "Margin %": float(m.get("margin_pct") or 0),
                "Leverage": f"{float(m.get('leverage') or 0):.2f}x" if m.get("leverage") else "—",
                "Updated": str(m.get("updated_at",""))[:10],
            } for m in margins])
            st.dataframe(mdf, use_container_width=True, hide_index=True)
        else:
            st.caption("No tickers added yet.")

        st.markdown("<br>", unsafe_allow_html=True)
        if margins:
            ticker_opts = [m["ticker"] for m in margins]
            sel_mtf = st.selectbox("Search & select ticker", ["— Search —"] + ticker_opts,
                key="mtf_lookup_search", label_visibility="visible")
            if sel_mtf != "— Search —":
                _m = next((m for m in margins if m["ticker"] == sel_mtf), None)
                if _m:
                    mc1, mc2, mc3 = st.columns(3)
                    mc1.metric("Ticker", sel_mtf)
                    mc2.metric("Margin %", f"{float(_m.get('margin_pct') or 0):.2f}%")
                    mc3.metric("Leverage", f"{float(_m.get('leverage') or 0):.2f}x")
        else:
            st.info("No MTF list uploaded yet. Go to Imports → Weekly → MTF/MIS List to upload.")
        if margins:
            del_ticker = st.selectbox("Remove a ticker", ["—"] + [m["ticker"] for m in margins], key="mtf_lookup_del")
            if del_ticker != "—" and st.button(f"🗑️ Remove {del_ticker}", key="mtf_lookup_del_btn"):
                delete_mtf_margin(del_ticker)
                st.success(f"Removed {del_ticker}")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── monthly net P&L from journal, split by funding type ──────────────
    monthly_pnl = {m: 0.0 for m in range(1, 13)}
    monthly_pnl_cash = {m: 0.0 for m in range(1, 13)}
    monthly_pnl_mtf = {m: 0.0 for m in range(1, 13)}
    for t in closed:
        d = str(t.get("exit_date",""))[:10]
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            continue
        if dt.year == year_sel:
            p = safe_float(t.get("pnl"))
            monthly_pnl[dt.month] += p
            if str(t.get("funding_type","CASH") or "CASH").upper() == "MTF":
                monthly_pnl_mtf[dt.month] += p
            else:
                monthly_pnl_cash[dt.month] += p

    # ── Add / Withdraw Funds Form ─────────────────────────────────────────
    st.markdown(section_label("Add / Withdraw Funds"), unsafe_allow_html=True)
    fw1, fw2, fw3, fw4 = st.columns([1,1,1,1])
    with fw1:
        flow_type = st.radio("Type", ["➕ Add Funds", "➖ Withdraw Funds"], horizontal=True, key="flow_type")
    with fw2:
        flow_amount = st.number_input("Amount (₹)", min_value=0.0, step=10000.0, key="flow_amount", format="%.0f")
    with fw3:
        from datetime import date
        flow_date = st.date_input("Date", value=date.today(), key="flow_date")
        flow_month = flow_date.month
        flow_year = flow_date.year
    with fw4:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("💾 Save", key="flow_save_btn", type="primary", use_container_width=True):
            if flow_amount > 0:
                existing = get_capital_flows(flow_year).get(flow_month, {"added": 0, "withdrawn": 0})
                if "➕" in flow_type:
                    new_added = float(existing.get("added", 0)) + flow_amount
                    save_capital_flow(flow_year, flow_month, new_added, float(existing.get("withdrawn", 0)))
                else:
                    new_withdrawn = float(existing.get("withdrawn", 0)) + flow_amount
                    save_capital_flow(flow_year, flow_month, float(existing.get("added", 0)), new_withdrawn)
                st.success(f"✅ {'Added' if '➕' in flow_type else 'Withdrawn'} ₹{flow_amount:,.0f} for {flow_date.strftime('%B %Y')}")
                st.rerun()
            else:
                st.warning("Enter an amount greater than 0")

    # ── compute starting capital roll-forward ───────────────────────────
    # Auto-calculate opening capital = cash deployed in open trades - closed P&L
    try:
        from data.db import get_trades as _get_trades
        _all_trades = _get_trades()
        _open = [t for t in _all_trades if t.get("status") == "OPEN"]
        _closed = [t for t in _all_trades if t.get("status") == "CLOSED"]
        _cash = 0
        for _t in _open:
            _qty = float(_t.get("qty") or 0)
            _ep  = float(_t.get("entry_price") or 0)
            _pos = _qty * _ep
            if str(_t.get("funding_type","") or "").upper() == "MTF":
                _margin = float(_t.get("mtf_margin_pct") or 50) / 100
                _cash += _pos * _margin
            else:
                _cash += _pos
        _closed_pnl = sum(float(t.get("pnl") or 0) for t in _closed)
        _auto_capital = max(_cash - _closed_pnl, 0)
    except:
        _auto_capital = 0.0
    _saved_capital = safe_float(flows.get(0, {}).get("base_capital", 0.0))
    _default_capital = _saved_capital if _saved_capital > 0 else _auto_capital
    starting_capital = st.number_input(
        f"Starting capital (₹) — auto-calculated: ₹{_auto_capital:,.0f}",
        min_value=0.0, value=_default_capital,
        step=10000.0, key=f"base_cap_{year_sel}",
        help="One-time anchor — only needed once per year you start tracking. Leave 0 if unknown."
    )

    rows = []
    running_capital = starting_capital
    total_added = total_withdrawn = total_pnl = total_mtf_interest = 0.0

    for m in range(1, 13):
        f = flows.get(m, {"added": 0.0, "withdrawn": 0.0, "mtf_interest": 0.0})
        added = f.get("added", 0.0)
        withdrawn = f.get("withdrawn", 0.0)
        mtf_interest = auto_interest_by_month.get(m, 0.0)  # auto-calculated, not manual
        pnl = monthly_pnl.get(m, 0.0)
        net_pnl = pnl - mtf_interest
        start_cap = running_capital
        running_capital = running_capital + added - withdrawn + net_pnl
        total_added += added
        total_withdrawn += withdrawn
        total_pnl += pnl
        total_mtf_interest += mtf_interest
        rows.append({
            "month": MONTHS[m-1], "month_num": m,
            "added": added, "withdrawn": withdrawn,
            "starting_capital": start_cap, "gross_pnl": pnl,
            "mtf_interest": mtf_interest, "net_pnl": net_pnl,
            "ending_capital": running_capital,
        })

    # ── KPI strip ────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("TOTAL ADDED", fmt_inr(total_added)), unsafe_allow_html=True)
    k2.markdown(kpi_card("TOTAL WITHDRAWN", fmt_inr(total_withdrawn)), unsafe_allow_html=True)
    k3.markdown(kpi_card("MTF INTEREST PAID", fmt_inr(total_mtf_interest), color=AMBER), unsafe_allow_html=True)
    k4.markdown(kpi_card("CURRENT CAPITAL", fmt_inr(running_capital)), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── editable monthly table ──────────────────────────────────────────
    st.markdown(section_label(f"Monthly Flows — {year_sel}"), unsafe_allow_html=True)
    st.caption("Edit Added / Withdrawn / MTF Interest inline below, then click Save. Starting Capital and Net P/L are computed automatically.")

    edit_df = pd.DataFrame([{
        "Month": r["month"],
        "Added (₹)": r["added"],
        "Withdrawn (₹)": r["withdrawn"],
        "MTF Interest (₹)": r["mtf_interest"],
        "Starting Capital (₹)": r["starting_capital"],
        "Gross P/L (₹)": r["gross_pnl"],
        "Net P/L (₹)": r["net_pnl"],
        "Ending Capital (₹)": r["ending_capital"],
    } for r in rows])

    edited = st.data_editor(
        edit_df,
        use_container_width=True, hide_index=True, key=f"fund_editor_{year_sel}",
        disabled=["Month", "MTF Interest (₹)", "Starting Capital (₹)", "Gross P/L (₹)", "Net P/L (₹)", "Ending Capital (₹)"],
        column_config={
            "Added (₹)": st.column_config.NumberColumn(format="₹%.0f", min_value=0.0),
            "Withdrawn (₹)": st.column_config.NumberColumn(format="₹%.0f", min_value=0.0),
            "MTF Interest (₹)": st.column_config.NumberColumn(format="₹%.0f",
                                                                help="Auto-calculated from MTF trades (Zerodha's 0.04%/day formula) — not editable here"),
            "Starting Capital (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Gross P/L (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Net P/L (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Ending Capital (₹)": st.column_config.NumberColumn(format="₹%.0f"),
        },
    )

    if st.button("💾 Save Changes", key=f"save_flows_{year_sel}"):
        for i, m in enumerate(range(1, 13)):
            added = safe_float(edited.iloc[i]["Added (₹)"])
            withdrawn = safe_float(edited.iloc[i]["Withdrawn (₹)"])
            save_capital_flow(year_sel, m, added, withdrawn)  # MTF interest is auto-calculated, not saved manually
        save_capital_flow(year_sel, 0, 0, 0, base_capital=starting_capital)  # month=0 stores the anchor
        st.success("Saved. Reload the page to see updated roll-forward.")
        st.rerun()

    # ── TOTAL (post-tax placeholder) row ─────────────────────────────────
    st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
        padding:14px 18px;margin-top:10px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <span style="font-size:12px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.07em;font-weight:600">
            TOTAL <span style="color:{TEAL}">POST-TAX</span>
        </span>
        <span style="font-size:13px;color:{TEXT_BODY}">
            Added {fmt_inr(total_added)} &nbsp;·&nbsp; Withdrawn {fmt_inr(total_withdrawn)} &nbsp;·&nbsp;
            Gross P/L {fmt_pnl(total_pnl)} &nbsp;·&nbsp; MTF Interest -{fmt_inr(total_mtf_interest)} &nbsp;·&nbsp;
            <b style="color:{TEXT_H}">Ending {fmt_inr(running_capital)}</b>
        </span>
    </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # MTF ANALYTICS — Interest Cost (auto-calculated), MTF vs Cash P&L, Leverage Trend
    # ════════════════════════════════════════════════════════════════════
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown(section_label("MTF Analytics"), unsafe_allow_html=True)

    import plotly.graph_objects as go

    mtf_tab1, mtf_tab2, mtf_tab3, mtf_tab4 = st.tabs(["💸 Interest Cost", "⚖️ MTF vs Cash P&L", "📈 Leverage Trend", "🏦 MTF Eligible Stocks"])

    # ── 1. MTF Interest Cost Over Time (auto-calculated) ─────────────────
    with mtf_tab1:
        st.caption("Auto-calculated per Zerodha's MTF rate: 0.04%/day (₹40 per lakh) on the borrowed amount, "
                   "from T+1 until exit (or today, for open positions). No manual entry needed.")

        interest_months_auto = MONTHS
        interest_vals_auto = [auto_interest_by_month[m] for m in range(1, 13)]

        if total_mtf_interest_auto == 0:
            st.info("No MTF interest accrued yet — either no MTF trades this year, or all MTF positions were entered today.")
        else:
            fig_int = go.Figure()
            fig_int.add_trace(go.Bar(
                x=interest_months_auto, y=interest_vals_auto,
                marker=dict(color=AMBER, opacity=0.85, line=dict(width=0)),
                hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>",
            ))
            l_int = chart_layout(height=260, title="")
            l_int["yaxis"]["tickprefix"] = "₹"
            fig_int.update_layout(**l_int)
            st.plotly_chart(fig_int, use_container_width=True, config={"displayModeBar": False})

            ic1, ic2, ic3 = st.columns(3)
            active_months_count = sum(1 for v in interest_vals_auto if v > 0)
            avg_monthly_interest = total_mtf_interest_auto / max(1, active_months_count)
            ic1.markdown(kpi_card("TOTAL MTF INTEREST (auto)", fmt_inr(total_mtf_interest_auto), color=AMBER), unsafe_allow_html=True)
            ic2.markdown(kpi_card("AVG MONTHLY (active months)", fmt_inr(avg_monthly_interest)), unsafe_allow_html=True)
            interest_pct_of_gross = (total_mtf_interest_auto / total_pnl * 100) if total_pnl else 0
            ic3.markdown(kpi_card("% OF GROSS P&L", f"{interest_pct_of_gross:.1f}%",
                                   color=(RED if interest_pct_of_gross > 15 else AMBER if interest_pct_of_gross > 5 else TEAL),
                                   sub="interest cost as a share of gross profit"), unsafe_allow_html=True)

        st.caption("⚠️ Excludes brokerage (0.3% or ₹20/order, whichever lower), pledge/unpledge charges (₹15+GST each), "
                   "and square-off charges (₹50+GST) — interest only. Check console.zerodha.com/funds/interest-statement "
                   "for the exact billed figure if you need precision for tax purposes.")

    # ── 2. MTF vs Cash P&L Comparison ────────────────────────────────────
    with mtf_tab2:
        st.caption(f"Is leverage actually paying for itself? Gross P&L by funding type, {year_sel}, net of auto-calculated MTF interest.")

        cash_total = sum(monthly_pnl_cash.values())
        mtf_total_gross = sum(monthly_pnl_mtf.values())
        mtf_total_net = mtf_total_gross - total_mtf_interest_auto

        cash_trades_n = sum(1 for t in closed if str(t.get("funding_type", "CASH") or "CASH").upper() != "MTF"
                             and str(t.get("exit_date", ""))[:4].isdigit() and int(str(t.get("exit_date", ""))[:4]) == year_sel)
        mtf_trades_n = sum(1 for t in closed if str(t.get("funding_type", "CASH") or "CASH").upper() == "MTF"
                            and str(t.get("exit_date", ""))[:4].isdigit() and int(str(t.get("exit_date", ""))[:4]) == year_sel)
        mtf_open_n = sum(1 for t in trades if t.get("status") == "OPEN"
                          and str(t.get("funding_type", "CASH") or "CASH").upper() == "MTF")

        if cash_trades_n == 0 and mtf_trades_n == 0:
            st.info("No closed trades this year to compare.")
        else:
            if mtf_trades_n == 0 and mtf_open_n > 0:
                st.markdown(f"""<div style="background:{AMBER_BG};border:1px solid {AMBER_BORDER};border-radius:8px;
                    padding:8px 12px;font-size:11px;color:{TEXT_BODY};margin-bottom:10px">
                    ℹ️ You have {mtf_open_n} open MTF position(s), but none closed yet this year — MTF P&L will show
                    ₹0 until at least one MTF trade is exited. Interest is still accruing (see Interest Cost tab).
                </div>""", unsafe_allow_html=True)

            mc1, mc2, mc3 = st.columns(3)
            mc1.markdown(kpi_card("CASH P&L", fmt_pnl(cash_total), color=pnl_color(cash_total),
                                   sub=f"{cash_trades_n} trade(s)"), unsafe_allow_html=True)
            mc2.markdown(kpi_card("MTF P&L (GROSS)", fmt_pnl(mtf_total_gross), color=pnl_color(mtf_total_gross),
                                   sub=f"{mtf_trades_n} closed trade(s)"), unsafe_allow_html=True)
            mc3.markdown(kpi_card("MTF P&L (NET OF INTEREST)", fmt_pnl(mtf_total_net), color=pnl_color(mtf_total_net),
                                   sub=f"after -{fmt_inr(total_mtf_interest_auto)} interest"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            fig_cmp = go.Figure()
            cmp_months = MONTHS
            fig_cmp.add_trace(go.Bar(
                x=cmp_months, y=[monthly_pnl_cash[i+1] for i in range(12)],
                name="Cash", marker=dict(color=BLUE, opacity=0.85),
                hovertemplate="%{x}<br>Cash: ₹%{y:,.0f}<extra></extra>",
            ))
            fig_cmp.add_trace(go.Bar(
                x=cmp_months, y=[monthly_pnl_mtf[i+1] for i in range(12)],
                name="MTF (gross)", marker=dict(color=AMBER, opacity=0.85),
                hovertemplate="%{x}<br>MTF: ₹%{y:,.0f}<extra></extra>",
            ))
            l_cmp = chart_layout(height=280, title="Monthly P&L — Cash vs MTF (gross, closed trades only)")
            l_cmp["yaxis"]["tickprefix"] = "₹"
            l_cmp["barmode"] = "group"
            l_cmp["legend"] = dict(orientation="h", y=-0.18, x=0, font=dict(size=10, color=TEXT_MUTED))
            l_cmp["showlegend"] = True
            fig_cmp.update_layout(**l_cmp)
            st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})

            if mtf_total_gross > 0:
                st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;
                    padding:14px 18px;font-size:13px;color:{TEXT_BODY};line-height:1.6;margin-top:8px">
                    MTF interest consumed <b style="color:{TEXT_H}">{(total_mtf_interest_auto/mtf_total_gross*100 if mtf_total_gross else 0):.1f}%</b>
                    of your gross MTF profit this year. {"Leverage is paying for itself." if mtf_total_net > 0 else "Net MTF result is negative after interest — worth reviewing whether the leverage is adding edge or just risk."}
                </div>""", unsafe_allow_html=True)

    # ── 3. Leverage Trend (approximate, reconstructed from trade entries) ──
    with mtf_tab3:
        st.caption(f"Approximate monthly leverage — % of newly-opened position value that was MTF-borrowed, by entry month, {year_sel}.")
        st.markdown(f"""<div style="background:{AMBER_BG};border:1px solid {AMBER_BORDER};border-radius:8px;
            padding:8px 12px;font-size:11px;color:{TEXT_BODY};margin-bottom:12px">
            ⚠️ This is reconstructed from trade entry dates, not a stored daily snapshot — it shows leverage at the
            point positions were <i>opened</i> each month, not your actual exposure on every day. Treat as directional, not exact.
        </div>""", unsafe_allow_html=True)

        all_trades_year = [t for t in trades if str(t.get("entry_date", ""))[:4].isdigit()
                            and int(str(t.get("entry_date", ""))[:4]) == year_sel]

        lev_by_month = {m: {"own": 0.0, "borrowed": 0.0} for m in range(1, 13)}
        for t in all_trades_year:
            try:
                month = datetime.strptime(str(t.get("entry_date", ""))[:10], "%Y-%m-%d").month
            except Exception:
                continue
            qty = safe_float(t.get("qty"))
            price = safe_float(t.get("entry_price"))
            value = qty * price
            funding = str(t.get("funding_type", "CASH") or "CASH").upper()
            if funding == "MTF":
                margin_pct = safe_float(t.get("mtf_margin_pct")) or 50.0
                lev_by_month[month]["own"] += value * margin_pct / 100
                lev_by_month[month]["borrowed"] += value * (1 - margin_pct / 100)
            else:
                lev_by_month[month]["own"] += value

        lev_pct_by_month = []
        for m in range(1, 13):
            own = lev_by_month[m]["own"]
            borrowed = lev_by_month[m]["borrowed"]
            total = own + borrowed
            lev_pct_by_month.append((borrowed / total * 100) if total > 0 else None)

        if all(v is None for v in lev_pct_by_month):
            st.info("No trade entries this year to reconstruct a leverage trend from.")
        else:
            lev_months_plot = [MONTHS[i] for i in range(12) if lev_pct_by_month[i] is not None]
            lev_vals_plot = [v for v in lev_pct_by_month if v is not None]

            fig_lev = go.Figure()
            fig_lev.add_trace(go.Scatter(
                x=lev_months_plot, y=lev_vals_plot, mode="lines+markers",
                line=dict(color=AMBER, width=2.5, shape="spline"),
                marker=dict(size=7, color=[RED if v > 30 else AMBER if v > 15 else TEAL for v in lev_vals_plot],
                            line=dict(color="white", width=1.5)),
                fill="tozeroy", fillcolor="rgba(245,158,11,0.15)",
                hovertemplate="%{x}<br>%{y:.1f}% leverage<extra></extra>",
            ))
            fig_lev.add_hline(y=30, line=dict(color=RED, width=1, dash="dot"),
                               annotation_text="30% — high leverage", annotation_font=dict(color=RED, size=9))
            fig_lev.add_hline(y=15, line=dict(color=AMBER, width=1, dash="dot"),
                               annotation_text="15% — moderate", annotation_font=dict(color=AMBER, size=9))
            l_lev = chart_layout(height=280, title="")
            l_lev["yaxis"]["ticksuffix"] = "%"
            l_lev["yaxis"]["range"] = [0, max(50, max(lev_vals_plot) * 1.2 if lev_vals_plot else 50)]
            fig_lev.update_layout(**l_lev)
            st.plotly_chart(fig_lev, use_container_width=True, config={"displayModeBar": False})

            avg_lev = sum(lev_vals_plot) / len(lev_vals_plot) if lev_vals_plot else 0
            peak_lev = max(lev_vals_plot) if lev_vals_plot else 0
            lc1, lc2 = st.columns(2)
            lc1.markdown(kpi_card("AVG MONTHLY LEVERAGE", f"{avg_lev:.1f}%",
                                   color=(RED if avg_lev > 30 else AMBER if avg_lev > 15 else TEAL)), unsafe_allow_html=True)
            lc2.markdown(kpi_card("PEAK MONTHLY LEVERAGE", f"{peak_lev:.1f}%",
                                   color=(RED if peak_lev > 30 else AMBER if peak_lev > 15 else TEAL)), unsafe_allow_html=True)

    st.caption("Post-tax total is illustrative — wire to your Tax Analytics page output if you want an exact post-STCG/LTCG figure. "
               "MTF interest is auto-calculated from your MTF trades using Zerodha's published 0.04%/day rate — excludes brokerage and other charges.")
    with mtf_tab4:
        st.markdown("### 🏦 MTF Eligible Stocks")
        st.caption("Stocks approved for MTF funding by Zerodha. Upload updated list from Zerodha website.")

        from data.db import _sb as _fm_sb
        try:
            mtf_list = _fm_sb().table("mtf_margins").select("*").order("ticker").execute().data
        except:
            mtf_list = []

        if not mtf_list:
            st.info("No MTF securities uploaded yet. Go to Screener → 🏦 Upload Zerodha MTF List to upload.")
        else:
            st.markdown(f'<p style="font-size:11px;color:{TEXT_SUBTLE}">{len(mtf_list)} MTF eligible stocks</p>', unsafe_allow_html=True)

            # Search filter
            mtf_search = st.text_input("Search ticker", placeholder="e.g. HSCL", key="mtf_search", label_visibility="collapsed")
            if mtf_search:
                mtf_list = [r for r in mtf_list if mtf_search.upper() in r.get("ticker","").upper()]

            # Cross-reference with open trades
            open_trades = get_trades(status="OPEN")
            open_tickers = {t.get("ticker","") for t in open_trades}
            mtf_tickers = {r["ticker"] for r in mtf_list}
            holding_mtf = open_tickers & mtf_tickers

            m1, m2, m3 = st.columns(3)
            m1.metric("MTF Eligible", len(mtf_list))
            m2.metric("Your Holdings (MTF eligible)", len(holding_mtf))
            m3.metric("Your Holdings (NOT MTF eligible)", len(open_tickers - mtf_tickers))

            st.markdown("<br>", unsafe_allow_html=True)

            # Table
            TH_m = f"padding:8px 12px;font-size:10px;color:white;background:#1E293B;text-align:left"
            TD_m = f"padding:8px 12px;font-size:11px;border-bottom:1px solid {BORDER_LIGHT}"
            rows_m = ""
            for r in mtf_list:
                ticker = r.get("ticker","")
                margin = r.get("margin_pct")
                lev = r.get("leverage")
                in_portfolio = "🟢 Yes" if ticker in open_tickers else ""
                rows_m += f"""<tr>
                    <td style="{TD_m};font-weight:700">{ticker}</td>
                    <td style="{TD_m};text-align:right">{f"{margin:.1f}%" if margin else "—"}</td>
                    <td style="{TD_m};text-align:right">{f"{lev:.1f}x" if lev else "—"}</td>
                    <td style="{TD_m};text-align:center">{in_portfolio}</td>
                </tr>"""
            st.markdown(f"""<div style="overflow-x:auto;border-radius:10px;border:1px solid {BORDER};max-height:500px;overflow-y:auto">
            <table style="width:100%;border-collapse:collapse">
                <thead><tr>
                    <th style="{TH_m}">Ticker</th>
                    <th style="{TH_m};text-align:right">Margin%</th>
                    <th style="{TH_m};text-align:right">Leverage</th>
                    <th style="{TH_m};text-align:center">In Portfolio</th>
                </tr></thead>
                <tbody>{rows_m}</tbody>
            </table></div>""", unsafe_allow_html=True)

            # Upload section
            st.markdown("---")
            st.info("📌 To update the MTF list go to **Imports → Weekly → MTF/MIS List**")

