"""Run variant B on open tournament questions it has not forecast yet. Never publishes."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from forecasting_tools import MetaculusClient, MonetaryCostManager

from config import VARIANTS, build_llms, build_panel
from harness.chunked import forecast_in_chunks
from harness.panel_bot import PanelBot
from harness.recorder import load_records, record_reports
from harness.scoring import MAX_GAP_HOURS, parse_time

FORECASTS = Path("data/forecasts")
logger = logging.getLogger(__name__)


def latest_a_times(records: list[dict]) -> dict[int, datetime]:
    times: dict[int, datetime] = {}
    for r in records:
        if r["variant"] != "A":
            continue
        t = parse_time(r["forecast_time"])
        if r["question_id"] not in times or t > times[r["question_id"]]:
            times[r["question_id"]] = t
    return times


def questions_to_forecast(
    questions: Sequence[Any], done_ids: set[int], a_times: dict[int, datetime], now: datetime
) -> list[Any]:
    # A B forecast more than MAX_GAP_HOURS after A's is never scored, so don't pay for it.
    # Questions A has not forecast yet are kept.
    oldest_pairable = now - timedelta(hours=MAX_GAP_HOURS)
    todo, seen = [], set(done_ids)
    for question in questions:
        if question.get_api_type_name() == "conditional" or question.id_of_question in seen:
            continue
        a_time = a_times.get(question.id_of_question)
        if a_time is not None and a_time < oldest_pairable:
            continue
        seen.add(question.id_of_question)
        todo.append(question)
    return todo


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    variant = VARIANTS["B"]
    records = load_records(FORECASTS)
    done = {r["question_id"] for r in records if r["variant"] == "B"}

    client = MetaculusClient()
    questions = []
    for tournament in (client.CURRENT_AI_COMPETITION_ID, client.CURRENT_MINIBENCH_ID):
        # get_all_open_questions_from_tournament calls asyncio.run internally,
        # so it must be called outside any running event loop.
        try:
            questions += client.get_all_open_questions_from_tournament(tournament)
        except Exception as e:
            logger.warning(f"Could not fetch questions for tournament {tournament}: {e}")
    todo = questions_to_forecast(questions, done, latest_a_times(records), datetime.now(timezone.utc))
    logger.info(f"Shadow B: {len(todo)} new questions ({len(done)} already forecast)")
    if not todo:
        return

    bot = PanelBot(
        panel=build_panel(variant),
        research_reports_per_question=1,
        predictions_per_research_report=variant.predictions_per_research_report,
        use_research_summary_to_forecast=False,
        publish_reports_to_metaculus=False,
        skip_previously_forecasted_questions=False,
        extra_metadata_in_explanation=True,
        llms=build_llms(variant),
    )
    with MonetaryCostManager(hard_limit=variant.cost_cap_usd) as cost_manager:
        try:
            forecast_in_chunks(
                bot,
                todo,
                variant.chunk_size,
                cost_manager,
                lambda reports: record_reports(reports, "B", variant.forecaster_models, FORECASTS),
            )
        finally:
            logger.info(
                f"Shadow run cost ${cost_manager.current_usage:.2f} of ${variant.cost_cap_usd:.2f} cap"
            )


if __name__ == "__main__":
    main()
