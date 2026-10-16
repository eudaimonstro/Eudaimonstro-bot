from types import SimpleNamespace

from harness.shadow import questions_to_forecast


def q(question_id, qtype="binary"):
    return SimpleNamespace(id_of_question=question_id, get_api_type_name=lambda: qtype)


def test_skips_already_forecast_and_conditional():
    questions = [q(1), q(2), q(3, "conditional"), q(4, "numeric")]
    assert [x.id_of_question for x in questions_to_forecast(questions, done_ids={2})] == [1, 4]


def test_deduplicates_questions_in_both_tournaments():
    assert [x.id_of_question for x in questions_to_forecast([q(1), q(1)], done_ids=set())] == [1]
