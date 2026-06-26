# SAK Trade Analyst — Claude Code Skills

NSE equity research tool for the SAK trading system. 4 slash commands, 5 parallel agents, Van Tharp position sizing, SA format output.

## Installation

### Step 1 — Install Claude Code
```bash
curl -fsSL https://claude.ai/install.sh | bash
```
Requires Claude Pro or Max plan.

### Step 2 — Create your project folder
```bash
mkdir ~/sak-trade
cd ~/sak-trade
```

### Step 3 — Copy skills into your project
```bash
cp -r /path/to/this/download/.claude ~/sak-trade/
cp /path/to/this/download/CLAUDE.md ~/sak-trade/
```

Or if cloning from your repo:
```bash
git clone <your-repo-url> ~/sak-trade
cd ~/sak-trade
```

### Step 4 — Launch Claude Code
```bash
cd ~/sak-trade
claude
```

## Usage

Type `/` to see all available commands:

```
/trade-analyze RELIANCE     # Full 5-agent report
/trade-quick HDFCBANK       # 60-second snapshot  
/trade-sa                   # Market SA for today
/trade-sa INFY              # Stock-specific SA
/trade-compare TCS INFY     # Head-to-head
```

## Commands Reference

### `/trade-analyze $TICKER`
Full analysis. Deploys 5 parallel agents:
1. Technical — identifies VCP/REVERSAL/SVRO/EP/MARS/TS setup
2. Fundamental — quality and growth assessment
3. Sentiment — news, social, analyst coverage
4. Risk — risk matrix + Bonde/Cohort 3 flag
5. Thesis — synthesises into SA format + entry/stop/targets + Van Tharp sizing

Takes ~2 minutes. Produces full markdown report.

### `/trade-quick $TICKER`
Single-pass snapshot in ~30 seconds. Price, stage, setup identification, key level, one-line verdict.

### `/trade-sa [$TICKER]`
Situational Analysis in SAK's fixed four-section format: Bias / Volume / Events / Strategy.
Run without ticker for market-wide SA. With ticker for stock-specific SA.

### `/trade-compare $TICKER1 $TICKER2`
Side-by-side scored comparison. Picks the better trade with reasoning.

## Customisation

Edit `CLAUDE.md` to change:
- Portfolio size (default ₹25,00,000)
- Active strategies
- Risk per trade (default 1R = 1%)

## Notes

- NSE stocks only
- Uses live web search — requires internet
- Not financial advice — research tool only
