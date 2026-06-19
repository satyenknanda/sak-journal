# -*- coding: utf-8 -*-
import streamlit as st
import sqlite3
import json
import os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "journal.db")

def _use_supabase():
    try:
        url = st.secrets.get("SUPABASE_URL","")
        key = st.secrets.get("SUPABASE_KEY","")
        if url and key:
            os.environ["SUPABASE_URL"] = url
            os.environ["SUPABASE_KEY"] = key
            return True
    except: pass
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))

def _sb():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def get_db():
    conn = sqlite3.connect(os.path.abspath(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if _use_supabase(): return
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS morning_brief (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brief_date TEXT UNIQUE,
        data TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    conn.commit(); conn.close()

def save_brief(brief_date, data):
    if _use_supabase():
        try:
            _sb().table("morning_brief").upsert({
                "brief_date": str(brief_date),
                "data": json.dumps(data),
                "updated_at": str(__import__("datetime").datetime.now())
            }).execute()
            return
        except Exception as e:
            print(f"save_brief supabase error: {e}")
            return
    conn = get_db()
    conn.execute("""INSERT INTO morning_brief (brief_date, data, updated_at)
        VALUES (?,?,datetime('now','localtime'))
        ON CONFLICT(brief_date) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at""",
        (brief_date, json.dumps(data)))
    conn.commit(); conn.close()

def load_brief(brief_date):
    if _use_supabase():
        try:
            res = _sb().table("morning_brief").select("data").eq("brief_date", str(brief_date)).execute()
            return json.loads(res.data[0]["data"]) if res.data else None
        except Exception as e:
            print(f"load_brief supabase error: {e}")
            return None
    conn = get_db()
    row = conn.execute("SELECT data FROM morning_brief WHERE brief_date=?", (brief_date,)).fetchone()
    conn.close()
    return json.loads(row["data"]) if row else None

def list_briefs():
    if _use_supabase():
        try:
            res = _sb().table("morning_brief").select("brief_date,data").order("brief_date", desc=True).limit(20).execute()
            return res.data or []
        except Exception as e:
            print(f"list_briefs supabase error: {e}")
            return []
    conn = get_db()
    rows = conn.execute("SELECT brief_date, data FROM morning_brief ORDER BY brief_date DESC LIMIT 20").fetchall()
    conn.close()
    return rows

def sv(v):
    if v is None: return ""
    s = str(v).strip()
    return "" if s in ("None","nan","null") else s

# Colours
TEAL="#10B981"; RED="#EF4444"; AMBER="#F59E0B"; BLUE="#3B82F6"; PURPLE="#8B5CF6"; GRAY="#6B7280"
VERDICT_COLORS={"HUNT":TEAL,"SELECTIVE":AMBER,"SIT":RED}
NEWS_TAG_COLORS={"Bullish":TEAL,"Bearish":RED,"Neutral":GRAY,"Watch":AMBER}
FOCUS_CAT_COLORS={"Results":PURPLE,"Block Deal":BLUE,"Upgrade":TEAL,"Downgrade":RED,
    "Order Win":AMBER,"52W High":"#EC4899","Breakout":"#F97316","SEBI/Regulatory":"#92400E",
    "Insider Buy":TEAL,"Other":GRAY}
STRAT_COLORS={"VCP":PURPLE,"SVRO":BLUE,"EP":"#F97316","REVERSAL":RED,"NR1HR":TEAL,"TS":AMBER,"MARS":"#DB2777"}

def card(title, accent=TEAL):
    return f"""<div style="background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:14px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
<div style="display:flex;align-items:center;gap:7px;border-bottom:1px solid #F3F4F6;padding-bottom:7px;margin-bottom:10px">
<span style="width:3px;height:14px;background:{accent};border-radius:2px;display:inline-block"></span>
<span style="font-size:11px;font-weight:700;color:#374151">{title}</span></div>"""

def tcolor(val):
    s = sv(val)
    if not s: return "#94A3B8"
    return RED if s.lstrip("+").startswith("-") else TEAL

def fetch_data():
    import urllib.request, urllib.error, ssl, certifi
    api_key = os.environ.get("ANTHROPIC_API_KEY","")
    if not api_key:
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.strip().split("=",1)[1].strip().strip('"\'')
    if not api_key:
        return None, "API key not found in .env file"

    today_str = date.today().strftime("%A, %d %B %Y")
    prompt = f"""You are an expert Indian stock market analyst. Today is {today_str}.
Return ONLY a raw JSON object with NO markdown and NO explanation. All numeric values must be strings.
Include ALL of these exact keys:

niftyClose, niftyChange, bnClose, bnChange, vix, giftNifty, giftDiff, crude, usdinr, sp500, nasdaq, nikkei,
niftyPivot, niftyR1, niftyR2, niftyS1, niftyS2, bnR1, bnS1,
fiiCash, diiCash, fiiIndexFut, flowNote,
leadingSector, laggingSector, sectorNote,
sector_bank, sector_it, sector_energy, sector_pharma, sector_metal, sector_fmcg, sector_auto, sector_realty,
dayType, topFocus, riskNote,
vcpCount, svroCount, epCount, reversalCount, watchlistNotes,
news (array of 4 objects with: stock, headline, tag, note),
companiesInFocus (array of 5 objects with: stock, category, headline, detail, bias, tradeNote)

Rules:
- sector values must be exactly one of: "▲ Strong" or "→ Neutral" or "▼ Weak"
- dayType must be exactly one of: HUNT, SELECTIVE, SIT
- news tag must be exactly one of: Bullish, Bearish, Neutral, Watch
- companiesInFocus bias must be exactly one of: Bullish, Bearish, Neutral
- companiesInFocus category must be one of: Results, Block Deal, Upgrade, Downgrade, Order Win, 52W High, Breakout, SEBI/Regulatory, Insider Buy, Other
- Use realistic values for Indian markets on {today_str}
- niftyPivot = (niftyHigh + niftyLow + niftyClose) / 3, R1 = 2*pivot - low, R2 = pivot + (high-low), S1 = 2*pivot - high, S2 = pivot - (high-low)
- topFocus must be 2-3 sentences about what to watch today
- riskNote must be 2-3 sentences about key risks today
- watchlistNotes must list 3-5 specific stock setups with entry/stop/target

Output raw JSON only. Start with {{ and end with }}"""

    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01"},
        method="POST"
    )
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None, f"API error {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return None, f"Request failed: {e}"

    text = "".join(b.get("text","") for b in result.get("content",[]) if b.get("type")=="text")
    clean = text.replace("```json","").replace("```","").strip()
    s, e2 = clean.find("{"), clean.rfind("}")
    if s == -1 or e2 == -1:
        return None, f"No JSON in response: {text[:200]}"
    try:
        return json.loads(clean[s:e2+1]), None
    except Exception as e:
        return None, f"JSON parse error: {e}. Text: {clean[s:s+200]}"

def set_state(parsed):
    """Write all parsed values directly into st.session_state widget keys."""
    def s(v): return sv(v)

    # Market
    st.session_state["m_nc"]    = s(parsed.get("niftyClose",""))
    st.session_state["m_nch"]   = s(parsed.get("niftyChange",""))
    st.session_state["m_bn"]    = s(parsed.get("bnClose",""))
    st.session_state["m_bnch"]  = s(parsed.get("bnChange",""))
    st.session_state["m_vix"]   = s(parsed.get("vix",""))
    st.session_state["m_gift"]  = s(parsed.get("giftNifty",""))
    st.session_state["m_gdiff"] = s(parsed.get("giftDiff",""))
    st.session_state["m_crude"] = s(parsed.get("crude",""))
    st.session_state["m_inr"]   = s(parsed.get("usdinr",""))
    st.session_state["m_sp"]    = s(parsed.get("sp500",""))
    st.session_state["m_nq"]    = s(parsed.get("nasdaq",""))
    st.session_state["m_nk"]    = s(parsed.get("nikkei",""))
    # Levels
    st.session_state["l_piv"]   = s(parsed.get("niftyPivot",""))
    st.session_state["l_r1"]    = s(parsed.get("niftyR1",""))
    st.session_state["l_r2"]    = s(parsed.get("niftyR2",""))
    st.session_state["l_s1"]    = s(parsed.get("niftyS1",""))
    st.session_state["l_s2"]    = s(parsed.get("niftyS2",""))
    st.session_state["l_bnr"]   = s(parsed.get("bnR1",""))
    st.session_state["l_bns"]   = s(parsed.get("bnS1",""))
    # Flows
    st.session_state["f_fii"]   = s(parsed.get("fiiCash",""))
    st.session_state["f_dii"]   = s(parsed.get("diiCash",""))
    st.session_state["f_fut"]   = s(parsed.get("fiiIndexFut",""))
    st.session_state["f_note"]  = s(parsed.get("flowNote",""))
    # Sectors
    st.session_state["s_lead"]  = s(parsed.get("leadingSector",""))
    st.session_state["s_lag"]   = s(parsed.get("laggingSector",""))
    st.session_state["s_note"]  = s(parsed.get("sectorNote",""))
    opts = ["▲ Strong","→ Neutral","▼ Weak"]
    for k in ["sector_bank","sector_it","sector_energy","sector_pharma","sector_metal","sector_fmcg","sector_auto","sector_realty"]:
        v = s(parsed.get(k,"→ Neutral"))
        st.session_state[f"sr_{k}"] = v if v in opts else "→ Neutral"
    # Watchlist
    st.session_state["wl_vcp"]   = s(parsed.get("vcpCount",""))
    st.session_state["wl_svro"]  = s(parsed.get("svroCount",""))
    st.session_state["wl_ep"]    = s(parsed.get("epCount",""))
    st.session_state["wl_rev"]   = s(parsed.get("reversalCount",""))
    st.session_state["wl_notes"] = s(parsed.get("watchlistNotes",""))
    # Verdict
    dt = s(parsed.get("dayType","SELECTIVE"))
    dmap = {"HUNT":"HUNT ▶","SELECTIVE":"SELECTIVE ▶","SIT":"SIT ▶"}
    st.session_state["vd_day"]   = dmap.get(dt, "SELECTIVE ▶")
    st.session_state["vd_focus"] = s(parsed.get("topFocus",""))
    st.session_state["vd_risk"]  = s(parsed.get("riskNote",""))
    # News + Focus stored separately
    if parsed.get("news"):        st.session_state["brief_news"]  = parsed["news"]
    if parsed.get("companiesInFocus"): st.session_state["brief_focus"] = parsed["companiesInFocus"]

def render():
    init_db()

    # Init session state
    for k,v in [("brief_news",[]),("brief_focus",[]),("brief_orders",[])]:
        if k not in st.session_state: st.session_state[k] = v

    # ── Header ────────────────────────────────────────────────
    c1,c2 = st.columns([3,1])
    with c1:
        st.markdown(f"""<div style="background:linear-gradient(135deg,#1E40AF,#7C3AED);border-radius:12px;padding:14px 20px;margin-bottom:8px">
        <div style="font-size:10px;color:rgba(255,255,255,0.6);letter-spacing:4px">SAK TRADING</div>
        <div style="font-size:20px;font-weight:800;color:#fff">Morning Brief</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.6)">{date.today().strftime('%A, %d %B %Y')}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        sel_date = st.date_input("Date", value=date.today(), label_visibility="collapsed")
        if st.button("📂 Load", use_container_width=True):
            saved = load_brief(sel_date.isoformat())
            if saved:
                set_state(saved)
                st.rerun()
                st.session_state["brief_news"]   = saved.get("news",[])
                st.session_state["brief_focus"]  = saved.get("companiesInFocus",[])
                st.session_state["brief_orders"] = saved.get("orders",[])
                st.session_state["brief_date_loaded"] = sel_date.isoformat()
                st.rerun()
            else:
                st.warning("No saved brief for this date.")

    # ── Ticker strip ──────────────────────────────────────────
    nc = st.session_state.get("m_nc","—") or "—"
    bn = st.session_state.get("m_bn","—") or "—"
    vx = st.session_state.get("m_vix","—") or "—"
    gd = st.session_state.get("m_gdiff","—") or "—"
    cr = st.session_state.get("m_crude","") or ""
    ir = st.session_state.get("m_inr","") or ""
    sp = st.session_state.get("m_sp","—") or "—"

    gift_display = (gd if gd.startswith(("+","-")) else "+"+gd) if gd not in ("—","") else "—"

    html = '<div style="background:#1E293B;border-radius:8px;padding:8px 16px;display:flex;gap:20px;overflow-x:auto;margin-bottom:10px">'
    for lbl,val,col in [
        ("NIFTY",    nc,                                    tcolor(st.session_state.get("m_nch",""))),
        ("BK NIFTY", bn,                                    tcolor(st.session_state.get("m_bnch",""))),
        ("VIX",      vx,                                    AMBER),
        ("GIFT",     gift_display,                          tcolor(gd)),
        ("CRUDE",    ("$"+cr) if cr else "—",               AMBER),
        ("USD/INR",  ("₹"+ir) if ir else "—",              "#67E8F9"),
        ("S&P 500",  sp,                                    tcolor(sp)),
    ]:
        html += f'<div style="min-width:60px;text-align:center"><div style="font-size:8px;color:#64748B;letter-spacing:2px">{lbl}</div><div style="font-size:13px;font-weight:700;color:{col}">{val}</div></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    # ── Auto Populate ─────────────────────────────────────────
    ca,cb = st.columns([1,1])
    with ca:
        if st.button("⚡ AUTO POPULATE — Fetch Live Data", type="primary", use_container_width=True):
            with st.spinner("Fetching market data... (30-60 sec)"):
                parsed, err = fetch_data()
            if parsed:
                set_state(parsed)
                st.success("✅ All fields populated!")
                st.rerun()
            else:
                st.error(f"❌ {err}")
    with cb:
        with st.expander("📋 Or paste JSON manually"):
            paste = st.text_area("JSON", height=80, key="paste_json")
            if st.button("LOAD", type="primary", use_container_width=True):
                try:
                    clean = paste.replace("```json","").replace("```","").strip()
                    parsed = json.loads(clean[clean.find("{"):clean.rfind("}")+1])
                    set_state(parsed)
                    st.success("✅ Loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Invalid JSON: {e}")

    # ── Tabs ──────────────────────────────────────────────────
    tabs = st.tabs(["📊 MARKET","📐 LEVELS","💰 FLOWS","🔄 SECTORS",
                    "🔭 FOCUS","📰 NEWS","🎯 WATCHLIST","📋 ORDERS","📖 POSITIONS","🏁 VERDICT","🧭 SITUATION"])

    # MARKET
    with tabs[0]:
        st.markdown(card("Yesterday's Close", BLUE), unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        c1.text_input("Nifty 50",   key="m_nc")
        c2.text_input("Chg %",      key="m_nch")
        c3.text_input("Bank Nifty", key="m_bn")
        c4.text_input("Chg %",      key="m_bnch")
        c5,c6 = st.columns([1,3])
        c5.text_input("VIX", key="m_vix")
        c6.checkbox("⚡ Expiry Day", key="m_exp")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(card("Pre-Market Cues", TEAL), unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        c1.text_input("GIFT Nifty",    key="m_gift")
        c2.text_input("vs Close (pts)",key="m_gdiff")
        c3.text_input("Crude ($/bbl)", key="m_crude")
        c4.text_input("USD/INR",       key="m_inr")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(card("Global Overnight", PURPLE), unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        c1.text_input("S&P 500", key="m_sp")
        c2.text_input("Nasdaq",  key="m_nq")
        c3.text_input("Nikkei",  key="m_nk")
        st.markdown("</div>", unsafe_allow_html=True)

    # LEVELS
    with tabs[1]:
        st.markdown(card("Nifty 50 Key Levels", TEAL), unsafe_allow_html=True)
        st.text_input("Pivot", key="l_piv")
        c1,c2 = st.columns(2)
        c1.text_input("🟢 R2 — Strong Resistance", key="l_r2")
        c2.text_input("🟢 R1 — Resistance",        key="l_r1")
        c3,c4 = st.columns(2)
        c3.text_input("🔴 S1 — Support",        key="l_s1")
        c4.text_input("🔴 S2 — Strong Support", key="l_s2")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(card("Bank Nifty Levels", BLUE), unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        c1.text_input("🟢 Resistance", key="l_bnr")
        c2.text_input("🔴 Support",    key="l_bns")
        st.markdown("</div>", unsafe_allow_html=True)
        st.info("📌 No trades inside Pivot ±30 pts on expiry. Wait for 15-min candle close.")

    # FLOWS
    with tabs[2]:
        st.markdown(card("Institutional Flows", AMBER), unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        c1.text_input("FII Cash (₹ Cr)",    key="f_fii")
        c2.text_input("DII Cash (₹ Cr)",    key="f_dii")
        c3.text_input("FII Index Fut (net)", key="f_fut")
        fii = st.session_state.get("f_fii","") or ""
        dii = st.session_state.get("f_dii","") or ""
        if fii and dii:
            fc = TEAL if not fii.lstrip("+").startswith("-") else RED
            dc = TEAL if not dii.lstrip("+").startswith("-") else RED
            st.markdown(f"""<div style="display:flex;gap:12px;margin:8px 0">
                <div style="flex:1;background:{fc}15;border:1px solid {fc}44;border-radius:8px;padding:10px;text-align:center">
                <div style="font-size:9px;color:{fc};letter-spacing:2px">FII</div>
                <div style="font-size:18px;font-weight:800;color:{fc}">₹{fii} Cr</div></div>
                <div style="display:flex;align-items:center;font-size:20px;color:#9CA3AF">⇄</div>
                <div style="flex:1;background:{dc}15;border:1px solid {dc}44;border-radius:8px;padding:10px;text-align:center">
                <div style="font-size:9px;color:{dc};letter-spacing:2px">DII</div>
                <div style="font-size:18px;font-weight:800;color:{dc}">₹{dii} Cr</div></div>
            </div>""", unsafe_allow_html=True)
        st.text_area("Flow Interpretation", key="f_note", height=100,
            placeholder="e.g. FII turned net buyers. DIIs absorbing strongly...")
        st.markdown("</div>", unsafe_allow_html=True)

    # SECTORS
    with tabs[3]:
        st.markdown(card("Sector Rotation", PURPLE), unsafe_allow_html=True)
        c1,c2 = st.columns(2)
        c1.text_input("Leading Today 🟢", key="s_lead")
        c2.text_input("Lagging Today 🔴", key="s_lag")
        st.text_area("Rotation Note", key="s_note", height=80)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(card("Quick Sector Rating ⚡", PURPLE), unsafe_allow_html=True)
        opts = ["▲ Strong","→ Neutral","▼ Weak"]
        for label, key in [("🏦 Nifty Bank","sector_bank"),("💻 Nifty IT","sector_it"),
            ("⚡ Nifty Energy / OMC","sector_energy"),("💊 Nifty Pharma","sector_pharma"),
            ("⚙️ Nifty Metal","sector_metal"),("🛒 Nifty FMCG","sector_fmcg"),
            ("🚗 Nifty Auto","sector_auto"),("🏗️ Nifty Realty","sector_realty")]:
            cur = st.session_state.get(f"sr_{key}","→ Neutral")
            if cur not in opts: cur = "→ Neutral"
            cl,cr2 = st.columns([2,3])
            cl.markdown(f"<div style='padding-top:6px;font-size:13px'>{label}</div>", unsafe_allow_html=True)
            cr2.radio(label, opts, index=opts.index(cur), horizontal=True,
                      label_visibility="collapsed", key=f"sr_{key}")
        st.markdown("</div>", unsafe_allow_html=True)

    # FOCUS
    with tabs[4]:
        focus_list = st.session_state.get("brief_focus",[])
        if focus_list:
            cats = {}
            for f in focus_list: cats[f.get("category","Other")] = cats.get(f.get("category","Other"),0)+1
            bull = sum(1 for f in focus_list if f.get("bias")=="Bullish")
            bear = sum(1 for f in focus_list if f.get("bias")=="Bearish")
            badges = " ".join([f'<span style="background:{FOCUS_CAT_COLORS.get(c,GRAY)}22;color:{FOCUS_CAT_COLORS.get(c,GRAY)};padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700">{c} {n}</span>' for c,n in cats.items()])
            st.markdown(f"{badges} &nbsp; 🟢{bull} 🔴{bear}", unsafe_allow_html=True)
            st.markdown("---")
        for i,f in enumerate(focus_list):
            cc = FOCUS_CAT_COLORS.get(f.get("category","Other"),GRAY)
            bc = TEAL if f.get("bias")=="Bullish" else RED if f.get("bias")=="Bearish" else GRAY
            be = "🟢" if f.get("bias")=="Bullish" else "🔴" if f.get("bias")=="Bearish" else "⚪"
            st.markdown(f"""<div style="background:#fff;border:1px solid {cc}33;border-left:4px solid {cc};border-radius:8px;padding:14px;margin-bottom:10px">
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap">
                <span style="font-size:15px;font-weight:800">{sv(f.get('stock',''))}</span>
                <span style="background:{cc}22;color:{cc};padding:2px 10px;border-radius:12px;font-size:10px;font-weight:700">{sv(f.get('category',''))}</span>
                <span style="background:{bc}22;color:{bc};padding:2px 10px;border-radius:12px;font-size:10px;font-weight:700">{be} {sv(f.get('bias',''))}</span></div>
                <div style="font-size:12px;font-weight:700;color:#1E293B;line-height:1.5;margin-bottom:6px">{sv(f.get('headline',''))}</div>
                {"<div style='font-size:11px;color:#6B7280;background:#F8FAFC;border-radius:6px;padding:6px 10px;margin-bottom:6px'>"+sv(f.get('detail',''))+"</div>" if f.get('detail') else ""}
                {"<div style='font-size:11px;font-weight:600;color:"+bc+";background:"+bc+"15;border-left:3px solid "+bc+";padding:6px 10px;border-radius:0 6px 6px 0'>📈 "+sv(f.get('tradeNote',''))+"</div>" if f.get('tradeNote') else ""}
            </div>""", unsafe_allow_html=True)
            if st.button("🗑 Remove", key=f"df_{i}"):
                focus_list.pop(i); st.session_state["brief_focus"]=focus_list; st.rerun()
        with st.expander("+ Add Company in Focus"):
            c1,c2 = st.columns(2)
            fs = c1.text_input("Stock", key="f_stock")
            fb = c2.selectbox("Bias",["Bullish","Neutral","Bearish"],key="f_bias")
            fc2 = st.selectbox("Category", list(FOCUS_CAT_COLORS.keys()), key="f_cat")
            fh = st.text_input("Headline", key="f_head")
            fd = st.text_area("Detail", key="f_detail", height=60)
            ft = st.text_area("Trade Note", key="f_trade", height=60)
            if st.button("+ ADD", type="primary"):
                if fs and fh:
                    focus_list.append({"stock":fs.upper(),"category":fc2,"headline":fh,"detail":fd,"bias":fb,"tradeNote":ft})
                    st.session_state["brief_focus"]=focus_list; st.rerun()

    # NEWS
    with tabs[5]:
        news_list = st.session_state.get("brief_news",[])
        for i,n in enumerate(news_list):
            tc = NEWS_TAG_COLORS.get(n.get("tag","Neutral"),GRAY)
            st.markdown(f"""<div style="background:#fff;border:1px solid {tc}33;border-left:4px solid {tc};border-radius:8px;padding:12px;margin-bottom:8px">
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:6px">
                {"<span style='font-size:13px;font-weight:800;background:#F1F5F9;padding:2px 10px;border-radius:4px'>"+sv(n.get('stock',''))+"</span>" if n.get('stock') else ""}
                <span style="background:{tc}22;color:{tc};padding:2px 8px;border-radius:12px;font-size:10px;font-weight:700">{sv(n.get('tag','')).upper()}</span></div>
                <div style="font-size:12px;font-weight:600;color:#374151;line-height:1.5">{sv(n.get('headline',''))}</div>
                {"<div style='font-size:11px;color:#6B7280;background:#F8FAFC;border-radius:4px;padding:5px 8px;margin-top:4px'>→ "+sv(n.get('note',''))+"</div>" if n.get('note') else ""}
            </div>""", unsafe_allow_html=True)
            if st.button("🗑", key=f"dn_{i}"):
                news_list.pop(i); st.session_state["brief_news"]=news_list; st.rerun()
        with st.expander("+ Add News"):
            c1,c2 = st.columns(2)
            ns = c1.text_input("Stock", key="n_stock")
            nt = c2.selectbox("Tag", list(NEWS_TAG_COLORS.keys()), key="n_tag")
            nh = st.text_input("Headline", key="n_head")
            nn = st.text_area("Note", key="n_note", height=60)
            if st.button("+ ADD NEWS", type="primary"):
                if nh:
                    news_list.append({"stock":ns.upper(),"headline":nh,"tag":nt,"note":nn})
                    st.session_state["brief_news"]=news_list; st.rerun()

    # WATCHLIST
    with tabs[6]:
        st.markdown(card("Setup Count by Strategy", BLUE), unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        for col,strat,key in [(c1,"VCP","wl_vcp"),(c2,"SVRO","wl_svro"),(c3,"EP","wl_ep"),(c4,"REVERSAL","wl_rev")]:
            sc = STRAT_COLORS.get(strat,GRAY)
            col.markdown(f"<div style='background:{sc}15;border:2px solid {sc}33;border-radius:8px;padding:8px;text-align:center;margin-bottom:4px'><div style='font-size:9px;color:{sc};font-weight:700;letter-spacing:2px'>{strat}</div></div>", unsafe_allow_html=True)
            col.text_input("", key=key, label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(card("Top Setups Today", BLUE), unsafe_allow_html=True)
        st.text_area("Setups", key="wl_notes", height=180,
            placeholder="1. STOCK A — VCP, pivot 450, stop 425, target 520\n2. STOCK B — SVRO, 9:20 breakout above 230")
        st.markdown("</div>", unsafe_allow_html=True)
        st.info("📌 VCP/EP: enter after 9:20 AM candle. SVRO: alert at 9:20. No chasing beyond 2%.")

    # ORDERS
    with tabs[7]:
        orders = st.session_state.get("brief_orders",[])
        for i,o in enumerate(orders):
            tc = STRAT_COLORS.get(o.get("strategy",""),GRAY)
            bc = TEAL if o.get("type")=="BUY" else RED if o.get("type")=="SELL" else AMBER
            st.markdown(f"""<div style="background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:12px;margin-bottom:10px">
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap">
                <span style="font-size:15px;font-weight:800">{sv(o.get('stock',''))}</span>
                <span style="background:{bc}22;color:{bc};padding:2px 10px;border-radius:12px;font-size:10px;font-weight:700">{sv(o.get('type',''))}</span>
                <span style="background:{tc}15;color:{tc};padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700">{sv(o.get('strategy',''))}</span>
                {"<span style='font-size:10px;font-weight:700;color:"+(TEAL if float(sv(o.get('rr','0')) or 0)>=2 else AMBER)+"'>1:"+sv(o.get('rr',''))+"R</span>" if o.get('rr') else ""}</div>
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">
                {"".join([f'<div style="background:{bg};border-radius:6px;padding:6px;text-align:center"><div style="font-size:9px;color:#6B7280">{lbl}</div><div style="font-size:13px;font-weight:700;color:{fc}">{sv(val) or chr(8212)}</div></div>' for lbl,val,fc,bg in [('Entry',o.get('entry'),BLUE,'#EFF6FF'),('Stop',o.get('sl'),RED,'#FEE2E2'),('Target',o.get('target'),TEAL,'#DCFCE7'),('Qty',o.get('qty'),GRAY,'#F8FAFC')]])}</div>
                {"<div style='font-size:11px;color:#6B7280;background:#F8FAFC;border-radius:4px;padding:5px 8px;margin-top:6px'>→ "+sv(o.get('note',''))+"</div>" if o.get('note') else ""}
            </div>""", unsafe_allow_html=True)
            if st.button("🗑", key=f"do_{i}"):
                orders.pop(i); st.session_state["brief_orders"]=orders; st.rerun()
        with st.expander("+ Plan New Order"):
            c1,c2 = st.columns(2)
            os2 = c1.text_input("Stock", key="o_stock")
            ostr = c2.selectbox("Strategy", list(STRAT_COLORS.keys()), key="o_strat")
            c3,c4 = st.columns(2)
            ot = c3.selectbox("Type",["BUY","SELL","SL-M","TARGET"],key="o_type")
            oq = c4.text_input("Qty",key="o_qty")
            c5,c6,c7 = st.columns(3)
            oe = c5.text_input("Entry ₹",key="o_entry")
            osl = c6.text_input("Stop ₹",key="o_sl")
            otgt = c7.text_input("Target ₹",key="o_target")
            if oe and osl and otgt:
                try:
                    e,s2,t2 = float(oe),float(osl),float(otgt)
                    risk=abs(e-s2); reward=abs(t2-e); rr=reward/risk
                    rc = TEAL if rr>=2 else AMBER
                    st.markdown(f"""<div style="display:flex;gap:10px;background:#F8FAFC;border-radius:8px;padding:10px;margin:4px 0">
                        <div style="flex:1;text-align:center"><div style="font-size:9px;color:#6B7280">RISK</div><div style="font-size:18px;font-weight:800;color:{RED}">₹{risk:.1f}</div></div>
                        <div style="flex:1;text-align:center"><div style="font-size:9px;color:#6B7280">REWARD</div><div style="font-size:18px;font-weight:800;color:{TEAL}">₹{reward:.1f}</div></div>
                        <div style="flex:1;text-align:center;background:{rc}15;border-radius:6px"><div style="font-size:9px;color:#6B7280">R:R</div><div style="font-size:18px;font-weight:800;color:{rc}">1:{rr:.1f}</div></div>
                    </div>""", unsafe_allow_html=True)
                except: pass
            on = st.text_area("Note",key="o_note",height=60)
            if st.button("+ ADD ORDER", type="primary"):
                if os2 and oe:
                    try: e,s2,t2=float(oe),float(osl or 0),float(otgt or 0); rr=round(abs(t2-e)/abs(e-s2),1) if s2 and abs(e-s2)>0 else None
                    except: rr=None
                    orders.append({"stock":os2.upper(),"strategy":ostr,"type":ot,"qty":oq,"entry":oe,"sl":osl,"target":otgt,"rr":rr,"note":on})
                    st.session_state["brief_orders"]=orders; st.rerun()

    # POSITIONS
    with tabs[8]:
        st.markdown(card("Open Position Book", TEAL), unsafe_allow_html=True)
        st.text_area("Positions", key="pos_book", height=150,
            placeholder="STOCK X — Entry 340, Stop 320, CMP 355, +1.5R\nSTOCK Y — Entry 180, Stop 170, CMP 176, -0.4R")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(card("Risk Budget", TEAL), unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        c1.text_input("Max Heat %",      key="pos_max")
        c2.text_input("Deployed Heat %", key="pos_dep")
        c3.text_input("R Remaining",     key="pos_r")
        try:
            mh=float(st.session_state.get("pos_max","6") or 6)
            dh=float(st.session_state.get("pos_dep","0") or 0)
            pct=min(100,dh/mh*100); bc2=RED if pct>90 else AMBER if pct>65 else TEAL
            st.markdown(f"""<div style="background:#E5E7EB;border-radius:10px;height:10px;overflow:hidden;margin:6px 0">
                <div style="width:{pct}%;height:100%;background:{bc2};border-radius:10px"></div></div>
                <div style="font-size:10px;color:#6B7280">{pct:.0f}% of max heat deployed</div>""", unsafe_allow_html=True)
        except: pass
        st.text_area("Notes", key="pos_notes", height=80)
        st.markdown("</div>", unsafe_allow_html=True)

    # VERDICT
    with tabs[9]:
        st.markdown(card("Day Type", GRAY), unsafe_allow_html=True)
        dopts=["HUNT ▶","SELECTIVE ▶","SIT ▶"]
        dcolors={"HUNT ▶":TEAL,"SELECTIVE ▶":AMBER,"SIT ▶":RED}
        cur_day = st.session_state.get("vd_day","SELECTIVE ▶")
        if cur_day not in dopts: cur_day="SELECTIVE ▶"
        sel=st.radio("Day Type",dopts,index=dopts.index(cur_day),horizontal=True,
                     label_visibility="collapsed",key="vd_day")
        dc=dcolors.get(sel,AMBER)
        msgs={"HUNT ▶":"🟢 Green light. Setups are clean. Execute your process with full size.",
              "SELECTIVE ▶":"🟡 Yellow flag. One or two setups max. Size down 50%.",
              "SIT ▶":"🔴 Red light. No new trades. Protect capital. There's always tomorrow."}
        st.markdown(f"""<div style="background:{dc}15;border:2px solid {dc}44;border-radius:8px;
            padding:12px 16px;font-size:12px;color:{dc};font-weight:600;line-height:1.7;margin:8px 0">
            {msgs.get(sel,'')}</div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown(card("Focus & Reminders", GRAY), unsafe_allow_html=True)
        st.text_area("Today's Focus",  key="vd_focus", height=90)
        st.text_area("Risk Reminders", key="vd_risk",  height=90)
        st.markdown("</div>", unsafe_allow_html=True)

        # Summary
        fii2 = st.session_state.get("f_fii","") or ""
        fii_c = TEAL if fii2 and not fii2.lstrip("+").startswith("-") else RED
        cols=st.columns(3)
        for i,(lbl,val,color) in enumerate([
            ("NIFTY",          st.session_state.get("m_nc","—") or "—",   tcolor(st.session_state.get("m_nch",""))),
            ("VIX",            st.session_state.get("m_vix","—") or "—",  AMBER),
            ("GIFT",           gift_display,                                tcolor(st.session_state.get("m_gdiff",""))),
            ("FII CASH",       fii2 or "—",                                fii_c),
            ("IN FOCUS",       str(len(st.session_state.get("brief_focus",[]))), TEAL),
            ("ORDERS PENDING", str(len(st.session_state.get("brief_orders",[]))), BLUE),
        ]):
            with cols[i%3]:
                st.markdown(f"""<div style="background:#1E293B;border-radius:8px;padding:12px;margin-bottom:8px;text-align:center">
                <div style="font-size:8px;color:#475569;letter-spacing:2px;margin-bottom:4px">{lbl}</div>
                <div style="font-size:18px;font-weight:800;color:{color}">{val}</div></div>""", unsafe_allow_html=True)


    # SITUATION
    with tabs[10]:
        from datetime import date as _d
        _today = _d.today().strftime("%d-%m-%Y")
        st.markdown(f"""<div style="background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:14px;margin-bottom:10px">
<div style="display:flex;align-items:center;gap:7px;border-bottom:1px solid #F3F4F6;padding-bottom:7px;margin-bottom:10px">
<span style="width:3px;height:14px;background:#7C3AED;border-radius:2px;display:inline-block"></span>
<span style="font-size:11px;font-weight:700;color:#374151">Situational Awareness — #SA_Notes</span>
<span style="font-size:10px;color:#6B7280;margin-left:auto">📅 {_today}</span>
</div>""", unsafe_allow_html=True)

        # 1. Long-Term
        _lt_opts = ["No change. Early Bull Market.","No change. Bull Market.","Bull Market Under Doubt.","Wait and Watch — Transition Phase.","Possible Capitulation Phase.","Early Bear Market.","Bear Market — Avoid Longs.","Recovery Phase.","Stage 1 Consolidation."]
        _lt_cur = st.session_state.get("sit_lt", _lt_opts[0])
        if _lt_cur not in _lt_opts: _lt_cur = _lt_opts[0]
        st.markdown('<div style="background:#F0FDF4;border-left:4px solid #10B981;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:8px"><div style="font-size:10px;font-weight:700;color:#10B981;letter-spacing:1px;margin-bottom:6px">1) LONG-TERM</div>', unsafe_allow_html=True)
        st.selectbox("LT", _lt_opts, index=_lt_opts.index(_lt_cur), key="sit_lt", label_visibility="collapsed")
        st.text_area("LT notes", key="sit_lt_note", height=55, placeholder="No change. Early bull market.", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

        # 2. Short-Term
        _st_opts = ["Positive bias — Bull swing in progress.","Positive bias — Follow-through expected.","Cautiously positive — Wait for confirmation.","Reactive — No clear bias, trade-by-trade.","Choppy — Limited participation, selective.","Choppy — One step forward, two steps back.","Neutral — Wait and watch.","Cautiously bearish — Stay defensive.","Bearish — Weakness continuing."]
        _st_cur = st.session_state.get("sit_st", _st_opts[3])
        if _st_cur not in _st_opts: _st_cur = _st_opts[3]
        st.markdown('<div style="background:#EFF6FF;border-left:4px solid #3B82F6;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:8px"><div style="font-size:10px;font-weight:700;color:#3B82F6;letter-spacing:1px;margin-bottom:6px">2) SHORT-TERM</div>', unsafe_allow_html=True)
        st.selectbox("ST", _st_opts, index=_st_opts.index(_st_cur), key="sit_st", label_visibility="collapsed")
        _mc1, _mc2 = st.columns([1,3])
        _mc1.text_input("MBMV2.0 Volume Reading", key="sit_mbmv", placeholder="e.g. 0.44", label_visibility="visible")
        _mbmv_opts = ["— Volume reading —","< 0.30 — Very low. Choppy.","0.30–0.45 — Low. Stay selective.","0.45–0.60 — Improving.","0.60–0.80 — Decent. Tradeable.","0.80–1.00 — Good participation.","1.00+ — High. Bull swing confirmed.","High but one-off (MSCI/event)."]
        _mbmv_cur = st.session_state.get("sit_mbmv_interp", _mbmv_opts[0])
        if _mbmv_cur not in _mbmv_opts: _mbmv_cur = _mbmv_opts[0]
        _mc2.selectbox("MBMV interp", _mbmv_opts, index=_mbmv_opts.index(_mbmv_cur), key="sit_mbmv_interp", label_visibility="collapsed")
        st.text_area("ST notes", key="sit_st_note", height=90, placeholder="e.g. Choppiness continues. Volume at 0.44. US markets strong but Asian mixed...", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

        # 3. Events
        st.markdown('<div style="background:#FEF9C3;border-left:4px solid #F59E0B;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:8px"><div style="font-size:10px;font-weight:700;color:#F59E0B;letter-spacing:1px;margin-bottom:6px">3) KEY EVENTS & CATALYSTS</div>', unsafe_allow_html=True)
        st.multiselect("Events", ["Iran-US deal — unresolved","Iran-US deal — resolved ✅","US Fed meeting pending","US Fed — rates held","RBI policy meeting","MSCI rebalancing","Earnings season active","Earnings season over","Tax reform announcements","Weekly expiry (Thu)","Monthly expiry","Holiday — short week","Crude oil spike","US-China tensions"], default=[], key="sit_ev_presets", label_visibility="collapsed")
        st.text_area("Event details", key="sit_events", height=70, placeholder="Additional event context...", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

        # 4. Strategy
        _stance_opts = ["All guns blazing — Aggressive. Full size.","Aggressive — Favor all setups.","Positive bias — Standard approach.","Trade-by-trade — Decide on each setup.","Reactive — Let market decide.","Selective — 1-2 high conviction only.","Light exposure — Small size.","Wait and watch — Observe first.","Sit out — No new trades today.","Defensive — Trail stops."]
        _stance_cur = st.session_state.get("sit_stance", _stance_opts[3])
        if _stance_cur not in _stance_opts: _stance_cur = _stance_opts[3]
        _pri_opts = ["EP Day 1 + Momentum Burst","Post-EP + Momentum Burst","VCP Breakouts — Primary","SVRO — Primary","Reversal setups","Momentum Suppression","Gap-down reversal setups","Parabolic longs + breakouts","All bread-and-butter setups","Stock-specific — ignore market","No specific priority — reactive"]
        _pri_cur = st.session_state.get("sit_priority", _pri_opts[0])
        if _pri_cur not in _pri_opts: _pri_cur = _pri_opts[0]
        st.markdown('<div style="background:#FDF4FF;border-left:4px solid #7C3AED;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:8px"><div style="font-size:10px;font-weight:700;color:#7C3AED;letter-spacing:1px;margin-bottom:6px">4) STRATEGY FOR TODAY</div>', unsafe_allow_html=True)
        st.selectbox("Stance", _stance_opts, index=_stance_opts.index(_stance_cur), key="sit_stance", label_visibility="collapsed")
        st.selectbox("Priority", _pri_opts, index=_pri_opts.index(_pri_cur), key="sit_priority", label_visibility="collapsed")
        st.text_area("Strategy notes", key="sit_strategy", height=90, placeholder="e.g. Gap-down Monday favorite setup. Bring to risk-free quickly. All setups on table...", label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

        # Preview
        _lt_v=st.session_state.get("sit_lt",""); _lt_n=st.session_state.get("sit_lt_note","")
        _st_v=st.session_state.get("sit_st",""); _st_n=st.session_state.get("sit_st_note","")
        _mbmv_v=st.session_state.get("sit_mbmv",""); _mbmv_i=st.session_state.get("sit_mbmv_interp","")
        _ev_p=st.session_state.get("sit_ev_presets",[]); _ev_n=st.session_state.get("sit_events","")
        _stance_v=st.session_state.get("sit_stance",""); _pri_v=st.session_state.get("sit_priority","")
        _str_n=st.session_state.get("sit_strategy","")

        if _lt_v or _st_n or _str_n:
            st.markdown("---")
            _p1, _p2 = st.columns([1,4])
            with _p1:
                if st.button("🖨️ Print / Save PDF", key="sit_print", use_container_width=True):
                    st.session_state["sit_show_print"] = True
            _txt = f"#SituationalAwareness ({_today})\n\n"
            if _lt_v: _txt += f"1) Long-Term: {_lt_v}{(' '+_lt_n) if _lt_n else ''}\n\n"
            _st_full = _st_v
            if _mbmv_v: _st_full += f" Volume at {_mbmv_v}."
            if _mbmv_i and "—" not in _mbmv_i: _st_full += f" {_mbmv_i}"
            if _st_n: _st_full += f"\n\n{_st_n}"
            if _st_full: _txt += f"2) Short-Term: {_st_full}\n\n"
            _ev_full = ("; ".join(_ev_p) + ". " if _ev_p else "") + _ev_n
            if _ev_full.strip(): _txt += f"3) Events: {_ev_full.strip()}\n\n"
            _str_full = (_stance_v + "\n\n" if _stance_v else "") + ("Priority: " + _pri_v + "\n\n" if _pri_v else "") + _str_n
            if _str_full.strip(): _txt += f"4) Strategy: {_str_full.strip()}"
            st.code(_txt, language=None)

        if st.session_state.get("sit_show_print"):
            _print_html = f"""<!DOCTYPE html><html><head><title>SA {_today}</title>
<style>body{{font-family:Georgia,serif;max-width:700px;margin:40px auto;padding:20px;color:#1a1a1a;line-height:1.8}}
h2{{color:#7C3AED;border-bottom:2px solid #7C3AED;padding-bottom:8px}}
.section{{margin:20px 0;padding:14px;border-radius:8px}}
.lt{{background:#f0fdf4;border-left:4px solid #10B981}}.st{{background:#eff6ff;border-left:4px solid #3B82F6}}
.ev{{background:#fef9c3;border-left:4px solid #F59E0B}}.str{{background:#fdf4ff;border-left:4px solid #7C3AED}}
.label{{font-size:11px;font-weight:700;letter-spacing:2px;margin-bottom:8px}}
.lt .label{{color:#10B981}}.st .label{{color:#3B82F6}}.ev .label{{color:#F59E0B}}.str .label{{color:#7C3AED}}
@media print{{body{{margin:20px}}button{{display:none}}}}</style></head><body>
<h2>#SituationalAwareness ({_today})</h2>
{('<div class="section lt"><div class="label">1) LONG-TERM</div><p>'+_lt_v+(' '+_lt_n if _lt_n else '')+'</p></div>') if _lt_v else ''}
{('<div class="section st"><div class="label">2) SHORT-TERM</div><p>'+_st_v+('  Volume: '+_mbmv_v if _mbmv_v else '')+('<br><br>'+_st_n if _st_n else '')+'</p></div>') if _st_v else ''}
{('<div class="section ev"><div class="label">3) EVENTS</div><p>'+_ev_full+'</p></div>') if _ev_full.strip() else ''}
{('<div class="section str"><div class="label">4) STRATEGY</div><p>'+_stance_v+('<br><br>Priority: '+_pri_v if _pri_v else '')+('<br><br>'+_str_n if _str_n else '')+'</p></div>') if _stance_v or _str_n else ''}
<script>window.print();</script></body></html>"""
            import base64 as _b64
            _b64_html = _b64.b64encode(_print_html.encode()).decode()
            st.markdown(f'<a href="data:text/html;base64,{_b64_html}" download="SA_{_today}.html" target="_blank"><button style="background:#7C3AED;color:white;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px">⬇ Download & Print</button></a>', unsafe_allow_html=True)
            st.session_state["sit_show_print"] = False

        st.markdown("</div>", unsafe_allow_html=True)


    # ── Save ──────────────────────────────────────────────────
    st.markdown("---")
    _,sc2,_ = st.columns([2,1,2])
    with sc2:
        if st.button("💾 SAVE BRIEF", type="primary", use_container_width=True):
            data = {
                "niftyClose":st.session_state.get("m_nc",""), "niftyChange":st.session_state.get("m_nch",""),
                "bnClose":st.session_state.get("m_bn",""), "bnChange":st.session_state.get("m_bnch",""),
                "vix":st.session_state.get("m_vix",""), "giftNifty":st.session_state.get("m_gift",""),
                "giftDiff":st.session_state.get("m_gdiff",""), "crude":st.session_state.get("m_crude",""),
                "usdinr":st.session_state.get("m_inr",""), "sp500":st.session_state.get("m_sp",""),
                "nasdaq":st.session_state.get("m_nq",""), "nikkei":st.session_state.get("m_nk",""),
                "niftyPivot":st.session_state.get("l_piv",""), "niftyR1":st.session_state.get("l_r1",""),
                "niftyR2":st.session_state.get("l_r2",""), "niftyS1":st.session_state.get("l_s1",""),
                "niftyS2":st.session_state.get("l_s2",""), "bnR1":st.session_state.get("l_bnr",""),
                "bnS1":st.session_state.get("l_bns",""), "fiiCash":st.session_state.get("f_fii",""),
                "diiCash":st.session_state.get("f_dii",""), "fiiIndexFut":st.session_state.get("f_fut",""),
                "flowNote":st.session_state.get("f_note",""), "leadingSector":st.session_state.get("s_lead",""),
                "laggingSector":st.session_state.get("s_lag",""), "sectorNote":st.session_state.get("s_note",""),
                "sector_bank":st.session_state.get("sr_sector_bank","→ Neutral"),
                "sector_it":st.session_state.get("sr_sector_it","→ Neutral"),
                "sector_energy":st.session_state.get("sr_sector_energy","→ Neutral"),
                "sector_pharma":st.session_state.get("sr_sector_pharma","→ Neutral"),
                "sector_metal":st.session_state.get("sr_sector_metal","→ Neutral"),
                "sector_fmcg":st.session_state.get("sr_sector_fmcg","→ Neutral"),
                "sector_auto":st.session_state.get("sr_sector_auto","→ Neutral"),
                "sector_realty":st.session_state.get("sr_sector_realty","→ Neutral"),
                "vcpCount":st.session_state.get("wl_vcp",""), "svroCount":st.session_state.get("wl_svro",""),
                "epCount":st.session_state.get("wl_ep",""), "reversalCount":st.session_state.get("wl_rev",""),
                "watchlistNotes":st.session_state.get("wl_notes",""),
                "dayType":st.session_state.get("vd_day","SELECTIVE ▶").replace(" ▶",""),
                "topFocus":st.session_state.get("vd_focus",""), "riskNote":st.session_state.get("vd_risk",""),
                "news":st.session_state.get("brief_news",[]),
                "companiesInFocus":st.session_state.get("brief_focus",[]),
                "orders":st.session_state.get("brief_orders",[]),
            }
            brief_date = st.session_state.get("brief_date_loaded", date.today().isoformat())
            save_brief(brief_date, data)
            st.success(f"Saved for {brief_date}")

    # ── Past briefs sidebar ───────────────────────────────────
    with st.sidebar:
        st.markdown("---")
        st.markdown("**📅 Past Briefs**")
        for row in list_briefs()[:10]:
            d2 = json.loads(row["data"] or "{}")
            dt = d2.get("dayType","—")
            if st.button(f"{row['brief_date']}  •  {dt}", key=f"pb_{row['brief_date']}"):
                set_state(d2)
                st.rerun()
                st.session_state["brief_news"]   = d2.get("news",[])
                st.session_state["brief_focus"]  = d2.get("companiesInFocus",[])
                st.session_state["brief_orders"] = d2.get("orders",[])
                st.session_state["brief_date_loaded"] = row["brief_date"]
                st.rerun()
