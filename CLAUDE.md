# SAK Trade Analyst — Claude Code Project

NSE equity research tool built on SAK trading system. Generates institutional-quality trade analysis using the Van Tharp R-multiple framework and SAK multi-strategy setup identification.

## Trading System

**Active Strategies:** VCP, REVERSAL, SVRO, EP, MARS, TS
**Paused:** NR 1HR
**Strongest:** VCP and REVERSAL (highest expectancy)
**Position Sizing:** Van Tharp R-multiple (1R = 1% of portfolio)
**Stop rules:** 2.5% floor for VCP and REVERSAL; technical stop where wider
**Scale-out:** 50% at T1, trail remainder

## Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `/trade-analyze` | `/trade-analyze RELIANCE` | Full 5-agent report (~2 min) |
| `/trade-quick` | `/trade-quick RELIANCE` | 60-sec snapshot |
| `/trade-sa` | `/trade-sa` or `/trade-sa RELIANCE` | SA format output |
| `/trade-compare` | `/trade-compare RELIANCE TCS` | Head-to-head comparison |

## Output Standards

- All analysis in SA format where applicable (Bias / Volume / Events / Strategy)
- All price levels in ₹
- Always include Bonde/Cohort 3 screen flag
- Van Tharp sizing assumes ₹25,00,000 portfolio unless user specifies otherwise
- No financial advice disclaimer on every output — user is a professional trader

## Market Context

- Exchange: NSE (National Stock Exchange, India)
- Benchmark: Nifty50, Nifty500
- Broker: Zerodha
- Charting: TradingView
