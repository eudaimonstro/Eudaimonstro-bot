import json
from datetime import datetime, timezone
from types import SimpleNamespace

from forecasting_tools import BinaryQuestion, PredictedOptionList
from forecasting_tools.data_models.multiple_choice_report import PredictedOption

from harness.recorder import load_records, record_reports, report_to_record

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def fake_question(qtype: str, post_id: int = 1, question_id: int = 11):
    return SimpleNamespace(get_api_type_name=lambda: qtype, id_of_post=post_id, id_of_question=question_id)


def fake_report(question, prediction, errors=None, price=0.12):
    return SimpleNamespace(question=question, prediction=prediction, errors=errors or [], price_estimate=price)


def test_binary_record_with_real_question_type():
    question = BinaryQuestion(question_text="Will it rain?", id_of_post=5, id_of_question=55)
    record = report_to_record(fake_report(question, 0.7), "A", ("m1",), NOW)
    assert record == {
        "question_id": 55,
        "post_id": 5,
        "question_type": "binary",
        "variant": "A",
        "forecast": 0.7,
        "forecast_time": "2026-10-20T12:00:00+00:00",
        "model_ids": ["m1"],
        "price_usd": 0.12,
        "error_count": 0,
    }


def test_multiple_choice_record_is_option_map():
    options = PredictedOptionList(
        predicted_options=[PredictedOption(option_name="a", probability=0.25), PredictedOption(option_name="b", probability=0.75)]
    )
    record = report_to_record(fake_report(fake_question("multiple_choice"), options), "B", ("m1", "m2"), NOW)
    assert record is not None
    assert record["forecast"] == {"a": 0.25, "b": 0.75}


def test_numeric_record_is_percentile_list():
    distribution = SimpleNamespace(declared_percentiles=[SimpleNamespace(percentile=0.1, value=3.0), SimpleNamespace(percentile=0.9, value=9.0)])
    record = report_to_record(fake_report(fake_question("numeric"), distribution), "A", ("m1",), NOW)
    assert record is not None
    assert record["forecast"] == [{"percentile": 0.1, "value": 3.0}, {"percentile": 0.9, "value": 9.0}]


def test_conditional_is_skipped():
    assert report_to_record(fake_report(fake_question("conditional"), object()), "A", ("m1",), NOW) is None


def test_errors_are_counted():
    record = report_to_record(fake_report(fake_question("binary"), 0.4, errors=["429", "timeout"]), "B", ("m1",), NOW)
    assert record is not None
    assert record["error_count"] == 2


def test_record_reports_appends_jsonl_and_skips_exceptions(tmp_path):
    reports = [fake_report(fake_question("binary", 1, 11), 0.6), RuntimeError("boom"), fake_report(fake_question("binary", 2, 22), 0.3)]
    assert record_reports(reports, "A", ("m1",), tmp_path, now=NOW) == 2
    assert record_reports(reports[:1], "A", ("m1",), tmp_path, now=NOW) == 1
    lines = (tmp_path / "A" / "2026-10-20.jsonl").read_text().splitlines()
    assert [json.loads(line)["question_id"] for line in lines] == [11, 22, 11]


def test_load_records_reads_every_variant(tmp_path):
    record_reports([fake_report(fake_question("binary", 1, 11), 0.6)], "A", ("m1",), tmp_path, now=NOW)
    record_reports([fake_report(fake_question("binary", 1, 11), 0.5)], "B", ("m1",), tmp_path, now=NOW)
    assert sorted(r["variant"] for r in load_records(tmp_path)) == ["A", "B"]


def test_load_records_on_missing_folder_is_empty(tmp_path):
    assert load_records(tmp_path / "nope") == []
