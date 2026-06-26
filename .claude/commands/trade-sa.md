# /trade-sa

**Usage:** `/trade-sa` OR `/trade-sa $TICKER`

Generates a Situational Analysis (SA) document in SAK's fixed four-section format. Run without ticker for market-wide SA. Run with ticker for stock-specific SA.

---

## INSTRUCTIONS

**If no ticker — MARKET SA:**

Search for:
1. `Nifty50 today price change`
2. `BankNifty today`
3. `India VIX today`
4. `S&P500 Nasdaq overnight`
5. `USD INR today`
6. `Crude oil price today`
7. `NSE FII DII data today`
8. `India market news today`

**If ticker provided — STOCK SA:**

Search for:
1. `$TICKER NSE price volume today`
2. `$TICKER news latest`
3. `$TICKER technical levels support resistance`

---

## OUTPUT — STRICT FORMAT (no deviation)

---

**SITUATIONAL ANALYSIS**
*[Date] | [Market / $TICKER]*

---

**1. BIAS**
[2-3 sentences. Directional bias for the session/swing. Bullish, bearish, or neutral. Why.]

**2. VOLUME**
[2-3 sentences. Volume picture. Accumulation, distribution, or indecision. What it signals.]

**3. EVENTS**
- [Event 1 — date if known]
- [Event 2]
- [Event 3]
- [Macro event if relevant]

**4. STRATEGY**
[3-4 sentences. Specific actionable plan. Which setups to focus on today. What levels matter. What to avoid.]

---
