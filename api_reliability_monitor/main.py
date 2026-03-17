import time
import yaml
import logging
import os
import sys

# Robust path handling for both standalone and package imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

# Import local modules using absolute package paths if possible, 
# otherwise fallback to direct imports
try:
    from .src.collector.pinger import APIPinger
    from .src.storage.database import ObservabilityDB
    from .src.utils.logger import setup_logging
except (ImportError, ValueError):
    from src.collector.pinger import APIPinger
    from src.storage.database import ObservabilityDB
    from src.utils.logger import setup_logging

# Get absolute paths relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

setup_logging(os.path.join(CONFIG_DIR, "logging_config.yaml"))
logger = logging.getLogger("main")

def load_config(config_path=None):
    if config_path is None:
        config_path = os.path.join(CONFIG_DIR, "config.yaml")
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}

def run_monitor():
    logger.info("Starting API Reliability Monitor...")
    
    config = load_config()
    if not config:
        return

    interval = config.get("collection", {}).get("interval_seconds", 10)
    apis = config.get("collection", {}).get("apis", [])
    
    pinger = APIPinger(timeout=config.get("collection", {}).get("timeout_seconds", 3))
    # db_path is auto-configured in database.py but can be overridden if needed
    db = ObservabilityDB()

    logger.info(f"Monitoring {len(apis)} APIs with {interval}s interval.")

    while True:
        try:
            cycle_start = time.time()
            
            for api in apis:
                metric = pinger.ping(
                    name=api["name"],
                    url=api["url"],
                    method=api.get("method", "GET"),
                    headers=api.get("headers")
                )
                
                # Log to SQLite
                db.log_api_metric(
                    api_name=metric['api_name'],
                    url=metric['url'],
                    latency_ms=metric['latency_ms'],
                    status_code=metric['status_code'],
                    is_success=metric['is_success']
                )
                
                status_icon = "[OK]" if metric["is_success"] else "[FAIL]"
                logger.info(f"{status_icon} {metric['api_name']} - {metric['latency_ms']}ms - {metric['status_code']}")

            # Sleep remaining time
            cycle_duration = time.time() - cycle_start
            sleep_time = max(0, interval - cycle_duration)
            time.sleep(sleep_time)
            
        except Exception as e:
            logger.error(f"Unexpected error in monitor loop: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    run_monitor()
