"""Extract import/dependency edges from source code ASTs."""

from __future__ import annotations

import importlib
import re

import tree_sitter

from artifactor.analysis.static.schemas import DependencyEdge, DependencyGraph
from artifactor.config import GRAMMAR_MODULES
from artifactor.ingestion.schemas import ChunkedFiles, CodeChunk, LanguageMap

# Import-related node types per language
_IMPORT_NODE_TYPES: dict[str, set[str]] = {
    "python": {"import_statement", "import_from_statement"},
    "javascript": {"import_statement", "call_expression"},
    "typescript": {"import_statement", "call_expression"},
    "java": {"import_declaration"},
    "go": {"import_declaration", "import_spec"},
    "rust": {"use_declaration"},
    "c": {"preproc_include"},
    "cpp": {"preproc_include"},
}


def extract_imports(
    chunked_files: ChunkedFiles,
    language_map: LanguageMap,
) -> DependencyGraph:
    """Extract all import/require/include statements from the codebase."""
    grammar_langs = {
        li.name for li in language_map.languages if li.grammar_available
    }
    edges: list[DependencyEdge] = []

    for chunk in chunked_files.chunks:
        if chunk.language not in grammar_langs:
            continue
        try:
            chunk_edges = _extract_imports_from_chunk(chunk)
            edges.extend(chunk_edges)
        except Exception:  # noqa: BLE001
            continue

    return DependencyGraph(edges=edges)


def _extract_imports_from_chunk(chunk: CodeChunk) -> list[DependencyEdge]:
    """Extract import statements from a single chunk."""
    parser = _get_parser(chunk.language)
    if parser is None:
        return []

    tree = parser.parse(chunk.content.encode("utf-8"))
    import_types = _IMPORT_NODE_TYPES.get(chunk.language, set())
    edges: list[DependencyEdge] = []

    _walk_imports(tree.root_node, chunk, import_types, edges)
    return edges


def _walk_imports(
    node: tree_sitter.Node,
    chunk: CodeChunk,
    import_types: set[str],
    edges: list[DependencyEdge],
) -> None:
    """Recursively walk the AST collecting import edges."""
    if node.type in import_types:
        extracted = _parse_import_node(node, chunk)
        if extracted:
            edges.extend(extracted)

    for child in node.children:
        _walk_imports(child, chunk, import_types, edges)


def _parse_import_node(
    node: tree_sitter.Node,
    chunk: CodeChunk,
) -> list[DependencyEdge]:
    """Parse an import node into DependencyEdge(s)."""
    text = node.text.decode("utf-8") if node.text else ""
    source_file = str(chunk.file_path)
    lang = chunk.language

    if lang == "python":
        return _parse_python_import(text, source_file)
    if lang in ("javascript", "typescript"):
        return _parse_js_import(node, text, source_file)
    if lang == "java":
        return _parse_java_import(text, source_file)
    if lang == "go":
        return _parse_go_import(text, source_file)
    if lang == "rust":
        return _parse_rust_import(text, source_file)
    if lang in ("c", "cpp"):
        return _parse_c_include(text, source_file)

    return []


def _parse_python_import(
    text: str, source_file: str
) -> list[DependencyEdge]:
    """Parse Python import/from...import statements."""
    edges: list[DependencyEdge] = []

    # from X import Y, Z
    m = re.match(r"from\s+([\w.]+)\s+import\s+(.+)", text.strip())
    if m:
        module = m.group(1)
        symbols_str = m.group(2).strip()
        if symbols_str == "*":
            edges.append(
                DependencyEdge(
                    source_file=source_file,
                    target=module,
                    import_type="wildcard",
                    symbols=["*"],
                )
            )
        else:
            symbols = [s.strip().split(" as ")[0] for s in symbols_str.split(",")]
            edges.append(
                DependencyEdge(
                    source_file=source_file,
                    target=module,
                    import_type="symbol",
                    symbols=symbols,
                )
            )
        return edges

    # import X, Y
    m = re.match(r"import\s+(.+)", text.strip())
    if m:
        for mod in m.group(1).split(","):
            mod = mod.strip().split(" as ")[0]
            edges.append(
                DependencyEdge(
                    source_file=source_file,
                    target=mod,
                    import_type="module",
                )
            )
        return edges

    return edges


def _parse_js_import(
    node: tree_sitter.Node, text: str, source_file: str
) -> list[DependencyEdge]:
    """Parse JavaScript/TypeScript import and require()."""
    edges: list[DependencyEdge] = []

    # ES import: import X from 'Y' or import { X } from 'Y'
    m = re.search(r"""from\s+['"]([^'"]+)['"]""", text)
    if m:
        target = m.group(1)
        # Extract named imports
        named = re.search(r"\{([^}]+)\}", text)
        symbols = (
            [s.strip().split(" as ")[0] for s in named.group(1).split(",")]
            if named
            else []
        )
        import_type = "symbol" if symbols else "module"
        edges.append(
            DependencyEdge(
                source_file=source_file,
                target=target,
                import_type=import_type,
                symbols=symbols,
            )
        )
        return edges

    # require() call
    if node.type == "call_expression":
        m = re.search(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", text)
        if m:
            edges.append(
                DependencyEdge(
                    source_file=source_file,
                    target=m.group(1),
                    import_type="module",
                )
            )
    return edges


def _parse_java_import(
    text: str, source_file: str
) -> list[DependencyEdge]:
    """Parse Java import declarations."""
    m = re.match(r"import\s+(static\s+)?([\w.]+)(\.\*)?;", text.strip())
    if m:
        target = m.group(2)
        is_wildcard = m.group(3) is not None
        return [
            DependencyEdge(
                source_file=source_file,
                target=target,
                import_type="wildcard" if is_wildcard else "symbol",
            )
        ]
    return []


def _parse_go_import(
    text: str, source_file: str
) -> list[DependencyEdge]:
    """Parse Go import declarations."""
    edges: list[DependencyEdge] = []
    for m in re.finditer(r'"([^"]+)"', text):
        edges.append(
            DependencyEdge(
                source_file=source_file,
                target=m.group(1),
                import_type="module",
            )
        )
    return edges


def _parse_rust_import(
    text: str, source_file: str
) -> list[DependencyEdge]:
    """Parse Rust use declarations."""
    m = re.match(r"use\s+([\w:]+)", text.strip())
    if m:
        return [
            DependencyEdge(
                source_file=source_file,
                target=m.group(1),
                import_type="module",
            )
        ]
    return []


def _parse_c_include(
    text: str, source_file: str
) -> list[DependencyEdge]:
    """Parse C/C++ #include directives."""
    m = re.match(r'#include\s+[<"]([^>"]+)[>"]', text.strip())
    if m:
        return [
            DependencyEdge(
                source_file=source_file,
                target=m.group(1),
                import_type="module",
            )
        ]
    return []


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
