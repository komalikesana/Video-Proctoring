import sqlite3
import os
from datetime import datetime
import csv

BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

DB_PATH = os.path.join(LOG_DIR, "events.db")

# ---------------- Initialize Database ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT NOT NULL,
            integrity_score REAL DEFAULT 100,
            start_time TEXT,
            end_time TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            event TEXT NOT NULL,
            score_change REAL,
            FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------- Add Candidate ----------------
def add_candidate(candidate_name: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    start_time = datetime.now().isoformat()
    c.execute('''
        INSERT INTO candidates (candidate_name, start_time)
        VALUES (?, ?)
    ''', (candidate_name, start_time))
    candidate_id = c.lastrowid
    conn.commit()
    conn.close()
    print(f"[logger] Added candidate {candidate_name} with ID {candidate_id}")
    return candidate_id

# ---------------- Log Event ----------------
def log_event(candidate_id: int, event: str, score_change: float = 0):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        timestamp = datetime.now().isoformat()

        # Insert event
        c.execute('''
            INSERT INTO events (candidate_id, timestamp, event, score_change)
            VALUES (?, ?, ?, ?)
        ''', (candidate_id, timestamp, event, score_change))

        # Update candidate score
        if score_change != 0:
            c.execute('''
                UPDATE candidates
                SET integrity_score = integrity_score - ?
                WHERE candidate_id = ?
            ''', (score_change, candidate_id))

        conn.commit()
        conn.close()
        print(f"[logger] Event logged for candidate {candidate_id}: {event} (-{score_change})")
    except Exception as e:
        print(f"[logger] Failed to log event: {e}")

# ---------------- End Candidate Session ----------------
def end_candidate_session(candidate_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    end_time = datetime.now().isoformat()
    c.execute('''
        UPDATE candidates
        SET end_time = ?
        WHERE candidate_id = ?
    ''', (end_time, candidate_id))
    conn.commit()
    conn.close()
    print(f"[logger] Session ended for candidate {candidate_id} at {end_time}")

# ---------------- Generate Report ----------------
def generate_report(candidate_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Candidate info
    c.execute('''
        SELECT candidate_name, integrity_score, start_time, end_time
        FROM candidates
        WHERE candidate_id = ?
    ''', (candidate_id,))
    candidate = c.fetchone()
    if not candidate:
        conn.close()
        raise ValueError("Candidate not found")
    candidate_name, integrity_score, start_time, end_time = candidate

    # Events
    c.execute('''
        SELECT timestamp, event, score_change
        FROM events
        WHERE candidate_id = ?
    ''', (candidate_id,))
    events = c.fetchall()
    conn.close()

    # Write CSV report
    report_path = os.path.join(LOG_DIR, f"{candidate_name}_report.csv")
    with open(report_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Candidate ID", "Candidate Name", "Timestamp", "Event", "Score Change"])
        for row in events:
            writer.writerow([candidate_id, candidate_name, row[0], row[1], row[2]])
        writer.writerow([])
        writer.writerow(["Final Integrity Score", integrity_score])
        writer.writerow(["Session Start Time", start_time])
        writer.writerow(["Session End Time", end_time])

    print(f"[logger] Report generated: {report_path}")
    return report_path
