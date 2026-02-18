"""Extract data schemas from ORM models and SQL files."""

from __future__ import annotations

import re

from artifactor.analysis.static.schemas import (
    ASTForest,
    SchemaAttribute,
    SchemaEntity,
    SchemaMap,
    SchemaRelationship,
)
from artifactor.ingestion.schemas import ChunkedFiles, LanguageMap


def extract_schemas(
    ast_forest: ASTForest,
    chunked_files: ChunkedFiles,
    language_map: LanguageMap,
) -> SchemaMap:
    """Find data models and SQL table definitions in the codebase.

    Currently supports:
    - SQL: ``CREATE TABLE`` statements in ``.sql`` files
    - Python ORM: SQLAlchemy ``Column()`` and ``mapped_column()`` patterns

    Returns an empty :class:`SchemaMap` if no schemas are found.
    """
    entities: list[SchemaEntity] = []

    for chunk in chunked_files.chunks:
        if chunk.language == "sql":
            path = str(chunk.file_path)
            entities.extend(
                _parse_sql_chunk(chunk.content, path, chunk.start_line)
            )

    # Look for ORM patterns in Python files
    for chunk in chunked_files.chunks:
        if chunk.language == "python":
            path = str(chunk.file_path)
            entities.extend(
                _parse_python_orm(chunk.content, path, chunk.start_line)
            )

    return SchemaMap(entities=entities)


def _parse_sql_chunk(
    content: str, file_path: str, base_line: int
) -> list[SchemaEntity]:
    """Parse CREATE TABLE statements from SQL content."""
    entities: list[SchemaEntity] = []
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        pattern = r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\("
        m = re.match(pattern, line, re.IGNORECASE)
        if m:
            table_name = m.group(1)
            start_line = base_line + i

            # Collect all lines until closing );
            body_lines: list[str] = []
            j = i
            while j < len(lines):
                body_lines.append(lines[j])
                if ");" in lines[j] or (lines[j].strip() == ")"):
                    break
                j += 1

            body = "\n".join(body_lines)
            attrs, rels = _parse_sql_columns(body)
            entities.append(
                SchemaEntity(
                    name=table_name,
                    source_type="sql_definition",
                    file_path=file_path,
                    start_line=start_line,
                    attributes=attrs,
                    relationships=rels,
                )
            )
            i = j + 1
        else:
            i += 1

    return entities


def _parse_sql_columns(
    body: str,
) -> tuple[list[SchemaAttribute], list[SchemaRelationship]]:
    """Parse column definitions and constraints from a CREATE TABLE body."""
    attrs: list[SchemaAttribute] = []
    rels: list[SchemaRelationship] = []

    # Remove the CREATE TABLE ... ( prefix and trailing );
    m = re.search(r"\((.*)\)", body, re.DOTALL)
    if not m:
        return attrs, rels

    inner = m.group(1)
    # Split on commas that are not inside parentheses
    col_defs = _split_columns(inner)

    for col_def in col_defs:
        col_def = col_def.strip()
        if not col_def:
            continue

        # FOREIGN KEY constraint
        fk = re.match(
            r"FOREIGN\s+KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)",
            col_def,
            re.IGNORECASE,
        )
        if fk:
            rels.append(
                SchemaRelationship(
                    target_entity=fk.group(2),
                    relationship_type="one_to_many",
                    foreign_key=fk.group(1),
                )
            )
            continue

        # Regular column: name TYPE [constraints...]
        parts = col_def.split()
        if len(parts) < 2:
            continue

        name = parts[0]
        # Skip SQL keywords that aren't column names
        if name.upper() in (
            "PRIMARY",
            "UNIQUE",
            "CHECK",
            "CONSTRAINT",
            "INDEX",
        ):
            continue

        data_type = parts[1]
        upper = col_def.upper()
        attrs.append(
            SchemaAttribute(
                name=name,
                data_type=data_type,
                nullable="NOT NULL" not in upper,
                primary_key="PRIMARY KEY" in upper,
                constraints=_extract_sql_constraints(upper),
            )
        )

    return attrs, rels


def _extract_sql_constraints(upper_def: str) -> list[str]:
    """Extract constraint keywords from a column definition."""
    constraints: list[str] = []
    if "UNIQUE" in upper_def:
        constraints.append("unique")
    if "DEFAULT" in upper_def:
        m = re.search(r"DEFAULT\s+(\S+)", upper_def)
        if m:
            constraints.append(f"default:{m.group(1).lower()}")
    return constraints


def _split_columns(inner: str) -> list[str]:
    """Split column definitions respecting parenthesized expressions."""
    result: list[str] = []
    depth = 0
    current: list[str] = []
    for char in inner:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            result.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        result.append("".join(current))
    return result


def _parse_python_orm(
    content: str, file_path: str, base_line: int
) -> list[SchemaEntity]:
    """Detect SQLAlchemy model classes and extract columns."""
    entities: list[SchemaEntity] = []
    lines = content.split("\n")

    for i, line in enumerate(lines):
        # Look for class definitions that inherit from common ORM bases
        m = re.match(
            r"class\s+(\w+)\s*\(.*(?:Base|Model|DeclarativeBase).*\)\s*:",
            line,
        )
        if not m:
            continue

        class_name = m.group(1)
        attrs: list[SchemaAttribute] = []
        rels: list[SchemaRelationship] = []

        # Scan body lines for Column() / mapped_column() / relationship()
        j = i + 1
        while j < len(lines) and _is_indented_or_blank(lines[j]):
            stripped = lines[j].strip()

            # Column() or mapped_column()
            col_m = re.match(
                r"(\w+)\s*[=:]\s*(?:Column|mapped_column)\s*\((.+)\)",
                stripped,
            )
            if col_m:
                col_name = col_m.group(1)
                col_args = col_m.group(2)
                attrs.append(
                    SchemaAttribute(
                        name=col_name,
                        data_type=_infer_sqlalchemy_type(col_args),
                        nullable="nullable=False" not in col_args,
                        primary_key="primary_key=True" in col_args,
                    )
                )

            # relationship()
            rel_m = re.match(
                r"(\w+)\s*=\s*relationship\s*\(['\"]?(\w+)['\"]?",
                stripped,
            )
            if rel_m:
                rels.append(
                    SchemaRelationship(
                        target_entity=rel_m.group(2),
                        relationship_type="one_to_many",
                    )
                )

            j += 1

        if attrs:
            entities.append(
                SchemaEntity(
                    name=class_name,
                    source_type="orm_model",
                    file_path=file_path,
                    start_line=base_line + i,
                    attributes=attrs,
                    relationships=rels,
                )
            )

    return entities


def _is_indented_or_blank(line: str) -> bool:
    """Return True if the line is indented or blank (class body)."""
    return line.startswith((" ", "\t")) or not line.strip()


def _infer_sqlalchemy_type(args: str) -> str:
    """Infer the data type from SQLAlchemy Column/mapped_column args."""
    # First positional arg is usually the type
    type_m = re.match(r"\s*(\w+)", args)
    if type_m:
        return type_m.group(1)
    return "unknown"
