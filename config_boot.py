import sqlite3
import json
from datetime import date

def boot_system():
    conn = sqlite3.connect("life_os.db")
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")

    weights = {"engine": 0.4, "vessel": 0.3, "resources": 0.2, "system": 0.1}
    veto = {"alcohol_units": 0, "sleep_min": 5, "missed_logs": 1}
    locks = {"bypass_phrase": "I am ignoring my better judgement", "cooldown_mins": 60}
    
    c.execute("""
        INSERT INTO system_config 
        (version_name, season_mode_default, nps_weights, veto_thresholds, lock_settings, change_log_note)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("v1.0 Genesis", "STANDARD", json.dumps(weights), json.dumps(veto), json.dumps(locks), "Initial Boot"))
    
    config_id = c.lastrowid
    print(f"Created Config ID: {config_id}")

    today = date.today().isoformat()
    try:
        c.execute("INSERT INTO daily_state (date, active_mode, trigger_reason, override_note) VALUES (?, 'WIN', 'NONE', 'Day 1')", (today,))
        c.execute("INSERT INTO daily_config_routing (date, config_id) VALUES (?, ?)", (today, config_id))
        print(f"Pinned Config {config_id} to Date {today}")
    except sqlite3.IntegrityError:
        print("System already booted.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    boot_system()