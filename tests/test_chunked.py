from types import SimpleNamespace

from harness.chunked import forecast_in_chunks


class FakeBot:
    def __init__(self, cost_manager, cost_per_question):
        self.cost_manager = cost_manager
        self.cost_per_question = cost_per_question
        self.calls = []

    async def forecast_questions(self, questions, return_exceptions=False):
        self.calls.append(list(questions))
        self.cost_manager.amount_left -= self.cost_per_question * len(questions)
        return [f"report-{q}" for q in questions]


def test_processes_in_order_in_chunks_and_calls_on_chunk_per_chunk():
    cm = SimpleNamespace(amount_left=100.0)
    bot = FakeBot(cm, 1.0)
    chunks = []
    result = forecast_in_chunks(bot, [1, 2, 3, 4, 5], 2, cm, chunks.append)
    assert bot.calls == [[1, 2], [3, 4], [5]]
    assert chunks == [["report-1", "report-2"], ["report-3", "report-4"], ["report-5"]]
    assert result == [f"report-{i}" for i in range(1, 6)]


def test_stops_before_next_chunk_when_cap_is_used_up():
    cm = SimpleNamespace(amount_left=3.0)
    bot = FakeBot(cm, 1.0)
    chunks = []
    result = forecast_in_chunks(bot, list(range(10)), 2, cm, chunks.append)
    # chunk 1 leaves 1.0, chunk 2 leaves -1.0, so chunk 3 never starts
    assert bot.calls == [[0, 1], [2, 3]]
    assert chunks == [["report-0", "report-1"], ["report-2", "report-3"]]
    assert result == ["report-0", "report-1", "report-2", "report-3"]


def test_empty_question_list_makes_no_calls():
    cm = SimpleNamespace(amount_left=10.0)
    bot = FakeBot(cm, 1.0)
    chunks = []
    assert forecast_in_chunks(bot, [], 3, cm, chunks.append) == []
    assert bot.calls == []
    assert chunks == []
