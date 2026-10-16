# MiniBench Forecasting Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Metaculus template bot (variant A, one frontier model) to MiniBench and the Fall 2026 FutureEval tournament, plus a shadow model-panel variant (B) and a scoring harness that compares them on resolved questions.

**Architecture:** Import `Metaculus/metac-bot-template` into this repo and keep `main.py` close to upstream. New code lives in `config.py` (variant settings) and `harness/` (recorder, panel bot, shadow runner, pure scoring, scoring CLI). GitHub Actions runs A every 20 minutes, B every 2 hours, and scoring weekly. Each run commits its JSONL records under `data/`.

**Tech Stack:** Python 3.11+, Poetry, `forecasting-tools` (0.2.90 to under 0.4), litellm via OpenRouter, AskNews, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-16-minibench-bot-design.md`

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `main.py`, `bot_helpers.py`, `pyproject.toml`, `poetry.lock`, `.env.template`, `.github/workflows/*` | imported from template | Template bot and workflows |
| `config.py` | create | `Variant` dataclass, `VARIANTS` dict, `build_llms()`, `build_panel()` |
| `harness/__init__.py` | create | Package marker |
| `harness/recorder.py` | create | Reports to JSONL records, and loading records back |
| `harness/scoring.py` | create | Pure functions: log score, pairing, bootstrap, decision, report text |
| `harness/score.py` | create | CLI: resolution cache plus fetch, calls `scoring`, writes report |
| `harness/panel_bot.py` | create | `PanelBot`: the template bot with a rotating forecasting model |
| `harness/shadow.py` | create | CLI: runs B on open questions it has not forecast yet |
| `scripts/commit_data.sh` | create | Commit `data/` and push with retry |
| `main.py` | modify | Read variant A from config, `--dry-run`, cost cap, record reports |
| `.github/workflows/run_bot_on_tournament.yaml` | modify | Write permission plus commit step |
| `.github/workflows/run_shadow.yaml` | create | Every 2 hours, gated by `SHADOW_ENABLED` |
| `.github/workflows/review_bot.yaml` | modify | Also run `harness.score`, commit reports |
| `tests/test_config.py`, `tests/test_recorder.py`, `tests/test_scoring.py`, `tests/test_panel_bot.py`, `tests/test_shadow.py` | create | Unit tests |
| `pyrightconfig.json` | create | Point pyright at `./venv` |

---

### Task 0: Steve's account steps (manual, can run in parallel with Tasks 1-9)

Claude cannot do these, because each one creates an account or handles a credential. Nothing in Tasks 1-9 needs them; Task 10 does.

- [ ] **Step 1:** Create a Metaculus bot account and copy its token from https://www.metaculus.com/futureeval/participate/
- [ ] **Step 2:** Fill in the FutureEval participant form (three required questions). Apply for LLM credits through the form linked in `.env.template` (https://forms.gle/aQdYMq9Pisrf1v7d8), and say the bot will be open source.
- [ ] **Step 3:** Create an OpenRouter account and API key (or use the key that comes with donated credits). In the OpenRouter key settings, set a **credit limit** on the key. This is the hard cap from the spec.
- [ ] **Step 4:** Request AskNews access through the Metaculus partnership (AskNews Discord, contact @freqai, or email). You'll get `ASKNEWS_CLIENT_ID` and `ASKNEWS_SECRET` (if AskNews gives you a single API key instead, use `ASKNEWS_API_KEY` as the secret name).
- [ ] **Step 5:** Create an empty **public** GitHub repo. With the GitHub CLI, run `gh repo create <name> --public` in a terminal.
- [ ] **Step 6:** In the repo, go to Settings → Secrets and variables → Actions and add these secrets: `METACULUS_TOKEN`, `OPENROUTER_API_KEY`, `ASKNEWS_CLIENT_ID`, `ASKNEWS_SECRET` (or just `ASKNEWS_API_KEY` if AskNews gave you an API key instead). Add these variables: `REVIEW_BOT_ENABLED=true` and `SHADOW_ENABLED=false` (B stays off until Task 10).
- [ ] **Step 7:** Create a local `.env` from `.env.template` once Task 1 imports it, and fill in the same four values. `.env` is gitignored.

---

### Task 1: Import the template and set up the environment

**Files:**
- Import: everything from `https://github.com/Metaculus/metac-bot-template` (`main` branch)
- Create: `pyrightconfig.json`
- Modify: `.gitignore`, `pyproject.toml`

- [ ] **Step 1: Pull the template into this repo, keeping its history**

```bash
cd /home/steve/workspace/project
git fetch https://github.com/Metaculus/metac-bot-template.git main
git merge --allow-unrelated-histories -m "Import metac-bot-template" FETCH_HEAD
ls
```
Expected: `README.md bot_helpers.py docs integrations main.py main_with_no_framework.py poetry.lock pyproject.toml` (plus dotfiles).

- [ ] **Step 2: Create the venv with a Python the dependencies support**

The system Python is 3.14. Try it first. If `poetry install` fails on a wheel build, recreate the venv with 3.11 (`uv venv venv --python 3.11`, after `pipx install uv` if uv is missing).

```bash
cd /home/steve/workspace/project
python3 -m venv venv
. venv/bin/activate
pip install --quiet poetry
poetry install --no-interaction --no-root --with integrations
python -c "import forecasting_tools, sys; print(sys.version.split()[0], 'ok')"
```
Expected: a version string followed by `ok`. Poetry installs into the activated `venv` because `VIRTUAL_ENV` is set.

This plan was written against `forecasting-tools` 0.3.4, the version in the template's `poetry.lock` on 2026-10-16. Check that it still matches with `grep -A1 'name = "forecasting-tools"' poetry.lock`. If it differs, re-check the symbols this plan uses (`MonetaryCostManager(hard_limit=...)`, `get_api_type_name`, `declared_percentiles`, `CURRENT_MINIBENCH_ID`, `resolution_string`) before Task 3.

- [ ] **Step 3: Add pytest and make the repo root importable in tests**

```bash
. venv/bin/activate
poetry add --group dev pytest
```

Then append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Configure pyright and gitignore**

Create `pyrightconfig.json`:

```json
{
  "venvPath": ".",
  "venv": "venv"
}
```

Append to `.gitignore` (create it if the template has none):

```
.env
venv/
__pycache__/
.pytest_cache/
```

- [ ] **Step 5: Verify pytest runs (no tests yet)**

Run: `. venv/bin/activate && pytest`
Expected: `no tests ran` with exit code 5. This is fine at this point.

- [ ] **Step 6: Commit**

```bash
git add .gitignore pyproject.toml poetry.lock pyrightconfig.json
git commit -m "Set up venv, pytest, and pyright"
```

---

### Task 2: Variant config

**Files:**
- Create: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Verify current OpenRouter model IDs and prices**

```bash
curl -s https://openrouter.ai/api/v1/models | jq -r '.data[] | select(.id | test("^(openai/gpt-5|anthropic/claude-opus|anthropic/claude-haiku|google/gemini)")) | "\(.id)\t\(.pricing.prompt)\t\(.pricing.completion)"' | sort
```
Expected: one line per model, with per-token prompt and completion prices. Write down the exact IDs for:
1. the GPT-5.4 model
2. Claude Opus 5.5
3. the highest-version `google/gemini-*-pro` model
4. Claude Haiku 5.5, for the parser

In Step 3, prefix each with `openrouter/` for litellm. If an ID below differs from the listing, use the listing's ID.

- [ ] **Step 2: Write the failing test**

`tests/test_config.py`:

```python
from forecasting_tools import GeneralLlm

from config import VARIANTS, build_llms, build_panel


def test_variant_a_is_a_single_model():
    a = VARIANTS["A"]
    assert len(a.forecaster_models) == 1
    assert a.predictions_per_research_report == 5


def test_variant_b_is_a_three_model_panel_with_equal_samples():
    b = VARIANTS["B"]
    assert len(b.forecaster_models) == 3
    assert len(set(b.forecaster_models)) == 3
    assert b.predictions_per_research_report == 15


def test_b_includes_a_model():
    assert VARIANTS["A"].forecaster_models[0] in VARIANTS["B"].forecaster_models


def test_build_llms_has_every_purpose_the_template_uses():
    llms = build_llms(VARIANTS["A"])
    assert set(llms) == {"default", "parser", "researcher", "summarizer"}
    default = llms["default"]
    assert isinstance(default, GeneralLlm)
    assert default.model == VARIANTS["A"].forecaster_models[0]


def test_build_panel_returns_one_llm_per_model():
    panel = build_panel(VARIANTS["B"])
    assert [llm.model for llm in panel] == list(VARIANTS["B"].forecaster_models)


def test_cost_caps_are_positive():
    assert all(v.cost_cap_usd > 0 for v in VARIANTS.values())
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`.

- [ ] **Step 4: Write `config.py`**

```python
"""Bot variants. A is the live bot; B is the shadow panel it is compared against."""

from dataclasses import dataclass

from forecasting_tools import GeneralLlm

GPT = "openrouter/openai/gpt-5.4"
CLAUDE = "openrouter/anthropic/claude-opus-5-5"
GEMINI = "openrouter/google/gemini-3-pro"
PARSER = "openrouter/anthropic/claude-haiku-5-5"
RESEARCHER = "asknews/news-summaries"


@dataclass(frozen=True)
class Variant:
    name: str
    forecaster_models: tuple[str, ...]
    predictions_per_model: int
    reasoning_effort: str
    cost_cap_usd: float  # per run; the OpenRouter key limit is the hard cap

    @property
    def predictions_per_research_report(self) -> int:
        return self.predictions_per_model * len(self.forecaster_models)


VARIANTS: dict[str, Variant] = {
    "A": Variant("A", (GPT,), predictions_per_model=5, reasoning_effort="high", cost_cap_usd=5.0),
    "B": Variant("B", (GPT, CLAUDE, GEMINI), predictions_per_model=5, reasoning_effort="high", cost_cap_usd=15.0),
}


def _forecaster(model: str, variant: Variant) -> GeneralLlm:
    # No temperature: reasoning models reject non-default values.
    return GeneralLlm(model=model, reasoning_effort=variant.reasoning_effort, timeout=300, allowed_tries=3)


def build_llms(variant: Variant) -> dict[str, str | GeneralLlm | None]:
    return {
        "default": _forecaster(variant.forecaster_models[0], variant),
        "parser": GeneralLlm(model=PARSER, temperature=0, timeout=60, allowed_tries=3),
        "researcher": RESEARCHER,
        "summarizer": GeneralLlm(model=PARSER, temperature=0, timeout=60, allowed_tries=3),
    }


def build_panel(variant: Variant) -> list[GeneralLlm]:
    return [_forecaster(model, variant) for model in variant.forecaster_models]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "Add variant config for live bot A and shadow panel B"
```

---

### Task 3: Recorder

**Files:**
- Create: `harness/__init__.py` (empty), `harness/recorder.py`
- Test: `tests/test_recorder.py`

- [ ] **Step 1: Write the failing test**

`tests/test_recorder.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recorder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness'`.

- [ ] **Step 3: Write `harness/__init__.py` (empty file) and `harness/recorder.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_recorder.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add harness/__init__.py harness/recorder.py tests/test_recorder.py
git commit -m "Add forecast recorder"
```

---

### Task 4: Pure scoring

**Files:**
- Create: `harness/scoring.py`
- Test: `tests/test_scoring.py`

- [ ] **Step 1: Write the failing test**

`tests/test_scoring.py`:

```python
import math

import pytest

from harness.scoring import (
    bootstrap_interval,
    decide,
    log_score,
    paired_scores,
    render_report,
)


def rec(variant, qid, forecast, time, qtype="binary", errors=0):
    return {
        "question_id": qid,
        "post_id": qid,
        "question_type": qtype,
        "variant": variant,
        "forecast": forecast,
        "forecast_time": time,
        "error_count": errors,
    }


def test_binary_log_score():
    assert log_score("binary", 0.8, "yes") == pytest.approx(math.log(0.8))
    assert log_score("binary", 0.8, "no") == pytest.approx(math.log(0.2))


def test_binary_log_score_clips_extremes():
    assert log_score("binary", 1.0, "no") == pytest.approx(math.log(0.001))


def test_multiple_choice_log_score():
    assert log_score("multiple_choice", {"a": 0.3, "b": 0.7}, "b") == pytest.approx(math.log(0.7))


def test_annulled_and_unknown_are_unscored():
    assert log_score("binary", 0.5, "annulled") is None
    assert log_score("binary", 0.5, "ambiguous") is None
    assert log_score("multiple_choice", {"a": 1.0}, "z") is None
    assert log_score("numeric", [{"percentile": 0.5, "value": 1}], "3.0") is None


def test_pairs_use_latest_forecast_before_close():
    records = [
        rec("A", 1, 0.6, "2026-10-20T00:00:00+00:00"),
        rec("A", 1, 0.9, "2026-10-21T00:00:00+00:00"),
        rec("A", 1, 0.1, "2026-10-25T00:00:00+00:00"),  # after close: ignored
        rec("B", 1, 0.7, "2026-10-20T06:00:00+00:00", errors=1),
        rec("A", 2, 0.5, "2026-10-20T00:00:00+00:00"),  # no B record: unpaired
    ]
    resolutions = {
        "1": {"resolution": "yes", "close_time": "2026-10-22T00:00:00+00:00"},
        "2": {"resolution": "no", "close_time": "2026-10-22T00:00:00+00:00"},
    }
    pairs = paired_scores(records, resolutions)
    assert len(pairs) == 1
    assert pairs[0].question_id == 1
    assert pairs[0].score_a == pytest.approx(math.log(0.9))
    assert pairs[0].score_b == pytest.approx(math.log(0.7))
    assert pairs[0].had_errors is True


def test_bootstrap_of_constant_differences_is_that_constant():
    assert bootstrap_interval([0.1] * 50) == pytest.approx((0.1, 0.1))


def test_bootstrap_is_deterministic_and_ordered():
    diffs = [0.3, -0.1, 0.2, 0.05, -0.2, 0.4, 0.1]
    low, high = bootstrap_interval(diffs)
    assert low < high
    assert bootstrap_interval(diffs) == (low, high)


def test_decide():
    assert decide(99, 0.5) == "Keep collecting"
    assert decide(100, 0.01) == "Switch to B"
    assert decide(150, -0.01) == "Keep collecting"
    assert decide(250, -0.01) == "End the B experiment and keep A"


def test_render_report_with_no_pairs():
    text = render_report([], "2026-10-26")
    assert "No paired, resolved questions yet" in text


def test_render_report_mentions_decision_and_counts():
    records = [rec("A", 1, 0.6, "2026-10-20T00:00:00+00:00"), rec("B", 1, 0.8, "2026-10-20T00:00:00+00:00")]
    pairs = paired_scores(records, {"1": {"resolution": "yes", "close_time": None}})
    text = render_report(pairs, "2026-10-26")
    assert "Paired questions: 1" in text
    assert "Decision: Keep collecting" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.scoring'`.

- [ ] **Step 3: Write `harness/scoring.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scoring.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add harness/scoring.py tests/test_scoring.py
git commit -m "Add paired log scoring, bootstrap interval, and switch rule"
```

---

### Task 5: Scoring CLI with resolution cache

**Files:**
- Create: `harness/score.py`

This is a thin I/O layer over Task 4. Its one piece of logic, `missing_question_ids`, gets a unit test. The Metaculus fetch is exercised by the dry run in Task 9.

- [ ] **Step 1: Write the failing test** (append to `tests/test_scoring.py`)

```python
from harness.score import missing_question_ids


def test_missing_question_ids_skips_cached():
    records = [{"question_id": 1, "post_id": 10}, {"question_id": 2, "post_id": 20}, {"question_id": 1, "post_id": 10}]
    assert missing_question_ids(records, {"1": {"resolution": "yes", "close_time": None}}) == {(20, 2)}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scoring.py::test_missing_question_ids_skips_cached -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.score'`.

- [ ] **Step 3: Write `harness/score.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scoring.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add harness/score.py tests/test_scoring.py
git commit -m "Add scoring CLI with cached resolutions"
```

---

### Task 6: Panel bot

**Files:**
- Create: `harness/panel_bot.py`
- Test: `tests/test_panel_bot.py`

- [ ] **Step 1: Write the failing test**

`tests/test_panel_bot.py`:

```python
from collections import Counter

from forecasting_tools import GeneralLlm

from config import VARIANTS, build_llms
from harness.panel_bot import PanelBot


def make_bot():
    panel = [GeneralLlm(model=m) for m in ("openrouter/x/one", "openrouter/x/two", "openrouter/x/three")]
    return PanelBot(panel=panel, llms=build_llms(VARIANTS["B"]), predictions_per_research_report=15)


def test_default_llm_rotates_evenly_across_panel():
    bot = make_bot()
    picks = Counter(bot.get_llm("default", "llm").model for _ in range(15))
    assert picks == {"openrouter/x/one": 5, "openrouter/x/two": 5, "openrouter/x/three": 5}


def test_other_purposes_are_untouched():
    bot = make_bot()
    assert bot.get_llm("researcher") == "asknews/news-summaries"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_panel_bot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.panel_bot'`.

- [ ] **Step 3: Write `harness/panel_bot.py`**

```python
"""Variant B: the template bot, with the forecasting model rotating across a panel.

The template asks get_llm("default") once per prediction, so rotating here gives each
model an equal share of the samples, and the library's median aggregation pools them.
"""

from __future__ import annotations

from itertools import cycle

from forecasting_tools import GeneralLlm

from main import FallTemplateBot2026


class PanelBot(FallTemplateBot2026):
    def __init__(self, *, panel: list[GeneralLlm], **kwargs) -> None:
        self._panel = cycle(panel)  # set first: the base __init__ may look up LLMs
        super().__init__(**kwargs)

    def get_llm(self, purpose="default", guarantee_type=None):  # type: ignore[override]
        if purpose == "default":
            return next(self._panel)
        return super().get_llm(purpose, guarantee_type)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_panel_bot.py -v`
Expected: 2 passed. If construction fails because `METACULUS_TOKEN` or `OPENROUTER_API_KEY` is missing, set dummy values with `monkeypatch.setenv` in the test (the same fix applies to `tests/test_config.py`); this is not a design problem. If the base `__init__` turns out to call `get_llm("default")` (the rotation test would then show a 6/5/4 split), call `self._panel = cycle(panel)` again after `super().__init__(**kwargs)`, and rerun.

- [ ] **Step 5: Commit**

```bash
git add harness/panel_bot.py tests/test_panel_bot.py
git commit -m "Add panel bot that rotates forecasting models"
```

---

### Task 7: Wire variant A into `main.py`

**Files:**
- Modify: `main.py` (imports near the top; the whole `if __name__ == "__main__":` block at the bottom)

- [ ] **Step 1: Add imports**

In the `from forecasting_tools import (...)` list, add `MonetaryCostManager,` after `MetaculusClient,`. Below `dotenv.load_dotenv()` and `logger = ...`, add:

```python
from pathlib import Path

from config import VARIANTS, build_llms
from harness.recorder import record_reports
```

- [ ] **Step 2: Replace everything from `if __name__ == "__main__":` to the end of the file with**

```python
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run the forecasting bot (variant A)")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["tournament", "metaculus_cup", "test_questions"],
        default="tournament",
        help="What to forecast on (default: tournament)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Forecast without publishing to Metaculus",
    )
    args = parser.parse_args()
    run_mode: Literal["tournament", "metaculus_cup", "test_questions"] = args.mode

    check_environment(strict=True)
    publish_to_metaculus = not args.dry_run
    print_startup_banner(run_mode, will_publish=publish_to_metaculus)

    variant = VARIANTS["A"]
    template_bot = FallTemplateBot2026(
        research_reports_per_question=1,
        predictions_per_research_report=variant.predictions_per_research_report,
        use_research_summary_to_forecast=False,
        publish_reports_to_metaculus=publish_to_metaculus,
        folder_to_save_reports_to=None,
        skip_previously_forecasted_questions=True,
        extra_metadata_in_explanation=True,
        llms=build_llms(variant),
    )

    TOURNAMENT_URLS = {
        "tournament": "https://www.metaculus.com/tournament/fall-futureeval-2026/",
        "metaculus_cup": "https://www.metaculus.com/tournament/metaculus-cup-fall-2026/",
        "test_questions": "https://www.metaculus.com/tournament/bot-testing-area/",
    }

    client = MetaculusClient()
    with MonetaryCostManager(hard_limit=variant.cost_cap_usd):
        if run_mode == "tournament":
            seasonal_tournament_reports = asyncio.run(
                template_bot.forecast_on_tournament(
                    client.CURRENT_AI_COMPETITION_ID, return_exceptions=True
                )
            )
            minibench_reports = asyncio.run(
                template_bot.forecast_on_tournament(
                    client.CURRENT_MINIBENCH_ID, return_exceptions=True
                )
            )
            forecast_reports = seasonal_tournament_reports + minibench_reports
        elif run_mode == "metaculus_cup":
            template_bot.skip_previously_forecasted_questions = False
            forecast_reports = asyncio.run(
                template_bot.forecast_on_tournament(
                    client.CURRENT_METACULUS_CUP_ID, return_exceptions=True
                )
            )
        else:
            template_bot.skip_previously_forecasted_questions = False
            forecast_reports = asyncio.run(
                template_bot.forecast_on_tournament(
                    "bot-testing-area", return_exceptions=True
                )
            )

    template_bot.log_report_summary(forecast_reports)
    print_run_summary_banner(
        forecast_reports,
        will_publish=publish_to_metaculus,
        tournament_url=TOURNAMENT_URLS.get(run_mode),
    )

    # Only live tournament forecasts are scored; test-area and dry runs are not recorded.
    if run_mode == "tournament" and publish_to_metaculus:
        count = record_reports(
            forecast_reports, "A", variant.forecaster_models, Path("data/forecasts")
        )
        logger.info(f"Recorded {count} forecasts for variant A")
```

- [ ] **Step 3: Verify it still imports and parses arguments**

Run: `. venv/bin/activate && python main.py --help`
Expected: usage text that lists `--mode` and `--dry-run`.

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass (`test_panel_bot.py` imports `main`, so this also checks that the edit didn't break the import).

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "Configure live bot from variant A with cost cap and recording"
```

---

### Task 8: Shadow runner

**Files:**
- Create: `harness/shadow.py`
- Test: `tests/test_shadow.py`

- [ ] **Step 1: Write the failing test**

`tests/test_shadow.py`:

```python
from types import SimpleNamespace

from harness.shadow import questions_to_forecast


def q(question_id, qtype="binary"):
    return SimpleNamespace(id_of_question=question_id, get_api_type_name=lambda: qtype)


def test_skips_already_forecast_and_conditional():
    questions = [q(1), q(2), q(3, "conditional"), q(4, "numeric")]
    assert [x.id_of_question for x in questions_to_forecast(questions, done_ids={2})] == [1, 4]


def test_deduplicates_questions_in_both_tournaments():
    assert [x.id_of_question for x in questions_to_forecast([q(1), q(1)], done_ids=set())] == [1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_shadow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'harness.shadow'`.

- [ ] **Step 3: Write `harness/shadow.py`**

```python
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
        questions += client.get_all_open_questions_from_tournament(tournament)
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
    with MonetaryCostManager(hard_limit=variant.cost_cap_usd):
        reports = asyncio.run(bot.forecast_questions(todo, return_exceptions=True))
    count = record_reports(reports, "B", variant.forecaster_models, FORECASTS)
    logger.info(f"Recorded {count} forecasts for variant B")


if __name__ == "__main__":
    main()
```

The template's `main.py` already calls `dotenv.load_dotenv()` at import, and `harness.panel_bot` imports `main`, so `.env` is loaded here too.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add harness/shadow.py tests/test_shadow.py
git commit -m "Add shadow runner for variant B"
```

---

### Task 9: Workflows and the data commit script

**Files:**
- Create: `scripts/commit_data.sh`, `.github/workflows/run_shadow.yaml`
- Modify: `.github/workflows/run_bot_on_tournament.yaml`, `.github/workflows/review_bot.yaml`

- [ ] **Step 1: Write `scripts/commit_data.sh`**

```bash
#!/usr/bin/env bash
# Commit anything new under data/ and push. Each variant writes only to its own
# folder, so rebasing onto a concurrent push never conflicts.
set -euo pipefail
message="$1"
git config user.name "forecast-bot"
git config user.email "forecast-bot@users.noreply.github.com"
git add data
if git diff --cached --quiet; then
  echo "No new data to commit"
  exit 0
fi
git commit --quiet -m "$message"
for attempt in 1 2 3 4 5; do
  if git pull --rebase --quiet origin "${GITHUB_REF_NAME:-main}" && git push --quiet origin "HEAD:${GITHUB_REF_NAME:-main}"; then
    exit 0
  fi
  echo "Push attempt $attempt failed, retrying"
  sleep $((attempt * 5))
done
echo "Could not push data after 5 attempts" >&2
exit 1
```

Run: `chmod +x scripts/commit_data.sh && bash -n scripts/commit_data.sh && echo syntax ok`
Expected: `syntax ok`

- [ ] **Step 2: Edit `run_bot_on_tournament.yaml`**

After the `concurrency:` block, add:

```yaml
permissions:
  contents: write
```

After the `Run bot` step (at the same indentation as `- name: Run bot`), add:

```yaml
      - name: Commit forecast records
        run: scripts/commit_data.sh "Record variant A forecasts"
```

- [ ] **Step 3: Create `.github/workflows/run_shadow.yaml`**

```yaml
name: Shadow forecasts (variant B)

on:
  workflow_dispatch:
  schedule:
    - cron: "37 */2 * * *" # every 2 hours

concurrency:
  group: ${{ github.workflow }}
  cancel-in-progress: false

permissions:
  contents: write

# Variant B never publishes. It only runs while the repository variable
# SHADOW_ENABLED is "true", so it can be turned off first if credits run low.
jobs:
  shadow_job:
    if: vars.SHADOW_ENABLED == 'true' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install poetry
        uses: snok/install-poetry@v1
        with:
          virtualenvs-create: true
          virtualenvs-in-project: true
          installer-parallel: true
      - name: Install dependencies
        run: poetry install --no-interaction --no-root
      - name: Run shadow bot
        run: poetry run python -m harness.shadow
        env:
          METACULUS_TOKEN: ${{ secrets.METACULUS_TOKEN }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          ASKNEWS_CLIENT_ID: ${{ secrets.ASKNEWS_CLIENT_ID }}
          ASKNEWS_SECRET: ${{ secrets.ASKNEWS_SECRET }}
      - name: Commit forecast records
        run: scripts/commit_data.sh "Record variant B forecasts"
```

- [ ] **Step 4: Edit `review_bot.yaml`**

After its `concurrency:` block, add:

```yaml
permissions:
  contents: write
```

Replace its last two steps (`Show the summary in the run page` and `Keep the review`) with:

```yaml
      - name: Score A vs. B
        run: poetry run python -m harness.score
        env:
          METACULUS_TOKEN: ${{ secrets.METACULUS_TOKEN }}
      - name: Save reports
        run: |
          mkdir -p data/reports
          cp review.md "data/reports/$(date -u +%F)-bot-review.md"
          cat review.md "data/reports/$(date -u +%F)-comparison.md" >> $GITHUB_STEP_SUMMARY
      - name: Commit reports
        run: scripts/commit_data.sh "Weekly review and A vs. B report"
```

- [ ] **Step 5: Remove the Metaculus Cup workflow**

The Cup is out of scope, and this workflow would spend credits on it every 2 days once pushed. (`test_bot.yaml` runs only by hand, so it stays.)

Run: `git rm .github/workflows/run_bot_on_metaculus_cup.yaml`

- [ ] **Step 6: Validate YAML syntax**

Run: `python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yaml')]; print('yaml ok')"`
Expected: `yaml ok` (PyYAML comes in with the dependencies; if it's missing, `pip install pyyaml` into the venv).

- [ ] **Step 7: Commit**

```bash
git add scripts/commit_data.sh .github/workflows
git commit -m "Run shadow bot and weekly scoring in Actions, commit data"
```

---

### Task 10: Smoke test and go live

Needs Task 0 done.

- [ ] **Step 1: Local dry run on the testing area**

Run: `. venv/bin/activate && python main.py --mode test_questions --dry-run`
Expected: the run summary banner shows forecasts for several question types and `will_publish` false. Errors mentioning `reasoning_effort` mean litellm rejected the parameter for that model. In that case, remove `reasoning_effort=...` from `_forecaster` in `config.py`, use `extra_body={"reasoning": {"effort": variant.reasoning_effort}}` instead, and rerun. If AskNews access hasn't arrived yet, set `RESEARCHER = "openrouter/openai/gpt-5.4:online"` in `config.py` (the template treats any other model string as an LLM researcher, and OpenRouter's `:online` suffix adds web search). Switch back once AskNews works.

- [ ] **Step 2: Check the cost per question**

In the dry-run output, read each report's price estimate. Multiply the average by about 60 questions per MiniBench round, and check that against the OpenRouter key limit from Task 0. If it's too high, lower `predictions_per_model` for A to 3 in `config.py`, then rerun Step 1.

Gate: the `Run cost $X of $5.00 cap` log line and the report price estimates must be above $0.00. If they read $0.00, OpenRouter isn't reporting cost and the per-run cap can't trip, so don't go live until the OpenRouter key limit is set (it must be set regardless).

- [ ] **Step 3: Publish to the testing area and confirm comments**

Run: `python main.py --mode test_questions`
Expected: forecasts appear at https://www.metaculus.com/tournament/bot-testing-area/ under the bot account, **each with a reasoning comment**. Comments are required for prizes.

- [ ] **Step 4: Shadow smoke test**

Run: `python -c "import asyncio; from harness.shadow import *; from forecasting_tools import MetaculusClient; qs = questions_to_forecast(MetaculusClient().get_all_open_questions_from_tournament('bot-testing-area'), set())[:2]; from config import *; from harness.panel_bot import PanelBot; v = VARIANTS['B']; b = PanelBot(panel=build_panel(v), predictions_per_research_report=v.predictions_per_research_report, llms=build_llms(v)); print(asyncio.run(b.forecast_questions(qs, return_exceptions=True)))"`
Expected: two reports printed (no exceptions), with all three panel models named in the explanations.

- [ ] **Step 5: Push to GitHub (this is the real go-live) and run the workflow by hand**

The 20-minute schedule starts firing, and publishing, as soon as the workflows land on `main` in GitHub. Push only once the Task 0 secrets are in place and you want variant A live.

The code is on branch `bot-v1`. Merge it into `main` first (the finishing-a-development-branch step does this), then push `main`.

```bash
git remote add origin "$(gh repo view --json url -q .url <repo-name-from-task-0-step-5>)"
git push -u origin main
gh workflow run run_bot_on_tournament.yaml
gh run watch
```
Expected: the run succeeds, and a `Record variant A forecasts` commit appears if any tournament questions were open.

- [ ] **Step 6: Turn on B and the weekly review**

Set the repository variable `SHADOW_ENABLED=true`, then run `gh workflow run run_shadow.yaml` and `gh run watch`.
Expected: a `Record variant B forecasts` commit.

- [ ] **Step 7: Check the first scheduled runs**

After a day, run `gh run list --limit 20` and confirm the A runs every 20 minutes and B every 2 hours are green. The first useful A vs. B report needs resolved questions, so expect `No paired, resolved questions yet` for the first week or two.
