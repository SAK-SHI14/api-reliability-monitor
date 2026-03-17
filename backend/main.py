from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import subprocess
import sys
import sqlite3
import os
import json

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Determine the exact absolute path to the poller script
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monitor_path = os.path.join(root_dir, "api_reliability_monitor", "main.py")
    
    logger.info(f"BOOTSTRAP: Starting background telemetry worker at {monitor_path}")
    
    if not os.path.exists(monitor_path):
        logger.error(f"FATAL: Monitor script not found at {monitor_path}")
    else:
        try:
            # Use absolute path for CWD to avoid any ambiguity
            poller_cwd = os.path.dirname(monitor_path)
            poller = subprocess.Popen(
                [sys.executable, monitor_path], 
                cwd=poller_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info(f"BOOTSTRAP: Background worker started with PID {poller.pid}")
        except Exception as e:
            logger.error(f"FATAL: Failed to start background worker: {e}")

    yield
    
    logger.info("SHUTDOWN: Terminating background telemetry worker")
    try:
        poller.terminate()
        poller.wait(timeout=5)
    except Exception as e:
        logger.warning(f"SHUTDOWN: Error terminating worker: {e}")

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
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/api-metrics")
def get_api_metrics(seconds: int = 600):
    conn = get_db_connection(API_DB_PATH)
    if not conn:
        raise HTTPException(status_code=404, detail="API DB not found")
    
    # Get recent metrics
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM api_metrics WHERE timestamp > (strftime('%s', 'now') - ?) ORDER BY timestamp DESC LIMIT 500",
        (seconds,)
    )
    # The stored timestamp is just time.time(). For time.time(), it's usually UTC epoch.
    # Actually 'now' is not time.time(). It's better to fetch all and filter in python if time logic is complex, 
    # but the API monitor uses python `time.time()`. 
    # Let's just fetch recent 500 records.
    cursor.execute("SELECT * FROM api_metrics ORDER BY timestamp DESC LIMIT 100")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.get("/api/pipeline-events")
def get_pipeline_events():
    conn = get_db_connection(API_DB_PATH)
    if not conn:
        raise HTTPException(status_code=404, detail="API DB not found")
    
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
    if not conn:
        raise HTTPException(status_code=404, detail="LLM DB not found")
    
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
