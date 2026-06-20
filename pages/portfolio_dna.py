import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data.db import get_journal_trades
from theme import *

def safe_float(v):
    try: return float(v or 0)
    except: return 0.0

def fmt_pnl(v):
    return f"{'+' if v>=0 else ''}₹{abs(v):,.0f}" if v>=0 else f"-₹{abs(v):,.0f}"

DNA_COLORS = ["#7C3AED","#EC4899","#10B981","#F59E0B","#3B82F6","#14B8A6",
              "#F97316","#06B6D4","#8B5CF6","#DC2626","#0D9488","#D97706"]


def render():
    st.markdown("## Portfolio DNA")
    st.caption("Sector / industry concentration across your current holdings — no built-in concentration-risk view existed before this.")

    trades = get_journal_trades()
    open_trades = [t for t in trades if t.get("status") == "OPEN"]

    if not open_trades:
        st.info("No open positions found — Portfolio DNA reflects currently open holdings.")
        return

    sector_map = _get_sector_map()

    rows = []
    total_value = 0.0
    for t in open_trades:
        ticker = (t.get("ticker") or "").upper().strip()
        qty = safe_float(t.get("qty"))
        price = safe_float(t.get("entry_price")) or safe_float(t.get("live_price"))
        value = qty * price
        total_value += value
        info = sector_map.get(ticker, {"sector": "Unclassified", "industry": "Unclassified", "niche": "Unclassified"})
        rows.append({
            "ticker": ticker, "value": value,
            "sector": info["sector"], "industry": info["industry"], "niche": info["niche"],
        })

    if total_value <= 0:
        st.info("Could not compute position values — check entry_price/qty fields on open trades.")
        return

    df = pd.DataFrame(rows)
    df["weight"] = df["value"] / total_value * 100

    unclassified_n = (df["sector"] == "Unclassified").sum()

    # ── KPI strip ────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("OPEN POSITIONS", f"{len(open_trades)}"), unsafe_allow_html=True)
    k2.markdown(kpi_card("SECTORS", f"{df['sector'].nunique()}"), unsafe_allow_html=True)
    k3.markdown(kpi_card("TOP SECTOR WEIGHT", f"{df.groupby('sector')['weight'].sum().max():.1f}%"), unsafe_allow_html=True)
    k4.markdown(kpi_card("UNCLASSIFIED TICKERS", f"{unclassified_n}",
                          color=AMBER if unclassified_n else TEAL), unsafe_allow_html=True)

    if unclassified_n:
        unclass_tickers = sorted(df[df["sector"]=="Unclassified"]["ticker"].unique())
        st.markdown(f"""<div style="background:{AMBER_BG};border:1px solid {AMBER_BORDER};border-radius:8px;
            padding:10px 14px;font-size:12px;color:{TEXT_BODY};margin:10px 0">
            ⚠️ {unclassified_n} ticker(s) not yet mapped: <b>{', '.join(unclass_tickers)}</b>.
            Add them to <code>SECTOR_SEED</code> in <code>pages/portfolio_dna.py</code> to classify.
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs: Niche / Industry / Sector ─────────────────────────────────
    tab_niche, tab_industry, tab_sector = st.tabs(["NICHE", "INDUSTRY", "SECTOR"])

    for tab, level in [(tab_niche, "niche"), (tab_industry, "industry"), (tab_sector, "sector")]:
        with tab:
            grp = df.groupby(level)["weight"].sum().sort_values(ascending=False)
            avg_weight = grp.mean() if len(grp) else 0

            colL, colR = st.columns([1, 1.3])
            with colL:
                st.markdown(section_label(f"{level.upper()} BREAKDOWN"))
                for i, (name, w) in enumerate(grp.items()):
                    color = DNA_COLORS[i % len(DNA_COLORS)]
                    st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
                        padding:7px 0;border-bottom:1px solid {BORDER_LIGHT}">
                        <div style="display:flex;align-items:center;gap:8px;font-size:13px;color:{TEXT_BODY}">
                            <span style="width:8px;height:8px;border-radius:50%;background:{color};display:inline-block"></span>
                            {name}
                        </div>
                        <span style="font-size:13px;font-weight:600;color:{TEXT_H}">{w:.1f}%</span>
                    </div>""", unsafe_allow_html=True)

            with colR:
                fig = go.Figure(go.Pie(
                    labels=grp.index.tolist(), values=grp.values.tolist(), hole=0.62,
                    marker=dict(colors=[DNA_COLORS[i % len(DNA_COLORS)] for i in range(len(grp))],
                                line=dict(color=CARD_BG, width=2)),
                    textinfo="none",
                    hovertemplate="%{label}<br>%{value:.1f}%<extra></extra>",
                ))
                fig.add_annotation(text=f"AVG WEIGHT<br><b style='font-size:22px'>{avg_weight:.1f}%</b><br>"
                                         f"<span style='font-size:10px;color:{TEXT_SUBTLE}'>{len(grp)} CATEGORIES</span>",
                                    showarrow=False, font=dict(size=11, color=TEXT_MUTED, family="Inter"))
                l = chart_layout(height=300)
                l["showlegend"] = False
                fig.update_layout(**l)
                st.plotly_chart(fig, use_container_width=True, key=f"dna_pie_{level}")

    # ── Theme / peer cards (sector-level grouping with peers) ───────────
    st.markdown(section_label("Theme Exposure & Peers"), unsafe_allow_html=True)
    sector_groups = df.groupby("sector")
    cards_per_row = 3
    sectors_list = list(sector_groups.groups.keys())
    for row_start in range(0, len(sectors_list), cards_per_row):
        cols = st.columns(cards_per_row)
        for j, sname in enumerate(sectors_list[row_start:row_start+cards_per_row]):
            sub = df[df["sector"] == sname]
            peers = sorted(sub["ticker"].unique())
            weight = sub["weight"].sum()
            industries = sub["industry"].unique()
            color = DNA_COLORS[sectors_list.index(sname) % len(DNA_COLORS)]
            with cols[j]:
                st.markdown(f"""<div style="background:{CARD_BG};border:1px solid {BORDER};border-top:3px solid {color};
                    border-radius:10px;padding:14px 16px;margin-bottom:12px;min-height:140px;box-shadow:{SHADOW_SM}">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start">
                        <div style="font-size:13px;font-weight:700;color:{TEXT_H};line-height:1.3">{sname}</div>
                        <div style="font-size:14px;font-weight:700;color:{color}">{weight:.1f}%</div>
                    </div>
                    <div style="font-size:10px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.05em;
                        margin:10px 0 4px;font-weight:600">PEERS</div>
                    <div style="font-size:12px;color:{TEXT_BODY}">{' · '.join(peers)}</div>
                    <div style="font-size:10px;color:{TEXT_SUBTLE};text-transform:uppercase;letter-spacing:0.05em;
                        margin:10px 0 2px;font-weight:600">INDUSTRY</div>
                    <div style="font-size:11px;color:{TEXT_MUTED};font-style:italic">{', '.join(industries)}</div>
                </div>""", unsafe_allow_html=True)


def _get_sector_map():
    """Static NSE sector/industry/niche seed for tickers seen in SAK's portfolio.
    Extend this dict as new tickers appear — key = NSE ticker symbol (uppercase)."""
    return SECTOR_SEED


# ── Seed mapping — extend as needed ─────────────────────────────────────
SECTOR_SEED = {
    "AXISBANK":   {"sector": "Financial Services", "industry": "Private Sector Bank Companies",   "niche": "Private Sector Bank"},
    "ICICIBANK":  {"sector": "Financial Services", "industry": "Private Sector Bank Companies",   "niche": "Private Sector Bank"},
    "CUB":        {"sector": "Financial Services", "industry": "Private Sector Bank Companies",   "niche": "Private Sector Bank"},
    "SBIN":       {"sector": "Financial Services", "industry": "Public Sector Bank Companies",    "niche": "Public Sector Bank"},
    "M&M":        {"sector": "Consumer Discretionary", "industry": "Passenger Cars & Utility Vehicles", "niche": "Passenger Cars"},
    "NH":         {"sector": "Healthcare",         "industry": "Hospital Companies",              "niche": "Hospitals"},
    "LENSKART":   {"sector": "Consumer Discretionary", "industry": "Speciality Retail Companies",  "niche": "Apparel Retail Chains"},
    "BEL":        {"sector": "Industrials",        "industry": "Aerospace & Defense Companies",   "niche": "Aerospace & Defense OEM"},
    "SUNPHARMA":  {"sector": "Healthcare",         "industry": "Pharmaceuticals Companies",       "niche": "Pharma - Formulators"},
    "SUVEN":      {"sector": "Healthcare",         "industry": "Pharmaceuticals Companies",       "niche": "Pharma - Formulators"},
    "HSCL":       {"sector": "Materials",          "industry": "Carbon Black Companies",          "niche": "Carbon Black"},
    "MANINDS":    {"sector": "Materials",          "industry": "Iron & Steel Products Companies", "niche": "Steel Tubes & Pipes"},
    "BELRISE":    {"sector": "Industrials",        "industry": "Auto Components & Equipment",     "niche": "Chassis & Metal Parts"},
    "ADANIPOWER": {"sector": "Utilities",          "industry": "Integrated Power Utilities Companies", "niche": "Integrated Utilities"},
    "TATATECH":   {"sector": "Information Technology", "industry": "IT Enabled Services Companies", "niche": "ER&D / Product Software"},
    "BLISSGVS":   {"sector": "Healthcare",         "industry": "Pharmaceuticals Companies",       "niche": "Pharma - Formulators"},
    "AEROFLEX":   {"sector": "Industrials",        "industry": "Industrial Products Companies",   "niche": "Stainless Steel Hoses"},
    "ACUTAAS":    {"sector": "Healthcare",         "industry": "Pharmaceuticals & Drugs",         "niche": "Specialty Chemicals - Pharma"},
    "GRANULES":   {"sector": "Healthcare",         "industry": "Pharmaceuticals Companies",       "niche": "Pharma - API/Formulators"},
    "FINCABLES":  {"sector": "Industrials",        "industry": "Cables - Electricals Companies",  "niche": "Cables & Wires"},
    "SYRMA":      {"sector": "Information Technology", "industry": "Consumer Electronics Companies", "niche": "Electronic Manufacturing Services"},
    "OIL":        {"sector": "Energy",             "industry": "Oil Exploration Companies",       "niche": "Oil & Gas E&P"},
    "MEDPLUS":    {"sector": "Healthcare",         "industry": "Speciality Retail Companies",     "niche": "Pharmacy Retail"},
}
