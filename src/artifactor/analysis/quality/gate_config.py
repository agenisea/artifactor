"""Per-section-type quality gate configuration.

Each section type has its own validation thresholds. The gate evaluator
(section_gate.py) consumes these configs directly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionGateConfig:
    """Validation configuration for a section type."""

    min_length: int = 200
    required_headings: tuple[str, ...] = ()
    check_placeholders: bool = True
    check_repetition: bool = True
    max_iterations: int = 2  # 1 initial + 1 retry


SECTION_GATES: dict[str, SectionGateConfig] = {
    "executive_overview": SectionGateConfig(
        min_length=300,
    ),
    "features": SectionGateConfig(
        min_length=200,
        required_headings=("Feature Areas",),
    ),
    "system_overview": SectionGateConfig(
        min_length=200,
        required_headings=("Architecture Diagram",),
    ),
    "data_models": SectionGateConfig(min_length=100),
    "api_specs": SectionGateConfig(min_length=100),
    "user_stories": SectionGateConfig(min_length=200),
    "tech_stories": SectionGateConfig(min_length=200),
    "security_requirements": SectionGateConfig(min_length=100),
    "security_considerations": SectionGateConfig(
        min_length=200,
        required_headings=("Coverage Summary",),
    ),
    "integrations": SectionGateConfig(min_length=100),
    "interfaces": SectionGateConfig(min_length=100),
    "personas": SectionGateConfig(min_length=100),
    "ui_specs": SectionGateConfig(min_length=50),
}
