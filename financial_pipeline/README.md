# Financial Data Pipeline

## Overview
This project implements a production-grade financial data pipeline that ingests stock market data from Alpha Vantage, cleans and transforms it, computes statistical metrics, and visualizes the results via a Streamlit dashboard.

The pipeline is designed to be modular, scalable, and maintainable, following SOLID principles and data engineering best practices.

## Architecture
The pipeline consists of the following stages:
1.  **Ingestion Layer**: Fetches daily stock data from Alpha Vantage API with retry logic and rate limiting. Stores raw JSON responses in a partitioned data lake structure (`data/raw/alpha_vantage/symbol=.../date=...`).
2.  **Cleaning Layer**: Loads raw data, handles missing values (forward fill), removes duplicates, and ensures correct data types. Outputs to `data/processed/cleaned_data.parquet`.
3.  **Transformation Layer**: Computes financial metrics such as Daily Returns, Rolling Means (7, 14, 30 days), and Volatility (7-day rolling std dev). Outputs to `data/processed/analytics_data.parquet`.
4.  **Analysis Layer (Statistics Engine)**: Computes aggregate statistics (Mean, Median, Max, Volatility, etc.) for each stock symbol.
5.  **Visualization Layer**: A Streamlit dashboard (`src/visualization/dashboard.py`) to interactively explore price trends, moving averages, and volatility.

## Folder Structure
```
financial_pipeline/
├── config/
│   ├── config.yaml          # Main configuration (symbols, paths, settings)
│   └── logging_config.yaml  # Logging configuration
├── data/
│   ├── raw/                 # Raw API responses (partitioned)
│   └── processed/           # Cleaned and Transformed Parquet files
├── src/
│   ├── ingestion/           # Alpha Vantage Client
│   ├── processing/          # Cleaner and Transformer modules
│   ├── analysis/            # Statistics Engine
│   ├── visualization/       # Streamlit Dashboard
│   └── utils/               # Logger utility
├── main.py                  # Main pipeline orchestrator
├── requirements.txt         # Python dependencies
└── .env.example             # Environment variables template
```

## Setup & Usage

### 1. Prerequisites
- Python 3.8+
- Alpha Vantage API Key (Get a free key from [https://www.alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key))

### 2. Installation
```bash
# Clone the repository (if applicable) or navigate to the project directory
cd financial_pipeline

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
- Rename `.env.example` to `.env` and add your API key:
```bash
cp .env.example .env
# Edit .env and set ALPHA_VANTAGE_API_KEY=your_actual_key
```
- Update `config/config.yaml` to change target symbols or settings.

### 4. Run the Pipeline
To run the full ETL process (Ingestion -> Cleaning -> Transformation -> Analysis):
```bash
python main.py
```
Check `pipeline.log` for execution details.

### 5. Launch Dashboard
To visualize the processed data:
```bash
streamlit run src/visualization/dashboard.py
```

## Engineering Decisions
- **Parquet Format**: Used for processed data for efficient storage and faster read/write operations compared to CSV.
- **Partitioned Raw Storage**: Simulates a Data Lake pattern, making it easier to scale or backfill data.
- **Modular Design**: Each stage is a separate module, allowing for independent testing and easier migration to distributed systems like Spark (e.g., replacing pandas in `cleaner.py` with PySpark).
- **Config-Driven**: Hardcoded values are avoided; behavior is controlled via `config.yaml`.
- **Robustness**: Retries for API calls and comprehensive logging ensure reliability.
