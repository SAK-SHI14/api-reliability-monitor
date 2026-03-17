from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import subprocess
import sys
import sqlite3
import os
import json

import asyncio
import threading
import logging
from api_reliability_monitor.main import run_monitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Determine absolute paths
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mock_script = os.path.join(root_dir, "llm_observability ollama", "mock_data.py")
    
    def run_initialization():
        # 1. Start the telemetry poller (Blocking loop in a thread)
        logger.info("BOOTSTRAP: Starting background telemetry worker...")
        try:
            # 2. Run the LLM Mock Generator first to prime the DB
            if os.path.exists(mock_script):
                logger.info("BOOTSTRAP: Initializing LLM Trace Mock Data...")
                subprocess.run([sys.executable, mock_script], cwd=os.path.dirname(mock_script), check=False)
            
            # 3. Start the infinite monitoring loop
            run_monitor()
        except Exception as e:
            logger.error(f"BOOTSTRAP ERROR: {e}")

    # Start entire background logic in one non-blocking thread
    thread = threading.Thread(target=run_initialization, daemon=True)
    thread.start()
    
    yield
    logger.info("SHUTDOWN: Stopping backend services...")

app = FastAPI(title="Unified Observability API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths to the two databases
API_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "api_reliability_monitor", "data", "observability.db")
LLM_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "llm_observability ollama", "data", "observability.db")

def get_db_connection(db_path):
    # Create the directory if missing (Resilience for first-run)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Connect
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Ensure tables exist even if the poller hasn't finished its first cycle
    # This prevents 404/500 errors on first frontend load
    try:
        cursor = conn.cursor()
        if "api_reliability_monitor" in db_path:
            cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (id INTEGER PRIMARY KEY, timestamp REAL, api_name TEXT, url TEXT, latency_ms REAL, status_code INTEGER, is_success BOOLEAN)")
            cursor.execute("CREATE TABLE IF NOT EXISTS pipeline_events (id INTEGER PRIMARY KEY, timestamp REAL, event_type TEXT, stage TEXT, metrics_json TEXT)")
        elif "llm_observability" in db_path:
            cursor.execute("CREATE TABLE IF NOT EXISTS prompt_traces (id INTEGER PRIMARY KEY, trace_id TEXT, prompt_hash TEXT, request_ts REAL, total_latency_ms REAL, tokens_per_second REAL, total_tokens INTEGER)")
        conn.commit()
    except Exception as e:
        logger.warning(f"DB Warmup Warning: {e}")
        
    return conn

@app.get("/api/system/status")
def get_system_status():
    return {
        "status": "operational",
        "api_db_exists": os.path.exists(API_DB_PATH),
        "llm_db_exists": os.path.exists(LLM_DB_PATH),
        "paths": {
            "api_db": API_DB_PATH,
            "llm_db": LLM_DB_PATH
        }
    }

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/api-metrics")
def get_api_metrics(seconds: int = 600):
    conn = get_db_connection(API_DB_PATH)
    # Get recent metrics
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM api_metrics ORDER BY timestamp DESC LIMIT 100")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.get("/api/pipeline-events")
def get_pipeline_events():
    conn = get_db_connection(API_DB_PATH)
    
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pipeline_events ORDER BY timestamp DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    
    events = []
    for row in rows:
        r = dict(row)
        if r.get("metrics_json"):
            try:
                r["metrics"] = json.loads(r["metrics_json"])
            except:
                r["metrics"] = {}
        events.append(r)
    return events

@app.get("/api/llm-traces")
def get_llm_traces():
    conn = get_db_connection(LLM_DB_PATH)
    
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prompt_traces ORDER BY request_ts DESC LIMIT 100")
    rows = cursor.fetchall()
    conn.close()
    
    traces = []
    for row in rows:
        r = dict(row)
        traces.append(r)
    return traces

# Mount the React frontend
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    # Use PORT from environment for cloud deployment, default to 8000 locally
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
