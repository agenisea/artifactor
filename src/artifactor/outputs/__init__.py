"""Section generators registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from artifactor.config import Settings
from artifactor.intelligence.model import IntelligenceModel
from artifactor.outputs import (
    api_specs,
    data_models,
    executive_overview,
    features,
    integrations,
    interfaces,
    personas,
    security_considerations,
    security_requirements,
    system_overview,
    tech_stories,
    ui_specs,
    user_stories,
)
from artifactor.outputs.base import SectionOutput

GeneratorFn = Callable[
    [IntelligenceModel, str, Settings], Awaitable[SectionOutput]
]

SECTION_GENERATORS: dict[str, GeneratorFn] = {
    "executive_overview": executive_overview.generate,
    "features": features.generate,
    "personas": personas.generate,
    "user_stories": user_stories.generate,
    "security_requirements": security_requirements.generate,
    "system_overview": system_overview.generate,
    "data_models": data_models.generate,
    "interfaces": interfaces.generate,
    "ui_specs": ui_specs.generate,
    "api_specs": api_specs.generate,
    "integrations": integrations.generate,
    "tech_stories": tech_stories.generate,
    "security_considerations": security_considerations.generate,
}

__all__ = [
    "SECTION_GENERATORS",
    "SectionOutput",
]
