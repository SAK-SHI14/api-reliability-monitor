import sqlite3
import time
import os
import json
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "observability.db")

class ObservabilityDB:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_conn() as conn:
            # API Metrics Table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS api_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                api_name TEXT,
                url TEXT,
                latency_ms REAL,
                status_code INTEGER,
                is_success BOOLEAN
            )
            """)
            
            # Pipeline Events Table (Health Pings)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                event_type TEXT,  -- 'start', 'success', 'error', 'heartbeat'
                stage TEXT,       -- 'ingestion', 'processing', 'analysis'
                metrics_json TEXT -- JSON string for flexible metrics (records_processed, error_msg, etc.)
            )
            """)
            conn.commit()

    def log_api_metric(self, api_name, url, latency_ms, status_code, is_success):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO api_metrics (timestamp, api_name, url, latency_ms, status_code, is_success) VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), api_name, url, latency_ms, status_code, is_success)
            )
            conn.commit()

    def log_pipeline_event(self, event_type, stage, metrics=None):
        metrics_json = json.dumps(metrics or {})
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO pipeline_events (timestamp, event_type, stage, metrics_json) VALUES (?, ?, ?, ?)",
                (time.time(), event_type, stage, metrics_json)
            )
            conn.commit()

    # --- Readers for Dashboard ---

    def get_recent_api_metrics(self, seconds=300):
        cutoff = time.time() - seconds
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM api_metrics WHERE timestamp > ? ORDER BY timestamp ASC",
                (cutoff,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_pipeline_status(self):
        # customized query to get the last event for each stage or just the last general event
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM pipeline_events ORDER BY timestamp DESC LIMIT 50"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_pipeline_lag(self):
        # Calculate lag: time.time() - last 'success' timestamp
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT timestamp FROM pipeline_events WHERE event_type = 'success' ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                return time.time() - row['timestamp']
            return None # Unknown
