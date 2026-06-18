-- SAK Journal — Supabase Schema
-- Run this in Supabase SQL Editor

-- TRADES
create table if not exists trades (
  id bigserial primary key,
  trade_no text, status text, entry_date text, side text,
  qty numeric, ticker text, strategy text, entry_price numeric,
  stop_loss numeric, take_profit numeric, commission_entry numeric,
  tsl numeric, live_price numeric, change_pct numeric,
  exit_date text, exit_qty numeric, exit_price numeric,
  commission_exit numeric, risk_status text, notes text,
  pnl numeric, r_multiple numeric, created_at text, updated_at text,
  mae_price numeric, mfe_price numeric, trade_rating integer default 0,
  best_exit_price numeric, best_exit_time text, open_time text,
  close_time text, reviewed integer default 0, playbook text,
  setup text, mistakes text, tags text
);

-- DAILY NOTES
create table if not exists daily_notes (
  id bigserial primary key,
  note_date text unique, note text, updated_at text
);

-- MORNING BRIEF
create table if not exists morning_brief (
  id bigserial primary key,
  brief_date text unique, data text, updated_at text
);

-- PLAYBOOKS
create table if not exists playbooks (
  id bigserial primary key,
  name text, description text, strategy text,
  entry_rules text, exit_rules text, notes text,
  created_at text, updated_at text
);

-- PT/SL LEVELS
create table if not exists trade_pt_sl (
  id bigserial primary key,
  trade_id bigint, level_type text, price numeric,
  qty numeric, sort_order integer default 0
);

-- ATTACHMENTS
create table if not exists trade_attachments (
  id bigserial primary key,
  trade_id bigint, filename text, filepath text,
  filetype text, created_at text
);

-- NOTE TEMPLATES
create table if not exists note_templates (
  id bigserial primary key,
  name text, content text, used_at text
);

-- PROGRESS TRACKER RULES
create table if not exists pt_rules (
  id bigserial primary key,
  name text, description text, rule_type text default 'manual',
  condition_type text default 'checkbox', condition_value text,
  active_days text default 'Mon,Tue,Wed,Thu,Fri',
  enabled integer default 1, sort_order integer default 0
);

-- PROGRESS TRACKER CHECKINS
create table if not exists pt_checkins (
  id bigserial primary key,
  checkin_date text, rule_id bigint, completed integer default 0,
  unique(checkin_date, rule_id)
);

-- SETTINGS
create table if not exists settings (
  id bigserial primary key,
  key text unique, value text
);

-- Enable Row Level Security (open for now, restrict later)
alter table trades enable row level security;
alter table daily_notes enable row level security;
alter table morning_brief enable row level security;

-- Allow all operations for anon key (for personal use)
create policy "Allow all" on trades for all using (true) with check (true);
create policy "Allow all" on daily_notes for all using (true) with check (true);
create policy "Allow all" on morning_brief for all using (true) with check (true);
create policy "Allow all" on playbooks for all using (true) with check (true);
create policy "Allow all" on trade_pt_sl for all using (true) with check (true);
create policy "Allow all" on trade_attachments for all using (true) with check (true);
create policy "Allow all" on note_templates for all using (true) with check (true);
create policy "Allow all" on pt_rules for all using (true) with check (true);
create policy "Allow all" on pt_checkins for all using (true) with check (true);
create policy "Allow all" on settings for all using (true) with check (true);
