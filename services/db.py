import sqlite3
import contextlib

DB_NAME = "life_os.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

@contextlib.contextmanager
def get_cursor(commit=False):
    conn = get_connection()
    try:
        yield conn.cursor()
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()