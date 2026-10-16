"""Weekly A vs. B scoring: fetch resolutions once, cache them, write a comparison report."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import dotenv
from forecasting_tools import MetaculusClient

from harness.recorder import load_records
from harness.scoring import paired_scores_with_gap_exclusions, render_report

DATA = Path("data")
CACHE = DATA / "resolutions.json"
logger = logging.getLogger(__name__)


def missing_by_post(records: list[dict], cache: dict[str, dict]) -> dict[int, set[int]]:
    missing: dict[int, set[int]] = {}
    for r in records:
        if str(r["question_id"]) not in cache:
            missing.setdefault(r["post_id"], set()).add(r["question_id"])
    return missing


def fetch_resolution(client: MetaculusClient, post_id: int, question_ids: set[int]) -> dict[int, dict]:
    result = client.get_question_by_post_id(post_id, group_question_mode="unpack_subquestions")
    questions = result if isinstance(result, list) else [result]
    resolved: dict[int, dict] = {}
    for question in questions:
        if question.id_of_question not in question_ids:
            continue
        if question.state is None or question.state.value != "resolved" or question.resolution_string is None:
            continue
        close_time = question.close_time.isoformat() if question.close_time else None
        resolved[question.id_of_question] = {"resolution": question.resolution_string, "close_time": close_time}
    return resolved


def main() -> None:
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.INFO)
    records = load_records(DATA / "forecasts")
    cache: dict[str, dict] = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    client = MetaculusClient()
    try:
        for post_id, question_ids in sorted(missing_by_post(records, cache).items()):
            try:
                resolved = fetch_resolution(client, post_id, question_ids)
            except Exception as e:  # one bad post should not stop the weekly report
                logger.warning(f"Could not fetch post {post_id} (questions {sorted(question_ids)}): {e}")
                continue
            for question_id, resolution in resolved.items():
                cache[str(question_id)] = resolution
    finally:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_name(CACHE.name + ".tmp")
        tmp.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")
        tmp.replace(CACHE)

    today = date.today().isoformat()
    pairs, excluded_for_gap = paired_scores_with_gap_exclusions(records, cache)
    report = render_report(pairs, today, excluded_for_gap)
    out = DATA / "reports" / f"{today}-comparison.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(report)


if __name__ == "__main__":
    main()
