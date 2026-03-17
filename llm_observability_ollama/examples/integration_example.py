"""
Ollama integration — drop-in traced wrappers for local LLM calls.

100% free. No API keys. No cloud. Just Ollama running locally.

Prerequisites:
    1. Install Ollama:  https://ollama.com/download
    2. Start server:    ollama serve
    3. Pull models:     ollama pull llama3.2
                        ollama pull nomic-embed-text   (for semantic drift)
    4. Install deps:    pip install requests streamlit plotly pandas

Usage:
    response = traced_chat("What is 2 + 2?", model="llama3.2")
    print(response)
"""

from __future__ import annotations
import asyncio
from typing import Optional, Iterator

from src.ollama.ollama_client import OllamaClient
from src.tracer.prompt_tracer import PromptTracer
from src.storage.trace_store import TraceStore
from src.drift.drift_detector import DriftDetector
from src.drift.canary_runner import CanaryRunner, CanaryConfig

# ── Shared singletons (initialise once at app startup) ────────────────
ollama  = OllamaClient("http://localhost:11434")
store   = TraceStore("data/observability.db")
tracer  = PromptTracer(store)
detector = DriftDetector(store)

# ── Embedding function using Ollama's embedding models ────────────────
# nomic-embed-text is free, local, 768-dim — great for semantic drift
# Pull it once: ollama pull nomic-embed-text

def embedding_fn(text: str) -> list[float]:
    """
    Generate embeddings locally using Ollama.
    Falls back to empty list if the embedding model isn't pulled.
    """
    try:
        return ollama.embed(text, model="nomic-embed-text")
    except Exception as e:
        # If nomic-embed-text isn't pulled, drift runs in statistical-only mode
        print(f"[warning] Embedding unavailable (pull nomic-embed-text): {e}")
        return []


# ── Traced non-streaming chat ─────────────────────────────────────────

def traced_chat(
    prompt: str,
    model: str = "llama3.2",
    temperature: float = 0.7,
    max_tokens: int = 1024,
    system: str = "",
    tags: Optional[dict] = None,
) -> str:
    """
    Non-streaming chat call with full tracing.
    Returns the response text.

    Example:
        reply = traced_chat(
            "Summarise this in 3 bullets: ...",
            model="llama3.2",
            tags={"feature": "summariser", "team": "search"},
        )
    """
    with tracer.trace(
        prompt=prompt,
        model=model,
        provider="ollama",
        temperature=temperature,
        max_tokens=max_tokens,
        tags=tags or {},
    ) as ctx:
        resp = ollama.chat(
            model=model,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        ctx.record_response(
            response_text=resp.text,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            finish_reason=resp.finish_reason,
            tokens_per_second=resp.tokens_per_second,   # Ollama's native value
        )

        # Attach embedding for semantic drift analysis (free, local)
        embedding = embedding_fn(resp.text)
        if embedding:
            ctx._trace.response_embedding = embedding

    return resp.text


# ── Traced streaming chat ─────────────────────────────────────────────

def traced_chat_stream(
    prompt: str,
    model: str = "llama3.2",
    temperature: float = 0.7,
    max_tokens: int = 1024,
    tags: Optional[dict] = None,
) -> Iterator[str]:
    """
    Streaming chat with accurate TTFT tracing.
    Yields text chunks. Trace is saved after the last chunk.

    Example:
        for chunk in traced_chat_stream("Tell me about black holes"):
            print(chunk, end="", flush=True)
    """
    with tracer.trace(
        prompt=prompt,
        model=model,
        provider="ollama",
        temperature=temperature,
        max_tokens=max_tokens,
        tags=tags or {},
    ) as ctx:
        full_text = ""

        for chunk in ollama.chat_stream(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            on_first_token=ctx.mark_first_token,   # ← accurate TTFT
        ):
            full_text += chunk
            yield chunk

        # After stream ends, extract Ollama's native token stats
        prompt_tokens, completion_tokens, tps, finish_reason = (
            ollama.stream_token_counts()
        )

        ctx.record_response(
            response_text=full_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
            tokens_per_second=tps,
        )

        embedding = embedding_fn(full_text)
        if embedding:
            ctx._trace.response_embedding = embedding


# ── Multi-model comparison ────────────────────────────────────────────

def compare_models(
    prompt: str,
    models: list[str],
    temperature: float = 0.0,
    tags: Optional[dict] = None,
) -> dict[str, str]:
    """
    Run the same prompt against multiple local models and trace each.
    Useful for building baseline data for drift detection across models.

    Example:
        results = compare_models(
            "What is the capital of France?",
            models=["llama3.2", "mistral", "phi3"],
        )
    """
    results = {}
    for model in models:
        try:
            results[model] = traced_chat(
                prompt,
                model=model,
                temperature=temperature,
                tags={**(tags or {}), "comparison_run": "true"},
            )
        except Exception as e:
            results[model] = f"ERROR: {e}"
    return results


# ── Canary setup ──────────────────────────────────────────────────────

def build_ollama_llm_fn():
    """
    Returns an LLMCallFn compatible with CanaryRunner, using Ollama.
    Signature: (prompt, model, provider, temperature, max_tokens)
                → (response_text, prompt_tokens, completion_tokens, finish_reason)
    """
    def call(prompt: str, model: str, provider: str, temperature: float, max_tokens: int):
        resp = ollama.chat(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.text, resp.prompt_tokens, resp.completion_tokens, resp.finish_reason

    return call


# ── Example: run canaries + drift report ─────────────────────────────

if __name__ == "__main__":
    # ── Step 1: Check Ollama is running ──────────────────────────────
    if not ollama.is_healthy():
        print("❌ Ollama is not running. Start it with: ollama serve")
        exit(1)

    available = ollama.model_names()
    print(f"✅ Ollama running. Available models: {available}")

    # ── Step 2: Auto-pull required models if missing ──────────────────
    for model in ["llama3.2", "nomic-embed-text"]:
        if not ollama.is_model_available(model):
            print(f"📥 Pulling {model}...")
            ollama.pull_model(model)

    # ── Step 3: Run a traced chat call ───────────────────────────────
    print("\n─── Traced chat ───")
    reply = traced_chat(
        "What is 17 × 23? Show your working.",
        model="llama3.2",
        tags={"feature": "demo"},
    )
    print(reply)

    # ── Step 4: Streaming traced call ────────────────────────────────
    print("\n─── Streaming chat ───")
    for chunk in traced_chat_stream("Explain what a hash function does in one paragraph."):
        print(chunk, end="", flush=True)
    print()

    # ── Step 5: Set up canary runner ──────────────────────────────────
    canaries = [
        CanaryConfig(
            id="reasoning_llama",
            text="What is 17 × 23? Show your working step by step.",
            model="llama3.2",
            provider="ollama",
            temperature=0.0,   # deterministic — maximises drift signal
            max_tokens=256,
            tags={"type": "canary", "category": "reasoning"},
        ),
        CanaryConfig(
            id="instruction_following_llama",
            text="List exactly 5 European capitals, one per line, numbered 1 to 5.",
            model="llama3.2",
            provider="ollama",
            temperature=0.0,
            max_tokens=128,
            tags={"type": "canary", "category": "instruction_following"},
        ),
        CanaryConfig(
            id="factual_recall_llama",
            text="What is the chemical formula for water? Answer in one word.",
            model="llama3.2",
            provider="ollama",
            temperature=0.0,
            max_tokens=32,
            tags={"type": "canary", "category": "factual"},
        ),
    ]

    runner = CanaryRunner(
        canaries=canaries,
        tracer=tracer,
        llm_call_fn=build_ollama_llm_fn(),
        schedule_minutes=60,
        embedding_fn=embedding_fn,
    )

    # Run canaries once immediately
    print("\n─── Running canaries ───")
    results = runner.run_all_sync()
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['canary_id']} | {r.get('response_length', 0)} chars")

    # ── Step 6: Run drift analysis ────────────────────────────────────
    print("\n─── Drift analysis ───")
    reports = detector.analyse_all(days=30)
    if not reports:
        print("  Not enough history yet — run canaries for a few hours first.")
    else:
        for rep in reports:
            icon = {"none": "🟢", "warning": "🟡", "critical": "🔴"}.get(rep.severity, "⚪")
            print(f"  {icon} {rep.prompt_hash[:8]} | {rep.model} | {rep.severity.upper()}")
            if rep.overall_drifted:
                print(f"     {rep.summary}")
                for sig in rep.signals:
                    if sig.is_drifted:
                        print(f"     ↳ {sig.description}")

    # ── Step 7: Show model summary ────────────────────────────────────
    print("\n─── Model summary (last 7 days) ───")
    summary = store.get_model_summary(days=7)
    for row in summary:
        print(
            f"  {row['model']} | calls={row['call_count']} "
            f"| avg_ttft={row['avg_ttft_ms']:.0f}ms "
            f"| avg_tps={row['avg_tps']:.1f} "
            f"| truncations={row['truncated_count']}"
        )

    print("\n─── Launch dashboard ───")
    print("  streamlit run src/ui/dashboard_drift.py")

