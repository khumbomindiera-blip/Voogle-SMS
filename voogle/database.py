import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "voogle.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the queries table if it doesn't exist."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            user_query TEXT NOT NULL,
            gemini_response TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_query(phone_number: str, user_query: str, gemini_response: str, timestamp: str):
    """Insert a new query record."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO queries (phone_number, user_query, gemini_response, timestamp) VALUES (?, ?, ?, ?)",
        (phone_number, user_query, gemini_response, timestamp),
    )
    conn.commit()
    conn.close()


def get_all_queries() -> list[dict]:
    """Return all queries ordered newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, phone_number, user_query, gemini_response, timestamp FROM queries ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
