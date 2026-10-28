import os
import sqlite3
from datetime import datetime


APP_DATA_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "SACA"
)

os.makedirs(APP_DATA_DIR, exist_ok=True)

DATABASE_PATH = os.path.join(
    APP_DATA_DIR,
    "history.db"
)


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialise_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                symptom_text TEXT NOT NULL,
                severity TEXT,
                confidence REAL,
                reason TEXT,
                extracted_text TEXT,
                symptoms TEXT,
                fallback_used INTEGER DEFAULT 0
            )
        """)


def save_analysis(symptom_text, result):
    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO history (
                created_at,
                symptom_text,
                severity,
                confidence,
                reason,
                extracted_text,
                symptoms,
                fallback_used
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            symptom_text,
            result.get("severity"),
            result.get("confidence"),
            result.get("reason"),
            result.get("extracted_text"),
            ", ".join(
                str(s) for s in result.get("symptoms", [])
            ),
            int(bool(result.get("fallback_used")))
        ))

        return cursor.lastrowid


def get_history():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM history
            ORDER BY id DESC
        """).fetchall()

        return [dict(row) for row in rows]


def get_analysis(record_id):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT *
            FROM history
            WHERE id = ?
        """, (record_id,)).fetchone()

        return dict(row) if row else None


def delete_analysis(record_id):
    with get_connection() as connection:
        connection.execute("""
            DELETE FROM history
            WHERE id = ?
        """, (record_id,))


def clear_history():
    with get_connection() as connection:
        connection.execute("DELETE FROM history")


initialise_database()