from datetime import date
from services.db import get_cursor

def submit_daily_log(target_date: date, weight: float, sleep_score: int, alcohol: int, spend: float, screen_time: int, notes: str):
    """
    Submits the final immutable log for the day.
    """
    date_iso = target_date.isoformat()
    
    with get_cursor(commit=True) as c:
        # Ensure strict immutability: Fail if row exists
        c.execute("SELECT 1 FROM daily_logs WHERE date = ?", (date_iso,))
        if c.fetchone():
            raise ValueError(f"Log for {date_iso} already exists. Logs are immutable.")

        try:
            c.execute("""
                INSERT INTO daily_logs 
                (date, morning_weight, sleep_score, alcohol_units, total_spend, screen_time_mins, manual_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date_iso, weight, sleep_score, alcohol, spend, screen_time, notes))
            print(f"✅ Logged {date_iso} successfully.")
        except Exception as e:
            if "CHECK" in str(e):
                raise ValueError(f"Data verification failed (Constraint Error): {e}")
            raise e

def log_exists(target_date: date) -> bool:
    """
    Checks if a log has already been submitted for the given date.
    """
    date_iso = target_date.isoformat()
    with get_cursor() as c:
        c.execute("SELECT 1 FROM daily_logs WHERE date = ?", (date_iso,))
        return c.fetchone() is not None