# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP (Model Context Protocol) server that gives AI assistants read-only access to the AACT clinical trials database (ClinicalTrials.gov). It exposes three tools: `list_tables`, `describe_table`, and `read_query` over the FastMCP framework, connecting to a remote PostgreSQL database.

## Commands

```bash
# Run the server
uv run mcp-server-aact

# Run tests
uv run pytest

# Type checking
uv run pyright src/

# Install dependencies (including dev)
uv sync

# Docker build and run
docker build -t mcp-server-aact .
docker run --rm -i --env DB_USER=X --env DB_PASSWORD=Y mcp-server-aact
```

## Architecture

Three source files in `src/`, each with a single responsibility:

- **server.py** — FastMCP server definition and tool handlers. Loads `.env` at startup, creates the `AACTDatabase` instance and the `FastMCP` app. All tool handlers are async and use `Context` for structured logging/progress.
- **database.py** — `AACTDatabase` class wrapping psycopg2. Connects to `aact-db.ctti-clinicaltrials.org`, schema `ctgov`. Validates that queries are SELECT/SHOW/DESCRIBE only and enforces row limits. Fails hard if `DB_USER`/`DB_PASSWORD` env vars are missing.
- **models.py** — Pydantic models (`TableInfo`, `ColumnInfo`, `QueryResult`) used as tool return types.

Entry point: `src/__init__.py` exports `main()` which calls `mcp.run()`.

## Key Design Decisions

- **Read-only enforcement**: Query validation in both `server.py` (SELECT prefix check) and `database.py` (additional validation + rollback after every query).
- **Fail-hard**: No silent defaults for missing config. Missing credentials raise immediately.
- **Row limiting**: Default 25 rows per query, configurable via `max_rows` parameter.
- **Remote database**: Connects directly to AACT's hosted PostgreSQL — no local DB setup needed. Users register at https://aact.ctti-clinicaltrials.org for credentials.

## Environment Variables

Required in `.env` or environment:
- `DB_USER` — AACT database username
- `DB_PASSWORD` — AACT database password
