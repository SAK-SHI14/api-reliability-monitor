"""
CanaryRunner: Runs fixed "canary" prompts on a schedule.

Canary prompts are your ground truth. By running the same prompt against
the same model every hour, you build a clean time-series of responses
that the DriftDetector can analyse without any noise from user behaviour.

This is how you catch silent model updates: a provider updates gpt-4o at
3 AM, and by 4 AM your canary is already flagging semantic drift on the
same prompt that used to return consistent answers.

Configuration in config.yaml:

    canary:
      schedule_minutes: 60
      prompts:
        - id: "reasoning_canary"
          text: "What is 17 × 23? Show your working."
          model: "gpt-4o"
          provider: "openai"
          temperature: 0.0          # deterministic — maximises drift signal
          tags:
            type: "canary"
            category: "reasoning"

        - id: "instruction_following_canary"
          text: "List exactly 5 European capitals, numbered."
          model: "claude-sonnet-4-6"
          provider: "anthropic"
          temperature: 0.0
          tags:
            type: "canary"
            category: "instruction_following"
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from ..tracer.prompt_tracer import PromptTracer
from ..storage.trace_store import TraceStore
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CanaryConfig:
    id: str
    text: str
    model: str
    provider: str
    temperature: float = 0.0   # Always 0 for canaries — maximises drift signal
    max_tokens: int = 512
    tags: dict = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {"type": "canary"}
        self.tags["canary_id"] = self.id


# Type for the LLM call function your app provides
# Signature: (prompt, model, provider, temperature, max_tokens) -> (response_text, prompt_tokens, completion_tokens, finish_reason)
LLMCallFn = Callable[[str, str, str, float, int], tuple[str, int, int, str]]


class CanaryRunner:
    """
    Runs a set of canary prompts on a fixed schedule and records traces.

    Usage:
        runner = CanaryRunner(
            canaries=canary_configs,
            tracer=tracer,
            llm_call_fn=your_openai_wrapper,
            schedule_minutes=60,
        )
        # In your async event loop:
        await runner.run_forever()

        # Or run once (e.g. from a cron job):
        runner.run_all_sync()
    """

    def __init__(
        self,
        canaries: list[CanaryConfig],
        tracer: PromptTracer,
        llm_call_fn: LLMCallFn,
        schedule_minutes: int = 60,
        embedding_fn: Optional[Callable[[str], list[float]]] = None,
    ):
        self.canaries = canaries
        self.tracer = tracer
        self.llm_call_fn = llm_call_fn
        self.schedule_minutes = schedule_minutes
        self.embedding_fn = embedding_fn   # Optional: openai embeddings, sentence-transformers, etc.
        self._results: list[dict] = []

    def run_canary(self, canary: CanaryConfig) -> dict:
        """Execute a single canary prompt and return the trace summary."""
        logger.info(f"Running canary: {canary.id} ({canary.model})")

        result = {
            "canary_id": canary.id,
            "model": canary.model,
            "provider": canary.provider,
            "ts": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "error": None,
        }

        try:
            with self.tracer.trace(
                prompt=canary.text,
                model=canary.model,
                provider=canary.provider,
                temperature=canary.temperature,
                max_tokens=canary.max_tokens,
                tags=canary.tags,
            ) as ctx:
                response_text, prompt_tokens, completion_tokens, finish_reason = (
                    self.llm_call_fn(
                        canary.text,
                        canary.model,
                        canary.provider,
                        canary.temperature,
                        canary.max_tokens,
                    )
                )
                ctx.record_response(
                    response_text=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    finish_reason=finish_reason,
                )

                # Attach embedding if embedding function is configured
                if self.embedding_fn:
                    try:
                        ctx._trace.response_embedding = self.embedding_fn(response_text)
                    except Exception as e:
                        logger.warning(f"Embedding failed for canary {canary.id}: {e}")

                result["success"] = True
                result["trace_id"] = ctx._trace.trace_id
                result["prompt_hash"] = ctx._trace.prompt_hash
                result["response_length"] = len(response_text)
                result["finish_reason"] = finish_reason

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Canary {canary.id} failed: {e}")

        return result

    def run_all_sync(self) -> list[dict]:
        """Run all canaries synchronously (for cron / one-shot use)."""
        results = [self.run_canary(c) for c in self.canaries]
        self._results = results
        successes = sum(1 for r in results if r["success"])
        logger.info(f"Canary run complete: {successes}/{len(results)} succeeded")
        return results

    async def run_forever(self):
        """Async loop that runs all canaries every schedule_minutes."""
        logger.info(
            f"CanaryRunner started — {len(self.canaries)} canaries, "
            f"interval: {self.schedule_minutes}m"
        )
        while True:
            self.run_all_sync()
            await asyncio.sleep(self.schedule_minutes * 60)

    @property
    def last_results(self) -> list[dict]:
        return self._results


# ── Factory helper ────────────────────────────────────────────────────

def load_canaries_from_config(config: dict) -> list[CanaryConfig]:
    """Parse canary configs from the config.yaml canary section."""
    canary_cfg = config.get("canary", {})
    canaries = []
    for item in canary_cfg.get("prompts", []):
        canaries.append(
            CanaryConfig(
                id=item["id"],
                text=item["text"],
                model=item["model"],
                provider=item["provider"],
                temperature=item.get("temperature", 0.0),
                max_tokens=item.get("max_tokens", 512),
                tags=item.get("tags", {}),
            )
        )
    return canaries
