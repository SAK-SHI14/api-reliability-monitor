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
        Loads the most recent metrics efficiently using a deque with maxlen.
        This prevents reading the entire file into memory.
        """
        data = []
        if not self.file_path.exists():
            return data
            
        try:
            with open(self.file_path, 'r') as f:
                # Use deque to keep only the last 'limit' lines in memory efficiently
                from collections import deque
                last_lines = deque(f, maxlen=limit)
                
                for line in last_lines:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")
            
        return data
