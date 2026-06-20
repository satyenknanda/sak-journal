import sys
sys.path.insert(0, '.')

modules = [
    ('theme', 'from theme import TEAL'),
    ('data.db', 'from data.db import init_db, get_trades, get_strategies'),
    ('components.trade_modals', 'from components.trade_modals import render_add_trade_modal'),
    ('pages.dashboard', 'from pages.dashboard import render'),
    ('pages.trade_log', 'from pages.trade_log import render'),
    ('pages.morning_brief', 'from pages.morning_brief import render'),
    ('pages.daily_journal', 'from pages.daily_journal import render'),
    ('pages.progress_tracker', 'from pages.progress_tracker import render'),
    ('pages.playbook', 'from pages.playbook import render'),
]

for name, imp in modules:
    try:
        exec(imp)
        print(f"✅ {name}")
    except Exception as e:
        print(f"❌ {name}: {e}")
