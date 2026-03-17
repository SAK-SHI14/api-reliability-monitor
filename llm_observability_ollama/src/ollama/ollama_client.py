"""
OllamaClient: Production-grade client for the local Ollama server.

Handles:
  - Non-streaming chat completions
  - Streaming chat with accurate TTFT marking
  - Model management (list, pull, check availability)
  - Native token count extraction from Ollama's response metadata
  - Embedding generation using Ollama's /api/embeddings endpoint
    (uses nomic-embed-text by default — pull with: ollama pull nomic-embed-text)
  - Health check for the Ollama server

Zero external dependencies beyond the standard library + requests.
No API keys. No cloud. Runs 100% locally.

Ollama must be running: `ollama serve`
Default base URL: http://localhost:11434
"""

import json
import time
from typing import Optional, Iterator, Callable
from dataclasses import dataclass

import requests

from ..utils.logger import get_logger

logger = get_logger(__name__)

OLLAMA_DEFAULT_URL = "http://localhost:11434"


# ── Response dataclass ────────────────────────────────────────────────

@dataclass
class OllamaResponse:
    """Parsed response from Ollama's /api/chat endpoint."""
    text: str
    model: str
    prompt_tokens: int         # prompt_eval_count from Ollama
    completion_tokens: int     # eval_count from Ollama
    total_tokens: int
    finish_reason: str         # "stop" | "length"
    tokens_per_second: float   # eval_count / eval_duration (nanoseconds)
    total_latency_ms: float    # wall-clock from request start to end
    ttft_ms: float             # time to first token (streaming only; 0 for non-streaming)
    raw: dict                  # original Ollama response dict


# ── Client ────────────────────────────────────────────────────────────

class OllamaClient:
    """
    Wrapper around Ollama's REST API.

    Usage:
        client = OllamaClient()                     # localhost:11434
        client = OllamaClient("http://192.168.1.5:11434")  # remote machine

        # Non-streaming
        resp = client.chat("llama3.2", "What is 2 + 2?")
        print(resp.text, resp.tokens_per_second)

        # Streaming
        for chunk in client.chat_stream("llama3.2", "Tell me a story"):
            print(chunk, end="", flush=True)

        # Embeddings (for drift detection)
        vec = client.embed("nomic-embed-text", "Hello world")
    """

    def __init__(
        self,
        base_url: str = OLLAMA_DEFAULT_URL,
        timeout: int = 120,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session = requests.Session()

    # ── Health & model management ─────────────────────────────────────

    def is_healthy(self) -> bool:
        """Returns True if the Ollama server is reachable."""
        try:
            r = self._session.get(f"{self.base_url}/", timeout=5)
            return r.status_code == 200
        except requests.ConnectionError:
            return False

    def list_models(self) -> list[dict]:
        """Returns list of locally available models."""
        r = self._session.get(f"{self.base_url}/api/tags", timeout=10)
        r.raise_for_status()
        return r.json().get("models", [])

    def model_names(self) -> list[str]:
        return [m["name"] for m in self.list_models()]

    def is_model_available(self, model: str) -> bool:
        """Check if model is already pulled locally."""
        names = self.model_names()
        # Ollama stores models as "llama3.2:latest" — match with or without tag
        return any(
            n == model or n.startswith(model + ":")
            for n in names
        )

    def pull_model(self, model: str) -> None:
        """Pull a model if not already available. Blocks until complete."""
        if self.is_model_available(model):
            logger.info(f"Model already available: {model}")
            return
        logger.info(f"Pulling model: {model} — this may take a few minutes...")
        r = self._session.post(
            f"{self.base_url}/api/pull",
            json={"name": model, "stream": False},
            timeout=600,
        )
        r.raise_for_status()
        logger.info(f"Model pulled: {model}")

    # ── Non-streaming chat ────────────────────────────────────────────

    def chat(
        self,
        model: str,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        context_window: Optional[int] = None,
    ) -> OllamaResponse:
        """
        Single-turn chat completion. Blocks until the full response is ready.
        Returns OllamaResponse with native token counts and throughput.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if context_window:
            payload["options"]["num_ctx"] = context_window

        start = time.perf_counter()
        resp_json = self._post_with_retry("/api/chat", payload)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return self._parse_response(resp_json, elapsed_ms, ttft_ms=0.0)

    # ── Streaming chat ────────────────────────────────────────────────

    def chat_stream(
        self,
        model: str,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        on_first_token: Optional[Callable] = None,
    ) -> Iterator[str]:
        """
        Streaming chat. Yields text chunks as they arrive.

        on_first_token: optional callback called the moment the first
        chunk arrives. Pass ctx.mark_first_token for TTFT tracking.

        The final (done=True) chunk contains token counts — these are
        available via the last_stream_stats property after iteration ends.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        self._last_stream_stats = {}
        first_token = False

        r = self._session.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=self.timeout,
        )
        r.raise_for_status()

        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)

            if not first_token:
                first_token = True
                if on_first_token:
                    on_first_token()

            text = chunk.get("message", {}).get("content", "")
            if text:
                yield text

            if chunk.get("done"):
                self._last_stream_stats = chunk   # contains eval_count etc.
                break

    @property
    def last_stream_stats(self) -> dict:
        """
        After a streaming call, returns the final Ollama stats chunk:
        {eval_count, eval_duration, prompt_eval_count, ...}
        Use this to get accurate token counts post-stream.
        """
        return getattr(self, "_last_stream_stats", {})

    def stream_token_counts(self) -> tuple[int, int, float]:
        """
        Helper to extract (prompt_tokens, completion_tokens, tokens_per_second)
        from last_stream_stats. Call after chat_stream iteration is complete.
        """
        stats = self.last_stream_stats
        prompt_tokens     = stats.get("prompt_eval_count", 0)
        completion_tokens = stats.get("eval_count", 0)
        eval_duration_ns  = stats.get("eval_duration", 1)   # nanoseconds
        tps = completion_tokens / (eval_duration_ns / 1e9) if eval_duration_ns > 0 else 0.0
        finish = "length" if stats.get("done_reason") == "length" else "stop"
        return prompt_tokens, completion_tokens, tps, finish

    # ── Embeddings ────────────────────────────────────────────────────

    def embed(self, text: str, model: str = "nomic-embed-text") -> list[float]:
        """
        Generate a text embedding using a locally-running Ollama embedding model.

        Recommended free models:
          nomic-embed-text   — 768-dim, great quality (pull: ollama pull nomic-embed-text)
          mxbai-embed-large  — 1024-dim, higher quality (pull: ollama pull mxbai-embed-large)
          all-minilm         — 384-dim, fastest (pull: ollama pull all-minilm)

        These embeddings are used by DriftDetector for semantic drift analysis.
        """
        payload = {"model": model, "prompt": text}
        resp = self._post_with_retry("/api/embeddings", payload)
        return resp.get("embedding", [])

    def embed_batch(self, texts: list[str], model: str = "nomic-embed-text") -> list[list[float]]:
        """Embed multiple texts. Sequential — Ollama doesn't batch natively."""
        return [self.embed(t, model) for t in texts]

    # ── Internal helpers ──────────────────────────────────────────────

    def _post_with_retry(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        last_exc = None
        for attempt in range(self.max_retries):
            try:
                r = self._session.post(url, json=payload, timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            except requests.exceptions.Timeout:
                logger.warning(f"Ollama timeout on attempt {attempt + 1}: {path}")
                last_exc = TimeoutError(f"Ollama did not respond within {self.timeout}s")
            except requests.exceptions.ConnectionError as e:
                logger.error(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    f"Is 'ollama serve' running? Error: {e}"
                )
                raise RuntimeError(
                    f"Ollama server not reachable at {self.base_url}. "
                    "Start it with: ollama serve"
                ) from e
            except requests.HTTPError as e:
                logger.error(f"Ollama HTTP error: {e.response.status_code} — {e.response.text}")
                raise

            time.sleep(self.retry_delay * (2 ** attempt))

        raise last_exc or RuntimeError("Ollama request failed after retries")

    def _parse_response(
        self,
        resp: dict,
        elapsed_ms: float,
        ttft_ms: float,
    ) -> OllamaResponse:
        msg = resp.get("message", {})
        text = msg.get("content", "")

        prompt_tokens     = resp.get("prompt_eval_count", 0)
        completion_tokens = resp.get("eval_count", 0)
        eval_duration_ns  = resp.get("eval_duration", 1)
        tps = completion_tokens / (eval_duration_ns / 1e9) if eval_duration_ns > 0 else 0.0

        finish_reason = "length" if resp.get("done_reason") == "length" else "stop"

        return OllamaResponse(
            text=text,
            model=resp.get("model", ""),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason=finish_reason,
            tokens_per_second=round(tps, 2),
            total_latency_ms=round(elapsed_ms, 1),
            ttft_ms=round(ttft_ms, 1),
            raw=resp,
        )
