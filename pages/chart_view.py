import streamlit as st
import streamlit.components.v1 as components
from data.db import get_journal_trades
from theme import *

QUICK = [
    "NIFTY50","BANKNIFTY","SENSEX","FINNIFTY",
    "RELIANCE","TCS","HDFCBANK","INFY","SBIN","ICICIBANK",
    "ITC","AXISBANK","MARUTI","TITAN","WIPRO","BAJFINANCE",
    "CDSL","KPIGREEN","ENDURANCE","MIDHANI","CUB","BEL","HAL",
]

NSE_SYMBOLS = [
    ("NIFTY50","Nifty 50 Index"),("BANKNIFTY","Bank Nifty"),
    ("SENSEX","BSE Sensex"),("FINNIFTY","Nifty Financial"),
    ("MIDCPNIFTY","Midcap Nifty"),
    ("RELIANCE","Reliance Industries"),("TCS","Tata Consultancy"),
    ("HDFCBANK","HDFC Bank"),("INFY","Infosys"),("SBIN","State Bank of India"),
    ("ICICIBANK","ICICI Bank"),("ITC","ITC Limited"),("AXISBANK","Axis Bank"),
    ("KOTAKBANK","Kotak Mahindra Bank"),("LT","Larsen & Toubro"),
    ("MARUTI","Maruti Suzuki"),("TITAN","Titan Company"),
    ("WIPRO","Wipro"),("BAJFINANCE","Bajaj Finance"),
    ("HCLTECH","HCL Technologies"),("TATAMOTORS","Tata Motors"),
    ("TATASTEEL","Tata Steel"),("ADANIENT","Adani Enterprises"),
    ("ADANIPORTS","Adani Ports"),("JSWSTEEL","JSW Steel"),
    ("BEL","Bharat Electronics"),("HAL","Hindustan Aeronautics"),
    ("CDSL","Central Depository Services"),("KPIGREEN","KPI Green Energy"),
    ("BLISSGVS","Bliss GVS Pharma"),("MIDHANI","Mishra Dhatu Nigam"),
    ("ENDURANCE","Endurance Technologies"),("CUB","City Union Bank"),
    ("KPEL","K.P. Energy"),("ZOMATO","Zomato"),
    ("DMART","Avenue Supermarts"),("NAUKRI","Info Edge"),
    ("SUNPHARMA","Sun Pharmaceutical"),("DRREDDY","Dr Reddy's Labs"),
    ("CIPLA","Cipla"),("NTPC","NTPC"),("ONGC","ONGC"),
    ("COALINDIA","Coal India"),("POWERGRID","Power Grid"),
    ("NESTLEIND","Nestle India"),("BRITANNIA","Britannia Industries"),
    ("HAVELLS","Havells India"),("SIEMENS","Siemens India"),
    ("PIDILITIND","Pidilite Industries"),("APOLLOHOSP","Apollo Hospitals"),
]

INTERVALS = {
    "1m":"1","3m":"3","5m":"5","15m":"15","30m":"30",
    "1H":"60","2H":"120","4H":"240","1D":"D","1W":"W","1M":"M"
}

def tv_sym(sym):
    m = {"NIFTY50":"NSE:NIFTY50","BANKNIFTY":"NSE:BANKNIFTY",
         "SENSEX":"BSE:SENSEX","FINNIFTY":"NSE:FINNIFTY",
         "MIDCPNIFTY":"NSE:MIDCPNIFTY"}
    return m.get(sym, f"BSE:{sym}")

def tv_url(sym, interval="D"):
    return f"https://www.tradingview.com/chart/?symbol={tv_sym(sym)}&interval={interval}"

def search_syms(q):
    q = q.lower()
    return [(s,d) for s,d in NSE_SYMBOLS if q in s.lower() or q in d.lower()][:8]


def render():
    st.markdown("## Chart")
    st.markdown(
        f'<p style="color:{TEXT_SUBTLE};margin-top:-8px;margin-bottom:14px;font-size:11px">'
        f'TradingView · BSE/NSE · Opens in new tab with your account</p>',
        unsafe_allow_html=True
    )

    if "tv_symbol"   not in st.session_state: st.session_state.tv_symbol   = "NIFTY50"
    if "tv_interval" not in st.session_state: st.session_state.tv_interval = "D"

    sym  = st.session_state.tv_symbol
    intv = st.session_state.tv_interval

    # ── Controls ──────────────────────────────────────────────────────────────
    CHART_TYPES = {
        "Candles":"1","Bars":"0","Line":"2","Area":"3",
        "Heikin Ashi":"8","Hollow Candles":"9"
    }
    if "tv_chart_type" not in st.session_state:
        st.session_state.tv_chart_type = "1"

    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1.5])
    with c1:
        q = st.text_input("", placeholder="🔍 Search symbol… e.g. Reliance, HDFC, CDSL",
            label_visibility="collapsed", key="csearch")
    with c2:
        intv_label = st.selectbox("", list(INTERVALS.keys()), index=8,
            label_visibility="collapsed", key="cintv")
        st.session_state.tv_interval = INTERVALS[intv_label]
        intv = st.session_state.tv_interval
    with c3:
        chart_type_label = st.selectbox("", list(CHART_TYPES.keys()),
            index=0, label_visibility="collapsed", key="ctype")
        st.session_state.tv_chart_type = CHART_TYPES[chart_type_label]
    with c4:
        st.link_button(
            f"📈 Open {sym} in TradingView ↗",
            tv_url(sym, intv),
            use_container_width=True,
            type="primary"
        )

    # Search results
    if q and len(q) >= 1:
        results = search_syms(q)
        if results:
            rcols = st.columns(min(len(results), 6))
            for i, (col, (s, d)) in enumerate(zip(rcols, results)):
                active = sym == s
                col.markdown(
                    f'<div style="background:{"rgba(124,58,237,0.1)" if active else CARD_BG};'
                    f'border:1px solid {"#7C3AED" if active else BORDER};'
                    f'border-radius:8px;padding:8px;text-align:center;margin-bottom:4px">'
                    f'<div style="font-size:12px;font-weight:700;color:{TEXT_H}">{s}</div>'
                    f'<div style="font-size:9px;color:{TEXT_MUTED}">{d[:22]}</div></div>',
                    unsafe_allow_html=True
                )
                if col.button("Select", key=f"sr_{i}_{s}", use_container_width=True):
                    st.session_state.tv_symbol = s; st.rerun()

    # ── TradingView Embed ────────────────────────────────────────────────────
    import streamlit.components.v1 as components
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    display_sym = tv_sym(sym)
    intv_rev    = {v:k for k,v in INTERVALS.items()}
    intv_disp   = intv_rev.get(intv, intv)
    url         = tv_url(sym, intv)
    bg          = "#131722"

    tv_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;padding:0;background:{bg};overflow:hidden;height:100%}}
  .tradingview-widget-container{{width:100%;height:620px}}
  .tradingview-widget-container__widget{{height:100%}}
</style></head>
<body>
<div class="tradingview-widget-container">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript"
    src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
    async>
  {{
    "autosize": true,
    "symbol": "{display_sym}",
    "interval": "{intv}",
    "timezone": "Asia/Kolkata",
    "theme": "dark",
    "style": "{st.session_state.get('tv_chart_type','1')}",
    "locale": "en",
    "allow_symbol_change": true,
    "calendar": false,
    "hide_volume": false,
    "support_host": "https://www.tradingview.com"
  }}
  </script>
</div>
</body></html>"""

    components.html(tv_html, height=630, scrolling=False)
    st.markdown(
        f'<p style="font-size:10px;color:{TEXT_SUBTLE};text-align:center;margin-top:2px">'
        f'{display_sym} · {intv_disp} · '
        f'<a href="{url}" target="_blank" style="color:#7C3AED">Open full screen ↗</a></p>',
        unsafe_allow_html=True
    )

    # ── Trade history for this symbol ─────────────────────────────────────────
    closed_t = [t for t in trades if t["status"] == "CLOSED"
                and t.get("ticker","").upper() == sym.upper()]
    if closed_t:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown(
            f'<p style="font-size:13px;font-weight:600;color:{TEXT_H};margin-bottom:8px">'
            f'Your trades in {sym} ({len(closed_t)})</p>',
            unsafe_allow_html=True
        )
        TH = f"padding:9px 14px;font-size:10px;color:{TEXT_SUBTLE};font-weight:500;text-transform:uppercase;letter-spacing:0.06em;background:{TABLE_HEAD_BG};border-bottom:1px solid {BORDER}"
        TD = f"padding:9px 14px;font-size:12.5px;border-bottom:1px solid {BORDER_LIGHT}"

        total_pnl = sum(float(t.get("pnl") or 0) for t in closed_t)
        wins      = sum(1 for t in closed_t if float(t.get("pnl") or 0) > 0)
        wr        = f"{wins/len(closed_t)*100:.0f}%"
        tpc       = TEAL if total_pnl >= 0 else RED

        # Summary strip
        st.markdown(f"""<div style="display:flex;gap:16px;margin-bottom:10px">
            <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:8px;padding:10px 16px">
                <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Trades</div>
                <div style="font-size:18px;font-weight:700;color:{TEXT_H}">{len(closed_t)}</div>
            </div>
            <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:8px;padding:10px 16px">
                <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Total P&L</div>
                <div style="font-size:18px;font-weight:700;color:{tpc}">{"+" if total_pnl>=0 else ""}₹{abs(total_pnl):,.0f}</div>
            </div>
            <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:8px;padding:10px 16px">
                <div style="font-size:9px;color:{TEXT_SUBTLE};font-weight:600;text-transform:uppercase;letter-spacing:0.06em">Win Rate</div>
                <div style="font-size:18px;font-weight:700;color:{TEAL if wins/len(closed_t)>=0.5 else RED}">{wr}</div>
            </div>
        </div>""", unsafe_allow_html=True)

        rows = ""
        for t in sorted(closed_t, key=lambda x: str(x.get("exit_date","") or ""), reverse=True)[:15]:
            p   = float(t.get("pnl") or 0)
            pc  = TEAL if p > 0 else RED
            ep  = float(t.get("entry_price") or 0)
            xp  = float(t.get("exit_price") or 0)
            qty = t.get("qty","—")
            rmult = t.get("r_multiple","")
            rows += f"""<tr>
                <td style="{TD};color:{TEXT_MUTED}">{str(t.get("exit_date","") or "")[:10]}</td>
                <td style="{TD};color:{TEXT_MUTED}">{t.get("strategy","")}</td>
                <td style="{TD}">₹{ep:,.2f}</td>
                <td style="{TD}">₹{xp:,.2f}</td>
                <td style="{TD};color:{TEXT_MUTED}">{qty}</td>
                <td style="{TD};font-weight:600;color:{pc}">{"+" if p>0 else ""}₹{abs(p):,.0f}</td>
                <td style="{TD};color:{TEXT_MUTED}">{f"{float(rmult):.2f}R" if rmult else "—"}</td>
            </tr>"""

        st.markdown(f"""<table style="width:100%;border-collapse:collapse">
            <thead><tr>
                <th style="{TH};text-align:left">Date</th>
                <th style="{TH};text-align:left">Strategy</th>
                <th style="{TH};text-align:left">Entry ₹</th>
                <th style="{TH};text-align:left">Exit ₹</th>
                <th style="{TH};text-align:left">Qty</th>
                <th style="{TH};text-align:left">P&L</th>
                <th style="{TH};text-align:left">R-Mult</th>
            </tr></thead><tbody>{rows}</tbody>
        </table>""", unsafe_allow_html=True)
    else:
        st.markdown(
            f'<p style="font-size:12px;color:{TEXT_SUBTLE};margin-top:12px;text-align:center">'
            f'No closed trades for {sym} in your journal</p>',
            unsafe_allow_html=True
        )
