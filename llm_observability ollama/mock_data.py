import sys
import os
import time
import uuid
import random

sys.path.append(os.path.dirname(__file__))

from src.storage.trace_store import TraceStore

store = TraceStore("data/observability.db")

class DummyTrace:
    def __init__(self):
        self.trace_id = str(uuid.uuid4())
        self.prompt_hash = "abcdef1234567890"
        self.prompt_text = "What is 17x23?"
        self.model = "gpt-4o"
        self.provider = "openai"
        self.temperature = 0.0
        self.max_tokens = 100
        self.response_text = "391"
        self.response_length = 3
        self.prompt_tokens = 10
        self.completion_tokens = 2
        self.total_tokens = 12
        self.finish_reason = "stop"
        self.is_truncated = False
        self.is_refusal = False
        self.request_ts = time.time()
        self.ttft_ms = 150
        self.total_latency_ms = 300
        self.tokens_per_second = 10.0
        self.estimated_cost_usd = 0.0001
        self.tags = {"type": "canary", "category": "reasoning"}
        self.response_embedding = None

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "prompt_hash": self.prompt_hash,
            "prompt_text": self.prompt_text,
            "model": self.model,
            "provider": self.provider,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_text": self.response_text,
            "response_length": self.response_length,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "finish_reason": self.finish_reason,
            "request_ts": self.request_ts,
            "ttft_ms": self.ttft_ms,
            "total_latency_ms": self.total_latency_ms,
            "tokens_per_second": self.tokens_per_second,
            "estimated_cost_usd": self.estimated_cost_usd,
        }

# Generate 40 traces to have enough for drift analysis history (20 baseline + 10 current)
for i in range(40):
    t = DummyTrace()
    # Spread over the last 40 hours
    t.request_ts = time.time() - (40 - i) * 3600
    
    # Introduce drift in the last 10 entries (current window)
    if i >= 30:
        # simulate drift
        t.response_text = "Let me think. It is 391."
        t.response_length = len(t.response_text)
        t.completion_tokens = 6
        t.total_tokens = 16
        t.ttft_ms = 300 + random.randint(0, 50)
        t.total_latency_ms = 1000 + random.randint(0, 50)
        t.estimated_cost_usd = 0.0002
        t.tokens_per_second = 6.0
        t.response_embedding = [0.2] * 384
    else:
        t.ttft_ms = 150 + random.randint(0, 20)
        t.total_latency_ms = 300 + random.randint(0, 20)
        t.response_embedding = [0.1] * 384

    store.save_trace(t)

# Add another prompt hash without drift 
for i in range(40):
    t = DummyTrace()
    t.prompt_hash = "9876543210fedcba"
    t.prompt_text = "List 5 European capitals."
    t.model = "claude-sonnet-4-6"
    t.provider = "anthropic"
    t.request_ts = time.time() - (40 - i) * 3600
    t.response_text = "1. Paris\n2. Berlin\n3. Rome\n4. Madrid\n5. Vienna"
    t.response_length = len(t.response_text)
    t.prompt_tokens = 15
    t.completion_tokens = 25
    t.total_tokens = 40
    t.ttft_ms = 200 + random.randint(0, 20)
    t.total_latency_ms = 600 + random.randint(0, 20)
    t.tokens_per_second = 41.5
    t.response_embedding = [0.5] * 384
    store.save_trace(t)

print(f"Mock DB populated at data/observability.db")
