"""Bot variants. A is the live bot; B is the shadow panel it is compared against."""

from dataclasses import dataclass

from forecasting_tools import GeneralLlm

GPT = "openrouter/openai/gpt-5.4"
CLAUDE = "openrouter/anthropic/claude-opus-5.5"
GEMINI = "openrouter/google/gemini-3.1-pro-preview"
PARSER = "openrouter/anthropic/claude-haiku-5.5"
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
