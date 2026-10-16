"""Forecast questions a few at a time, so a cost cap stops cleanly and finished work is kept."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Sequence

from forecasting_tools import MonetaryCostManager

logger = logging.getLogger(__name__)


def forecast_in_chunks(
    bot: Any,
    questions: Sequence[Any],
    chunk_size: int,
    cost_manager: MonetaryCostManager,
    on_chunk: Callable[[list], object],
) -> list:
    """Forecast `chunk_size` questions at a time, handing each chunk's reports to `on_chunk`
    as soon as it finishes. Stops before starting a chunk once the cost cap is used up."""
    all_reports: list = []
    for start in range(0, len(questions), chunk_size):
        if cost_manager.amount_left <= 0:
            logger.warning(
                f"Cost cap reached; skipping {len(questions) - start} remaining questions until the next run"
            )
            break
        chunk = list(questions[start : start + chunk_size])
        # Repeated asyncio.run relies on forecasting_tools applying nest_asyncio on import; otherwise the
        # template's class-level semaphore stays bound to the first event loop.
        reports = asyncio.run(bot.forecast_questions(chunk, return_exceptions=True))
        on_chunk(reports)
        all_reports.extend(reports)
    return all_reports
