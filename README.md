[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/navisbio-aact-mcp-badge.png)](https://mseep.ai/app/navisbio-aact-mcp)

# AACT Clinical Trials MCP Server

## Overview
A Model Context Protocol (MCP) server implementation that provides access to the AACT (Aggregate Analysis of ClinicalTrials.gov) database using the FastMCP framework. This server allows AI assistants to directly query clinical trial data from the ClinicalTrials.gov database.

## Features

### Tools

- `list_tables`
   - Get an overview of all available tables in the AACT database
   - Useful for understanding the database structure before analysis

- `describe_table`
   - Examine the detailed structure of a specific AACT table
   - Shows column names and data types
   - Example: `{"table_name": "studies"}`

- `read_query`
   - Execute a SELECT query on the AACT clinical trials database
   - Safely handle SQL queries with validation
   - Example: `{"query": "SELECT nct_id, brief_title FROM ctgov.studies LIMIT 5"}`

- `append_insight`
   - Record key findings and insights discovered during analysis
   - Helps build an analytical narrative
   - Example: `{"finding": "Phase 3 oncology trials have increased by 15% over the last 5 years"}`

### Resources

- `schema://database`
   - Returns the database schema as a JSON resource

- `memo://insights`
   - Returns a formatted memo of insights collected during the session

## Configuration

### Required Environment Variables
- `DB_USER`: Your AACT database username
- `DB_PASSWORD`: Your AACT database password

## Usage with Semantic Kernel

```python
from semantic_kernel import Kernel
from semantic_kernel.connectors.mcp import MCPStdioPlugin

# Create an AACT Clinical Trials MCP plugin
aact_mcp = MCPStdioPlugin(
    name="aact",
    description="Clinical Trials Database Plugin",
    command="uvx",
    args=["mcp-server-aact"],
    env={
        "DB_USER": "your_aact_username", 
        "DB_PASSWORD": "your_aact_password"
    }
)

# Add to Semantic Kernel
kernel = Kernel()
kernel.add_plugin(aact_mcp)
```

## Example Prompts

Here are some example prompts to use with this plugin:

1. "What are the most common types of interventions in breast cancer clinical trials?"
2. "How many phase 3 clinical trials were completed in 2023?"
3. "Show me the enrollment statistics for diabetes trials across different countries"
4. "What percentage of oncology trials have reported results in the last 5 years?"

## Implementation Details

This server is built using:
- FastMCP for the Model Context Protocol implementation
- Python psycopg2 for PostgreSQL database connectivity
- AACT database as the data source for ClinicalTrials.gov information

## License
MIT License

## Contributing
We welcome contributions! Please:
- Open an issue on GitHub
- Start a discussion
- Email: jonas.walheim@navis-bio.com

## Acknowledgements

This project was inspired by and initially based on code from:
- [SQLite MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite)
- [DuckDB MCP Server](https://github.com/ktanaka101/mcp-server-duckdb/tree/main)
- [OpenDataMCP](https://github.com/OpenDataMCP/OpenDataMCP)

Thanks to these awesome projects for showing us the way! 🙌

