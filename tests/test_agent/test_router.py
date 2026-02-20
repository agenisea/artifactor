"""Tests for intent-based chat router."""

from __future__ import annotations

from artifactor.agent.router import ChatIntent, classify_intent
from artifactor.constants import SEARCH_PRIORITY_WEIGHT


class TestChatIntent:
    def test_intent_values(self) -> None:
        assert ChatIntent.LOOKUP == "lookup"
        assert ChatIntent.CODE_EXPLORATION == "code_exploration"
        assert ChatIntent.SEARCH == "search"
        assert ChatIntent.GENERAL == "general"

    def test_intent_is_str(self) -> None:
        for intent in ChatIntent:
            assert isinstance(intent, str)


class TestClassifyIntent:
    def test_lookup_section(self) -> None:
        assert classify_intent("Show me the features section") == ChatIntent.LOOKUP

    def test_lookup_specification(self) -> None:
        assert classify_intent("Get the API specification") == ChatIntent.LOOKUP

    def test_lookup_stories(self) -> None:
        assert classify_intent("What user stories exist?") == ChatIntent.LOOKUP

    def test_lookup_security(self) -> None:
        assert classify_intent("Show security findings") == ChatIntent.LOOKUP

    def test_lookup_endpoint(self) -> None:
        assert classify_intent("List the endpoint details") == ChatIntent.LOOKUP

    def test_code_exploration_function(self) -> None:
        result = classify_intent("Explain the function parse_config")
        assert result == ChatIntent.CODE_EXPLORATION

    def test_code_exploration_class(self) -> None:
        result = classify_intent("What does the User class do?")
        assert result == ChatIntent.CODE_EXPLORATION

    def test_code_exploration_call_graph(self) -> None:
        result = classify_intent("Show the call graph for process")
        assert result == ChatIntent.CODE_EXPLORATION

    def test_code_exploration_data_model(self) -> None:
        result = classify_intent("Describe the data model")
        assert result == ChatIntent.CODE_EXPLORATION

    def test_code_exploration_symbol(self) -> None:
        result = classify_intent("Explain the symbol create_user")
        assert result == ChatIntent.CODE_EXPLORATION

    def test_search_find(self) -> None:
        assert classify_intent("Find authentication code") == ChatIntent.SEARCH

    def test_search_locate(self) -> None:
        assert classify_intent("Locate the config parser") == ChatIntent.SEARCH

    def test_search_where(self) -> None:
        assert classify_intent("Where is the database connection?") == ChatIntent.SEARCH

    def test_search_which_files(self) -> None:
        assert classify_intent("Which files handle routing?") == ChatIntent.SEARCH

    def test_search_priority_over_lookup(self) -> None:
        """'find the features' should be SEARCH not LOOKUP due to priority weight."""
        result = classify_intent("find the features")
        assert result == ChatIntent.SEARCH

    def test_general_empty_message(self) -> None:
        assert classify_intent("") == ChatIntent.GENERAL

    def test_general_ambiguous(self) -> None:
        assert classify_intent("hello there") == ChatIntent.GENERAL

    def test_general_conversational(self) -> None:
        assert classify_intent("thanks for the help") == ChatIntent.GENERAL

    def test_case_insensitive(self) -> None:
        assert classify_intent("SHOW ME THE FEATURES SECTION") == ChatIntent.LOOKUP

    def test_multi_word_keyword_call_graph(self) -> None:
        assert classify_intent("show call graph") == ChatIntent.CODE_EXPLORATION

    def test_multi_word_keyword_data_model(self) -> None:
        assert classify_intent("describe the data model") == ChatIntent.CODE_EXPLORATION

    def test_multi_word_keyword_show_me_all(self) -> None:
        assert classify_intent("show me all classes") == ChatIntent.SEARCH

    def test_ties_resolve_to_general(self) -> None:
        """When LOOKUP and CODE_EXPLORATION tie, should be GENERAL."""
        # "entity" matches CODE_EXPLORATION, "feature" matches LOOKUP
        # If both score 1.0, tie → GENERAL
        result = classify_intent("entity feature")
        # Both have score 1.0 (no SEARCH weight), so tie → GENERAL
        assert result == ChatIntent.GENERAL

    def test_search_priority_weight_constant(self) -> None:
        assert SEARCH_PRIORITY_WEIGHT == 1.5
