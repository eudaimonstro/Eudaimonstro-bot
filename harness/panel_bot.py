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
