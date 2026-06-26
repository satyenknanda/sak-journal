# /trade-quick

**Usage:** `/trade-quick $TICKER`

60-second NSE snapshot using live TradingView data. Single pass — no agents.

---

## INSTRUCTIONS

**Step 1 — TradingView MCP:**
```
chart_set_symbol(symbol: "NSE:$TICKER")
data_get_ohlcv(symbol: "NSE:$TICKER", timeframe: "1D", bars: 60)
data_get_indicator(symbol: "NSE:$TICKER", timeframe: "1D", indicator: "EMA", length: 21)
data_get_indicator(symbol: "NSE:$TICKER", timeframe: "1D", indicator: "EMA", length: 50)
data_get_indicator(symbol: "NSE:$TICKER", timeframe: "1D", indicator: "EMA", length: 200)
data_get_indicator(symbol: "NSE:$TICKER", timeframe: "1D", indicator: "Volume MA", length: 20)
```

**Step 2 — Single web search:**
`$TICKER NSE news today`

**Step 3 — Produce this output:**

---

**$TICKER — SAK QUICK SCAN**
*[Date]*

**Price:** ₹[X] | **Change:** [+/-]% | **Volume:** [X]x avg

**Stage:** [1/2/3/4] — [one line reason from EMA data]
**EMA Stack:** 10>[21]>[50]>[200]? [YES — bullish / PARTIAL / NO]
**% below 52W high:** [X]%

**Likely Setup:** [VCP / REVERSAL / SVRO / EP / MARS / TS / None]
**Confidence:** [HIGH / MEDIUM / LOW] — [one line reason from chart data]

**Key level:** ₹[X] — [what it is: pivot high / EMA / base low]
**Stop if long:** ₹[X] ([2.5%] below entry)

**Bonde Screen:** [✅ / ❌ / ⚠️] — [one line from EMA/stage data]

**Verdict:** [One actionable sentence]

---

Run `/trade-analyze $TICKER` for full 5-agent report.
