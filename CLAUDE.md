# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DPM (Dependency-aware Project Management) is a research project for a voice-controlled UI for project management. It provides hierarchical task management with dependency tracking (blockers), multi-domain support, and a kanban board interface.

## Commands

```bash
# Run all tests (includes coverage)
pytest tests

# Run a single test file
pytest tests/test_models.py

# Run a single test
pytest tests/test_models.py::test_task_crud_1

# Run with debugger on failure
pytest tests --pdb

# Type checking
pyright src/

# Run standalone server
uvicorn dpm.fastapi.server:app
```

Package management uses **uv**. Build system is **hatchling**.

## Architecture

### Dual-mode FastAPI structure (important)

The FastAPI components are split into `dpm/` and `standalone/` under `src/dpm/fastapi/`. This is intentional — the `dpm/` routers (API + UI) are designed to be embedded as a component in a larger FastAPI application alongside other components. The `standalone/` routers provide the home page and base templates only needed when DPM runs as its own server. `DPMServer` in `server.py` wires both together for standalone use.

The `ServerOps` protocol in `ops.py` defines the interface that routers expect from their host server (currently just `templates: Jinja2Blocks`). This allows the dpm routers to work with any server that satisfies the protocol.

### Store layer: Models → Wrappers → Domains

Three tiers in `src/dpm/store/`:

1. **`models.py`** — SQLModel definitions: `Project`, `Phase`, `Task`, `Blocker`. SQLite with `PRAGMA foreign_keys=ON`. All names have a `name_lower` field for case-insensitive uniqueness.

2. **`wrappers.py`** — Business logic wrappers: `ProjectRecord`, `PhaseRecord`, `TaskRecord`, `ModelDB`. Wrappers hold a reference to `ModelDB` and their underlying model. `ModelDB` is the main CRUD interface — it manages the SQLAlchemy engine/session and provides all query methods. Phases use a linked-list ordering pattern (`follows`/`follower`).

3. **`domains.py`** — Multi-domain management: `DomainCatalog` loads a JSON config pointing to multiple independent SQLite databases (one `ModelDB` per domain). `DPMManager` sits on top, tracking "last accessed" domain/project/phase/task and persisting this state to `.dpm_state.json`.

### Software taxonomy overlay

`sw_models.py` and `sw_wrappers.py` define an overlay that maps software engineering terminology onto the generic model:

- Vision → Project, Subsystem → Project (hierarchical), Deliverable → Project
- Epic → Project (with `GuardrailType`), Story → Phase, SWTask → Task
- `GuardrailType` enum: PRODUCTION, MVP, PROTOTYPE, POC, STUDY, RESEARCH
- `DomainMode.SOFTWARE` activates this overlay for a domain
- `SWModelDB` wraps `ModelDB` and adds the SW-specific creation methods

### REST API (`fastapi/dpm/api_router.py`)

`PMDBAPIService` provides domain-scoped CRUD endpoints under `/api/{domain}/`. Uses Pydantic models (`ProjectCreate`, `TaskUpdate`, etc.) for request validation. Supports project/phase/task CRUD plus blocker dependency management.

### UI (`fastapi/dpm/ui_router.py`)

`PMDBUIRouter` serves HTMX-driven HTML using Jinja2 templates with `jinja2-fragments` for partial page updates. Tailwind CSS + daisyUI for styling. Kanban board with drag-and-drop task movement between phases/statuses.

## Test Patterns

Tests use `tmp_path` fixtures for isolated SQLite databases. API tests create a `DPMServer` with a temporary config and use FastAPI's `TestClient`. The `conftest.py` configures `ipdb` as the default debugger for `breakpoint()` and `--pdb`.

Async mode is set to `auto` in pytest.ini (`asyncio_mode = auto`).

## Key Dependencies

- Python >= 3.12
- FastAPI, SQLModel (SQLAlchemy + Pydantic), Jinja2 + jinja2-fragments
- Dev: pytest, pytest-asyncio, pytest-cov, httpx, ipdb
