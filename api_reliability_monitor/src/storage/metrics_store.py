import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MetricsStore:
    def __init__(self, file_path="data/raw/metrics.jsonl"):
        self.file_path = Path(file_path)
        self._ensure_directory()

    def _ensure_directory(self):
        if not self.file_path.parent.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, metric):
        """
        Appends a metric record to the JSONL file.
        """
        try:
            with open(self.file_path, 'a') as f:
                f.write(json.dumps(metric) + '\n')
        except Exception as e:
            logger.error(f"Failed to save metric: {e}")

    def load_recent(self, limit=1000):
        """
        Loads the most recent metrics (inefficient for large files, but fine for this scope).
        For production, we would query a DB or read tail.
        """
        data = []
        if not self.file_path.exists():
            return data
            
        try:
            with open(self.file_path, 'r') as f:
                # Read all lines is simple but memory intensive for huge files.
                # For a monitor running for hours, this is okay. 
                # Optimization: Seek to end and read backwards, or simply keep in memory window.
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")
            
        return data
