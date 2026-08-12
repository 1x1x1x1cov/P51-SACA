import sqlite3
from datetime import datetime

DB_PATH = "saca.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symptom_text TEXT NOT NULL,
            symptoms_detected TEXT NOT NULL,
            severity TEXT NOT NULL,
            severity_sw TEXT NOT NULL,
            reason TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0,
            synced_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_session(symptom_text: str, symptoms: list, severity: str, severity_sw: str, reason: str):
    """
    Save a classification session locally. New sessions are always
    unsynced (synced=0) until a sync process marks them synced once
    connectivity is available. This supports offline-first use where
    the device may go hours or days without a network connection.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (symptom_text, symptoms_detected, severity, severity_sw, reason, timestamp, synced, synced_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
    """, (
        symptom_text,
        ", ".join(symptoms),
        severity,
        severity_sw,
        reason,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

def get_all_sessions():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_unsynced_sessions():
    """Return sessions that haven't yet been synced to a central server."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE synced = 0 ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def mark_synced(session_ids: list):
    """Mark a list of session IDs as synced, with the current timestamp."""
    if not session_ids:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.executemany(
        "UPDATE sessions SET synced = 1, synced_at = ? WHERE id = ?",
        [(now, sid) for sid in session_ids]
    )
    conn.commit()
    conn.close()