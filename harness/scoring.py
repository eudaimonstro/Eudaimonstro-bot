"""Pure scoring for the A vs. B comparison. No I/O, so every rule here is unit tested."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import mean

UNSCORED_RESOLUTIONS = {"annulled", "ambiguous"}
MIN_PAIRS_TO_SWITCH = 100
MAX_PAIRS_BEFORE_GIVING_UP = 250


@dataclass(frozen=True)
class PairedScore:
    question_id: int
    score_a: float
    score_b: float
    had_errors: bool

    @property
    def difference(self) -> float:
        return self.score_b - self.score_a


def log_score(question_type: str, forecast, resolution: str) -> float | None:
    if resolution in UNSCORED_RESOLUTIONS:
        return None
    if question_type == "binary":
        if resolution not in ("yes", "no"):
            return None
        p = min(max(float(forecast), 0.001), 0.999)
        return math.log(p if resolution == "yes" else 1 - p)
    if question_type == "multiple_choice":
        p = forecast.get(resolution)
        if p is None:
            return None
        return math.log(max(p, 0.001))
    return None


def _latest_before_close(records: list[dict], close_time: str | None) -> dict | None:
    eligible = [r for r in records if close_time is None or r["forecast_time"] <= close_time]
    return max(eligible, key=lambda r: r["forecast_time"], default=None)


def paired_scores(records: list[dict], resolutions: dict[str, dict]) -> list[PairedScore]:
    by_question: dict[int, dict[str, list[dict]]] = {}
    for record in records:
        by_question.setdefault(record["question_id"], {}).setdefault(record["variant"], []).append(record)

    pairs = []
    for question_id, by_variant in sorted(by_question.items()):
        resolved = resolutions.get(str(question_id))
        if resolved is None or "A" not in by_variant or "B" not in by_variant:
            continue
        a = _latest_before_close(by_variant["A"], resolved["close_time"])
        b = _latest_before_close(by_variant["B"], resolved["close_time"])
        if a is None or b is None:
            continue
        score_a = log_score(a["question_type"], a["forecast"], resolved["resolution"])
        score_b = log_score(b["question_type"], b["forecast"], resolved["resolution"])
        if score_a is None or score_b is None:
            continue
        had_errors = a.get("error_count", 0) > 0 or b.get("error_count", 0) > 0
        pairs.append(PairedScore(question_id, score_a, score_b, had_errors))
    return pairs


def bootstrap_interval(
    differences: list[float], level: float = 0.8, iterations: int = 10_000, seed: int = 0
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(differences)
    means = sorted(mean(rng.choices(differences, k=n)) for _ in range(iterations))
    low_index = int((1 - level) / 2 * iterations)
    high_index = int((1 + level) / 2 * iterations) - 1
    return means[low_index], means[high_index]


def decide(paired_count: int, interval_low: float) -> str:
    if paired_count >= MIN_PAIRS_TO_SWITCH and interval_low > 0:
        return "Switch to B"
    if paired_count >= MAX_PAIRS_BEFORE_GIVING_UP:
        return "End the B experiment and keep A"
    return "Keep collecting"


def render_report(pairs: list[PairedScore], date: str) -> str:
    lines = [f"# A vs. B comparison, {date}", ""]
    if not pairs:
        lines.append("No paired, resolved questions yet.")
        return "\n".join(lines) + "\n"
    differences = [p.difference for p in pairs]
    low, high = bootstrap_interval(differences)
    lines += [
        f"- Paired questions: {len(pairs)}",
        f"- Mean log score A: {mean(p.score_a for p in pairs):.4f}",
        f"- Mean log score B: {mean(p.score_b for p in pairs):.4f}",
        f"- Mean difference (B minus A): {mean(differences):.4f}",
        f"- 80% bootstrap interval: [{low:.4f}, {high:.4f}]",
        f"- Pairs where either variant had errors: {sum(p.had_errors for p in pairs)}",
        "",
        f"Decision: {decide(len(pairs), low)}",
        "",
        "Higher (closer to 0) log scores are better.",
    ]
    return "\n".join(lines) + "\n"
