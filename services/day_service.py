from datetime import date, timedelta
from services.db import get_cursor

def ensure_day(target_date: date):
    date_iso = target_date.isoformat()
    with get_cursor(commit=True) as c:
        c.execute("SELECT config_id FROM daily_config_routing WHERE date = ?", (date_iso,))
        if c.fetchone(): return 
        
        c.execute("SELECT config_id, date FROM daily_config_routing WHERE date < ? ORDER BY date DESC LIMIT 1", (date_iso,))
        prev = c.fetchone()
        if not prev: raise ValueError(f"CRITICAL: No config history found for {date_iso}. Run boot script.")
        
        last_date = date.fromisoformat(prev['date'])
        if (target_date - last_date).days > 30: print(f"⚠️ WARNING: Inheriting config from {prev['date']} (>30 days ago).")

        c.execute("INSERT OR IGNORE INTO daily_state (date, active_mode, trigger_reason, override_note) VALUES (?, 'WIN', 'NONE', 'Auto-initialized')", (date_iso,))
        c.execute("INSERT INTO daily_config_routing (date, config_id) VALUES (?, ?)", (date_iso, prev['config_id']))
        print(f"✅ Initialized {date_iso} using Config {prev['config_id']}")

def ensure_week_ahead():
    today = date.today()
    for i in range(8): ensure_day(today + timedelta(days=i))