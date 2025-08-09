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
   - Example: `{"query": "SELECT nct_id, brief_title FROM ctgov.studies LIMIT 5", "max_rows": 50}`

## Configuration

### Database Access
1. Create a free account at https://aact.ctti-clinicaltrials.org/users/sign_up
2. Set environment variables:
   - `DB_USER`: AACT database username
   - `DB_PASSWORD`: AACT database password

## Usage with Claude Desktop

Note that you need Claude Desktop and a Claude subscription at the moment. 

Add one of the following configurations to the file claude_desktop_config.json. (On macOS, the file is located at /Users/YOUR_USERNAME/Library/Application Support/Claude/claude_desktop_config.json and you will need to create it yourself if it does not exist yet).

### Option 1: Using the published package
```json
{
"mcpServers": {
    "CTGOV-MCP": {
      "command": "uvx",
      "args": [
        "mcp-server-aact"
      ],
      "env": {
        "DB_USER": "USERNAME",
        "DB_PASSWORD": "PASSWORD"
      }
    }
}
}
```

### Option 2: Running from source (development)
```json
{
"mcpServers": {
    "CTGOV-MCP-DEV": {
      "command": "uv",
      "args": [
        "--directory",
        "PATH_TO_REPOSITORY",
        "run",
        "mcp-server-aact"
      ],
      "env": {
        "DB_USER": "USERNAME",
        "DB_PASSWORD": "PASSWORD"
      }
    }
}
}
```

## Example Prompts

Here are some example prompts to use with this plugin:

1. "What are the most common types of interventions in breast cancer clinical trials?"
2. "How many phase 3 clinical trials were completed in 2023?"
3. "Show me the enrollment statistics for diabetes trials across different countries"
4. "What percentage of oncology trials have reported results in the last 5 years?"

## Troubleshooting

### `spawn uvx ENOENT` Error

This error has been reported when the system cannot find the `uvx` command which might happen when `uvx` is installed in a non-standard location (like `~/.local/bin/`).

**Potential Solution:** Update your configuration with the full path. For example:

```json
{
"mcpServers": {
    "CTGOV-MCP": {
      "command": "/Users/username/.local/bin/uvx",
      "args": [
        "mcp-server-aact"
      ],
      "env": {
        "DB_USER": "USERNAME",
        "DB_PASSWORD": "PASSWORD"
      }
    }
}
}
```



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

