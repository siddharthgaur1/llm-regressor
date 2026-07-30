"""Statistical checks: operate across multiple samples/runs rather than a single response.

Regressor calls these directly (not through the per-response check registry) once it has
collected `samples` completions for baseline and candidate.
"""
from __future__ import annotations

import difflib
import statistics


def self_consistency(responses: list[str], **_) -> tuple[float, str]:
    """1.0 = identical across runs, lower = more variance. Uses embeddings if available, else lexical diff."""
    if len(responses) < 2:
        return 1.0, "fewer than 2 samples, treated as consistent"
    try:
        from sentence_transformers import SentenceTransformer, util
        from .llm_judge import _get_embedder

        model = _get_embedder()
        embs = model.encode(responses)
        sims = [float(util.cos_sim(embs[i], embs[j])[0][0]) for i in range(len(embs)) for j in range(i + 1, len(embs))]
    except ImportError:
        sims = [
            difflib.SequenceMatcher(None, responses[i], responses[j]).ratio()
            for i in range(len(responses)) for j in range(i + 1, len(responses))
        ]
    score = statistics.mean(sims) if sims else 1.0
    return score, f"mean pairwise similarity {score:.3f} across {len(responses)} samples"


def latency_regression(baseline_latencies: list[float], candidate_latencies: list[float], threshold: float = 1.5, **_):
    if not baseline_latencies or not candidate_latencies:
        return True, "insufficient latency data"
    base_p95 = _percentile(baseline_latencies, 95)
    cand_p95 = _percentile(candidate_latencies, 95)
    ok = cand_p95 <= base_p95 * threshold
    return ok, f"candidate p95 {cand_p95:.0f}ms vs baseline p95 {base_p95:.0f}ms (threshold {threshold}x)"


def cost_regression(baseline_costs: list[float], candidate_costs: list[float], threshold: float = 2.0, **_):
    base_avg = statistics.mean(baseline_costs) if baseline_costs else 0.0
    cand_avg = statistics.mean(candidate_costs) if candidate_costs else 0.0
    if base_avg == 0:
        return True, "baseline cost is 0, skipping ratio check"
    ok = cand_avg <= base_avg * threshold
    return ok, f"candidate avg cost ${cand_avg:.5f} vs baseline ${base_avg:.5f} (threshold {threshold}x)"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)
