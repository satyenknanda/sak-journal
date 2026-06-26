# /trade-save

**Usage:** `/trade-save $TICKER`

Saves the most recent `/trade-analyze` output for $TICKER to the SAK Journal Supabase database.

Run this immediately after `/trade-analyze $TICKER` completes.

---

## INSTRUCTIONS

Parse the trade analysis output from this conversation and extract these fields:

```
ticker:              $TICKER (uppercase)
company_name:        from analysis
analysis_date:       today's date (YYYY-MM-DD)
setup:               from Agent 1 (VCP / REVERSAL / SVRO / EP / MARS / TS / None)
setup_confidence:    HIGH / MEDIUM / LOW
stage:               1 / 2 / 3 / 4
price_current:       current price ₹
price_entry:         entry trigger price ₹
price_stop:          stop loss price ₹ (wider of technical vs 2.5%)
price_t1:            T1 target ₹
price_t2:            T2 target ₹
price_t3:            T3 target ₹
pct_below_52w_high:  % below 52W high
risk_per_share:      entry - stop
position_size:       number of shares (Van Tharp)
position_value:      position_size × entry price
pct_of_portfolio:    position_value / 2500000 × 100
score_technical:     Agent 1 score /10
score_fundamental:   Agent 2 score /10
score_sentiment:     Agent 3 score /10
score_risk:          Agent 4 score /10
score_total:         weighted total /10
verdict:             STRONG BUY / BUY / WATCH / AVOID
bonde_match:         MATCH / NO / PARTIAL
bias:                Section 1 from SA format (full text)
volume_analysis:     Section 2 from SA format (full text)
events:              Section 3 from SA format (full text)
strategy:            Section 4 from SA format (full text)
full_report:         complete markdown output of /trade-analyze
```

Then run this JavaScript to POST to Supabase:

```javascript
const SUPABASE_URL = "https://dvfxkcjugpvvpijxgnow.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR2ZnhrY2p1Z3B2dnBpanhnbm93Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE3NTM0NTYsImV4cCI6MjA5NzMyOTQ1Nn0.W1WqI4QHWoctqs0GGhbTWnsEhWnAw9N_QCXu3eob6zc";

const payload = {
  // paste extracted fields here
};

const response = await fetch(`${SUPABASE_URL}/rest/v1/trade_research`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "apikey": SUPABASE_KEY,
    "Authorization": `Bearer ${SUPABASE_KEY}`,
    "Prefer": "return=representation"
  },
  body: JSON.stringify(payload)
});

const result = await response.json();
console.log("Saved:", result[0].id);
```

Use the `execute_javascript` or bash node approach to run this.

---

## OUTPUT

On success:
```
✅ Saved to SAK Journal
   Ticker: $TICKER
   Setup: [setup] ([confidence])
   Score: [total]/10 — [verdict]
   ID: [uuid]
```

On failure:
```
❌ Save failed: [error message]
```
