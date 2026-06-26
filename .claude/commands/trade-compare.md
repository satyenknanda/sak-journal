# /trade-compare

**Usage:** `/trade-compare $TICKER1 $TICKER2`

Head-to-head comparison of two NSE stocks. Useful for choosing between two setups in the same sector, or ranking watchlist candidates.

---

## INSTRUCTIONS

Run discovery searches for both tickers in parallel, then produce a side-by-side comparison.

**Searches:**
- `$TICKER1 NSE price technicals fundamentals`
- `$TICKER2 NSE price technicals fundamentals`
- `$TICKER1 vs $TICKER2 comparison`

---

## OUTPUT FORMAT

---

**SAK TRADE COMPARE**
*$TICKER1 vs $TICKER2 | [Date]*

| Factor | $TICKER1 | $TICKER2 |
|--------|----------|----------|
| Price | ₹ | ₹ |
| Stage | | |
| Above 200 DMA | | |
| Setup | | |
| Setup Score | /10 | /10 |
| Fundamentals | /10 | /10 |
| Sentiment | /10 | /10 |
| Risk | /10 | /10 |
| Bonde Match | ✅/❌/⚠️ | ✅/❌/⚠️ |
| **Total Score** | **/10** | **/10** |

**Winner:** $TICKER[X]

**Why:** [2-3 sentences explaining which is the better trade and why, in SAK system terms.]

**Caveat:** [Any reason to still consider the other, or conditions under which it becomes preferred.]

---
