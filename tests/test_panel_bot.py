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


def test_get_config_runs():
    assert make_bot().get_config()["llms"]["default"]


def test_make_llm_dict_lists_the_whole_panel():
    assert make_bot().make_llm_dict()["default"] == ["openrouter/x/one", "openrouter/x/two", "openrouter/x/three"]
