from llm_regressor.checks.statistical import (
    _percentile,
    cost_regression,
    latency_regression,
    self_consistency,
)


def test_percentile_interpolates_between_ranks():
    assert _percentile([10, 20, 30, 40], 50) == 25.0
    assert _percentile([10, 20, 30, 40], 0) == 10
    assert _percentile([10, 20, 30, 40], 100) == 40
    assert _percentile([], 95) == 0.0


def test_percentile_exact_rank_needs_no_interpolation():
    assert _percentile([1, 2, 3], 50) == 2


def test_self_consistency_single_sample_is_vacuously_consistent():
    score, detail = self_consistency(["only one"])
    assert score == 1.0
    assert "fewer than 2" in detail


def test_self_consistency_identical_responses_score_one(no_embeddings):
    score, _ = self_consistency(["same text", "same text"])
    assert score == 1.0


def test_self_consistency_divergent_responses_score_lower(no_embeddings):
    same, _ = self_consistency(["the sky is blue", "the sky is blue"])
    different, detail = self_consistency(["the sky is blue", "quarterly revenue rose 12%"])
    assert different < same
    assert "2 samples" in detail


def test_self_consistency_averages_every_pair(no_embeddings):
    # 3 responses -> 3 pairs; the two identical ones pull the mean above the
    # score the odd one out would produce alone.
    score, detail = self_consistency(["abc", "abc", "xyz"])
    assert 0.0 < score < 1.0
    assert "3 samples" in detail


def test_self_consistency_uses_embeddings_when_available(fake_embeddings):
    score, _ = self_consistency(["a", "b"])
    assert score == 0.42


def test_latency_regression_passes_within_threshold():
    ok, detail = latency_regression([100, 110, 105], [120, 125, 118])
    assert ok is True
    assert "p95" in detail


def test_latency_regression_fails_when_candidate_far_slower():
    ok, _ = latency_regression([100, 100, 100], [1000, 1000, 1000])
    assert ok is False


def test_latency_regression_with_no_data_does_not_claim_a_regression():
    ok, detail = latency_regression([], [100])
    assert ok is True
    assert "insufficient" in detail


def test_cost_regression_flags_doubling_beyond_threshold():
    assert cost_regression([0.001], [0.0015])[0] is True
    assert cost_regression([0.001], [0.010])[0] is False


def test_cost_regression_skips_ratio_when_baseline_is_free():
    ok, detail = cost_regression([0.0, 0.0], [0.005])
    assert ok is True
    assert "skipping ratio check" in detail
