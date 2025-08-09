"""Pydantic models for structured output in AACT MCP server."""
from pydantic import BaseModel, Field
from typing import Any


class TableInfo(BaseModel):
    """Information about a database table."""
    table_name: str = Field(..., description="Name of the table")
    
    
class ColumnInfo(BaseModel):
    """Information about a database column."""
    column_name: str = Field(..., description="Name of the column")
    data_type: str = Field(..., description="SQL data type of the column")
    character_maximum_length: int | None = Field(None, description="Maximum length for character columns")


class QueryResult(BaseModel):
    """Result from a database query."""
    rows: list[dict[str, Any]] = Field(..., description="Query result rows")
    row_count: int = Field(..., description="Number of rows returned")
    truncated: bool = Field(..., description="Whether results were truncated due to row limit")