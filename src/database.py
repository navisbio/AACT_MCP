import logging
import os
from contextlib import closing
from typing import Any
import psycopg2
import psycopg2.extras

logger = logging.getLogger('mcp_aact_server.database')

class AACTDatabase:
    def __init__(self):
        logger.info("Initializing AACT database connection")
        
        # Fail-hard policy: No defaults, immediate failure if config missing
        if "DB_USER" not in os.environ:
            raise ValueError("Missing required environment variable: DB_USER")
        if "DB_PASSWORD" not in os.environ:
            raise ValueError("Missing required environment variable: DB_PASSWORD")
            
        self.user = os.environ["DB_USER"]
        self.password = os.environ["DB_PASSWORD"]
        self.host = "aact-db.ctti-clinicaltrials.org"
        self.database = "aact"
        self._test_connection()
        logger.info("AACT database initialization complete")

    def _test_connection(self):
        logger.debug("Testing database connection to AACT")
        with closing(self._get_connection()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_schema;")
                db, schema = cur.fetchone()
                logger.info(f"Connected to database: {db}, current schema: {schema}")

    def _get_connection(self):
        logger.debug("Creating new database connection")
        return psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password
        )

    def execute_query(self, query: str, params: dict[str, Any] | None = None, row_limit: int | None = None) -> list[dict[str, Any]]:
        logger.debug(f"Executing query: {query}")
        if params:
            logger.debug(f"Query parameters: {params}")
        if row_limit:
            logger.debug(f"Row limit: {row_limit}")
            
        with closing(self._get_connection()) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                if params:
                    cur.execute(query, list(params.values()))
                else:
                    cur.execute(query)
                if query.strip().upper().startswith(("SELECT", "SHOW", "DESCRIBE")):
                    if row_limit:
                        results = cur.fetchmany(row_limit)
                    else:
                        results = cur.fetchall()
                    logger.debug(f"Query returned {len(results)} rows")
                    return [dict(row) for row in results]
                else:
                    conn.rollback()
                    logger.warning("Attempted write operation. Rolling back.")
                    return [{"message": "Only read operations are allowed"}]