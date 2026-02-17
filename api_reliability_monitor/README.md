# API Reliability Monitoring System

## Overview
A real-time, production-grade system to monitor the reliability and latency of public APIs. It actively pings configured endpoints, stores raw metrics, and visualizes live health status on an auto-refreshing dashboard.

## Key Features
- **Live Monitoring**: Pings APIs every few seconds (configurable).
- **Real-Time Dashboard**: Streamlit dashboard updates automatically without page reload.
- **Reliability Metrics**: Tracks Availability (%), Avg Latency, P95/P99.
- **Raw Data Storage**: Compiles all metrics into JSONL for audit and replay.

## Architecture
1.  **Collector**: `main.py` -> `src/collector/pinger.py` loops through APIs defined in `config.yaml`.
2.  **Storage**: `src/storage/metrics_store.py` appends results to `data/raw/metrics.jsonl`.
3.  **Visualization**: `src/ui/dashboard.py` reads from storage, computes stats via `src/processor/stats.py`, and renders charts.

## Setup & Usage

### 1. Installation
```bash
cd api_reliability_monitor
pip install -r requirements.txt
```

### 2. Configuration
Edit `config/config.yaml` to add APIs or change intervals.
```yaml
collection:
  interval_seconds: 5
  apis:
    - name: "Google DNS"
      url: "https://dns.google/resolve?name=google.com"
```

### 3. Run the Collector (Terminal 1)
Start the monitoring loop. This must keep running.
```bash
python main.py
```

### 4. Run the Dashboard (Terminal 2)
Launch the live view.
```bash
streamlit run src/ui/dashboard.py
```

## Engineering Decisions
- **JSONL Storage**: Chosen for simplicity and robustness. Appending to a file is atomic enough for this scale and allows for easy log rotation or ingestion into bigger systems (ELK, BigQuery) later.
- **Streamlit Polling**: The dashboard uses a "sleep & rerun" loop to simulate real-time updates, which is the standard pattern for simple Streamlit live monitors.
- **Separation of Concerns**: The collector is decoupled from the UI. The UI just reads the latest data. This allows the collector to run on a headless server while multiple users view the dashboard.
