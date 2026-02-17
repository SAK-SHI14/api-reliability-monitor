import requests
import time
import logging
import datetime

logger = logging.getLogger(__name__)

class APIPinger:
    def __init__(self, timeout=3):
        self.timeout = timeout

    def ping(self, name, url, method="GET", headers=None):
        """
        Pings an API and returns a metric record.
        """
        start_time = time.time()
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        try:
            response = requests.request(method, url, headers=headers, timeout=self.timeout)
            latency_ms = (time.time() - start_time) * 1000
            status_code = response.status_code
            is_success = 200 <= status_code < 400
            error_message = None
            
        except requests.exceptions.Timeout:
            latency_ms = (time.time() - start_time) * 1000
            status_code = 0
            is_success = False
            error_message = "Timeout"
            logger.warning(f"Timeout pinging {name} ({url})")
            
        except requests.exceptions.RequestException as e:
            latency_ms = (time.time() - start_time) * 1000
            status_code = 0
            is_success = False
            error_message = str(e)
            logger.error(f"Error pinging {name} ({url}): {e}")
            
        metric = {
            "timestamp": timestamp,
            "api_name": name,
            "url": url,
            "latency_ms": round(latency_ms, 2),
            "status_code": status_code,
            "is_success": is_success,
            "error_message": error_message
        }
        
        return metric
