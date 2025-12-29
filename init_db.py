import sqlite3
import os
import sys

DB_NAME = "life_os.db"

def check_json_support():
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute('SELECT json_valid("{}")')
        conn.close()
        return True
    except:
        return False

def initialize_db():
    if not check_json_support():
        print("❌ CRITICAL: SQLite JSON1 extension missing.")
        sys.exit(1)

    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"⚠️  Removed existing {DB_NAME} (Clean Slate)")

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")
    c.execute("PRAGMA journal_mode = WAL;")

    # --- TABLES ---

    # 1. SYSTEM CONFIG
    c.execute("""
    CREATE TABLE system_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at INTEGER DEFAULT (strftime('%s', 'now')),
        version_name TEXT NOT NULL,
        season_mode_default TEXT CHECK(season_mode_default IN ('STANDARD', 'SPRINT', 'RECOVERY')),
        nps_weights JSON NOT NULL CHECK(json_valid(nps_weights)),
        veto_thresholds JSON NOT NULL CHECK(json_valid(veto_thresholds)),
        lock_settings JSON NOT NULL CHECK(json_valid(lock_settings)),
        change_log_note TEXT
    );
    """)

    # 2. CONFIG ROUTING
    c.execute("""
    CREATE TABLE daily_config_routing (
        date DATE PRIMARY KEY,
        config_id INTEGER NOT NULL,
        FOREIGN KEY (config_id) REFERENCES system_config(id) ON DELETE RESTRICT
    );
    """)

    # 3. TASKS
    c.execute("""
    CREATE TABLE tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at INTEGER DEFAULT (strftime('%s', 'now')),
        domain TEXT NOT NULL CHECK(domain IN ('ENGINE', 'VESSEL', 'RESOURCES', 'SYSTEM')),
        title TEXT NOT NULL,
        shipping_type TEXT CHECK(shipping_type IN ('INTERNAL', 'STAGED', 'LIVE') OR shipping_type IS NULL),
        status TEXT DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'ARCHIVED'))
    );
    """)

    # 4. DAILY STATE
    c.execute("""
    CREATE TABLE daily_state (
        date DATE PRIMARY KEY,
        active_mode TEXT NOT NULL CHECK(active_mode IN ('WIN', 'HOLD', 'STABILIZE')),
        trigger_reason TEXT CHECK(trigger_reason IN ('NONE', 'ILLNESS', 'TRAVEL', 'FAMILY_EMERGENCY', 'FAIL_SLIDE')),
        override_note TEXT
    );
    """)

    # 5. DAILY PLAN
    c.execute("""
    CREATE TABLE daily_plan (
        date DATE,
        task_id INTEGER,
        planned_at INTEGER DEFAULT (strftime('%s', 'now')),
        is_keystone BOOLEAN DEFAULT 0,
        completion_status TEXT DEFAULT 'PENDING' CHECK(completion_status IN ('PENDING', 'COMPLETE', 'FAILED', 'DEFERRED')),
        completion_notes TEXT,
        PRIMARY KEY (date, task_id),
        FOREIGN KEY (date) REFERENCES daily_state(date) ON DELETE RESTRICT,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE RESTRICT
    );
    """)

    # 6. DAILY LOGS
    c.execute("""
    CREATE TABLE daily_logs (
        date DATE PRIMARY KEY,
        morning_weight REAL CHECK(morning_weight > 0),
        sleep_score INTEGER CHECK(sleep_score BETWEEN 0 AND 100),
        alcohol_units INTEGER CHECK(alcohol_units >= 0),
        total_spend REAL CHECK(total_spend >= 0),
        screen_time_mins INTEGER CHECK(screen_time_mins >= 0),
        manual_notes TEXT,
        created_at INTEGER DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (date) REFERENCES daily_state(date) ON DELETE RESTRICT
    );
    """)

    # 7. WORK SESSIONS
    c.execute("""
    CREATE TABLE work_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER, 
        start_ts INTEGER NOT NULL,
        end_ts INTEGER,
        duration_minutes INTEGER CHECK(duration_minutes IS NULL OR duration_minutes >= 0),
        session_type TEXT NOT NULL CHECK(session_type IN ('DEEP', 'SHALLOW')),
        evidence_url TEXT,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE RESTRICT,
        CHECK (end_ts IS NULL OR end_ts >= start_ts)
    );
    """)

    # 8. DAILY DERIVED LOG
    c.execute("""
    CREATE TABLE daily_derived_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE NOT NULL,
        config_id INTEGER NOT NULL,
        computed_at INTEGER DEFAULT (strftime('%s', 'now')),
        score_engine REAL CHECK(score_engine BETWEEN 0 AND 100),
        score_vessel REAL CHECK(score_vessel BETWEEN 0 AND 100),
        score_resources REAL CHECK(score_resources BETWEEN 0 AND 100),
        score_system REAL CHECK(score_system BETWEEN 0 AND 100),
        nps_score REAL,
        safety_multiplier REAL CHECK(safety_multiplier IN (0.0, 0.5, 1.0)),
        FOREIGN KEY (date) REFERENCES daily_logs(date) ON DELETE RESTRICT,
        FOREIGN KEY (config_id) REFERENCES system_config(id) ON DELETE RESTRICT
    );
    """)

    c.execute("""
    CREATE VIEW daily_derived_latest AS
    SELECT * FROM daily_derived_log d1
    WHERE id = (SELECT MAX(id) FROM daily_derived_log d2 WHERE d2.date = d1.date);
    """)

    # 9. AUDIT EVENTS
    c.execute("""
    CREATE TABLE audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp INTEGER DEFAULT (strftime('%s', 'now')),
        date_ref DATE NOT NULL,
        task_id INTEGER,
        config_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        severity_level INTEGER CHECK(severity_level BETWEEN 1 AND 5),
        user_input_text TEXT,
        FOREIGN KEY (date_ref) REFERENCES daily_state(date) ON DELETE RESTRICT,
        FOREIGN KEY (task_id) REFERENCES tasks(id),
        FOREIGN KEY (config_id) REFERENCES system_config(id)
    );
    """)

    # --- TRIGGERS ---
    immutable_tables = ['system_config', 'daily_config_routing', 'daily_logs', 'audit_events', 'daily_derived_log']
    for table in immutable_tables:
        c.execute(f"CREATE TRIGGER block_update_{table} BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'IMMUTABILITY VIOLATION: {table} is insert-only.'); END;")
        c.execute(f"CREATE TRIGGER block_delete_{table} BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'IMMUTABILITY VIOLATION: {table} deletion forbidden.'); END;")

    c.execute("""
    CREATE TRIGGER block_concurrent_sessions
    BEFORE INSERT ON work_sessions
    FOR EACH ROW
    WHEN EXISTS (SELECT 1 FROM work_sessions WHERE end_ts IS NULL)
    BEGIN SELECT RAISE(ABORT, 'FOCUS LOCK: You already have an active session. Close it first.'); END;
    """)

    c.execute("""
    CREATE TRIGGER validate_session_close
    BEFORE UPDATE ON work_sessions
    BEGIN
        SELECT CASE
            WHEN OLD.end_ts IS NOT NULL THEN RAISE(ABORT, 'SESSION LOCKED: Cannot modify a closed session.')
            WHEN NEW.end_ts IS NULL THEN RAISE(ABORT, 'INVALID OPERATION: Can only update session to close it.')
            WHEN NEW.duration_minutes IS NULL THEN RAISE(ABORT, 'DATA INTEGRITY: Duration cannot be NULL on close.')
            WHEN NEW.start_ts != OLD.start_ts THEN RAISE(ABORT, 'TAMPERING DETECTED: Start time cannot be changed.')
            WHEN COALESCE(NEW.task_id, -1) != COALESCE(OLD.task_id, -1) THEN RAISE(ABORT, 'TAMPERING DETECTED: Task ID cannot be changed.')
            WHEN NEW.session_type != OLD.session_type THEN RAISE(ABORT, 'TAMPERING DETECTED: Session Type cannot be changed.')
            WHEN NEW.duration_minutes != CAST((NEW.end_ts - NEW.start_ts) / 60 AS INTEGER) THEN RAISE(ABORT, 'DATA INTEGRITY: Duration mismatch with timestamps.')
        END;
    END;
    """)

    c.execute("CREATE TRIGGER block_delete_work_sessions BEFORE DELETE ON work_sessions BEGIN SELECT RAISE(ABORT, 'IMMUTABILITY VIOLATION: Sessions cannot be deleted.'); END;")
    c.execute("CREATE TRIGGER enforce_shipping_domain_insert AFTER INSERT ON tasks WHEN NEW.domain != 'ENGINE' AND NEW.shipping_type IS NOT NULL BEGIN SELECT RAISE(ABORT, 'DATA INTEGRITY: Shipping Type allowed only for ENGINE tasks.'); END;")
    c.execute("CREATE TRIGGER enforce_shipping_domain_update BEFORE UPDATE ON tasks WHEN NEW.domain != 'ENGINE' AND NEW.shipping_type IS NOT NULL BEGIN SELECT RAISE(ABORT, 'DATA INTEGRITY: Shipping Type allowed only for ENGINE tasks.'); END;")

    c.execute("CREATE INDEX idx_plan_lookup ON daily_plan(date, completion_status);")
    c.execute("CREATE INDEX idx_sessions_active ON work_sessions(end_ts) WHERE end_ts IS NULL;")
    c.execute("CREATE INDEX idx_routing_lookup ON daily_config_routing(date);")
    c.execute("CREATE INDEX idx_derived_latest ON daily_derived_log(date, id);")

    conn.commit()
    conn.close()
    print("✅ System Initialized: life_os.db created (v5 Final Hardening).")

if __name__ == "__main__":
    initialize_db()