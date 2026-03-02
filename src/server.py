import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

from .database import AACTDatabase
from .models import (
    TableInfo,
    ColumnInfo,
    QueryResultSummary,
    QueryResultPage,
    ResultBuffer,
)

logger = logging.getLogger('mcp_aact_server')


@dataclass
class AppContext:
    db: AACTDatabase
    result_buffer: ResultBuffer | None = field(default=None)
    query_counter: int = field(default=0)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle — initialize DB on startup."""
    db = AACTDatabase()
    try:
        yield AppContext(db=db)
    finally:
        logger.info("Server shutting down")


mcp = FastMCP(
    name="AACT Clinical Trials Database",
    instructions="""You are an MCP server providing access to the AACT (Aggregate Analysis of ClinicalTrials.gov) database.

Use the available tools to explore and query the database:
1. list_tables — discover available tables
2. describe_table — examine columns in a specific table
3. read_query — execute a SELECT query; returns a summary with a small preview, buffers full results server-side
4. fetch_rows — retrieve pages of rows from the buffered result using the query_id

Workflow: Use read_query to run your SQL. Review the preview rows. If you need more data,
use fetch_rows with the query_id to page through results without re-executing the query.
If you need different data, run a new read_query (this replaces the buffer).
Use SQL WHERE, LIMIT, and ORDER BY to narrow results before fetching.

CRITICAL: Your answer MUST be based on data received from the AACT database exclusively.
Do not add other data from your own knowledge or make any assumptions.
Everything must be grounded in the data received from the tools.""",
    lifespan=app_lifespan,
)


def _get_ctx(ctx: Context) -> AppContext:
    """Extract AppContext from lifespan context."""
    return ctx.request_context.lifespan_context


@mcp.tool()
async def list_tables(ctx: Context) -> list[TableInfo]:
    """Call this first to discover available tables before writing any queries.
    Returns all table names in the AACT ctgov schema (studies, interventions, outcomes, etc.).
    Use the returned names with describe_table to inspect columns before querying."""
    app = _get_ctx(ctx)
    results, _ = app.db.execute_query("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'ctgov'
        ORDER BY table_name;
    """)
    await ctx.debug(f"Retrieved {len(results)} tables")
    return [TableInfo(table_name=row['table_name']) for row in results]


@mcp.tool()
async def describe_table(
    table_name: Annotated[str, Field(description="Name of the table to describe", min_length=1)],
    ctx: Context,
) -> list[ColumnInfo]:
    """Call this before writing a query to learn the column names and types for a table.
    Returns all columns with their SQL data types. Use the exact column names in your SELECT queries.
    If the table name is invalid, returns an empty list — check list_tables for valid names."""
    app = _get_ctx(ctx)
    results, _ = app.db.execute_query("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'ctgov'
        AND table_name = %s
        ORDER BY ordinal_position;
    """, {"table_name": table_name})

    await ctx.debug(f"Retrieved {len(results)} columns for table {table_name}")
    return [
        ColumnInfo(
            column_name=row['column_name'],
            data_type=row['data_type'],
            character_maximum_length=row.get('character_maximum_length'),
        ) for row in results
    ]


@mcp.tool()
async def read_query(
    query: Annotated[str, Field(description="SELECT SQL query to execute", min_length=1)],
    ctx: Context,
    max_rows: Annotated[int, Field(
        description="Maximum rows to buffer. Use SQL LIMIT for precise control.",
        gt=0, le=5000,
    )] = 100,
    preview_rows: Annotated[int, Field(
        description="Number of rows to return immediately as a preview.",
        gt=0, le=50,
    )] = 5,
) -> QueryResultSummary:
    """Run a SELECT query and get a summary with a small preview of results.
    Full results are buffered server-side — call fetch_rows with the returned query_id
    to page through them without re-executing the query.
    Only SELECT statements are allowed. Use WHERE and LIMIT to narrow results before fetching.
    If truncated is true, the query had more rows than max_rows — add a LIMIT or tighter WHERE."""
    app = _get_ctx(ctx)

    query = query.strip()
    if not query.upper().startswith("SELECT"):
        raise ValueError(
            "Only SELECT queries are allowed. "
            "Rewrite your query to start with SELECT."
        )

    results, truncated = app.db.execute_query(query, row_limit=max_rows)
    row_count = len(results)
    await ctx.debug(f"Query returned {row_count} rows (truncated={truncated})")

    columns = list(results[0].keys()) if results else []

    app.query_counter += 1
    query_id = f"q{app.query_counter}"

    app.result_buffer = ResultBuffer(
        query_id=query_id,
        query=query,
        columns=columns,
        rows=results,
        truncated=truncated,
    )

    return QueryResultSummary(
        query_id=query_id,
        columns=columns,
        row_count=row_count,
        truncated=truncated,
        preview=results[:preview_rows],
    )


@mcp.tool()
async def fetch_rows(
    query_id: Annotated[str, Field(description="query_id from a previous read_query result")],
    ctx: Context,
    start: Annotated[int, Field(
        description="Row index to start from (0-based)",
        ge=0,
    )] = 0,
    count: Annotated[int, Field(
        description="Number of rows to fetch",
        gt=0, le=100,
    )] = 25,
) -> QueryResultPage:
    """Retrieve a page of rows from the buffered result of the most recent read_query.
    No database round-trip — reads from server memory. Use the query_id from read_query.
    If has_more is true, call again with start incremented by count for the next page.
    If the buffer was replaced by a newer read_query, re-run read_query to get a fresh query_id."""
    app = _get_ctx(ctx)
    buf = app.result_buffer

    if buf is None:
        raise ValueError(
            "No buffered query result. Call read_query first to execute a query."
        )
    if buf.query_id != query_id:
        raise ValueError(
            f"query_id '{query_id}' is stale — the buffer now holds '{buf.query_id}'. "
            "Call read_query again to re-execute your query and get a new query_id."
        )

    page = buf.rows[start:start + count]

    return QueryResultPage(
        rows=page,
        start=start,
        count=len(page),
        total_rows=len(buf.rows),
        has_more=(start + count) < len(buf.rows),
    )


def main():
    """Main entry point for the server."""
    load_dotenv()
    try:
        mcp.run()
    except Exception as e:
        logger.exception("Server error")
        raise


if __name__ == "__main__":
    main()
