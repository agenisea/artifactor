"""Extract code entities from tree-sitter ASTs."""

from __future__ import annotations

import importlib

import tree_sitter

from artifactor.analysis.static.schemas import ASTForest, CodeEntity
from artifactor.config import GRAMMAR_MODULES
from artifactor.ingestion.schemas import ChunkedFiles, CodeChunk, LanguageMap

# Node types that represent named declarations, per language.
_ENTITY_NODE_TYPES: dict[str, dict[str, str]] = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
        "decorated_definition": "decorated",
    },
    "javascript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "export_statement": "export",
        "lexical_declaration": "function",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "interface_declaration": "interface",
        "type_alias_declaration": "interface",
        "export_statement": "export",
    },
    "java": {
        "class_declaration": "class",
        "interface_declaration": "interface",
        "method_declaration": "function",
        "enum_declaration": "class",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "function",
        "type_declaration": "class",
    },
    "rust": {
        "function_item": "function",
        "impl_item": "class",
        "struct_item": "class",
        "enum_item": "class",
        "trait_item": "interface",
    },
    "c": {
        "function_definition": "function",
        "struct_specifier": "class",
        "enum_specifier": "class",
    },
    "cpp": {
        "function_definition": "function",
        "class_specifier": "class",
        "struct_specifier": "class",
        "namespace_definition": "class",
    },
}


def parse_asts(
    chunked_files: ChunkedFiles,
    language_map: LanguageMap,
) -> ASTForest:
    """Parse all chunks and extract code entities.

    Returns an :class:`ASTForest` with every named declaration found.
    Unsupported languages produce no entities (graceful degradation).
    """
    grammar_langs = {
        li.name for li in language_map.languages if li.grammar_available
    }
    entities: list[CodeEntity] = []

    for chunk in chunked_files.chunks:
        if chunk.language not in grammar_langs:
            continue
        try:
            chunk_entities = _extract_entities_from_chunk(chunk)
            entities.extend(chunk_entities)
        except Exception:  # noqa: BLE001
            # Malformed code or parser crash → skip chunk
            continue

    return ASTForest(entities=entities)


def _extract_entities_from_chunk(chunk: CodeChunk) -> list[CodeEntity]:
    """Extract all named declarations from a single chunk."""
    parser = _get_parser(chunk.language)
    if parser is None:
        return []

    tree = parser.parse(chunk.content.encode("utf-8"))
    root = tree.root_node
    node_types = _ENTITY_NODE_TYPES.get(chunk.language, {})
    entities: list[CodeEntity] = []

    for child in root.children:
        extracted = _extract_entity(
            child, chunk, node_types, parent_name=None
        )
        if extracted:
            entities.extend(extracted)

    return entities


def _extract_entity(
    node: tree_sitter.Node,
    chunk: CodeChunk,
    node_types: dict[str, str],
    parent_name: str | None,
) -> list[CodeEntity]:
    """Recursively extract entities from a node and its children."""
    results: list[CodeEntity] = []
    entity_kind = node_types.get(node.type)

    if entity_kind is None:
        return results

    # Handle decorated_definition / export_statement wrappers
    if entity_kind in ("decorated", "export"):
        for child in node.children:
            child_kind = node_types.get(child.type)
            if child_kind and child_kind not in ("decorated", "export"):
                inner = _extract_entity(child, chunk, node_types, parent_name)
                results.extend(inner)
        return results

    name = _get_name(node)
    if name is None:
        return results

    # Compute absolute line numbers (chunk.start_line is 1-indexed)
    abs_start = chunk.start_line + node.start_point[0]
    abs_end = chunk.start_line + node.end_point[0]

    signature = _get_signature(node, chunk.language)
    docstring = _get_docstring(node, chunk.language)

    # Collect children names for class-like entities
    children_names: list[str] = []
    if entity_kind == "class":
        children_names = _get_children_names(node, chunk.language, node_types)

    entity = CodeEntity(
        name=name,
        entity_type=entity_kind,
        file_path=chunk.file_path,
        start_line=abs_start,
        end_line=abs_end,
        language=chunk.language,
        signature=signature,
        docstring=docstring,
        parent=parent_name,
        children=children_names,
    )
    results.append(entity)

    return results


def _get_name(node: tree_sitter.Node) -> str | None:
    """Extract the identifier name from a declaration node."""
    for child in node.children:
        if child.type in ("identifier", "name", "type_identifier"):
            return child.text.decode("utf-8") if child.text else None
    return None


def _get_signature(node: tree_sitter.Node, language: str) -> str | None:
    """Extract the function/method signature (parameters)."""
    params_node = None
    for child in node.children:
        if child.type in ("parameters", "formal_parameters", "parameter_list"):
            params_node = child
            break

    if params_node is None:
        return None

    sig_text = params_node.text.decode("utf-8") if params_node.text else ""

    # For Python, prepend function name
    name = _get_name(node)
    if name and language == "python":
        # Check for return type annotation
        ret = _get_return_type(node)
        ret_str = f" -> {ret}" if ret else ""
        return f"{name}{sig_text}{ret_str}"

    return f"{name or ''}{sig_text}" if name else sig_text


def _get_return_type(node: tree_sitter.Node) -> str | None:
    """Extract return type annotation (Python)."""
    for child in node.children:
        if child.type == "type":
            return child.text.decode("utf-8") if child.text else None
    return None


def _get_docstring(node: tree_sitter.Node, language: str) -> str | None:
    """Extract the docstring or leading doc comment."""
    if language == "python":
        # Python docstring: first child of function/class body that is a string
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    if stmt.type == "expression_statement":
                        for expr in stmt.children:
                            if expr.type == "string":
                                raw = (
                                    expr.text.decode("utf-8")
                                    if expr.text
                                    else ""
                                )
                                return raw.strip("\"'").strip()
                    break  # Only check first statement
    elif language in ("javascript", "typescript", "java"):
        # JSDoc / Javadoc: look for comment node immediately preceding
        prev = node.prev_sibling
        if prev and prev.type in ("comment", "block_comment"):
            raw = prev.text.decode("utf-8") if prev.text else ""
            return raw.strip("/*").strip()
    return None


def _get_children_names(
    node: tree_sitter.Node,
    language: str,
    node_types: dict[str, str],
) -> list[str]:
    """Extract names of methods/fields inside a class-like node."""
    names: list[str] = []
    body = None
    for child in node.children:
        if child.type in ("block", "class_body", "declaration_list"):
            body = child
            break
    if body is None:
        return names

    for child in body.children:
        if child.type in node_types:
            name = _get_name(child)
            if name:
                names.append(name)
    return names


# ---------------------------------------------------------------------------
# Parser cache
# ---------------------------------------------------------------------------

_parser_cache: dict[str, tree_sitter.Parser] = {}


def _get_parser(language: str) -> tree_sitter.Parser | None:
    """Get or create a cached tree-sitter parser."""
    if language in _parser_cache:
        return _parser_cache[language]

    module_name = GRAMMAR_MODULES.get(language)
    if module_name is None:
        return None

    try:
        mod = importlib.import_module(module_name)
        capsule: object = mod.language()
        lang = tree_sitter.Language(capsule)
        parser = tree_sitter.Parser(lang)
        _parser_cache[language] = parser
        return parser
    except (ImportError, AttributeError):
        return None
