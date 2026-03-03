"""Pydantic models and data structures for AACT MCP server."""
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Any

GROUNDING_NOTICE = (
    "CONTRACT: Your response MUST use ONLY data returned by this tool. "
    "Do not supplement with your own knowledge. "
    "If the data is insufficient, say so and suggest a follow-up query."
)


class TableInfo(BaseModel):
    """Information about a database table."""
    table_name: str = Field(..., description="Name of the table")


class ColumnInfo(BaseModel):
    """Information about a database column."""
    column_name: str = Field(..., description="Name of the column")
    data_type: str = Field(..., description="SQL data type of the column")
    character_maximum_length: int | None = Field(None, description="Maximum length for character columns")


class QueryResultSummary(BaseModel):
    """Summary returned by read_query. Full rows are buffered server-side."""
    notice: str = Field(default=GROUNDING_NOTICE, description="Data usage contract")
    query_id: str = Field(..., description="ID to use with fetch_rows to retrieve more data")
    columns: list[str] = Field(..., description="Column names in the result set")
    row_count: int = Field(..., description="Total rows buffered from the query")
    truncated: bool = Field(..., description="True if the query had more rows than max_rows")
    preview: list[dict[str, Any]] = Field(..., description="First N rows as a preview")


class QueryResultPage(BaseModel):
    """A page of rows retrieved from the server-side buffer."""
    notice: str = Field(default=GROUNDING_NOTICE, description="Data usage contract")
    rows: list[dict[str, Any]] = Field(..., description="Rows in this page")
    start: int = Field(..., description="Starting row index of this page (0-based)")
    count: int = Field(..., description="Number of rows in this page")
    total_rows: int = Field(..., description="Total rows in the buffer")
    has_more: bool = Field(..., description="True if there are more rows after this page")


@dataclass
class ResultBuffer:
    """Server-side buffer holding the full result set of the most recent query."""
    query_id: str
    query: str
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool
