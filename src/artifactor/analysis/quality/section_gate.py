"""Section quality gate evaluator.

Validates generated section content against configurable quality checks.
Accepts a SectionGateConfig object for per-section-type configuration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from artifactor.analysis.quality.gate_config import SectionGateConfig
from artifactor.constants import Severity

_PLACEHOLDER_PATTERN = re.compile(r"\[([A-Z][A-Z0-9_\s]{2,30})\]")

_KNOWN_PLACEHOLDERS = {
    "[PROJECT NAME]",
    "[PROJECT_NAME]",
    "[TODO]",
    "[TBD]",
    "[PLACEHOLDER]",
    "[INSERT]",
    "[YOUR]",
    "[EXAMPLE]",
    "[MODULE NAME]",
    "[MODULE_NAME]",
    "[FUNCTION NAME]",
    "[FUNCTION_NAME]",
    "[CLASS NAME]",
    "[CLASS_NAME]",
    "[FILE PATH]",
    "[FILE_PATH]",
    "[DESCRIPTION]",
    "[DETAILS]",
}

_PLACEHOLDER_KEYWORDS = (
    "TODO",
    "TBD",
    "INSERT",
    "YOUR",
    "EXAMPLE",
    "PLACEHOLDER",
)


def detect_placeholders(content: str) -> list[str]:
    """Find unfilled placeholders in generated content.

    Skips code blocks and inline code.
    Returns list of found placeholder strings.
    """
    # Strip fenced code blocks
    stripped = re.sub(r"```[\s\S]*?```", "", content)
    # Strip inline code
    stripped = re.sub(r"`[^`]+`", "", stripped)

    matches = _PLACEHOLDER_PATTERN.findall(stripped)
    found: list[str] = []
    for match in matches:
        bracket_form = f"[{match}]"
        if bracket_form in _KNOWN_PLACEHOLDERS or any(
            kw in match for kw in _PLACEHOLDER_KEYWORDS
        ):
            found.append(bracket_form)
    return found


@dataclass(frozen=True)
class GateFailure:
    """A single quality gate check failure."""

    field: str
    expected: str
    actual: str
    severity: str  # "error" | "warning"
    remediation: str = ""


@dataclass(frozen=True)
class GateResult:
    """Outcome of running all quality gates on a section."""

    section_name: str
    passed: bool
    score: float  # 0.0–1.0
    failures: tuple[GateFailure, ...] = ()


def evaluate_section_gate(
    section_name: str,
    content: str,
    config: SectionGateConfig,
) -> GateResult:
    """Validate a generated section against quality gates.

    Uses config to determine which checks to run and their thresholds.
    """
    failures: list[GateFailure] = []
    total_checks = 0

    # 1. Minimum content length
    total_checks += 1
    if len(content.strip()) < config.min_length:
        failures.append(
            GateFailure(
                field="content_length",
                expected=f"At least {config.min_length} characters",
                actual=f"{len(content.strip())} characters",
                severity=Severity.ERROR,
                remediation="Generate more detailed content",
            )
        )

    # 2. Required headings
    if config.required_headings:
        total_checks += 1
        content_lower = content.lower()
        missing: list[str] = []
        for heading in config.required_headings:
            patterns = [
                f"## {heading.lower()}",
                f"### {heading.lower()}",
            ]
            if not any(p in content_lower for p in patterns):
                missing.append(heading)
        if missing:
            failures.append(
                GateFailure(
                    field="required_headings",
                    expected=(
                        "Headings present: "
                        + ", ".join(config.required_headings)
                    ),
                    actual=f"Missing: {', '.join(missing)}",
                    severity=Severity.WARNING,
                    remediation=(
                        "Add sections: " + ", ".join(missing)
                    ),
                )
            )

    # 3. Placeholder detection
    if config.check_placeholders:
        total_checks += 1
        found_placeholders = detect_placeholders(content)
        if found_placeholders:
            failures.append(
                GateFailure(
                    field="placeholders",
                    expected="No unfilled placeholders",
                    actual=(
                        f"{len(found_placeholders)} placeholder(s): "
                        + ", ".join(found_placeholders[:3])
                    ),
                    severity=Severity.ERROR,
                    remediation=(
                        "Replace all [PLACEHOLDER] text "
                        "with specific content"
                    ),
                )
            )

    # 4. Repetition detection
    if config.check_repetition:
        total_checks += 1
        paragraphs = [
            p.strip()
            for p in content.split("\n\n")
            if len(p.strip()) > 50
        ]
        seen: set[str] = set()
        dupes = 0
        for p in paragraphs:
            if p in seen:
                dupes += 1
            seen.add(p)
        if dupes > 0:
            failures.append(
                GateFailure(
                    field="repetition",
                    expected="No duplicate paragraphs",
                    actual=f"{dupes} duplicate paragraph(s)",
                    severity=Severity.WARNING,
                    remediation="Remove repeated content",
                )
            )

    error_count = sum(
        1 for f in failures if f.severity == Severity.ERROR
    )
    passed_checks = total_checks - len(failures)
    score = (
        max(0.0, passed_checks / total_checks)
        if total_checks > 0
        else 1.0
    )

    return GateResult(
        section_name=section_name,
        passed=error_count == 0,
        score=score,
        failures=tuple(failures),
    )
