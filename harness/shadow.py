"""Run variant B on open tournament questions it has not forecast yet. Never publishes."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Sequence

from forecasting_tools import MetaculusClient, MonetaryCostManager

from config import VARIANTS, build_llms, build_panel
from harness.panel_bot import PanelBot
from harness.recorder import load_records, record_reports

FORECASTS = Path("data/forecasts")
logger = logging.getLogger(__name__)


def questions_to_forecast(questions: Sequence[Any], done_ids: set[int]) -> list[Any]:
    todo, seen = [], set(done_ids)
    for question in questions:
        if question.get_api_type_name() == "conditional" or question.id_of_question in seen:
            continue
        seen.add(question.id_of_question)
        todo.append(question)
    return todo


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    variant = VARIANTS["B"]
    done = {r["question_id"] for r in load_records(FORECASTS) if r["variant"] == "B"}

    client = MetaculusClient()
    questions = []
    for tournament in (client.CURRENT_AI_COMPETITION_ID, client.CURRENT_MINIBENCH_ID):
        # get_all_open_questions_from_tournament calls asyncio.run internally,
        # so it must be called outside any running event loop.
        try:
            questions += client.get_all_open_questions_from_tournament(tournament)
        except Exception as e:
            logger.warning(f"Could not fetch questions for tournament {tournament}: {e}")
    todo = questions_to_forecast(questions, done)
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
        reports = asyncio.run(bot.forecast_questions(todo, return_exceptions=True))
    logger.info(
        f"Shadow run cost ${cost_manager.current_usage:.2f} of ${variant.cost_cap_usd:.2f} cap"
    )
    count = record_reports(reports, "B", variant.forecaster_models, FORECASTS)
    logger.info(f"Recorded {count} forecasts for variant B")


if __name__ == "__main__":
    main()
