"""Build a call graph by extracting call expressions from ASTs."""

from __future__ import annotations

import importlib

import tree_sitter

from artifactor.analysis.static.schemas import ASTForest, CallEdge, CallGraph
from artifactor.config import GRAMMAR_MODULES
from artifactor.ingestion.schemas import ChunkedFiles, CodeChunk, LanguageMap

# Call expression node types per language
_CALL_NODE_TYPES: dict[str, set[str]] = {
    "python": {"call"},
    "javascript": {"call_expression", "new_expression"},
    "typescript": {"call_expression", "new_expression"},
    "java": {"method_invocation", "object_creation_expression"},
    "go": {"call_expression"},
    "rust": {"call_expression", "macro_invocation"},
    "c": {"call_expression"},
    "cpp": {"call_expression"},
}


def build_call_graph(
    ast_forest: ASTForest,
    chunked_files: ChunkedFiles,
    language_map: LanguageMap,
) -> CallGraph:
    """Walk function bodies and extract call expressions.

    Resolves callees against known entities in the AST forest:
    - Match found → confidence "high"
    - No match → confidence "low" with raw callee string
    """
    known_names = {e.name for e in ast_forest.entities}
    grammar_langs = {
        li.name for li in language_map.languages if li.grammar_available
    }

    edges: list[CallEdge] = []
    for chunk in chunked_files.chunks:
        if chunk.language not in grammar_langs:
            continue
        try:
            chunk_edges = _extract_calls_from_chunk(
                chunk, known_names
            )
            edges.extend(chunk_edges)
        except Exception:  # noqa: BLE001
            continue

    return CallGraph(edges=edges)


def _extract_calls_from_chunk(
    chunk: CodeChunk,
    known_names: set[str],
) -> list[CallEdge]:
    """Extract call expressions from a single chunk."""
    parser = _get_parser(chunk.language)
    if parser is None:
        return []

    tree = parser.parse(chunk.content.encode("utf-8"))
    call_types = _CALL_NODE_TYPES.get(chunk.language, set())
    edges: list[CallEdge] = []

    _walk_calls(
        tree.root_node, chunk, call_types, known_names, edges
    )
    return edges


def _walk_calls(
    node: tree_sitter.Node,
    chunk: CodeChunk,
    call_types: set[str],
    known_names: set[str],
    edges: list[CallEdge],
) -> None:
    """Recursively walk the AST collecting call edges."""
    if node.type in call_types:
        callee, receiver = _get_callee_name(node)
        if callee:
            abs_line = chunk.start_line + node.start_point[0]
            call_type = "constructor" if node.type == "new_expression" else "direct"
            confidence = "high" if callee in known_names else "low"

            edges.append(
                CallEdge(
                    caller_file=str(chunk.file_path),
                    caller_line=abs_line,
                    callee=callee,
                    receiver=receiver,
                    call_type=call_type,
                    confidence=confidence,
                )
            )

    for child in node.children:
        _walk_calls(child, chunk, call_types, known_names, edges)


def _get_callee_name(
    node: tree_sitter.Node,
) -> tuple[str | None, str | None]:
    """Extract the callee identifier and optional receiver.

    Returns (callee_name, receiver_name). For ``obj.method()``,
    returns ``("method", "obj")``. For ``foo()``, returns
    ``("foo", None)``.
    """
    if not node.children:
        return None, None

    func_node = node.children[0]

    # Simple identifier: foo()
    if func_node.type in ("identifier", "name"):
        name = func_node.text.decode("utf-8") if func_node.text else None
        return name, None

    # Attribute access: obj.method()
    if func_node.type in (
        "attribute",
        "member_expression",
        "field_expression",
    ):
        method_name: str | None = None
        receiver_name: str | None = None
        # Method name: last identifier child
        for child in reversed(func_node.children):
            if child.type in (
                "identifier",
                "property_identifier",
                "field_identifier",
            ):
                method_name = (
                    child.text.decode("utf-8")
                    if child.text
                    else None
                )
                break
        # Receiver: first identifier child (the object)
        for child in func_node.children:
            if child.type in ("identifier", "name"):
                receiver_name = (
                    child.text.decode("utf-8")
                    if child.text
                    else None
                )
                break
        return method_name, receiver_name

    # Fallback: raw text of the function node
    text = func_node.text.decode("utf-8") if func_node.text else None
    if text and len(text) < 100:
        return text, None
    return None, None


# ---------------------------------------------------------------------------
# Parser cache
# ---------------------------------------------------------------------------

_parser_cache: dict[str, tree_sitter.Parser] = {}


def _get_parser(language: str) -> tree_sitter.Parser | None:
    """Get or create a cached parser."""
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
