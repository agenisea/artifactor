"""Tests for the schema extractor module."""

from __future__ import annotations

from pathlib import Path

from artifactor.analysis.static.ast_parser import parse_asts
from artifactor.analysis.static.schema_extractor import extract_schemas
from artifactor.ingestion.chunker import chunk_code
from artifactor.ingestion.language_detector import detect_languages
from artifactor.ingestion.schemas import RepoPath

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "test_repo"


def test_sql_create_table_parsed() -> None:
    """Extracts tables from schema.sql fixture."""
    rp = RepoPath(path=FIXTURE_DIR, commit_sha="test", branch="main")
    lm = detect_languages(rp)
    cf = chunk_code(rp, lm)
    af = parse_asts(cf, lm)
    sm = extract_schemas(af, cf, lm)

    table_names = {e.name for e in sm.entities}
    assert "users" in table_names
    assert "orders" in table_names

    # Check users table attributes
    users = next(e for e in sm.entities if e.name == "users")
    attr_names = {a.name for a in users.attributes}
    assert "id" in attr_names
    assert "name" in attr_names
    assert "email" in attr_names

    # Check orders has a relationship to users
    orders = next(e for e in sm.entities if e.name == "orders")
    assert len(orders.relationships) >= 1
    assert orders.relationships[0].target_entity == "users"
