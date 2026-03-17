# LLM Observability — Prompt Tracing + Drift Detection (Ollama edition)

**100% local. 100% free. No API keys. No cloud.**

Drop these modules into your existing `api_reliability_monitor/` project.

## Prerequisites

```bash
# 1. Install Ollama
# → https://ollama.com/download  (Linux / macOS / Windows)

# 2. Start the Ollama server (keep this running in background)
ollama serve

# 3. Pull the models you want to monitor
ollama pull llama3.2              # main chat model (~2GB)
ollama pull nomic-embed-text      # embedding model for semantic drift (~274MB)

# Optional extras
ollama pull mistral
ollama pull phi3
ollama pull gemma2

# 4. Install Python deps
pip install requests streamlit plotly pandas
```

## New directory structure

```
api_reliability_monitor/
│
├── src/
│   ├── ollama/
│   │   └── ollama_client.py       ← Ollama REST client (chat, stream, embed)
│   │
│   ├── tracer/
│   │   └── prompt_tracer.py       ← Core: hash, trace, record every LLM call
│   │
│   ├── drift/
│   │   ├── drift_detector.py      ← 5-signal drift analysis per prompt_hash
│   │   └── canary_runner.py       ← Scheduled canary prompts (ground truth)
│   │
│   ├── storage/
│   │   └── trace_store.py         ← SQLite persistence (extends observability.db)
│   │
│   └── ui/
│       └── dashboard_drift.py     ← Streamlit dashboard
│
├── examples/
│   └── integration_example.py     ← Ollama drop-in wrappers
│
└── config/
    └── config.yaml                ← Ollama + canary + drift config
```

## How it works

```
Every Ollama call
     │
     ▼
PromptTracer.trace()
  • prompt_hash = SHA256(model | temperature | normalised_prompt)[:16]
  • Measures TTFT, total latency, tokens/sec (from Ollama's native stats)
  • Records token counts, finish_reason, refusal detection
     │
     ├──► TraceStore.save_trace()        → prompt_traces table
     └──► TraceStore.save_embedding()    → response_embeddings table
               ↑ uses nomic-embed-text via Ollama (free, local, 768-dim)

Every hour (CanaryRunner)
     │
     ▼
Run fixed canary prompts at temperature=0.0
  • Same prompt → same model → should produce stable responses
  • If you run `ollama pull llama3.2` and get a newer version,
    the canary detects the behavioural change automatically

Every 30 min (DriftDetector.analyse_all())
     │
     ▼
For each prompt_hash with ≥30 traces:
  • baseline = older 20 traces, current = latest 10 traces
  • Signal 1: cross-window cosine similarity on response embeddings
  • Signal 2: z-score on response_length distribution
  • Signal 3: z-score on tokens_per_second (catches model quantisation changes)
  • Signal 4: truncation rate delta
  • Signal 5: refusal rate delta
  → DriftReport: severity = none | warning | critical
```

## Quickstart

### 1. Wrap your first Ollama call

```python
from src.ollama.ollama_client import OllamaClient
from src.tracer.prompt_tracer import PromptTracer
from src.storage.trace_store import TraceStore

ollama = OllamaClient()                        # http://localhost:11434
store  = TraceStore("data/observability.db")
tracer = PromptTracer(store)

with tracer.trace(
    prompt="Summarise this in 3 bullets.",
    model="llama3.2",
    tags={"feature": "summariser"},
) as ctx:
    resp = ollama.chat("llama3.2", "Summarise this in 3 bullets.")
    ctx.record_response(
        response_text=resp.text,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        finish_reason=resp.finish_reason,
        tokens_per_second=resp.tokens_per_second,  # Ollama's native value
    )
```

### 2. Or use the convenience wrapper (one line)

```python
from examples.integration_example import traced_chat, traced_chat_stream

# Non-streaming
reply = traced_chat("What causes thunder?", model="llama3.2")

# Streaming with accurate TTFT
for chunk in traced_chat_stream("Explain recursion in one paragraph"):
    print(chunk, end="", flush=True)
```

### 3. Launch the drift dashboard

```bash
streamlit run src/ui/dashboard_drift.py
```

### 4. Run the full example (canaries + drift report)

```bash
python examples/integration_example.py
```

## Why this works with Ollama specifically

**Token counts are exact.** Ollama returns `prompt_eval_count` and `eval_count`
in every response — no estimation needed unlike some cloud APIs.

**Tokens/sec is native.** Ollama's `eval_count / eval_duration` gives hardware-accurate
throughput. This becomes your primary performance signal instead of cost.

**Drift detection catches model updates.** When you run `ollama pull llama3.2`
and Ollama downloads a newer quantisation or version, the canary responses
shift — the detector flags it within the next analysis window.

**Embeddings are also local.** `nomic-embed-text` runs in Ollama with no external
calls. Semantic drift detection costs you zero beyond the electricity to run it.

## Key design decisions

**Why SHA-256 the prompt?**
The same logical prompt must always produce the same hash across restarts and
processes. `SHA256(model|temperature|normalised_prompt)[:16]` is deterministic,
fast to index, and collision-free at any realistic deployment scale.

**Why temperature=0 for canaries?**
Ollama models have some inherent randomness above temperature=0. Locking to 0
makes canary responses as deterministic as the model allows, so drift signals
reflect actual model changes rather than sampling noise.

**Why five drift signals?**
Each catches a different type of change:
- Semantic drift → model giving different answers
- Length drift   → model becoming more/less verbose
- Throughput     → quantisation or hardware changes (unique to local models)
- Truncation     → context window changes
- Refusal rate   → alignment/safety tuning changes

