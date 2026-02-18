# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue
2. Email the maintainer directly or use GitHub's private vulnerability reporting
3. Include steps to reproduce, impact assessment, and any suggested fixes
4. You will receive a response within 72 hours

## Security Model

### Local-First Architecture

Artifactor is designed to run locally. By default:

- **Code never leaves your machine** unless you configure a cloud LLM provider
- **No telemetry** — no data is collected or transmitted
- **No cloud storage** — all data stored in local SQLite and LanceDB databases
- **No code execution** — Artifactor performs static analysis and LLM inference only; it never runs, compiles, or evaluates analyzed code

### Analysis Safety

- **Read-only** — Artifactor reads source files but never modifies them
- **No runtime execution** — analysis is purely static (tree-sitter AST) and LLM-based
- **Sandboxed output** — generated documentation contains citations, not executable code

### Authentication

- The REST API supports optional API key authentication via the `API_KEY` environment variable
- When `API_KEY` is empty (default), no authentication is enforced — suitable for local development
- **Set `API_KEY` when exposing the API on a network**

### Data Handling

- **SQLite** stores project metadata, entities, relationships, and generated sections
- **LanceDB** stores vector embeddings for RAG search
- Both databases are local files — no external database connections by default
- Database files are stored in the `data/` directory (gitignored)

## Dependencies

- All Python dependencies are pinned in `uv.lock`
- Frontend dependencies are pinned in `pnpm-lock.yaml`
- CI runs on every PR to verify lint, type checks, and tests pass

## Best Practices for Users

- Keep API keys in `.env` files (gitignored) — never commit them
- Set `API_KEY` when deploying the API beyond localhost
- Review `CORS_ORIGINS` configuration before network deployment
- Use the Docker image for isolated deployments
