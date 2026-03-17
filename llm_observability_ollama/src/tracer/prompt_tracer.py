"""
Prompt-level tracer for LLM API calls — Ollama edition.

Intercepts every LLM request, assigns a deterministic prompt_hash,
records full trace (tokens, latency, TTFT, finish_reason), and
stores response embeddings for downstream drift detection.

100% local — works with Ollama running on localhost. No API keys,
no cloud costs, no rate limits.
"""

import hashlib
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone

from ..storage.trace_store import TraceStore
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PromptTrace:
    """Immutable record of a single LLM call."""
    trace_id: str
    prompt_hash: str               # SHA-256 of normalised prompt
    prompt_text: str
    model: str
    provider: str                  # Always "ollama" in this setup
    temperature: float
    max_tokens: int

    # Response fields (filled after call)
    response_text: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""        # "stop" | "length" | "error"
    is_truncated: bool = False
    is_refusal: bool = False

    # Timing — the key performance signals for local models
    request_ts: float = 0.0       # Unix epoch
    ttft_ms: float = 0.0          # Time-to-first-token (measures model load + first gen)
    total_latency_ms: float = 0.0
    tokens_per_second: float = 0.0 # Ollama reports this natively — use it

    # Cost: always $0.00 for Ollama (local inference)
    # Kept in schema for forward-compatibility if you ever add a paid provider
    estimated_cost_usd: float = 0.0

    # Tagging (for attribution: which feature/team generated this call)
    tags: dict = field(default_factory=dict)

    # Drift signals (populated by DriftDetector)
    response_embedding: Optional[list] = None
    response_length: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("response_embedding", None)  # stored separately in embeddings table
        return d


# ── Refusal detection ─────────────────────────────────────────────────
# Catches cases where the model refuses rather than answers.
# Useful for detecting safety-tuning changes across model versions.
REFUSAL_SIGNALS = [
    "i cannot", "i can't", "i'm unable", "i am unable",
    "i won't", "i will not", "as an ai", "i don't have the ability",
    "i'm not able", "i apologize, but i cannot",
    "i'm sorry, but i can't", "that's not something i can",
]


def compute_prompt_hash(prompt: str, model: str, temperature: float) -> str:
    """
    Deterministic hash — same prompt + model + temperature always → same hash.
    Normalises whitespace so trivial formatting changes don't create new hashes.
    Truncated to 16 hex chars (64-bit) — collision probability negligible for
    the scale of any single monitoring deployment.
    """
    normalised = " ".join(prompt.split()).lower()
    payload = f"{model}|{temperature:.2f}|{normalised}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def detect_refusal(text: str) -> bool:
    lower = text.lower()
    return any(signal in lower for signal in REFUSAL_SIGNALS)


class PromptTracer:
    """
    Wraps any Ollama LLM call with full observability.

    Usage (non-streaming):
        tracer = PromptTracer(store)

        with tracer.trace(
            prompt="Summarise this in 3 bullets.",
            model="llama3.2",
            tags={"feature": "summariser"},
        ) as ctx:
            result = ollama_client.chat(...)
            ctx.record_response(
                response_text=result["message"]["content"],
                prompt_tokens=result["prompt_eval_count"],
                completion_tokens=result["eval_count"],
                tokens_per_second=result["eval_count"] / (result["eval_duration"] / 1e9),
            )

    Usage (streaming):
        with tracer.trace(prompt, model="llama3.2") as ctx:
            for chunk in ollama_client.chat(..., stream=True):
                ctx.mark_first_token()   # call on first chunk only
                text += chunk["message"]["content"]
            ctx.record_response(text, prompt_tokens, completion_tokens)
    """

    def __init__(self, store: TraceStore):
        self.store = store

    def trace(
        self,
        prompt: str,
        model: str,
        provider: str = "ollama",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        tags: Optional[dict] = None,
    ) -> "TraceContext":
        prompt_hash = compute_prompt_hash(prompt, model, temperature)
        trace = PromptTrace(
            trace_id=str(uuid.uuid4()),
            prompt_hash=prompt_hash,
            prompt_text=prompt,
            model=model,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
            request_ts=time.time(),
            tags=tags or {},
            estimated_cost_usd=0.0,    # always free with Ollama
        )
        return TraceContext(trace, self.store)


class TraceContext:
    """Context manager returned by PromptTracer.trace()."""

    def __init__(self, trace: PromptTrace, store: TraceStore):
        self._trace = trace
        self._store = store
        self._start = time.perf_counter()
        self._first_token_ts: Optional[float] = None

    def __enter__(self):
        return self

    def mark_first_token(self):
        """
        Call this the moment the first streaming chunk arrives.
        For Ollama this captures model-load time + first token generation,
        which is the primary performance signal for local inference.
        """
        if self._first_token_ts is None:
            self._first_token_ts = time.perf_counter()
            self._trace.ttft_ms = (self._first_token_ts - self._start) * 1000

    def record_response(
        self,
        response_text: str,
        prompt_tokens: int,
        completion_tokens: int,
        finish_reason: str = "stop",
        tokens_per_second: Optional[float] = None,
    ):
        """
        Call after the full response is received.

        tokens_per_second: pass Ollama's native eval_count / eval_duration
        directly for highest accuracy. If None, it is computed from elapsed time.
        """
        elapsed = (time.perf_counter() - self._start) * 1000

        self._trace.response_text      = response_text
        self._trace.response_length    = len(response_text)
        self._trace.prompt_tokens      = prompt_tokens
        self._trace.completion_tokens  = completion_tokens
        self._trace.total_tokens       = prompt_tokens + completion_tokens
        self._trace.finish_reason      = finish_reason
        self._trace.total_latency_ms   = elapsed
        self._trace.is_truncated       = finish_reason == "length"
        self._trace.is_refusal         = detect_refusal(response_text)
        self._trace.estimated_cost_usd = 0.0   # Ollama is always free

        if self._first_token_ts is None:
            self._trace.ttft_ms = elapsed

        # Prefer Ollama's native tokens/sec (more accurate than wall-clock)
        if tokens_per_second is not None:
            self._trace.tokens_per_second = tokens_per_second
        elif elapsed > 0 and completion_tokens > 0:
            self._trace.tokens_per_second = (completion_tokens / elapsed) * 1000

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._trace.finish_reason = "error"
        try:
            self._store.save_trace(self._trace)
            logger.info(
                "trace_saved",
                extra={
                    "trace_id":    self._trace.trace_id,
                    "prompt_hash": self._trace.prompt_hash,
                    "model":       self._trace.model,
                    "tokens":      self._trace.total_tokens,
                    "tps":         round(self._trace.tokens_per_second, 1),
                    "ttft_ms":     round(self._trace.ttft_ms, 1),
                    "latency_ms":  round(self._trace.total_latency_ms, 1),
                },
            )
        except Exception as e:
            logger.error(f"Failed to save trace: {e}")
        return False   # never suppress caller exceptions
