import json
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras
from contextlib import closing
import os

def get_db_connection():
    """Create database connection using environment variables"""
    load_dotenv()
    
    if "DB_USER" not in os.environ:
        raise ValueError("Missing required environment variable: DB_USER")
    if "DB_PASSWORD" not in os.environ:
        raise ValueError("Missing required environment variable: DB_PASSWORD")
    
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    
    return psycopg2.connect(
        host="aact-db.ctti-clinicaltrials.org",
        database="aact",
        user=user,
        password=password
    )

def get_schema_info() -> dict[str, Any]:
    """Query and structure the database schema information - simplified version"""
    with closing(get_db_connection()) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Get all tables and their columns, but only the names
            cur.execute("""
                SELECT 
                    table_name,
                    array_agg(column_name ORDER BY ordinal_position) as columns
                FROM information_schema.columns
                WHERE table_schema = 'ctgov'
                GROUP BY table_name
                ORDER BY table_name;
            """)
            
            tables = {
                row['table_name']: row['columns']
                for row in cur.fetchall()
            }
            
            return {
                "schema_version": "1.0",
                "database": "aact",
                "tables": tables
            }

def main():
    resource_dir = Path(__file__).parent.parent / "src" / "resources"
    resource_dir.mkdir(parents=True, exist_ok=True)
    
    schema = get_schema_info()
    schema_file = resource_dir / "database_schema.json"
    
    with open(schema_file, 'w') as f:
        json.dump(schema, f, indent=2)
    
    print(f"Schema generated and saved to {schema_file}")

if __name__ == "__main__":
    main() 