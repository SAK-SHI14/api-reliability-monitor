import sqlite3
import time
import os
import json
from contextlib import contextmanager
import logging

# Hardcoded path to the shared Observability DB in the sibling project
# ../../api_reliability_monitor/data/observability.db
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "api_reliability_monitor",
    "data",
    "observability.db"
)

logger = logging.getLogger("telemetry")

class PipelineTelemetry:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        # Ensure directory exists but do not force create DB if it doesn't exist?
        # Ideally the monitor creates it, but we should be robust.
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    @contextmanager
    def _get_conn(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            logger.error(f"Telemetry DB connection failed: {e}")
            raise
        finally:
            try:
                conn.close()
            except:
                pass

    def log_event(self, event_type, stage, metrics=None):
        """
        Log a pipeline event.
        event_type: 'start', 'success', 'error', 'heartbeat'
        stage: 'ingestion', 'processing', 'analysis', 'pipeline'
        """
        metrics_json = json.dumps(metrics or {})
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO pipeline_events (timestamp, event_type, stage, metrics_json) VALUES (?, ?, ?, ?)",
                    (time.time(), event_type, stage, metrics_json)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to log telemetry event: {e}")
