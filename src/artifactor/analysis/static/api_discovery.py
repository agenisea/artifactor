"""Discover HTTP API endpoints from framework decorators and route definitions."""

from __future__ import annotations

import re

from artifactor.analysis.static.schemas import (
    ASTForest,
    APIEndpoint,
    APIEndpoints,
    APIParameter,
)
from artifactor.ingestion.schemas import ChunkedFiles, LanguageMap


def discover_endpoints(
    ast_forest: ASTForest,
    chunked_files: ChunkedFiles,
    language_map: LanguageMap,
) -> APIEndpoints:
    """Find HTTP endpoints by scanning for framework decorators and route patterns.

    Currently supports:
    - Python: FastAPI (``@app.get/post/put/delete/patch``), Flask (``@app.route``)
    - JavaScript/TypeScript: Express (``app.get/post``)

    Returns an empty :class:`APIEndpoints` if no framework is detected.
    """
    endpoints: list[APIEndpoint] = []

    for chunk in chunked_files.chunks:
        if chunk.language == "python":
            endpoints.extend(
                _find_python_endpoints(
                    chunk.content, str(chunk.file_path), chunk.start_line
                )
            )
        elif chunk.language in ("javascript", "typescript"):
            endpoints.extend(
                _find_js_endpoints(
                    chunk.content, str(chunk.file_path), chunk.start_line
                )
            )

    return APIEndpoints(endpoints=endpoints)


def _find_python_endpoints(
    content: str, file_path: str, base_line: int
) -> list[APIEndpoint]:
    """Find FastAPI/Flask route decorators in Python code."""
    endpoints: list[APIEndpoint] = []
    lines = content.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # FastAPI: @app.get("/path"), @router.post("/path")
        m = re.match(
            r"@\w+\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
            stripped,
            re.IGNORECASE,
        )
        if m:
            method = m.group(1).upper()
            path = m.group(2)
            handler = _find_next_function(lines, i + 1)
            params = _extract_path_params(path)
            endpoints.append(
                APIEndpoint(
                    method=method,
                    path=path,
                    handler_file=file_path,
                    handler_function=handler or "unknown",
                    handler_line=base_line + i,
                    parameters=params,
                )
            )
            continue

        # Flask: @app.route("/path", methods=["GET", "POST"])
        m = re.match(
            r"@\w+\.route\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?",
            stripped,
        )
        if m:
            path = m.group(1)
            methods_str = m.group(2)
            methods = ["GET"]
            if methods_str:
                methods = [
                    s.strip().strip("'\"").upper()
                    for s in methods_str.split(",")
                ]
            handler = _find_next_function(lines, i + 1)
            params = _extract_path_params(path)
            for method in methods:
                endpoints.append(
                    APIEndpoint(
                        method=method,
                        path=path,
                        handler_file=file_path,
                        handler_function=handler or "unknown",
                        handler_line=base_line + i,
                        parameters=params,
                    )
                )

    return endpoints


def _find_js_endpoints(
    content: str, file_path: str, base_line: int
) -> list[APIEndpoint]:
    """Find Express-style route definitions in JavaScript/TypeScript."""
    endpoints: list[APIEndpoint] = []
    lines = content.split("\n")

    for i, line in enumerate(lines):
        # app.get('/path', handler) or router.post('/path', handler)
        m = re.search(
            r"\w+\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
            line,
            re.IGNORECASE,
        )
        if m:
            method = m.group(1).upper()
            path = m.group(2)
            params = _extract_path_params(path)
            endpoints.append(
                APIEndpoint(
                    method=method,
                    path=path,
                    handler_file=file_path,
                    handler_function="anonymous",
                    handler_line=base_line + i,
                    parameters=params,
                )
            )

    return endpoints


def _find_next_function(lines: list[str], start: int) -> str | None:
    """Find the function name on the first def/async def after start index."""
    for i in range(start, min(start + 5, len(lines))):
        m = re.match(r"\s*(?:async\s+)?def\s+(\w+)", lines[i])
        if m:
            return m.group(1)
    return None


def _extract_path_params(path: str) -> list[APIParameter]:
    """Extract path parameters from URL patterns like /users/{id} or /users/:id."""
    params: list[APIParameter] = []
    # {param} style (FastAPI, Flask, Spring)
    for m in re.finditer(r"\{(\w+)\}", path):
        params.append(
            APIParameter(
                name=m.group(1),
                location="path",
                data_type="string",
                required=True,
            )
        )
    # :param style (Express)
    for m in re.finditer(r":(\w+)", path):
        params.append(
            APIParameter(
                name=m.group(1),
                location="path",
                data_type="string",
                required=True,
            )
        )
    return params
