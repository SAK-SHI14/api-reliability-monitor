"""
DriftDetector: Detects model behaviour drift for a given prompt_hash.

Three complementary signals are computed and combined into a DriftReport:

1. Semantic drift   — cosine similarity between response embeddings over time.
                      A drop in similarity means responses are semantically diverging.

2. Statistical drift — z-score on response_length and tokens_per_second distributions.
                       Catches cases where the model silently became more verbose or
                       slower without a semantic shift.

3. Quality drift    — rolling rates of is_truncated and is_refusal flags.
                      Catches safety-tuning changes and context-window policy changes.

The detector is intentionally provider-agnostic. It compares the last N traces
(the "current window") against the N traces before that (the "baseline window").

If embeddings are not available (no embedding model configured), only statistical
and quality signals are reported.
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..storage.trace_store import TraceStore
from ..utils.logger import get_logger

logger = get_logger(__name__)


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class WindowStats:
    """Summary statistics for a time window of traces."""
    trace_count: int = 0
    avg_response_length: float = 0.0
    std_response_length: float = 0.0
    avg_latency_ms: float = 0.0
    avg_ttft_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    truncation_rate: float = 0.0
    refusal_rate: float = 0.0
    avg_cost_usd: float = 0.0


@dataclass
class DriftSignal:
    name: str
    value: float            # The raw computed signal value
    threshold: float        # The threshold that triggers an alert
    is_drifted: bool
    description: str


@dataclass
class DriftReport:
    prompt_hash: str
    model: str
    provider: str
    generated_at: str

    baseline: WindowStats
    current: WindowStats

    signals: list[DriftSignal] = field(default_factory=list)
    overall_drifted: bool = False
    severity: str = "none"           # "none" | "warning" | "critical"
    summary: str = ""


# ── Cosine similarity (no external deps needed for basic embeddings) ──

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 1.0
    return dot / (mag_a * mag_b)


def mean_pairwise_cosine(embeddings: list[list[float]]) -> float:
    """Average cosine similarity across all pairs in a window."""
    if len(embeddings) < 2:
        return 1.0
    pairs = []
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            pairs.append(cosine_similarity(embeddings[i], embeddings[j]))
    return sum(pairs) / len(pairs)


def cross_window_cosine(
    baseline_embs: list[list[float]],
    current_embs: list[list[float]],
) -> float:
    """
    Average cosine similarity of every current embedding vs every baseline embedding.
    Low value = responses have semantically diverged from baseline.
    """
    if not baseline_embs or not current_embs:
        return 1.0
    sims = []
    for b in baseline_embs:
        for c in current_embs:
            sims.append(cosine_similarity(b, c))
    return sum(sims) / len(sims)


def z_score(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0
    return abs((value - mean) / std)


# ── Detector ─────────────────────────────────────────────────────────

class DriftDetector:
    """
    Detects behavioural drift for a given prompt_hash.

    Config:
        window_size     — number of recent traces in the "current" window
        baseline_size   — number of traces before that used as baseline
        sem_threshold   — cosine similarity below this → semantic drift alert
        z_threshold     — z-score above this → statistical drift alert
        quality_threshold — rate delta above this → quality drift alert
    """

    DEFAULT_CONFIG = {
        "window_size": 10,
        "baseline_size": 20,
        "sem_threshold": 0.85,   # < 0.85 cosine sim → semantic drift
        "z_threshold": 2.0,      # > 2σ on length/latency → statistical drift
        "quality_threshold": 0.15,  # > 15% delta in truncation/refusal rate
    }

    def __init__(self, store: TraceStore, config: Optional[dict] = None):
        self.store = store
        self.cfg = {**self.DEFAULT_CONFIG, **(config or {})}

    # ── Public API ────────────────────────────────────────────────────

    def analyse(self, prompt_hash: str, days: int = 30) -> Optional[DriftReport]:
        """
        Run full drift analysis for one prompt_hash.
        Returns None if there are not enough traces to compare.
        """
        traces = self.store.get_traces_for_hash(prompt_hash, days=days)
        total_needed = self.cfg["window_size"] + self.cfg["baseline_size"]

        if len(traces) < total_needed:
            logger.debug(
                f"Insufficient traces for {prompt_hash}: "
                f"{len(traces)}/{total_needed}"
            )
            return None

        baseline_traces = traces[: self.cfg["baseline_size"]]
        current_traces  = traces[-self.cfg["window_size"] :]

        baseline_stats = self._compute_stats(baseline_traces)
        current_stats  = self._compute_stats(current_traces)

        model    = current_traces[-1]["model"]
        provider = current_traces[-1]["provider"]

        signals = []

        # 1. Semantic drift (embedding-based)
        semantic_signal = self._semantic_drift(prompt_hash, days)
        if semantic_signal:
            signals.append(semantic_signal)

        # 2. Statistical drift on response length
        signals.append(self._length_drift(baseline_traces, current_traces))

        # 3. Statistical drift on tokens/sec (throughput)
        signals.append(self._throughput_drift(baseline_traces, current_traces))

        # 4. Quality: truncation rate change
        signals.append(self._quality_drift(
            "truncation_rate",
            baseline_stats.truncation_rate,
            current_stats.truncation_rate,
        ))

        # 5. Quality: refusal rate change
        signals.append(self._quality_drift(
            "refusal_rate",
            baseline_stats.refusal_rate,
            current_stats.refusal_rate,
        ))

        drifted_signals = [s for s in signals if s.is_drifted]
        overall_drifted = len(drifted_signals) > 0

        # Severity: 1 signal = warning, 2+ = critical
        severity = "none"
        if len(drifted_signals) == 1:
            severity = "warning"
        elif len(drifted_signals) >= 2:
            severity = "critical"

        report = DriftReport(
            prompt_hash=prompt_hash,
            model=model,
            provider=provider,
            generated_at=datetime.now(timezone.utc).isoformat(),
            baseline=baseline_stats,
            current=current_stats,
            signals=signals,
            overall_drifted=overall_drifted,
            severity=severity,
            summary=self._build_summary(prompt_hash, drifted_signals, severity),
        )

        if overall_drifted:
            logger.warning(
                "drift_detected",
                extra={
                    "prompt_hash": prompt_hash,
                    "model": model,
                    "severity": severity,
                    "signals": [s.name for s in drifted_signals],
                },
            )

        return report

    def analyse_all(self, days: int = 30) -> list[DriftReport]:
        """Run drift analysis across every tracked prompt_hash."""
        hashes = self.store.get_all_tracked_hashes()
        reports = []
        for ph in hashes:
            report = self.analyse(ph, days=days)
            if report:
                reports.append(report)
        return reports

    # ── Private helpers ───────────────────────────────────────────────

    def _compute_stats(self, traces: list[dict]) -> WindowStats:
        if not traces:
            return WindowStats()

        lengths  = [t["response_length"] for t in traces]
        latency  = [t["total_latency_ms"] for t in traces if t["total_latency_ms"] > 0]
        ttft     = [t["ttft_ms"] for t in traces if t["ttft_ms"] > 0]
        tps      = [t["tokens_per_second"] for t in traces if t["tokens_per_second"] > 0]
        costs    = [t["estimated_cost_usd"] for t in traces]

        trunc_rate   = sum(1 for t in traces if t["is_truncated"]) / len(traces)
        refusal_rate = sum(1 for t in traces if t["is_refusal"]) / len(traces)

        return WindowStats(
            trace_count=len(traces),
            avg_response_length=statistics.mean(lengths),
            std_response_length=statistics.stdev(lengths) if len(lengths) > 1 else 0.0,
            avg_latency_ms=statistics.mean(latency) if latency else 0.0,
            avg_ttft_ms=statistics.mean(ttft) if ttft else 0.0,
            avg_tokens_per_second=statistics.mean(tps) if tps else 0.0,
            truncation_rate=trunc_rate,
            refusal_rate=refusal_rate,
            avg_cost_usd=statistics.mean(costs),
        )

    def _semantic_drift(self, prompt_hash: str, days: int) -> Optional[DriftSignal]:
        emb_data = self.store.get_embeddings_for_hash(prompt_hash, days=days)
        if len(emb_data) < self.cfg["window_size"] + self.cfg["baseline_size"]:
            return None

        baseline_embs = [e["embedding"] for e in emb_data[: self.cfg["baseline_size"]]]
        current_embs  = [e["embedding"] for e in emb_data[-self.cfg["window_size"] :]]

        sim = cross_window_cosine(baseline_embs, current_embs)
        is_drifted = sim < self.cfg["sem_threshold"]

        return DriftSignal(
            name="semantic_drift",
            value=round(sim, 4),
            threshold=self.cfg["sem_threshold"],
            is_drifted=is_drifted,
            description=(
                f"Cross-window cosine similarity = {sim:.3f} "
                f"(threshold: {self.cfg['sem_threshold']})"
            ),
        )

    def _length_drift(
        self, baseline: list[dict], current: list[dict]
    ) -> DriftSignal:
        baseline_lengths = [t["response_length"] for t in baseline]
        current_lengths  = [t["response_length"] for t in current]

        bl_mean = statistics.mean(baseline_lengths)
        bl_std  = statistics.stdev(baseline_lengths) if len(baseline_lengths) > 1 else 0.0
        cur_mean = statistics.mean(current_lengths)

        z = z_score(cur_mean, bl_mean, bl_std)
        is_drifted = z > self.cfg["z_threshold"]
        direction = "increased" if cur_mean > bl_mean else "decreased"

        return DriftSignal(
            name="response_length_drift",
            value=round(z, 3),
            threshold=self.cfg["z_threshold"],
            is_drifted=is_drifted,
            description=(
                f"Avg response length {direction}: "
                f"{bl_mean:.0f} → {cur_mean:.0f} chars (z={z:.2f})"
            ),
        )

    def _throughput_drift(
        self, baseline: list[dict], current: list[dict]
    ) -> DriftSignal:
        bl_tps  = [t["tokens_per_second"] for t in baseline if t["tokens_per_second"] > 0]
        cur_tps = [t["tokens_per_second"] for t in current  if t["tokens_per_second"] > 0]

        if not bl_tps or not cur_tps:
            return DriftSignal(
                name="throughput_drift", value=0.0,
                threshold=self.cfg["z_threshold"], is_drifted=False,
                description="Insufficient throughput data",
            )

        bl_mean  = statistics.mean(bl_tps)
        bl_std   = statistics.stdev(bl_tps) if len(bl_tps) > 1 else 0.0
        cur_mean = statistics.mean(cur_tps)
        z = z_score(cur_mean, bl_mean, bl_std)

        return DriftSignal(
            name="throughput_drift",
            value=round(z, 3),
            threshold=self.cfg["z_threshold"],
            is_drifted=z > self.cfg["z_threshold"],
            description=(
                f"Tokens/sec: {bl_mean:.1f} → {cur_mean:.1f} (z={z:.2f})"
            ),
        )

    def _quality_drift(
        self, name: str, baseline_rate: float, current_rate: float
    ) -> DriftSignal:
        delta = abs(current_rate - baseline_rate)
        is_drifted = delta > self.cfg["quality_threshold"]
        direction = "↑" if current_rate > baseline_rate else "↓"

        return DriftSignal(
            name=name,
            value=round(delta, 4),
            threshold=self.cfg["quality_threshold"],
            is_drifted=is_drifted,
            description=(
                f"{name}: {baseline_rate:.1%} → {current_rate:.1%} "
                f"(Δ={delta:.1%} {direction})"
            ),
        )

    def _build_summary(
        self, prompt_hash: str, drifted: list[DriftSignal], severity: str
    ) -> str:
        if not drifted:
            return f"No drift detected for prompt {prompt_hash[:8]}."
        names = ", ".join(s.name.replace("_", " ") for s in drifted)
        return (
            f"[{severity.upper()}] Drift detected for {prompt_hash[:8]}: "
            f"{names}. Provider may have silently updated the model."
        )
