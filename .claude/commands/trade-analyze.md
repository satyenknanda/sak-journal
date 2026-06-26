# /trade-analyze

**Usage:** `/trade-analyze $TICKER`

Full SAK-system stock analysis for NSE equities. Phase 0 pulls live chart data from TradingView MCP, then deploys 5 parallel agents for a complete research report.

---

## PHASE 0 — LIVE CHART DATA (TradingView MCP)

Run these MCP calls first before any web search or agent work.

```
chart_set_symbol(symbol: "NSE:$TICKER")
chart_set_timeframe(timeframe: "1D")
chart_get_state()
data_get_ohlcv(symbol: "NSE:$TICKER", timeframe: "1D", bars: 200)
data_get_indicator(symbol: "NSE:$TICKER", timeframe: "1D", indicator: "EMA", length: 10)
data_get_indicator(symbol: "NSE:$TICKER", timeframe: "1D", indicator: "EMA", length: 21)
data_get_indicator(symbol: "NSE:$TICKER", timeframe: "1D", indicator: "EMA", length: 50)
data_get_indicator(symbol: "NSE:$TICKER", timeframe: "1D", indicator: "EMA", length: 200)
data_get_indicator(symbol: "NSE:$TICKER", timeframe: "1D", indicator: "Volume MA", length: 20)
```

From the OHLCV + EMA data, extract and compute:

**Price structure:**
- Current price, today's O/H/L
- 10 EMA, 21 EMA, 50 EMA, 200 EMA values
- Price vs each EMA (above/below, % distance)
- 52W high and low (from 200 bars)
- % below 52W high

**Stage identification (Weinstein):**
- Stage 1: Price below 200 EMA, flat/sideways
- Stage 2: Price above 200 EMA, rising — ONLY valid stage for long entries
- Stage 3: Price topping, below recent highs, 200 EMA flattening
- Stage 4: Price below 200 EMA, declining

**Volume analysis (from OHLCV):**
- Today's volume vs 20-bar volume MA
- Volume trend over last 10 bars: expanding / contracting / neutral
- Identify any volume spikes (>2x avg) in last 20 bars and which direction

**Base / contraction analysis (from OHLCV — last 60 bars):**
- Identify distinct price bases (consolidation zones where range tightens)
- Count contractions: each correction shallower than the last?
- Measure depth of each correction from prior high (%)
- Is current price action tight (daily range <1.5% for 5+ days)?
- Volume drying up during consolidation?

**EMA structure:**
- 10 EMA > 21 EMA > 50 EMA > 200 EMA? (bullish stack)
- Any EMA crossovers in last 20 bars?
- Price vs 10/21 EMA distance (%)

Compile all of the above as CHART_DATA before proceeding to Phase 1.

---

## PHASE 1 — WEB DISCOVERY

Run these searches in parallel:

1. `$TICKER NSE stock fundamentals revenue profit FY26`
2. `$TICKER NSE news sentiment latest 2026`
3. `$TICKER NSE upcoming events results concall`
4. `$TICKER promoter FII DII shareholding`
5. `$TICKER NSE sector relative strength`

---

## PHASE 2 — FIVE PARALLEL AGENTS

Use CHART_DATA from Phase 0 + web data from Phase 1.

---

### AGENT 1 — TECHNICAL ANALYST

Use CHART_DATA exclusively for setup scoring. Do not infer technical structure from web data.

**Pre-condition check:**
- If Stage ≠ 2: flag immediately. Only score REVERSAL for Stage 4. Mark all other setups N/A.
- If Stage = 2: score all setups below.

**VCP (Volatility Contraction Pattern)**
Requires ALL of:
- [ ] Stage 2 (price above rising 200 EMA)
- [ ] Minimum 2 prior bases visible in last 60 bars, each correction shallower than last
- [ ] Volume contracting progressively in each base
- [ ] Current price within 5% of pivot high (recent base high)
- [ ] Daily range tightening (volatility contracting)
Score: /10 — deduct 2 points for each missing criterion

**REVERSAL**
Requires ALL of:
- [ ] Stage 3 or Stage 4 price action
- [ ] Climactic volume selloff OR selling exhaustion (volume spike down then drying)
- [ ] Price reclaiming 21 EMA or key support from below
- [ ] Higher lows forming (at least 2)
Score: /10

**SVRO (Stage Velocity Range Opportunity)**
Requires ALL of:
- [ ] Stage 1 → Stage 2 transition (price just crossed 200 EMA)
- [ ] Breakout from long base (>6 weeks) on above-average volume
- [ ] 200 EMA itself is flat or just turning up
Score: /10

**EP (Episodic Pivot)**
Requires ALL of:
- [ ] Gap up or sharp single-day move >5% on volume >3x avg in last 20 bars
- [ ] Price holding above the gap / pivot level
- [ ] News/results catalyst present
Score: /10

**MARS (Momentum At Right Side)**
Requires ALL of:
- [ ] Stage 2, bullish EMA stack (10>21>50>200)
- [ ] Price pulled back to 10 or 21 EMA from above
- [ ] Pullback on declining volume
- [ ] No base structure required — riding existing trend
Score: /10

**TS (Trend Structure)**
Requires ALL of:
- [ ] Stage 2, clean higher highs and higher lows on daily
- [ ] Price above 50 EMA
- [ ] No specific EMA touch required
Score: /10

**Output:**
- Best setup + score + criteria met/missed checklist
- Second best if within 2 points
- "NO CLEAN SETUP" if all score below 5/10
- Full price level table from CHART_DATA
- Volume verdict
- EMA stack status

---

### AGENT 2 — FUNDAMENTAL ANALYST

Assess business quality from web discovery data.

**Analyse:**
- Revenue growth (YoY, TTM)
- Net profit margin + trend
- ROE, ROCE
- Debt/Equity
- Promoter holding % and trend (pledging?)
- FII/DII holding trend
- EPS growth
- P/E vs sector average
- Red flags: pledging, auditor issues, related party transactions

**Output:**
- Fundamental score: /10
- Bull case (2-3 points)
- Bear case (2-3 points)
- Verdict: STRONG / AVERAGE / WEAK

---

### AGENT 3 — SENTIMENT ANALYST

**Analyse:**
- News flow last 30 days
- Management commentary / concall tone
- Analyst targets and coverage count
- Promoter buying/selling activity
- Block/bulk deals
- Sector in favour or out of favour?

**Output:**
- Sentiment score: /10
- Key positive catalysts
- Key negative catalysts
- Verdict: BULLISH / NEUTRAL / BEARISH

---

### AGENT 4 — RISK ASSESSOR

**Analyse:**
- Beta
- ATR % from CHART_DATA (use daily range data)
- Liquidity (avg daily volume in ₹ crore)
- Sector/regulatory risks
- Company-specific risks

**Risk Matrix:**

| Risk Factor | Probability | Impact | Mitigation |
|-------------|-------------|--------|------------|
| [risk 1] | H/M/L | H/M/L | [action] |
| [risk 2] | H/M/L | H/M/L | [action] |
| [risk 3] | H/M/L | H/M/L | [action] |

**Bonde / Cohort 3 Screen:**
Use CHART_DATA to verify:
- Stage 2 confirmed from EMA data?
- Price above ALL MAs (10/21/50/200)?
- 1Y RS strong vs Nifty500?
- Volume expanding on up moves?

Flag: ✅ BONDE MATCH / ❌ NOT IN SCREEN / ⚠️ PARTIAL MATCH

**Output:**
- Risk score: /10
- Verdict: LOW / MEDIUM / HIGH

---

### AGENT 5 — THESIS SYNTHESISER

#### TRADE SCORE DASHBOARD

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|---------|
| Technical Setup | /10 | 35% | |
| Fundamentals | /10 | 20% | |
| Sentiment | /10 | 20% | |
| Risk Profile | /10 | 15% | |
| Thesis Conviction | /10 | 10% | |
| **TOTAL** | | | **/10** |

**Verdict:** STRONG BUY / BUY / WATCH / AVOID

---

#### SA FORMAT OUTPUT

**1. BIAS**
Directional bias based on Stage + setup + fundamental quality. Bullish / Bearish / Neutral. Why.

**2. VOLUME**
Volume story from CHART_DATA. Accumulation / Distribution / Indecision. What it signals.

**3. EVENTS**
Bullet list of upcoming catalysts from web discovery.

**4. STRATEGY**
Which setup applies. Specific actionable plan.

---

#### ENTRY & EXIT PLAN

**Setup:** [from Agent 1 — must be confirmed, not inferred]

**Entry trigger:** [exact price level from CHART_DATA — pivot high, EMA level, or breakout point]
**Entry type:** Buy stop above [price] OR Limit at [EMA level]

**Stop loss:**
- Technical stop: [price from CHART_DATA — base low, prior pivot, EMA]
- % stop: 2.5% below entry (VCP/REVERSAL floor)
- Use whichever is WIDER

**Targets:**
- T1 (1R): ₹[entry + 1× risk]
- T2 (2R): ₹[entry + 2× risk]
- T3 (3R+): ₹[entry + 3× risk]
- Scale-out: 50% at T1, trail remainder on 10 EMA

---

#### VAN THARP POSITION SIZING

Portfolio default ₹25,00,000 | 1R = 1% = ₹25,000
(User can override: "run with ₹50L portfolio")

```
Entry price:        ₹[X]
Stop loss price:    ₹[Y]
Risk per share:     ₹[X-Y]
Position size:      ₹25,000 ÷ ₹[X-Y] = [N] shares
Position value:     ₹[N × X]
% of portfolio:     [%]
```

Flag if position value >15% of portfolio — reduce to fit concentration cap.

---

#### RISK-REWARD SUMMARY

| Scenario | Target | R-Multiple | Probability |
|----------|--------|------------|-------------|
| Bull case | ₹[T3] | 3R | [%] |
| Base case | ₹[T2] | 2R | [%] |
| Bear case | Stop | −1R | [%] |
| **Expected Value** | | **[weighted R]** | |

---

#### BONDE / COHORT 3 FLAG

[✅ / ❌ / ⚠️] [One line — based on CHART_DATA, not inference]

---

#### FINAL VERDICT

3-4 lines. What to do, when, what invalidates the thesis.

---

## CRITICAL RULES

1. Setup identification MUST come from CHART_DATA (Phase 0). Never infer technical structure from news or price alone.
2. If Phase 0 MCP call fails, state "Chart data unavailable — technical scoring suspended" and run only Agents 2/3/4.
3. Never assign VCP without confirmed base contraction count from OHLCV data.
4. Never assign SVRO if stock is already in Stage 2 with extended move.
5. Entry/stop levels must be derived from actual OHLCV prices, not estimated.
