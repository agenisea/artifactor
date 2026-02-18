# Contributing to Artifactor

Thanks for your interest in contributing. This guide covers the development workflow, testing, and code standards.

## Getting Started

```bash
git clone https://github.com/agenisea/artifactor.git
cd artifactor
uv sync                             # Python dependencies
cd frontend && pnpm install && cd .. # Frontend dependencies
```

## Development Workflow

### One-Command Start

```bash
./dev.sh    # Installs deps, starts backend (8000) + frontend (3000), Ctrl-C to stop
```

### Manual Start

```bash
uv run uvicorn artifactor.main:app --reload    # Backend
cd frontend && pnpm dev                         # Frontend (separate terminal)
```

## Running Tests

Tests use demo API keys — no real LLM calls required.

```bash
uv run pytest tests/ -v              # 580 tests
uv run ruff check src/ tests/        # Linting
uv run pyright src/                  # Type checking (strict mode)
cd frontend && tsc --noEmit          # Frontend type checking
```

### Evals

```bash
uv run python -m evals.eval_tools    # Tier 3: deterministic, no LLM
uv run python -m evals.eval_agent    # Tier 4: TestModel, no LLM
```

## Pre-Build Gate

All three checks must pass before every commit/PR. A change is not done until all three are green:

```bash
uv run ruff check src/ tests/        # Lint — 0 errors
uv run pyright src/                  # Types — 0 errors, 0 warnings
uv run pytest tests/ -v              # Tests — 0 failures
```

## Code Style

- **Line length:** 88 (enforced by Ruff)
- **Python target:** 3.12
- **Ruff rules:** E, F, I, UP, B, SIM
- **Type checking:** Pyright strict mode
- **Imports:** Absolute imports only (`from artifactor.analysis.quality.scorer import ...`)
- **Async:** `asyncio_mode = "auto"` in pytest
- **Value objects:** Frozen dataclasses (`@dataclass(frozen=True)`)

## Pull Requests

1. Fork the repo and create a feature branch
2. Make your changes
3. Run the pre-build gate (all three checks)
4. Submit a PR against `main`
5. Keep PRs focused — one feature or fix per PR

## Areas for Contribution

- New tree-sitter grammars for first-class language support
- Additional section generators
- Export format improvements
- Frontend components and pages
- Documentation and examples
- Bug fixes and test coverage

## Questions

Open an issue on GitHub for questions, bug reports, or feature suggestions.
