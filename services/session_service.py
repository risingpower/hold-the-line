import time
from services.db import get_cursor

def start_session(task_id: int = None, session_type: str = 'DEEP'):
    start_ts = int(time.time())
    with get_cursor(commit=True) as c:
        try:
            c.execute("INSERT INTO work_sessions (task_id, start_ts, session_type) VALUES (?, ?, ?)", (task_id, start_ts, session_type))
            return c.lastrowid
        except Exception as e:
            if "FOCUS LOCK" in str(e): raise ValueError("Cannot start session: Another session is already active.")
            raise e

def stop_session(session_id: int, evidence_url: str = None):
    end_ts = int(time.time())
    with get_cursor(commit=True) as c:
        c.execute("SELECT start_ts FROM work_sessions WHERE id = ?", (session_id,))
        row = c.fetchone()
        if not row: raise ValueError("Session not found")
        
        duration_minutes = (end_ts - row['start_ts']) // 60
        c.execute("UPDATE work_sessions SET end_ts = ?, duration_minutes = ?, evidence_url = ? WHERE id = ?", (end_ts, duration_minutes, evidence_url, session_id))
        return duration_minutes

def get_active_session():
    with get_cursor() as c:
        c.execute("SELECT * FROM work_sessions WHERE end_ts IS NULL LIMIT 1")
        return c.fetchone()