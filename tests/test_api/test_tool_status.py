"""Tests for tool status templates."""

from __future__ import annotations

from artifactor.api.routes.chat import (
    TOOL_STATUS_TEMPLATES,
    _tool_status_message,
)


class TestToolStatusTemplates:
    def test_all_10_tools_have_templates(self) -> None:
        """Every agent tool must have a status template."""
        expected_tools = {
            "query_codebase",
            "get_specification",
            "list_features",
            "get_data_model",
            "explain_symbol",
            "get_call_graph",
            "get_user_stories",
            "get_api_endpoints",
            "search_code_entities",
            "get_security_findings",
        }
        assert set(TOOL_STATUS_TEMPLATES.keys()) == expected_tools

    def test_known_tool_with_matching_args(self) -> None:
        result = _tool_status_message(
            "query_codebase", {"question": "How does auth work?"}
        )
        assert result == "Searching codebase for: How does auth work?..."

    def test_known_tool_with_json_string_args(self) -> None:
        result = _tool_status_message(
            "get_specification",
            '{"section": "features"}',
        )
        assert result == "Retrieving features specification..."

    def test_unknown_tool_returns_fallback(self) -> None:
        result = _tool_status_message(
            "unknown_tool", {"foo": "bar"}
        )
        assert result == "Running unknown_tool..."

    def test_missing_args_returns_fallback(self) -> None:
        result = _tool_status_message("query_codebase", None)
        assert result == "Running query_codebase..."

    def test_wrong_args_keys_returns_fallback(self) -> None:
        result = _tool_status_message(
            "query_codebase", {"wrong_key": "value"}
        )
        assert result == "Running query_codebase..."

    def test_empty_dict_args_returns_fallback(self) -> None:
        result = _tool_status_message("list_features", {})
        assert result == "Running list_features..."

    def test_no_arg_template_works(self) -> None:
        """Templates with no placeholders work with any args."""
        result = _tool_status_message(
            "list_features", {"anything": "value"}
        )
        assert result == "Loading discovered features..."
