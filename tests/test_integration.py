"""Integration tests for the AACT MCP server.

These tests exercise the full tool chain against the live AACT database,
verifying real user stories end-to-end through the MCP protocol.

Requires: DB_USER and DB_PASSWORD environment variables (or .env file).
"""
import json
import pytest
from tests.conftest import parse_tool_result


# ---------------------------------------------------------------------------
# Story 1: Discover the database structure
# ---------------------------------------------------------------------------

class TestDatabaseDiscovery:
    """A user explores the database to understand what tables and columns exist."""

    async def test_list_tables_returns_known_tables(self, client):
        """The AACT database should contain well-known tables like 'studies'."""
        result = await client.call_tool("list_tables", {})
        tables = parse_tool_result(result)
        table_names = [t["table_name"] for t in tables]

        assert len(table_names) > 10, "AACT should have many tables"
        assert "studies" in table_names
        assert "sponsors" in table_names
        assert "interventions" in table_names

    async def test_describe_table_returns_columns(self, client):
        """Describing 'studies' should return columns with type information."""
        result = await client.call_tool("describe_table", {"table_name": "studies"})
        columns = parse_tool_result(result)
        col_names = [c["column_name"] for c in columns]

        assert len(col_names) > 5, "studies table should have many columns"
        assert "nct_id" in col_names
        assert "brief_title" in col_names

        # Each column should have type info
        for col in columns:
            assert "data_type" in col
            assert isinstance(col["data_type"], str)

    async def test_describe_nonexistent_table_returns_empty(self, client):
        """Describing a table that doesn't exist should return an empty list."""
        result = await client.call_tool(
            "describe_table", {"table_name": "this_table_does_not_exist_xyz"}
        )
        columns = parse_tool_result(result)
        assert columns == []


# ---------------------------------------------------------------------------
# Story 2: Query data with preview and pagination
# ---------------------------------------------------------------------------

class TestQueryAndPagination:
    """A user runs a query, gets a preview, then pages through results."""

    async def test_read_query_returns_summary_with_preview(self, client):
        """read_query should return a summary with query_id, columns, and preview rows."""
        result = await client.call_tool("read_query", {
            "query": "SELECT nct_id, brief_title FROM ctgov.studies LIMIT 20",
            "max_rows": 100,
            "preview_rows": 3,
        })
        summary = parse_tool_result(result)[0]

        assert "query_id" in summary
        assert summary["query_id"].startswith("q")
        assert "nct_id" in summary["columns"]
        assert "brief_title" in summary["columns"]
        assert summary["row_count"] == 20
        assert summary["truncated"] is False
        assert len(summary["preview"]) == 3

    async def test_fetch_rows_retrieves_pages_from_buffer(self, client):
        """After read_query, fetch_rows should return pages without re-querying."""
        # Run the query
        result = await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.studies LIMIT 50",
            "max_rows": 100,
            "preview_rows": 2,
        })
        summary = parse_tool_result(result)[0]
        query_id = summary["query_id"]
        assert summary["row_count"] == 50

        # Fetch first page
        page1 = await client.call_tool("fetch_rows", {
            "query_id": query_id, "start": 0, "count": 10,
        })
        page1_data = parse_tool_result(page1)[0]
        assert page1_data["count"] == 10
        assert page1_data["start"] == 0
        assert page1_data["total_rows"] == 50
        assert page1_data["has_more"] is True
        assert len(page1_data["rows"]) == 10

        # Fetch second page
        page2 = await client.call_tool("fetch_rows", {
            "query_id": query_id, "start": 10, "count": 10,
        })
        page2_data = parse_tool_result(page2)[0]
        assert page2_data["start"] == 10
        assert page2_data["has_more"] is True

        # Rows should be different between pages
        page1_ids = [r["nct_id"] for r in page1_data["rows"]]
        page2_ids = [r["nct_id"] for r in page2_data["rows"]]
        assert page1_ids != page2_ids

    async def test_fetch_rows_last_page_has_more_false(self, client):
        """The last page of results should have has_more=False."""
        result = await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.studies LIMIT 10",
            "max_rows": 100,
            "preview_rows": 2,
        })
        summary = parse_tool_result(result)[0]
        query_id = summary["query_id"]

        # Fetch beyond the end
        page = await client.call_tool("fetch_rows", {
            "query_id": query_id, "start": 0, "count": 100,
        })
        page_data = parse_tool_result(page)[0]
        assert page_data["count"] == 10
        assert page_data["has_more"] is False

    async def test_preview_rows_is_subset_of_full_result(self, client):
        """Preview rows should match the first rows you'd get from fetch_rows."""
        result = await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.studies ORDER BY nct_id LIMIT 20",
            "max_rows": 100,
            "preview_rows": 5,
        })
        summary = parse_tool_result(result)[0]
        query_id = summary["query_id"]
        preview_ids = [r["nct_id"] for r in summary["preview"]]

        # Fetch the same first 5 rows via fetch_rows
        page = await client.call_tool("fetch_rows", {
            "query_id": query_id, "start": 0, "count": 5,
        })
        page_data = parse_tool_result(page)[0]
        fetched_ids = [r["nct_id"] for r in page_data["rows"]]

        assert preview_ids == fetched_ids


# ---------------------------------------------------------------------------
# Story 3: Truncation detection
# ---------------------------------------------------------------------------

class TestTruncation:
    """A user runs a query that exceeds the buffer limit."""

    async def test_truncated_flag_when_more_rows_exist(self, client):
        """When the query has more rows than max_rows, truncated should be True."""
        result = await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.studies LIMIT 20",
            "max_rows": 5,
            "preview_rows": 2,
        })
        summary = parse_tool_result(result)[0]
        assert summary["truncated"] is True
        assert summary["row_count"] == 5  # capped at max_rows

    async def test_not_truncated_when_all_rows_fit(self, client):
        """When all rows fit in max_rows, truncated should be False."""
        result = await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.studies LIMIT 3",
            "max_rows": 100,
            "preview_rows": 2,
        })
        summary = parse_tool_result(result)[0]
        assert summary["truncated"] is False
        assert summary["row_count"] == 3


# ---------------------------------------------------------------------------
# Story 4: Buffer replacement and stale query_id
# ---------------------------------------------------------------------------

class TestBufferManagement:
    """When a new query runs, the old buffer is replaced."""

    async def test_new_query_replaces_buffer(self, client):
        """Running a second read_query should produce a new query_id."""
        r1 = await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.studies LIMIT 5",
        })
        q1 = parse_tool_result(r1)[0]["query_id"]

        r2 = await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.sponsors LIMIT 5",
        })
        q2 = parse_tool_result(r2)[0]["query_id"]

        assert q1 != q2

    async def test_stale_query_id_raises_error(self, client):
        """Using an old query_id after running a new query should fail."""
        r1 = await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.studies LIMIT 5",
        })
        old_id = parse_tool_result(r1)[0]["query_id"]

        # Run a new query, replacing the buffer
        await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.sponsors LIMIT 5",
        })

        # Try to fetch with the old query_id
        result = await client.call_tool("fetch_rows", {
            "query_id": old_id, "start": 0, "count": 5,
        })
        # MCP returns errors as isError=True content, not exceptions
        assert result.isError is True

    async def test_fetch_rows_without_prior_query_raises_error(self, client):
        """Calling fetch_rows before any read_query should fail."""
        # Use a fresh client — no prior queries
        result = await client.call_tool("fetch_rows", {
            "query_id": "q999", "start": 0, "count": 5,
        })
        assert result.isError is True


# ---------------------------------------------------------------------------
# Story 5: SQL validation (read-only enforcement)
# ---------------------------------------------------------------------------

class TestReadOnlyEnforcement:
    """The server must reject non-SELECT queries."""

    async def test_rejects_insert_query(self, client):
        """INSERT queries should be rejected."""
        result = await client.call_tool("read_query", {
            "query": "INSERT INTO studies (nct_id) VALUES ('test')",
        })
        assert result.isError is True

    async def test_rejects_delete_query(self, client):
        """DELETE queries should be rejected."""
        result = await client.call_tool("read_query", {
            "query": "DELETE FROM studies",
        })
        assert result.isError is True

    async def test_rejects_drop_query(self, client):
        """DROP queries should be rejected."""
        result = await client.call_tool("read_query", {
            "query": "DROP TABLE studies",
        })
        assert result.isError is True


# ---------------------------------------------------------------------------
# Story 6: Empty results
# ---------------------------------------------------------------------------

class TestEmptyResults:
    """Queries that return no rows should be handled gracefully."""

    async def test_empty_query_result(self, client):
        """A query matching nothing should return 0 rows and empty preview."""
        result = await client.call_tool("read_query", {
            "query": "SELECT nct_id FROM ctgov.studies WHERE nct_id = 'NONEXISTENT_ID_XYZ'",
        })
        summary = parse_tool_result(result)[0]
        assert summary["row_count"] == 0
        assert summary["preview"] == []
        assert summary["columns"] == []
        assert summary["truncated"] is False
