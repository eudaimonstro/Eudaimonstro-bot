from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from harness.shadow import latest_a_times, questions_to_forecast

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def q(question_id, qtype="binary"):
    return SimpleNamespace(id_of_question=question_id, get_api_type_name=lambda: qtype)


def ids(questions, done_ids=None, a_times=None):
    return [x.id_of_question for x in questions_to_forecast(questions, done_ids or set(), a_times or {}, NOW)]


def test_skips_already_forecast_and_conditional():
    assert ids([q(1), q(2), q(3, "conditional"), q(4, "numeric")], done_ids={2}) == [1, 4]


def test_deduplicates_questions_in_both_tournaments():
    assert ids([q(1), q(1)]) == [1]


def test_skips_questions_whose_a_forecast_is_too_old_to_pair():
    a_times = {
        1: NOW - timedelta(hours=25),  # can never be scored: skip
        2: NOW - timedelta(hours=23),
        3: NOW - timedelta(hours=24),  # exactly at the limit still pairs
    }
    assert ids([q(1), q(2), q(3), q(4)], a_times=a_times) == [2, 3, 4]  # 4 has no A record yet


def test_latest_a_times_keeps_newest_a_forecast_per_question():
    records = [
        {"question_id": 1, "variant": "A", "forecast_time": "2026-10-19T00:00:00+00:00"},
        {"question_id": 1, "variant": "A", "forecast_time": "2026-10-20T00:00:00Z"},
        {"question_id": 1, "variant": "B", "forecast_time": "2026-10-20T06:00:00+00:00"},
        {"question_id": 2, "variant": "B", "forecast_time": "2026-10-20T06:00:00+00:00"},
    ]
    assert latest_a_times(records) == {1: datetime(2026, 10, 20, tzinfo=timezone.utc)}
