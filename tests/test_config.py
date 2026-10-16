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
