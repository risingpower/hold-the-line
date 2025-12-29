from datetime import date
from services.db import get_cursor

def add_to_plan(target_date: date, task_id: int, is_keystone: bool = False):
    date_iso = target_date.isoformat()
    with get_cursor(commit=True) as c:
        try:
            c.execute("INSERT INTO daily_plan (date, task_id, is_keystone) VALUES (?, ?, ?)", (date_iso, task_id, is_keystone))
        except Exception as e:
            if "FOREIGN KEY" in str(e): raise ValueError(f"Day {date_iso} not initialized. Run ensure_day() first.")
            raise e

def set_completion(target_date: date, task_id: int, status: str, notes: str = None):
    date_iso = target_date.isoformat()
    with get_cursor(commit=True) as c:
        c.execute("UPDATE daily_plan SET completion_status = ?, completion_notes = ? WHERE date = ? AND task_id = ?", (status, notes, date_iso, task_id))

def get_plan_hit_rate(target_date: date):
    date_iso = target_date.isoformat()
    with get_cursor() as c:
        c.execute("SELECT COUNT(*) as total, SUM(CASE WHEN completion_status = 'COMPLETE' THEN 1 ELSE 0 END) as completed FROM daily_plan WHERE date = ?", (date_iso,))
        row = c.fetchone()
        if not row or row['total'] == 0: return 0.0
        return round(row['completed'] / row['total'] * 100, 1)
def create_task(title: str, domain: str, shipping_type: str = None):
    """Creates a new task in inventory and returns its ID."""
    with get_cursor(commit=True) as c:
        try:
            c.execute("""
                INSERT INTO tasks (title, domain, shipping_type) 
                VALUES (?, ?, ?)
            """, (title, domain, shipping_type))
            return c.lastrowid
        except Exception as e:
            if "DATA INTEGRITY" in str(e):
                raise ValueError("Shipping Type allowed only for ENGINE tasks.")
            raise e

def get_daily_plan(target_date: date):
    """Fetches all tasks planned for a specific date."""
    date_iso = target_date.isoformat()
    with get_cursor() as c:
        c.execute("""
            SELECT 
                t.id as task_id, 
                t.title, 
                t.domain, 
                p.is_keystone, 
                p.completion_status 
            FROM daily_plan p
            JOIN tasks t ON p.task_id = t.id
            WHERE p.date = ?
        """, (date_iso,))
        return c.fetchall()