"""Turn forecast reports into JSONL records: one line per question per variant per run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from forecasting_tools import PredictedOptionList


def forecast_to_json(prediction: Any) -> Any:
    if isinstance(prediction, PredictedOptionList):
        return {option.option_name: option.probability for option in prediction.predicted_options}
    if hasattr(prediction, "declared_percentiles"):
        return [{"percentile": p.percentile, "value": p.value} for p in prediction.declared_percentiles]
    if isinstance(prediction, (int, float)) and not isinstance(prediction, bool):
        return float(prediction)
    return None


def report_to_record(report: Any, variant: str, model_ids: Sequence[str], now: datetime) -> dict | None:
    question = report.question
    question_type = question.get_api_type_name()
    if question_type == "conditional":
        return None
    forecast = forecast_to_json(report.prediction)
    if forecast is None:
        return None
    return {
        "question_id": question.id_of_question,
        "post_id": question.id_of_post,
        "question_type": question_type,
        "variant": variant,
        "forecast": forecast,
        "forecast_time": now.isoformat(),
        "model_ids": list(model_ids),
        "price_usd": report.price_estimate,
        "error_count": len(report.errors),
    }


def record_reports(
    reports: Sequence[Any],
    variant: str,
    model_ids: Sequence[str],
    out_dir: Path,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(timezone.utc)
    records = []
    for report in reports:
        if isinstance(report, BaseException):
            continue
        record = report_to_record(report, variant, model_ids, now)
        if record is not None:
            records.append(record)
    if not records:
        return 0
    path = out_dir / variant / f"{now:%Y-%m-%d}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return len(records)


def load_records(root: Path) -> list[dict]:
    if not root.exists():
        return []
    records = []
    for path in sorted(root.glob("*/*.jsonl")):
        records.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return records
