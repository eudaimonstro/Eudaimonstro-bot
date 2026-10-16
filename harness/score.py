"""Weekly A vs. B scoring: fetch resolutions once, cache them, write a comparison report."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import dotenv
from forecasting_tools import MetaculusClient

from harness.recorder import load_records
from harness.scoring import paired_scores, render_report

DATA = Path("data")
CACHE = DATA / "resolutions.json"
logger = logging.getLogger(__name__)


def missing_question_ids(records: list[dict], cache: dict[str, dict]) -> set[tuple[int, int]]:
    return {(r["post_id"], r["question_id"]) for r in records if str(r["question_id"]) not in cache}


def fetch_resolution(client: MetaculusClient, post_id: int, question_id: int) -> dict | None:
    result = client.get_question_by_post_id(post_id, group_question_mode="unpack_subquestions")
    questions = result if isinstance(result, list) else [result]
    for question in questions:
        if question.id_of_question != question_id:
            continue
        if question.state is None or question.state.value != "resolved" or question.resolution_string is None:
            return None
        close_time = question.close_time.isoformat() if question.close_time else None
        return {"resolution": question.resolution_string, "close_time": close_time}
    return None


def main() -> None:
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.INFO)
    records = load_records(DATA / "forecasts")
    cache: dict[str, dict] = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    client = MetaculusClient()
    for post_id, question_id in sorted(missing_question_ids(records, cache)):
        try:
            resolved = fetch_resolution(client, post_id, question_id)
        except Exception as e:  # one bad post should not stop the weekly report
            logger.warning(f"Could not fetch post {post_id}: {e}")
            continue
        if resolved is not None:
            cache[str(question_id)] = resolved
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")

    today = date.today().isoformat()
    report = render_report(paired_scores(records, cache), today)
    out = DATA / "reports" / f"{today}-comparison.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(report)


if __name__ == "__main__":
    main()
