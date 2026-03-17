"""
TraceStore: SQLite persistence for PromptTrace objects.

Schema is designed for time-series queries:
  - Lookup by prompt_hash to retrieve all historical traces for drift analysis
  - Lookup by tags for cost attribution reports
  - Time-windowed aggregates for dashboard queries
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


CREATE_TRACES_SQL = """
CREATE TABLE IF NOT EXISTS prompt_traces (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id            TEXT NOT NULL UNIQUE,
    prompt_hash         TEXT NOT NULL,
    prompt_text         TEXT NOT NULL,
    model               TEXT NOT NULL,
    provider            TEXT NOT NULL,
    temperature         REAL,
    max_tokens          INTEGER,

    response_text       TEXT,
    response_length     INTEGER DEFAULT 0,
    prompt_tokens       INTEGER DEFAULT 0,
    completion_tokens   INTEGER DEFAULT 0,
    total_tokens        INTEGER DEFAULT 0,
    finish_reason       TEXT,
    is_truncated        INTEGER DEFAULT 0,
    is_refusal          INTEGER DEFAULT 0,

    request_ts          REAL NOT NULL,
    ttft_ms             REAL DEFAULT 0,
    total_latency_ms    REAL DEFAULT 0,
    tokens_per_second   REAL DEFAULT 0,
    estimated_cost_usd  REAL DEFAULT 0,

    tags_json           TEXT DEFAULT '{}'
);
"""

CREATE_EMBEDDINGS_SQL = """
CREATE TABLE IF NOT EXISTS response_embeddings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id        TEXT NOT NULL UNIQUE,
    prompt_hash     TEXT NOT NULL,
    model           TEXT NOT NULL,
    request_ts      REAL NOT NULL,
    embedding_json  TEXT NOT NULL,
    FOREIGN KEY (trace_id) REFERENCES prompt_traces(trace_id)
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_traces_hash ON prompt_traces(prompt_hash);",
    "CREATE INDEX IF NOT EXISTS idx_traces_ts   ON prompt_traces(request_ts);",
    "CREATE INDEX IF NOT EXISTS idx_traces_model ON prompt_traces(model);",
    "CREATE INDEX IF NOT EXISTS idx_emb_hash    ON response_embeddings(prompt_hash);",
    "CREATE INDEX IF NOT EXISTS idx_emb_ts      ON response_embeddings(request_ts);",
]


class TraceStore:
    """Thread-safe SQLite store for prompt traces and response embeddings."""

    def __init__(self, db_path: str = "data/observability.db"):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_schema(self):
        conn = self._conn()
        conn.execute(CREATE_TRACES_SQL)
        conn.execute(CREATE_EMBEDDINGS_SQL)
        for idx in CREATE_INDEXES_SQL:
            conn.execute(idx)
        conn.commit()

    # ── Write ──────────────────────────────────────────────────────────

    def save_trace(self, trace) -> None:
        """Persist a PromptTrace. Embedding stored separately if present."""
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO prompt_traces (
                trace_id, prompt_hash, prompt_text, model, provider,
                temperature, max_tokens, response_text, response_length,
                prompt_tokens, completion_tokens, total_tokens,
                finish_reason, is_truncated, is_refusal,
                request_ts, ttft_ms, total_latency_ms, tokens_per_second,
                estimated_cost_usd, tags_json
            ) VALUES (
                :trace_id, :prompt_hash, :prompt_text, :model, :provider,
                :temperature, :max_tokens, :response_text, :response_length,
                :prompt_tokens, :completion_tokens, :total_tokens,
                :finish_reason, :is_truncated, :is_refusal,
                :request_ts, :ttft_ms, :total_latency_ms, :tokens_per_second,
                :estimated_cost_usd, :tags_json
            )""",
            {
                **trace.to_dict(),
                "is_truncated": int(trace.is_truncated),
                "is_refusal": int(trace.is_refusal),
                "tags_json": json.dumps(trace.tags),
            },
        )
        conn.commit()

        if trace.response_embedding:
            self.save_embedding(
                trace.trace_id,
                trace.prompt_hash,
                trace.model,
                trace.request_ts,
                trace.response_embedding,
            )

    def save_embedding(
        self,
        trace_id: str,
        prompt_hash: str,
        model: str,
        request_ts: float,
        embedding: list,
    ) -> None:
        conn = self._conn()
        conn.execute(
            """INSERT OR REPLACE INTO response_embeddings
               (trace_id, prompt_hash, model, request_ts, embedding_json)
               VALUES (?, ?, ?, ?, ?)""",
            (trace_id, prompt_hash, model, request_ts, json.dumps(embedding)),
        )
        conn.commit()

    # ── Read ───────────────────────────────────────────────────────────

    def get_traces_for_hash(
        self,
        prompt_hash: str,
        days: int = 30,
        limit: int = 500,
    ) -> list[dict]:
        """All traces for a specific prompt over the last N days."""
        since = datetime.now(timezone.utc).timestamp() - days * 86400
        conn = self._conn()
        rows = conn.execute(
            """SELECT * FROM prompt_traces
               WHERE prompt_hash = ? AND request_ts >= ?
               ORDER BY request_ts ASC
               LIMIT ?""",
            (prompt_hash, since, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_embeddings_for_hash(
        self, prompt_hash: str, days: int = 30
    ) -> list[dict]:
        since = datetime.now(timezone.utc).timestamp() - days * 86400
        conn = self._conn()
        rows = conn.execute(
            """SELECT trace_id, request_ts, embedding_json FROM response_embeddings
               WHERE prompt_hash = ? AND request_ts >= ?
               ORDER BY request_ts ASC""",
            (prompt_hash, since),
        ).fetchall()
        return [
            {
                "trace_id": r["trace_id"],
                "request_ts": r["request_ts"],
                "embedding": json.loads(r["embedding_json"]),
            }
            for r in rows
        ]

    def get_all_tracked_hashes(self) -> list[str]:
        """All distinct prompt hashes that have been traced."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT prompt_hash FROM prompt_traces ORDER BY prompt_hash"
        ).fetchall()
        return [r[0] for r in rows]

    def get_recent_traces(self, hours: int = 24, limit: int = 200) -> list[dict]:
        since = datetime.now(timezone.utc).timestamp() - hours * 3600
        conn = self._conn()
        rows = conn.execute(
            """SELECT * FROM prompt_traces
               WHERE request_ts >= ?
               ORDER BY request_ts DESC
               LIMIT ?""",
            (since, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_cost_by_tag(
        self, tag_key: str, days: int = 30
    ) -> list[dict]:
        """Aggregate cost grouped by a specific tag value (e.g. tag_key='feature')."""
        since = datetime.now(timezone.utc).timestamp() - days * 86400
        conn = self._conn()
        rows = conn.execute(
            """SELECT tags_json, SUM(estimated_cost_usd) as total_cost,
                      SUM(total_tokens) as total_tokens, COUNT(*) as call_count
               FROM prompt_traces
               WHERE request_ts >= ?
               GROUP BY tags_json""",
            (since,),
        ).fetchall()

        # Parse tag_key from JSON and regroup
        from collections import defaultdict
        agg = defaultdict(lambda: {"total_cost": 0.0, "total_tokens": 0, "call_count": 0})
        for row in rows:
            tags = json.loads(row["tags_json"])
            key_val = tags.get(tag_key, "untagged")
            agg[key_val]["total_cost"] += row["total_cost"]
            agg[key_val]["total_tokens"] += row["total_tokens"]
            agg[key_val]["call_count"] += row["call_count"]

        return [{"tag_value": k, **v} for k, v in agg.items()]

    def get_model_summary(self, days: int = 7) -> list[dict]:
        since = datetime.now(timezone.utc).timestamp() - days * 86400
        conn = self._conn()
        rows = conn.execute(
            """SELECT model, provider,
                      COUNT(*) as call_count,
                      AVG(ttft_ms) as avg_ttft_ms,
                      AVG(total_latency_ms) as avg_latency_ms,
                      AVG(tokens_per_second) as avg_tps,
                      SUM(estimated_cost_usd) as total_cost,
                      SUM(CASE WHEN is_truncated THEN 1 ELSE 0 END) as truncated_count,
                      SUM(CASE WHEN is_refusal THEN 1 ELSE 0 END) as refusal_count
               FROM prompt_traces
               WHERE request_ts >= ?
               GROUP BY model, provider
               ORDER BY total_cost DESC""",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]
