import math

import pytest

from harness.scoring import (
    bootstrap_interval,
    decide,
    log_score,
    paired_scores,
    render_report,
)


def rec(variant, qid, forecast, time, qtype="binary", errors=0):
    return {
        "question_id": qid,
        "post_id": qid,
        "question_type": qtype,
        "variant": variant,
        "forecast": forecast,
        "forecast_time": time,
        "error_count": errors,
    }


def test_binary_log_score():
    assert log_score("binary", 0.8, "yes") == pytest.approx(math.log(0.8))
    assert log_score("binary", 0.8, "no") == pytest.approx(math.log(0.2))


def test_binary_log_score_clips_extremes():
    assert log_score("binary", 1.0, "no") == pytest.approx(math.log(0.001))


def test_multiple_choice_log_score():
    assert log_score("multiple_choice", {"a": 0.3, "b": 0.7}, "b") == pytest.approx(math.log(0.7))


def test_annulled_and_unknown_are_unscored():
    assert log_score("binary", 0.5, "annulled") is None
    assert log_score("binary", 0.5, "ambiguous") is None
    assert log_score("multiple_choice", {"a": 1.0}, "z") is None
    assert log_score("numeric", [{"percentile": 0.5, "value": 1}], "3.0") is None


def test_pairs_use_latest_forecast_before_close():
    records = [
        rec("A", 1, 0.6, "2026-10-20T00:00:00+00:00"),
        rec("A", 1, 0.9, "2026-10-21T00:00:00+00:00"),
        rec("A", 1, 0.1, "2026-10-25T00:00:00+00:00"),  # after close: ignored
        rec("B", 1, 0.7, "2026-10-20T06:00:00+00:00", errors=1),
        rec("A", 2, 0.5, "2026-10-20T00:00:00+00:00"),  # no B record: unpaired
    ]
    resolutions = {
        "1": {"resolution": "yes", "close_time": "2026-10-22T00:00:00+00:00"},
        "2": {"resolution": "no", "close_time": "2026-10-22T00:00:00+00:00"},
    }
    pairs = paired_scores(records, resolutions)
    assert len(pairs) == 1
    assert pairs[0].question_id == 1
    assert pairs[0].score_a == pytest.approx(math.log(0.9))
    assert pairs[0].score_b == pytest.approx(math.log(0.7))
    assert pairs[0].had_errors is True


def test_bootstrap_of_constant_differences_is_that_constant():
    assert bootstrap_interval([0.1] * 50) == pytest.approx((0.1, 0.1))


def test_bootstrap_is_deterministic_and_ordered():
    diffs = [0.3, -0.1, 0.2, 0.05, -0.2, 0.4, 0.1]
    low, high = bootstrap_interval(diffs)
    assert low < high
    assert bootstrap_interval(diffs) == (low, high)


def test_decide():
    assert decide(99, 0.5) == "Keep collecting"
    assert decide(100, 0.01) == "Switch to B"
    assert decide(150, -0.01) == "Keep collecting"
    assert decide(250, -0.01) == "End the B experiment and keep A"


def test_render_report_with_no_pairs():
    text = render_report([], "2026-10-26")
    assert "No paired, resolved questions yet" in text


def test_render_report_mentions_decision_and_counts():
    records = [rec("A", 1, 0.6, "2026-10-20T00:00:00+00:00"), rec("B", 1, 0.8, "2026-10-20T00:00:00+00:00")]
    pairs = paired_scores(records, {"1": {"resolution": "yes", "close_time": None}})
    text = render_report(pairs, "2026-10-26")
    assert "Paired questions: 1" in text
    assert "Decision: Keep collecting" in text


def _one_pair(close_time, forecast_time_a, forecast_time_b="2026-10-20T00:00:00+00:00"):
    records = [rec("A", 1, 0.9, forecast_time_a), rec("B", 1, 0.7, forecast_time_b)]
    return paired_scores(records, {"1": {"resolution": "yes", "close_time": close_time}})


def test_close_time_with_non_utc_offset():
    # 20:00-05:00 on the 21st is 01:00 UTC on the 22nd, so a 23:00 UTC forecast counts
    assert len(_one_pair("2026-10-21T20:00:00-05:00", "2026-10-21T23:00:00+00:00")) == 1


def test_close_time_with_z_suffix():
    assert len(_one_pair("2026-10-22T00:00:00Z", "2026-10-22T00:00:00+00:00")) == 1
    assert _one_pair("2026-10-22T00:00:00Z", "2026-10-22T00:00:01+00:00") == []


def test_fractional_seconds_around_boundary():
    close = "2026-10-22T00:00:00+00:00"
    assert len(_one_pair(close, "2026-10-21T23:59:59.999999+00:00")) == 1
    assert _one_pair(close, "2026-10-22T00:00:00.000001+00:00") == []


def test_missing_close_time_key_means_no_cutoff():
    records = [rec("A", 1, 0.9, "2026-10-20T00:00:00+00:00"), rec("B", 1, 0.7, "2026-10-20T00:00:00+00:00")]
    assert len(paired_scores(records, {"1": {"resolution": "yes"}})) == 1


from datetime import datetime, timezone
from types import SimpleNamespace

from harness.score import fetch_resolution, missing_by_post


def test_missing_by_post_skips_cached():
    records = [{"question_id": 1, "post_id": 10}, {"question_id": 2, "post_id": 20}, {"question_id": 1, "post_id": 10}]
    assert missing_by_post(records, {"1": {"resolution": "yes", "close_time": None}}) == {20: {2}}


def test_missing_by_post_groups_questions_per_post():
    records = [{"question_id": 1, "post_id": 10}, {"question_id": 2, "post_id": 10}]
    assert missing_by_post(records, {}) == {10: {1, 2}}


def _sub(qid, state, resolution):
    return SimpleNamespace(
        id_of_question=qid,
        state=SimpleNamespace(value=state),
        resolution_string=resolution,
        close_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class _StubClient:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def get_question_by_post_id(self, post_id, group_question_mode="exclude"):
        self.calls += 1
        return self.result


def test_fetch_resolution_returns_only_resolved_from_one_call():
    client = _StubClient([_sub(1, "resolved", "yes"), _sub(2, "open", None)])
    assert fetch_resolution(client, 10, {1, 2}) == {1: {"resolution": "yes", "close_time": "2026-01-01T00:00:00+00:00"}}
    assert client.calls == 1


def test_fetch_resolution_single_object_and_unwanted_ids():
    client = _StubClient(_sub(1, "resolved", "no"))
    assert fetch_resolution(client, 10, {1}) == {1: {"resolution": "no", "close_time": "2026-01-01T00:00:00+00:00"}}
    assert fetch_resolution(client, 10, {9}) == {}
