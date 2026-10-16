# MiniBench Forecasting Bot: Design

Date: 2026-10-16
Status: approved direction (approach "A, harness, then B")

## Goal

Build an automated forecasting bot that competes in Metaculus's MiniBench (two-week, roughly 60-question, $1k rounds) and the Fall 2026 FutureEval bot tournament, plus a scoring harness that judges every change against real outcomes.

The bot is a stepping stone. It builds the skills (model pipelines, scoring, not fooling yourself) for the follow-on project, a coded-antisemitism detection benchmark, which gets its own spec later.

## Success criteria

1. **Live by the November 2 MiniBench round** (the October 19 round if setup goes fast). These dates are inferred from the September 21 start and the two-week cadence, so confirm them on Metaculus. The bot forecasts forecasting every open question in MiniBench and the fall tournament, with a reasoning comment on every forecast.
2. **Beat the median bot** in the first full MiniBench round the bot enters, measured by rank in `bot-review` output.
3. **Top quarter** of MiniBench within three rounds.
4. **A working A vs. B comparison**: the harness produces a paired score report for the single-model bot (A) and a model-panel challenger (B) on the same resolved questions.
5. **Near-zero spend**: the project runs on donated credits, or on a personal key with a hard limit Steve sets. No uncapped spend, ever.

## Constraints and evidence behind the design

- **Budget:** Steve has no money to put into this. Credits are now selective ("funds ran out in Summer"), and open-source bots get about double the standard allocation.
- **Rules:** no human in the loop, a comment that accurately reflects the reasoning is required for prizes, the participant form and end-of-season survey are required, and there is one prize-eligible bot per user.
- **Spring 2026 results:**
  - The unmodified template with one frontier model at high reasoning placed 18th of 173.
  - Search provider swaps made no measurable difference.
  - Teams of 2-10 bots beat a single bot. Beyond about 10 bots, results got worse.
  - Bot makers report that simpler bots did better.
  - Top-10 bots overwhelmingly used GPT-5.4.
- **Things Claude cannot do:** create accounts, fill in forms, or enter credentials. Every account step below is Steve's.

## Approach

Approach A goes live first, with the harness built alongside it. Approach B runs in shadow mode and replaces A only if the harness says it is better. Approach C (agentic research) is out of scope for this spec.

| Variant | Forecaster | Research | Role |
|---|---|---|---|
| A | One frontier reasoning model at high reasoning effort, 5 samples per question, median (template default aggregation) | AskNews news summaries | Live bot, publishes to Metaculus |
| B | Panel of 3 frontier models from different labs (OpenAI, Anthropic, Google), 5 samples each; take each model's median, then the median of the three | Same research setting as A | Shadow, never publishes |

Initial model picks:
- **A:** `openai/gpt-5.4` via OpenRouter, at high reasoning, because of the spring evidence.
- **B's panel:** that model plus `anthropic/claude-opus-5-5` and the highest-tier Gemini model OpenRouter lists at setup time.
- **Parser:** a cheap small model.

The plan's first task verifies the exact OpenRouter model IDs and prices. If the credits do not cover a model, it is swapped for the strongest affordable one from the same lab, and the swap is recorded in `config.py`.

## Architecture

The repo starts as an import of `Metaculus/metac-bot-template` (its `main.py` is built on `forecasting-tools`). It lives in a public GitHub repo for the open-source credit bonus and free Actions minutes. Changes to the template are kept small so upstream updates stay easy to merge.

```
main.py                  template bot (FallTemplateBot2026), edited only to read config and call the recorder
config.py                variant definitions (A, B): model IDs, reasoning settings, samples, researcher, cost caps
harness/
  recorder.py            turns forecast reports into JSONL records (one line per question per variant per run)
  shadow.py              runs variant B on the same open questions with publishing off, records its forecasts
  score.py               fetches resolutions, scores paired forecasts, writes the comparison report
data/
  forecasts/<variant>/<YYYY-MM-DD>.jsonl
  reports/<YYYY-MM-DD>-comparison.md
tests/                   pytest unit tests for recorder and scorer
.github/workflows/
  run_bot_on_tournament.yaml   template workflow (every 20 min) plus a record-and-commit step
  run_shadow.yaml              variant B, every 2 hours, record-and-commit
  review_bot.yaml              template weekly bot-review, enabled, plus score.py
```

### Units

**`config.py`**
- **What it holds:** a dict of variant names mapped to settings: forecaster model IDs, reasoning effort, `predictions_per_research_report`, researcher, parser model, and a per-run cost cap in dollars.
- **Used by:** `main.py` and `shadow.py`.
- **Dependencies:** none.

**`harness/recorder.py`**
- **What it does:** `record(reports, variant, out_dir)` writes one JSON line per question with these fields: `question_id`, `post_id`, `question_type`, `variant`, `forecast` (probability for binary, option-to-probability map for multiple choice, list of percentiles for numeric), `forecast_time`, and `model_ids`. It reads the report objects `forecasting-tools` returns.
- **Dependencies:** `forecasting-tools` report types.

**`harness/shadow.py`**
- **What it does:**
  1. Builds the same bot class with variant B's settings, `publish_reports_to_metaculus=False`, and `skip_previously_forecasted_questions=False`.
  2. Runs it on the MiniBench and fall tournament IDs.
  3. Skips any question that already has a B record, so a question is forecast once per variant.
  4. Calls the recorder.
- **Why it's clean:** it forecasts only open questions at the same time A does, so research cannot leak outcomes. That is why the comparison runs in shadow mode instead of as a backtest.

**`harness/score.py`**
- **What it does:**
  1. Loads all records.
  2. Fetches each question's resolution through the `forecasting-tools` Metaculus API client.
  3. Keeps questions that are resolved, not annulled, and forecast by both A and B. Each variant's latest pre-close forecast counts.
  4. Computes log scores. Binary uses ln(p) of the outcome. Multiple choice uses ln of the probability on the resolved option.
  5. Reports per-variant means, the paired mean difference (B minus A), a bootstrap 80% interval on that difference, and the count of paired questions.
- **Out of scope:** numeric questions are recorded but not scored by `score.py` in this version. Metaculus's own scores, via `bot-review`, cover A on numeric.

### Data flow

1. Every 20 minutes, Actions runs `main.py --mode tournament`. Variant A forecasts new questions, publishes forecasts and comments, and the recorder appends records under `data/forecasts/A/`, which are committed.
2. Every 2 hours, Actions runs `shadow.py`. Variant B forecasts any open question it has not forecast yet, and its records go to `data/forecasts/B/`, which are committed.
3. Weekly, Actions runs `bot-review` (rank, best and worst questions for A) and `score.py` (A vs. B), then commits both reports to `data/reports/`.
4. Steve reads the weekly report. The decision rule below decides whether B replaces A.

All workflows that commit to `data/` share one Actions `concurrency` group, so their pushes cannot race.

### Switch rule

B replaces A as the live bot when both hold:
- At least 100 paired, resolved binary or multiple-choice questions.
- The bootstrap 80% interval on (B minus A) mean log score is entirely above zero.

Otherwise A stays live. After 250 paired questions with no clear winner, keep the cheaper variant (A) and end the B experiment.

## Cost control

- **Hard cap:** an OpenRouter credit limit on the API key itself. This is the cap that cannot fail.
- **Soft cap:** a per-run dollar cap from `config.py`. It uses `forecasting-tools`' cost tracking if the library provides it; otherwise the hard cap alone applies. The plan's first task checks which.
- **Credits denied:** variant A runs on a personal OpenRouter key with a hard limit Steve sets. The suggested limit is $20/month, with the parser and researcher on the cheapest settings and the shadow B variant off. If Steve sets no limit, the bot does not run.
- **Shadow cost:** B costs about 3x A per question. If credits run low, B pauses first, before A is ever affected.

## Research provider

The primary provider is AskNews (`asknews/news-summaries`) through the Metaculus partnership. Steve renews the account each season through the AskNews Discord or email. If AskNews is unavailable, the researcher setting falls back to an OpenRouter web-search-enabled model. This is a single config change.

## Error handling

- The template already runs questions with `return_exceptions=True`, so one failed question does not stop the run. Failures are logged in the Actions run summary.
- Comments are mandatory for prizes, so the smoke test (below) confirms that a published forecast carries a reasoning comment before the first live run.
- Google models have a shared limit of 150 requests per minute across all participants. On 429 errors, B's Google call retries with backoff, and if it still fails, B records the forecast as the median of the remaining models with a `degraded: true` flag. The scorer reports degraded counts.
- If `data/` commits fail, the run still succeeds (forecasts are on Metaculus). The next run's commit picks up the unwritten records, because the recorder writes before committing.

## Testing

- **Unit tests (pytest):**
  - recorder serialization for each question type
  - log-score math, with known values
  - pairing logic: only questions both variants forecast, latest pre-close forecast, annulled questions excluded
  - bootstrap interval output on a fixed seed
- **Smoke test:**
  1. Run `main.py --mode test_questions` on the `bot-testing-area` tournament, first with publishing off, then on.
  2. Verify that forecasts and comments appear.
  3. Run `shadow.py` once against the testing area.
- **Local environment:** a virtual environment in `./venv`, with pyright configured to use it (`venvPath = "."`, `venv = "venv"`).

## Steve's account steps (Claude cannot do these)

1. Create a Metaculus bot account and get its `METACULUS_TOKEN`.
2. Fill in the FutureEval participant form (three required questions) and apply for LLM credits, noting that the bot is open source.
3. Create an OpenRouter account and API key, or use the key from donated credits, and set a credit limit on it.
4. Get AskNews access through the Metaculus partnership.
5. Create an empty public GitHub repo and add secrets: `METACULUS_TOKEN`, `OPENROUTER_API_KEY`, and and the AskNews credentials, using the exact secret names in the template's `.env.template`.
6. Set the repository variable `REVIEW_BOT_ENABLED=true`.

## Out of scope

- Approach C (agentic research loop)
- Scoring numeric questions in `score.py`
- The Metaculus Cup and the Market Pulse tournament
- Extremizing or other calibration post-processing, which the spring results found contested
- The coded-antisemitism benchmark, which gets a separate spec
