import logging
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context
from .database import AACTDatabase
from .models import TableInfo, ColumnInfo, QueryResult

# Load environment variables once at startup
load_dotenv()

# Setup logging
logger = logging.getLogger('mcp_aact_server')
logger.setLevel(logging.DEBUG)

# Create database instance
db = AACTDatabase()

# Create an MCP server with enhanced configuration
mcp = FastMCP(
    name="AACT Clinical Trials Database",
    instructions="""You are an MCP server providing access to the AACT (Aggregate Analysis of ClinicalTrials.gov) database.

This server enables querying and analysis of clinical trial data from ClinicalTrials.gov.
Use the available tools to:
1. First explore the database structure with list_tables
2. Examine specific tables with describe_table
3. Query data using read_query (SELECT statements only)

The database contains comprehensive clinical trial information including studies, outcomes, 
interventions, sponsors, and more. Always validate table and column names before querying.

CRITICAL: If you use this tool, your answer MUST be based on data received from the AACT database exclusively. 
Do not add other data from your own knowledge or make any assumptions. 
Everything must be grounded in the data received from the tool."""
)

@mcp.tool()
async def list_tables(ctx: Context) -> list[TableInfo]:
    """Get an overview of all available tables in the AACT database. 
    This tool helps you understand the database structure before starting your analysis 
    to identify relevant data sources."""
    try:
        await ctx.info("Fetching AACT database tables...")
        results = db.execute_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'ctgov'
            ORDER BY table_name;
        """)
        await ctx.debug(f"Retrieved {len(results)} tables")
        return [TableInfo(table_name=row['table_name']) for row in results]
    except Exception as e:
        await ctx.error(f"Failed to list tables: {str(e)}")
        raise

@mcp.tool()
async def describe_table(table_name: str, ctx: Context) -> list[ColumnInfo]:
    """Examine the detailed structure of a specific AACT table, including column names and data types.
    Use this before querying to ensure you target the right columns and understand the data format."""
    if not table_name:
        raise ValueError("Missing table_name argument")
    
    try:
        await ctx.info(f"Examining structure of table: {table_name}")
        results = db.execute_query("""
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
                character_maximum_length=row['character_maximum_length'] if 'character_maximum_length' in row else None
            ) for row in results
        ]
    except Exception as e:
        await ctx.error(f"Failed to describe table {table_name}: {str(e)}")
        raise

@mcp.tool()
async def read_query(query: str, ctx: Context, max_rows: int = 25) -> QueryResult:
    """Execute a SELECT query on the AACT clinical trials database. 
    Use this tool to extract and analyze specific data from any table.
    
    Parameters:
    - query: The SQL query to execute (must be a SELECT statement)
    - max_rows: Maximum number of rows to return (default: 25). Increase this value if you need more data."""
    if not query:
        raise ValueError("Missing query argument")
    
    # Simple validation to prevent destructive queries
    query = query.strip()
    if not query.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")
    
    try:
        await ctx.info(f"Executing query (max {max_rows} rows)...")
        results = db.execute_query(query, row_limit=max_rows)
        row_count = len(results)
        await ctx.debug(f"Query returned {row_count} rows")
        
        # Report progress if large result set
        if row_count > 10:
            await ctx.report_progress(
                progress=1.0,
                total=1.0,
                message=f"Retrieved {row_count} rows"
            )
        
        return QueryResult(
            rows=results,
            row_count=row_count,
            truncated=(row_count >= max_rows)
        )
    except Exception as e:
        await ctx.error(f"Query execution failed: {str(e)}")
        raise

def main():
    """Main entry point for the server"""
    try:
        # Will shut down gracefully
        mcp.run()
    except Exception as e:
        logger.exception("Server error")
        raise

if __name__ == "__main__":
    main()