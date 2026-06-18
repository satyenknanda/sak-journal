# SAK Trading Journal — FY 2026-27

A clean, local trading journal app built with Streamlit + SQLite.

## Setup

### 1. Install Python dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Place your Excel file
Copy `Daily_P__FY26-27_.xlsx` into this folder (same level as `app.py`).

### 3. Run the app
```bash
# Option A: use the start script
chmod +x start.sh
./start.sh

# Option B: run directly
streamlit run app.py
```

App opens at **http://localhost:8501**

---

## Features (v1 — Trading Journal)

- **Trading Journal** — filterable table with live NSE prices (yfinance)
- **KPI strip** — Win Rate, Total P&L, Expectancy, Open/Closed counts
- **Add Trade** — full modal with 1R preview
- **Exit Trade** — modal with P&L and R-multiple preview
- **Excel re-sync** — sidebar button keeps Excel as master
- **Dark/Light theme** toggle

## V2 Roadmap
- Dashboard with equity curve & charts
- Daily Plan
- Position Sizing Calculator
- Strategy Dashboard
- Bell Curve (R-multiple distribution)

---

## File Structure
```
sak_journal/
├── app.py                  # Main entry point
├── start.sh                # One-click launcher
├── requirements.txt
├── journal.db              # SQLite (auto-created on first run)
├── Daily_P__FY26-27_.xlsx  # Your Excel master file
├── data/
│   ├── db.py               # DB schema, CRUD, Excel import
│   └── prices.py           # yfinance live price fetcher
├── components/
│   ├── kpi_strip.py        # KPI card row
│   └── trade_modals.py     # Add/Exit trade dialogs
└── pages/
    └── 02_journal.py       # Trading Journal page
```

## Notes
- Live prices are cached for 5 minutes to avoid rate limits
- SQLite DB is auto-created; Excel import runs on first launch
- Use "Re-sync from Excel" in sidebar to pull fresh data anytime
# sak-journal
