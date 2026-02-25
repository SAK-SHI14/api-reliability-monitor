<div align="center">

<h1>📡 API Reliability Monitor & Financial Data Pipeline</h1>

<p>
  <b>A production-grade observability platform for monitoring external API health in real-time,
  paired with an enterprise financial data pipeline powered by Alpha Vantage.</b>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Plotly-3F4F75?style=for-the-badge&logo=plotly&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />
</p>

<p>
  <a href="#-overview">Overview</a> •
  <a href="#-repository-structure">Structure</a> •
  <a href="#-api-reliability-monitor">API Monitor</a> •
  <a href="#-financial-data-pipeline">Financial Pipeline</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-engineering-decisions">Engineering</a> •
  <a href="#-contributing">Contributing</a>
</p>

</div>

---

## 🌐 Overview

This monorepo contains **two production-grade Python systems** built around the central philosophy of **observability-first engineering** — the idea that systems should actively report on their own health, and that data should flow reliably from source to insight.

| Sub-Project | Purpose | Tech Stack |
|---|---|---|
| [`api_reliability_monitor/`](./api_reliability_monitor/) | Real-time external API health monitoring | Python, Requests, SQLite, Streamlit, Altair |
| [`financial_pipeline/`](./financial_pipeline/) | End-to-end financial data ETL pipeline | Python, Alpha Vantage, Pandas, Parquet, Streamlit |

Both systems share a unified **SQLite observability backend**, allowing the live Streamlit dashboard to simultaneously display external API health AND internal pipeline health on a single pane of glass.

---

## 🗂️ Repository Structure

```
api-reliability-monitor/
│
├── 📁 api_reliability_monitor/       # Sub-project 1: Live API Monitor
│   ├── 📁 config/
│   │   ├── config.yaml               # API targets, intervals, timeouts
│   │   └── logging_config.yaml       # Structured logging configuration
│   ├── 📁 data/
│   │   └── observability.db          # Auto-generated SQLite database
│   ├── 📁 src/
│   │   ├── 📁 collector/
│   │   │   └── pinger.py             # Core HTTP polling engine (APIPinger)
│   │   ├── 📁 processor/             # Aggregation & statistical processing
│   │   ├── 📁 storage/
│   │   │   ├── database.py           # ObservabilityDB — unified SQLite ORM
│   │   │   └── metrics_store.py      # JSONL raw metric store
│   │   ├── 📁 ui/                    # Legacy Streamlit UI components
│   │   └── 📁 utils/
│   │       └── logger.py             # Structured logging setup
│   ├── dashboard_pro.py              # 🚀 Primary real-time observability dashboard
│   ├── main.py                       # Monitoring daemon entry point
│   └── requirements.txt
│
├── 📁 financial_pipeline/            # Sub-project 2: Financial ETL Pipeline
│   ├── 📁 config/
│   │   ├── config.yaml               # Symbols, data paths, Alpha Vantage settings
│   │   └── logging_config.yaml
│   ├── 📁 data/
│   │   ├── 📁 raw/                   # Partitioned raw JSON (Data Lake pattern)
│   │   └── 📁 processed/             # Cleaned & transformed Parquet files
│   ├── 📁 src/
│   │   ├── 📁 ingestion/
│   │   │   └── alpha_vantage_client.py  # Retryable Alpha Vantage API client
│   │   ├── 📁 processing/
│   │   │   ├── cleaner.py            # Missing value handling, deduplication
│   │   │   └── transformer.py        # Returns, rolling means, volatility
│   │   ├── 📁 analysis/
│   │   │   └── statistics_engine.py  # Aggregate stats per symbol
│   │   ├── 📁 visualization/
│   │   │   └── dashboard.py          # Interactive Streamlit analytics dashboard
│   │   └── 📁 utils/
│   │       ├── logger.py
│   │       └── telemetry.py          # Pipeline telemetry → observability.db
│   ├── 📁 tests/                     # Unit test suite
│   ├── main.py                       # Pipeline orchestrator entry point
│   ├── .env                          # API keys (gitignored)
│   └── requirements.txt
│
└── README.md                         # ← You are here
```

---

## 📡 API Reliability Monitor

### What It Does

The API Reliability Monitor is a **headless monitoring daemon** that continuously polls a configurable list of HTTP/HTTPS endpoints and records latency, status codes, and availability into an SQLite database. A live Streamlit dashboard reads this data and displays real-time health across three views:

- **System Health Overview** — Aggregated API and pipeline health status at a glance
- **External API Reliability** — Per-API latency time-series chart with error annotations
- **Internal Data Pipeline** — Pipeline stage events, lag metrics, and recent event log

### Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────────┐
│                       api_reliability_monitor/                      │
│                                                                    │
│   ┌──────────────┐    ping()    ┌──────────────────────────────┐   │
│   │   config.yaml│────────────▶│  APIPinger (pinger.py)       │   │
│   │  (API targets)│            │  • HTTP GET/POST              │   │
│   └──────────────┘            │  • Measures latency_ms        │   │
│                                │  • Captures status_code       │   │
│                                │  • Handles timeouts/errors    │   │
│                                └──────────────┬───────────────┘   │
│                                               │ metric dict        │
│                                               ▼                    │
│                                ┌──────────────────────────────┐   │
│                                │  ObservabilityDB (SQLite)    │   │
│                                │  ┌──────────────────────┐    │   │
│                                │  │ api_metrics table    │    │   │
│                                │  │ pipeline_events table│    │   │
│                                │  └──────────────────────┘    │   │
│                                └──────────────┬───────────────┘   │
│                                               │                    │
│                                               ▼                    │
│                                ┌──────────────────────────────┐   │
│                                │  dashboard_pro.py (Streamlit)│   │
│                                │  • 2s auto-refresh loop       │   │
│                                │  • Altair latency chart       │   │
│                                │  • Failure rate detection     │   │
│                                │  • Pipeline lag display       │   │
│                                └──────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

### Key Features

| Feature | Detail |
|---|---|
| 🔄 **Configurable Polling** | Interval, timeout, and target APIs defined purely in `config.yaml` — zero code changes needed to add a new endpoint |
| 📊 **Live Latency Charts** | Altair time-series charts updating every 2 seconds, per API, with colour coding |
| 🚨 **Failure Rate Alerting** | Dashboard status degrades automatically when failure rate exceeds 10% (Degraded) or 50% (Down) |
| 💾 **Persistent Storage** | SQLite with a proper ORM layer (`ObservabilityDB`). No flat-file corruption risks |
| 🏭 **Pipeline Health View** | The financial pipeline writes telemetry events into the same DB, giving a unified health view |
| 📋 **Structured Logging** | YAML-driven logging configuration with rotating file handlers |

### Configuration Reference

**`config/config.yaml`**

```yaml
collection:
  interval_seconds: 5      # How often to poll all APIs
  timeout_seconds: 3       # Per-request timeout

  apis:
    - name: "GitHub API"
      url: "https://api.github.com"
      method: "GET"
    - name: "JSONPlaceholder"
      url: "https://jsonplaceholder.typicode.com/posts/1"
      method: "GET"
    # Add any endpoint here — internal microservices, third-party APIs, etc.

storage:
  raw_path: "data/raw/metrics.jsonl"   # JSONL dump for replay/audit
  retention_days: 7

dashboard:
  refresh_interval: 2      # Seconds between dashboard updates
  window_minutes: 15       # Historical window shown in charts
```

---

## 💹 Financial Data Pipeline

### What It Does

A **config-driven, four-stage ETL pipeline** that ingests real-time and historical stock market data from [Alpha Vantage](https://www.alphavantage.co/), cleans and transforms it into analytics-ready formats, computes statistical metrics, and visualises results interactively. The pipeline is designed to be a drop-in foundation for a production financial data platform.

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         financial_pipeline/                          │
│                                                                     │
│  ┌──────────────┐                                                   │
│  │  config.yaml │  symbols: [AAPL, GOOGL, MSFT...]                 │
│  └──────┬───────┘                                                   │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Stage 1: INGESTION                                           │  │
│  │  AlphaVantageClient → fetch TIME_SERIES_INTRADAY per symbol  │  │
│  │  → Saves raw JSON to data/raw/alpha_vantage/symbol=.../      │  │
│  │    (Partitioned Data Lake pattern)                           │  │
│  └─────────────────────────────┬────────────────────────────────┘  │
│                                │                                    │
│                                ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Stage 2: CLEANING                                            │  │
│  │  DataCleaner → Forward-fill NaN, deduplicate, enforce dtypes │  │
│  │  → Outputs: data/processed/cleaned_data.parquet              │  │
│  └─────────────────────────────┬────────────────────────────────┘  │
│                                │                                    │
│                                ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Stage 3: TRANSFORMATION                                      │  │
│  │  DataTransformer → Daily Returns, 7/14/30-day Rolling Means, │  │
│  │  7-day Rolling Volatility (std dev)                          │  │
│  │  → Outputs: data/processed/analytics_data.parquet            │  │
│  └─────────────────────────────┬────────────────────────────────┘  │
│                                │                                    │
│                                ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Stage 4: ANALYSIS                                            │  │
│  │  StatisticsEngine → Mean, Median, Max, Volatility per symbol │  │
│  │  → Console report + structured log output                    │  │
│  └─────────────────────────────┬────────────────────────────────┘  │
│                                │                                    │
│                                ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Streamlit Dashboard (src/visualization/dashboard.py)         │  │
│  │  • Price trend charts      • Moving averages overlay         │  │
│  │  • Volatility heatmaps     • Symbol selector sidebar         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Features

| Feature | Detail |
|---|---|
| 📈 **Multi-Symbol Ingestion** | Ingests multiple ticker symbols in a single pipeline run, configurable in `config.yaml` |
| 🗄️ **Data Lake Pattern** | Raw JSON responses stored in `symbol=.../date=.../` partitioned directories — easy to backfill or replay |
| ⚡ **Parquet Storage** | Processed data stored in Apache Parquet for 10-100x faster reads vs CSV |
| 🔄 **Retry Logic** | Alpha Vantage client includes exponential backoff for transient API failures |
| 📡 **Pipeline Telemetry** | Each stage emits structured events (`start`, `success`, `error`) to the shared `observability.db` — visible in the Observability Dashboard |
| 🔢 **Financial Metrics** | Computes daily returns, 7/14/30-day rolling means, and 7-day rolling volatility (standard deviation) |
| 🔁 **Batch & Continuous Modes** | Set `execution_mode: continuous` in config for streaming-style repeated runs |

### Prerequisites

- Python 3.8+
- A free Alpha Vantage API key → [Get one here](https://www.alphavantage.co/support/#api-key)

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/SAK-SHI14/api-reliability-monitor.git
cd api-reliability-monitor
```

---

### 2. Setting Up the API Reliability Monitor

```bash
# Navigate to the sub-project
cd api_reliability_monitor

# Create and activate a virtual environment (recommended)
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

**Configure your target APIs** in `config/config.yaml`:

```yaml
collection:
  interval_seconds: 5
  apis:
    - name: "My Service"
      url: "https://your-api.example.com/health"
      method: "GET"
```

**Run the monitoring daemon** (Terminal 1 — keep this running):

```bash
python main.py
```

**Launch the live dashboard** (Terminal 2):

```bash
streamlit run dashboard_pro.py
```

Open your browser at **`http://localhost:8501`** to see the live observability dashboard.

---

### 3. Setting Up the Financial Data Pipeline

```bash
# Navigate to the sub-project
cd ../financial_pipeline

# Activate the same venv or create a new one
pip install -r requirements.txt
```

**Configure your API key:**

```bash
# Create a .env file from the template
copy .env.example .env     # Windows
# cp .env.example .env     # macOS / Linux
```

Edit `.env`:

```env
ALPHA_VANTAGE_API_KEY=your_actual_api_key_here
```

**Configure target symbols** in `config/config.yaml`:

```yaml
ingestion:
  symbols: ["AAPL", "GOOGL", "MSFT", "NVDA"]
  interval: "TIME_SERIES_INTRADAY"
  intraday_interval: "5min"
```

**Run the full ETL pipeline:**

```bash
python main.py
```

**Launch the analytics dashboard:**

```bash
streamlit run src/visualization/dashboard.py
```

---

### 4. Unified Observability View (Optional)

Run the financial pipeline first to populate telemetry, then launch the API Monitor dashboard — it will show **both** external API health and internal pipeline stage health on the same screen. No extra configuration required; both systems share `api_reliability_monitor/data/observability.db`.

---

## 🗄️ Database Schema

Both systems share a single SQLite database at `api_reliability_monitor/data/observability.db`.

### `api_metrics` Table

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-incrementing primary key |
| `timestamp` | REAL | Unix epoch timestamp |
| `api_name` | TEXT | Human-readable API label from config |
| `url` | TEXT | Full endpoint URL |
| `latency_ms` | REAL | Round-trip time in milliseconds |
| `status_code` | INTEGER | HTTP status code (0 = timeout/connection error) |
| `is_success` | BOOLEAN | True if `200 <= status_code < 400` |

### `pipeline_events` Table

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-incrementing primary key |
| `timestamp` | REAL | Unix epoch timestamp |
| `event_type` | TEXT | `start`, `success`, `error`, `heartbeat` |
| `stage` | TEXT | `ingestion`, `cleaning`, `transformation`, `analysis`, `pipeline` |
| `metrics_json` | TEXT | JSON string — flexible payload (records processed, error messages, etc.) |

---

## 🧠 Engineering Decisions

### Why SQLite Instead of a Cloud Database?

SQLite was chosen deliberately. It is:
- **Zero-configuration** — no server to spin up, no credentials to manage
- **Reliable for single-writer workloads** — the monitoring daemon is the sole writer
- **Portable** — the entire observability history ships as a single file
- **Sufficient at scale** — SQLite handles ~100K writes/day with sub-millisecond latency

For production scale (multi-node, multi-writer), the `ObservabilityDB` class can be swapped for PostgreSQL or TimescaleDB by changing only the connection string.

### Why Parquet for Financial Data?

Apache Parquet is the industry-standard columnar format for analytical workloads because:
- **Columnar storage** → queries that read only `close_price` don't load `open_price`
- **10-100x smaller** than equivalent CSV due to encodings and compression
- **Pandas/Spark compatible** → zero friction to migrate to distributed processing (PySpark)

### Why a Monolithic Streamlit Loop Instead of Caching?

The `while True: ... time.sleep(2)` pattern in the dashboard is intentional. Streamlit's native `st.cache` / `st.session_state` caching was avoided to ensure **always-current data** from the SQLite database without stale cache invalidation bugs. This is the standard pattern for simple real-time Streamlit monitors where data freshness > performance.

### Why Decoupled Collector and Dashboard?

The monitoring daemon (`main.py`) and the dashboard (`dashboard_pro.py`) are completely independent processes. This provides:
- **Fault isolation**: a dashboard crash does not stop metric collection
- **Headless deployability**: the collector runs on a server with no display; multiple users can view the dashboard simultaneously
- **Simpler testing**: each component can be tested independently

### Why JSONL as a Raw Data Dump?

`data/raw/metrics.jsonl` is maintained alongside SQLite as an append-only audit trail:
- **Replayable** — metrics can be re-imported into any database system
- **Portable** — can be streamed directly into ELK Stack, BigQuery, or Kafka
- **Atomic appends** — no corruption risk from partial writes

---

## 🧪 Testing

Unit tests for the financial pipeline are located in `financial_pipeline/tests/`.

```bash
cd financial_pipeline
pytest tests/ -v
```

---

## 📦 Dependencies

### `api_reliability_monitor/requirements.txt`

| Package | Purpose |
|---|---|
| `requests` | HTTP polling engine |
| `pyyaml` | Config file parsing |
| `pandas` | DataFrame operations for dashboard metrics |
| `streamlit` | Live observability dashboard |
| `plotly` | Interactive chart rendering |
| `python-dotenv` | Environment variable management |

### `financial_pipeline/requirements.txt`

| Package | Purpose |
|---|---|
| `pandas` | Core data manipulation |
| `numpy` | Numerical computing |
| `requests` | Alpha Vantage API client |
| `pyyaml` | Config parsing |
| `python-dotenv` | Secure API key loading |
| `streamlit` | Analytics dashboard |
| `matplotlib` / `seaborn` | Static chart generation |
| `plotly` | Interactive charts |
| `pyarrow` / `fastparquet` | Parquet read/write engines |
| `pytest` | Unit testing framework |

---

## 🔮 Roadmap

- [ ] **Alerting Engine** — Webhook / email / Slack notifications when API availability drops below threshold
- [ ] **Historical SLA Reports** — Generate weekly uptime % reports per API
- [ ] **Config Hot-Reload** — Detect `config.yaml` changes without restarting the daemon
- [ ] **Docker Compose** — Single-command deployment for both systems
- [ ] **Rate Limit Handling** — Smarter Alpha Vantage quota management (5 calls/min on free tier)
- [ ] **Multi-Region Monitoring** — Pin API pings from different geographic origins
- [ ] **REST API Layer** — FastAPI endpoint to query observability data programmatically

---

## 🤝 Contributing

Contributions are welcome! To contribute:

1. **Fork** the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. **Commit** your changes with clear messages: `git commit -m 'feat: add Slack alerting'`
4. **Push** to your branch: `git push origin feature/your-feature`
5. Open a **Pull Request** against `main`

Please follow [PEP 8](https://peps.python.org/pep-0008/) for Python code and ensure tests pass before submitting.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](./LICENSE) file for details.

---

<div align="center">

Built with 🐍 Python · 📊 Streamlit · 💾 SQLite · 📈 Altair

<i>Observability is not a feature — it's a foundation.</i>

</div>
