import pandas as pd
import datetime
import logging

logger = logging.getLogger(__name__)

class StatsProcessor:
    def __init__(self, window_minutes=15):
        self.window_minutes = window_minutes

    def process(self, metrics_data):
        """
        Computes rolling statistics from a list of metric dictionaries.
        Returns a DataFrame with aggregated stats per API.
        """
        if not metrics_data:
            return pd.DataFrame()
            
        df = pd.DataFrame(metrics_data)
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter for the last N minutes
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=self.window_minutes)
        df_window = df[df['timestamp'] >= cutoff_time].copy()
        
        if df_window.empty:
            return pd.DataFrame()
            
        # Group by API Name
        stats = []
        for api_name, group in df_window.groupby('api_name'):
            total_reqs = len(group)
            failed_reqs = len(group[group['is_success'] == False])
            error_rate = (failed_reqs / total_reqs) * 100 if total_reqs > 0 else 0
            
            # Latency stats (only for successful requests or all? Usually all attempts that didn't timeout completely)
            # If status_code is 0 (timeout), latency might be the timeout value.
            # Let's use all latency values captured.
            avg_latency = group['latency_ms'].mean()
            p95_latency = group['latency_ms'].quantile(0.95)
            p99_latency = group['latency_ms'].quantile(0.99)
            
            # Current Status (based on last request)
            last_req = group.sort_values('timestamp').iloc[-1]
            status = "UP" if last_req['is_success'] else "DOWN"
            
            stats.append({
                "api_name": api_name,
                "total_requests": total_reqs,
                "error_rate_pct": round(error_rate, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "p95_latency_ms": round(p95_latency, 2),
                "p99_latency_ms": round(p99_latency, 2),
                "status": status,
                "last_checked": last_req['timestamp']
            })
            
        return pd.DataFrame(stats)

    def get_timeseries(self, metrics_data):
        """
        Returns the raw dataframe prepared for time-series plotting.
        """
        if not metrics_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(metrics_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter window
        cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=self.window_minutes)
        df = df[df['timestamp'] >= cutoff_time]
        
        return df.sort_values('timestamp')
