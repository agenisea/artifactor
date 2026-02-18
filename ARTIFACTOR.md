# Artifactor — Complete Reference

Comprehensive technical documentation for Artifactor, an open-source code intelligence infrastructure that builds a programmable Intelligence Model from any codebase. For a quick overview, see [README.md](README.md).

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [API](#api)
- [MCP Server](#mcp-server)
- [Chat & RAG](#chat--rag)
- [Playbooks](#playbooks)
- [Section Generators](#section-generators)
- [Export Formats](#export-formats)
- [Language Support](#language-support)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Development](#development)
- [Why Artifactor](#why-artifactor)

---

## How It Works

Artifactor runs two independent analysis paths against your code and cross-validates their results.

### Path 1 — Static Analysis

Parses every file with tree-sitter to extract ASTs, call graphs, dependency graphs, database schemas, and API endpoints. This is deterministic and fast.

### Path 2 — LLM Inference

Sends code chunks to an LLM (configurable via litellm — defaults to GPT-4.1-mini with GPT-4.0-mini fallback) for narration, business rule extraction, and risk detection. This is probabilistic and slower.

### Cross-Validation

Reconciles both paths using token-based word-boundary matching. Entities found by both AST and LLM get high confidence. AST-only findings score lower. LLM-only findings score lowest. Confidence scores flow through a dedicated scorer module. Citations are verified against the source tree at the end of the pipeline.

### Section Generation

Uses LLM synthesis with template fallback. Each of the 13 section generators collects its relevant data slice from the intelligence model, sends it to the LLM with a section-specific prompt, and receives synthesized markdown. Quality gates validate the output (minimum length, no placeholders, required headings). If synthesis fails, the generator falls back to deterministic template rendering. Confidence scores are dynamic — derived from context richness and gate validation scores.

---

## Architecture

### Design Axioms

1. **Understanding > Action** — reads code, never writes or executes it
2. **Verified Citation > Coverage** — every claim must cite its source
3. **Honesty > Impression** — low confidence is disclosed, not hidden
4. **Local-First > Convenience** — code never leaves your machine unless you configure a cloud LLM
5. **Language-Agnostic > Language-Specific** — one platform for all languages via tree-sitter

### Key Patterns

- **Dual-path analysis** — Static (tree-sitter AST) + LLM inference, cross-validated with token-based matching and confidence scoring
- **Protocol-based repositories** — `typing.Protocol` interfaces for all data access (entity, document, conversation, relationship, project)
- **Typed pipeline** — `PipelineStage[TInput, TOutput]` + `ParallelGroup` with semaphore-bounded concurrency
- **Intelligence Model** — `KnowledgeGraph` (entities + relationships, cycle-safe traversal) + `ReasoningGraph` (purposes, rules, workflows)
- **SSE streaming** — `sse-starlette` for analysis progress and chat responses
- **RAG pipeline** — Hybrid vector (LanceDB) + keyword (SQLite FTS) search, merged via Reciprocal Rank Fusion (RRF)
- **Citation guardrails** — Every generated claim cites source code; citations verified against the source tree in the pipeline

The codebase is 139 Python source files with strict Pyright type checking, protocol-based repositories (no inheritance), frozen value objects, and a typed pipeline architecture with semaphore-bounded concurrency.

---

## API

Artifactor exposes a REST API (FastAPI) with 30 routes. Analysis progress and chat responses stream via Server-Sent Events (SSE).

```
POST /api/projects                          Create a project
GET  /api/projects/{id}                     Get project details
DELETE /api/projects/{id}                   Delete a project
GET  /api/projects/{id}/status              Analysis status
POST /api/projects/{id}/analyze             Run analysis (SSE progress stream)
POST /api/projects/{id}/pause               Pause a running analysis
GET  /api/projects/{id}/sections            List generated sections
GET  /api/projects/{id}/sections/{name}     Get section content
POST /api/projects/{id}/sections/{name}/regenerate  Re-run a section generator
GET  /api/projects/{id}/sections/{name}/export?format=pdf  Export section
GET  /api/projects/{id}/entities            Search code entities
GET  /api/projects/{id}/features            List detected features
GET  /api/projects/{id}/data-models         List data models
GET  /api/projects/{id}/api-endpoints       List API endpoints
GET  /api/projects/{id}/user-stories        List user stories
GET  /api/projects/{id}/security            Security findings
GET  /api/projects/{id}/call-graph/{file}/{symbol}  Call graph for a symbol
GET  /api/projects/{id}/diagrams/{type}     Mermaid diagrams (architecture, er, call_graph, sequence)
POST /api/projects/{id}/query               RAG-backed intelligence query (JSON)
POST /api/projects/{id}/chat                Chat with your codebase (SSE)
GET  /api/projects/{id}/conversations       List chat conversations
```

Analysis can be paused mid-run via `POST /api/projects/{id}/pause` and resumed by calling `POST /api/projects/{id}/analyze` again. The pause endpoint delivers a `paused` SSE event to the active connection before cancelling the background task, so the UI updates immediately. Late-joining clients receive the event through the event bus.

---

## MCP Server

Artifactor ships an MCP server for integration with AI coding agents:

```bash
artifactor mcp
```

This exposes 10 tools, 5 resources, and 5 prompts via the Model Context Protocol. AI agents can query your codebase's business rules, data models, API contracts, call graphs, and security findings — all grounded in citations.

**Tools**: `query_codebase`, `get_specification`, `list_features`, `get_data_model`, `explain_symbol`, `get_call_graph`, `get_user_stories`, `get_api_endpoints`, `search_code_entities`, `get_security_findings`

**Prompts**: `explain_repo`, `review_code`, `write_tests`, `fix_bug`, `migration_plan`

### Connection

**Local (stdio) — for Claude Code, Cursor, etc.:**

```bash
artifactor mcp --project <project-id>
```

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "artifactor": {
      "command": "uv",
      "args": ["run", "artifactor", "mcp", "--project", "<project-id>"]
    }
  }
}
```

**Docker (SSE) — for remote or containerized access:**

```bash
artifactor mcp --transport sse --host 0.0.0.0 --port 8001
```

Or uncomment the `mcp` service in `docker-compose.yml`. Then configure Claude Code:

```json
{
  "mcpServers": {
    "artifactor": {
      "url": "http://localhost:8001/sse"
    }
  }
}
```

| Flag | Default | Description |
|------|---------|-------------|
| `--transport` | `stdio` | Transport protocol (`stdio` or `sse`) |
| `--host` | `0.0.0.0` | Bind address for SSE transport |
| `--port` | `8001` | Port for SSE transport |
| `--project` | (none) | Default project ID for tools |
| `--db` | (from settings) | Database path override |

---

## Chat & RAG

Ask questions about your analyzed codebase through a hybrid RAG pipeline:

```
POST /api/projects/{id}/chat
{"message": "How does authentication work in this system?"}
```

The chat retrieves context via vector search (LanceDB) and keyword search (SQLite FTS), merges results using Reciprocal Rank Fusion (RRF), then generates a response with inline citations. Responses stream via SSE with thinking indicators.

---

## Playbooks

Five built-in playbooks provide guided workflows for common tasks:

- **explain-repo** — Understand an unfamiliar codebase top-down
- **review-code** — Review a file with full system context
- **write-tests** — Generate BDD test specs from user stories
- **fix-bug** — Diagnose a bug with architecture and data model context
- **migration-plan** — Plan a migration with security and integration awareness

Playbooks are metadata descriptors (YAML) that link to MCP prompts. They guide workflows; they don't execute them.

---

## Section Generators

Artifactor generates 13 documentation sections, each with exclusive ownership over specific data slices:

| Section | Description |
|---------|-------------|
| Executive Overview | What the system does, summarized from the code itself |
| System Overview | Components, modules, dependencies, with Mermaid diagrams |
| Data Models | Tables, schemas, entity relationships with ER diagrams |
| API Specifications | Endpoints, routes, request/response patterns |
| Features | Detected capabilities and functional areas |
| User Stories | Derived from detected workflows and inferred rules |
| Tech Stories | Technical implementation narratives |
| Personas | Inferred user types and their interactions |
| Interfaces | System boundaries and integration points |
| UI Specifications | Frontend component and page analysis |
| Integrations | External service connections and protocols |
| Security Requirements | Auth flows, access control, sensitive data handlers |
| Security Considerations | Vulnerability patterns and risk assessment |

Each generator collects its data slice from the intelligence model, synthesizes via LLM with a section-specific prompt, and validates through quality gates. If synthesis fails, it falls back to deterministic template rendering.

---

## Export Formats

| Format | Command | Notes |
|--------|---------|-------|
| Markdown | `--format markdown` | Default. Clean markdown with citations. |
| HTML | `--format html` | Styled single-file HTML document. |
| PDF | `--format pdf` | Branded PDF with cover page, TOC, page numbers, Mermaid diagrams rendered as SVG. Requires system libraries (see below). |
| JSON | `--format json` | Structured JSON with metadata, confidence scores, and citation objects. |

### PDF System Dependencies

PDF export uses WeasyPrint, which requires Pango:

```bash
# macOS
brew install pango

# Ubuntu/Debian
apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
```

The Docker image includes these dependencies.

### Mermaid Diagrams in PDF

Two sections (System Overview and Data Models) generate Mermaid diagrams. In PDF output, these are pre-rendered to inline SVG via `mmdc` (Mermaid CLI) if available. Without `mmdc`, diagrams appear as styled source code blocks.

```bash
npm install -g @mermaid-js/mermaid-cli   # optional, for PDF diagram rendering
```

---

## Language Support

Artifactor parses 40+ file extensions via tree-sitter. First-class grammar support (with AST-level call graph and dependency extraction) ships for Python, JavaScript, TypeScript, Java, Go, Rust, C, and C++. All other languages get file-level analysis and LLM inference.

---

## Configuration

All settings via environment variables or `.env` file:

```bash
# LLM Provider (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...     # if using Anthropic models

# Model chain (first = primary, rest = fallbacks tried in order)
LITELLM_MODEL_CHAIN="openai/gpt-4.1-mini,openai/gpt-4.0-mini"
LITELLM_EMBEDDING_MODEL=openai/text-embedding-3-small
LLM_MAX_CONCURRENCY=2
LLM_TIMEOUT_SECONDS=60

# Database (optional)
DATABASE_URL=sqlite:///data/artifactor.db
LANCEDB_URI=data/lancedb

# API (optional)
API_KEY=                  # empty = no auth (set this when exposing on a network)
CORS_ORIGINS=http://localhost:3000
```

Models are configured via [litellm](https://docs.litellm.ai/) — any supported provider works (OpenAI, Anthropic, Google, Azure, local Ollama, etc.). The first model in the chain is the primary. If it fails (timeout, circuit breaker, rate limit), the next model is tried automatically.

---

## Project Structure

```
src/artifactor/
  analysis/
    static/       AST parser, call graph, dependency graph, schema extraction, API discovery
    llm/          Embedder, narrator, rule extractor, risk detector, circuit breakers
    quality/      Cross-validation, confidence scoring, guardrails, quality gates
    pipeline.py   Typed PipelineStage[TInput, TOutput] + ParallelGroup
  intelligence/   KnowledgeGraph, ReasoningGraph, value objects (frozen dataclasses)
  outputs/        13 section generators (LLM synthesis + template fallback), synthesizer, section prompts
  diagrams/       Mermaid generators (architecture, ER, call graph, sequence) + renderer
  export/         Markdown, HTML, JSON, PDF (WeasyPrint), Mermaid pre-rendering
  chat/           RAG pipeline (hybrid vector + keyword + RRF merge), conversation management
  api/            FastAPI routes (30 endpoints), SSE streaming, auth middleware
  mcp/            MCP server (10 tools, 5 resources, 5 prompts)
  agent/          pydantic-ai agent with tool bindings
  playbooks/      YAML playbook loader and gallery API
  repositories/   Protocol-based data access (SQLAlchemy 2.0 async)
  models/         SQLAlchemy ORM models
  services/       Analysis orchestrator, project service, data service
  observability/  Event dispatcher, emitters, handlers (console, cost, langsmith, otel)
  ingestion/      Git connector, language detector, code chunker
  config.py       Environment-based settings (pydantic-settings)
  cli.py          CLI entry point
  main.py         FastAPI application factory

frontend/src/
  app/            Next.js App Router pages (projects, docs, chat)
  components/     Layout (header, sidebar), UI components
  hooks/          use-chat.ts, use-project.ts
  types/          TypeScript API types
```

---

## Development

### Quick Start

```bash
git clone https://github.com/agenisea/artifactor.git
cd artifactor
./dev.sh          # Starts backend + frontend together (Ctrl-C to stop both)
```

`dev.sh` checks for prerequisites (`uv`, `pnpm`), installs dependencies, frees stale ports, and launches both servers. Backend runs on port 8000, frontend on port 3000.

### Manual Start

```bash
uv sync                                           # Install Python deps
uv run uvicorn artifactor.main:app --reload        # Backend (port 8000)

cd frontend && pnpm install && pnpm dev            # Frontend (port 3000)
```

### Tests

Tests use demo API keys (`"for-demo-purposes-only"`) — no real LLM calls.

```bash
uv run pytest tests/ -v                            # 619 tests
uv run ruff check src/ tests/                      # Linting
uv run pyright src/                                # Type checking
cd frontend && tsc --noEmit                        # Frontend type checking
```

### Evals

```bash
uv run python -m evals.eval_tools                  # Tier 3: deterministic, no LLM
uv run python -m evals.eval_agent                  # Tier 4: TestModel, no LLM
```

### Pre-Build Gate

All three checks must pass before every commit/PR:

```bash
uv run ruff check src/ tests/                      # Lint — 0 errors
uv run pyright src/                                # Types — 0 errors
uv run pytest tests/ -v                            # Tests — 0 failures
```

### Docker

Docker Compose runs two services — a Python backend (FastAPI) and a Next.js frontend. An optional MCP service can be uncommented for AI agent access via SSE. The frontend proxies all `/api/*` requests to the backend.

#### Quick Start

```bash
docker compose up              # Build + run both services
```

Open `http://localhost:3000` for the UI. The backend API is also directly available at `http://localhost:8000`.

| Service | Port | Description |
|---------|------|-------------|
| `frontend` | 3000 | Next.js UI, proxies `/api/*` to backend |
| `backend` | 8000 | FastAPI REST API + SSE streaming |
| `mcp` | 8001 | MCP server over SSE (optional, commented out by default) |

The frontend waits for the backend health check to pass before starting.

#### With Environment Variables

Create a `.env` file (see `.env.example`) or pass variables directly:

```bash
# Using .env file (docker compose reads it automatically)
cp .env.example .env
# Edit .env with your API keys and settings
docker compose up

# Or pass variables inline
OPENAI_API_KEY=your-key docker compose up
```

#### Data Persistence

Docker Compose mounts two host volumes on the backend:

| Container Path | Host Path | Purpose |
|----------------|-----------|---------|
| `/app/data` | `./data` | SQLite database + LanceDB vector store |
| `/app/logs` | `./logs` | Application logs |

Analyzed projects persist across container restarts.

#### Standalone Docker (backend only, without Compose)

```bash
docker build -t artifactor .
docker run -p 8000:8000 \
  -v ./data:/app/data \
  -v ./logs:/app/logs \
  -e OPENAI_API_KEY=your-key \
  artifactor
```

#### Health Check

Both containers include built-in health checks:

```bash
docker compose ps              # Shows health status for both services
curl http://localhost:8000/api/health
# {"status": "healthy", "version": "0.1.0", ...}
```

---

## Why Artifactor

- **Infrastructure, not a destination** — MCP server, REST API, and playbooks. Not a web viewer you visit — infrastructure you build on.
- **Your code, your Intelligence Model** — runs on your machine, no telemetry, no cloud storage, read-only analysis. Your code never leaves your infrastructure. See [Security Policy](SECURITY.md).
- **Pluggable LLM** — any [litellm-supported provider](https://docs.litellm.ai/) works: OpenAI, Anthropic, Google, Azure, local Ollama. No vendor lock-in.
- **Verified citations** — every claim cites the exact file, function, and line. Dual-path cross-validation (AST + LLM) catches what either path alone would miss.
- **Honest confidence** — every finding carries a confidence score. Low-confidence claims are flagged, not hidden. Artifactor tells you what it doesn't know.
- **Engineering rigor** — 619+ tests across a 4-tier test pyramid, strict type checking, protocol-based architecture, frozen value objects.

---

Built by Patrick Pena, Agenisea™ 🪼
