"""Drift guard: SectionName enum must match SECTION_TITLES keys."""

from artifactor.config import SECTION_TITLES
from artifactor.constants import SectionName


class TestSectionNameDrift:
    def test_enum_matches_section_titles_keys(self) -> None:
        """SectionName members must be exactly the SECTION_TITLES keys."""
        enum_values = {s.value for s in SectionName}
        title_keys = set(SECTION_TITLES.keys())
        assert enum_values == title_keys, (
            f"Drift detected.\n"
            f"  In enum only: {enum_values - title_keys}\n"
            f"  In titles only: {title_keys - enum_values}"
        )
