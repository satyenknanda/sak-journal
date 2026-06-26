-- SAK Journal: trade_research table
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS trade_research (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  ticker TEXT NOT NULL,
  company_name TEXT,
  analysis_date DATE NOT NULL,
  
  -- Setup
  setup TEXT, -- VCP / REVERSAL / SVRO / EP / MARS / TS / None
  setup_confidence TEXT, -- HIGH / MEDIUM / LOW
  stage INTEGER, -- 1 / 2 / 3 / 4
  
  -- Price levels (from TradingView MCP)
  price_current NUMERIC,
  price_entry NUMERIC,
  price_stop NUMERIC,
  price_t1 NUMERIC,
  price_t2 NUMERIC,
  price_t3 NUMERIC,
  pct_below_52w_high NUMERIC,
  
  -- Van Tharp sizing
  risk_per_share NUMERIC,
  position_size INTEGER,
  position_value NUMERIC,
  pct_of_portfolio NUMERIC,
  
  -- Scores
  score_technical NUMERIC,
  score_fundamental NUMERIC,
  score_sentiment NUMERIC,
  score_risk NUMERIC,
  score_total NUMERIC,
  verdict TEXT, -- STRONG BUY / BUY / WATCH / AVOID
  
  -- Bonde screen
  bonde_match TEXT, -- MATCH / NO / PARTIAL
  
  -- SA format
  bias TEXT,
  volume_analysis TEXT,
  events TEXT,
  strategy TEXT,
  
  -- Full report
  full_report TEXT,
  
  -- Status tracking
  trade_taken BOOLEAN DEFAULT FALSE,
  trade_id UUID -- link to trades table when entered
);

-- Disable RLS (consistent with SAK Journal pattern)
ALTER TABLE trade_research DISABLE ROW LEVEL SECURITY;

-- Index for common queries
CREATE INDEX idx_trade_research_ticker ON trade_research(ticker);
CREATE INDEX idx_trade_research_date ON trade_research(analysis_date DESC);
CREATE INDEX idx_trade_research_setup ON trade_research(setup);
CREATE INDEX idx_trade_research_verdict ON trade_research(verdict);
