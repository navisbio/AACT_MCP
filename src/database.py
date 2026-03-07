import logging
import os
from contextlib import closing
from typing import Any
import psycopg2
import psycopg2.extras

logger = logging.getLogger('mcp_aact_server.database')

ALLOWED_READ_PREFIXES = ("SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE")


def _strip_leading_comments(sql: str) -> str:
    """Strip leading SQL comments (-- and /* */) to expose the real statement prefix."""
    s = sql.strip()
    while True:
        if s.startswith("--"):
            newline = s.find("\n")
            s = s[newline + 1:].strip() if newline != -1 else ""
        elif s.startswith("/*"):
            end = s.find("*/")
            s = s[end + 2:].strip() if end != -1 else ""
        else:
            break
    return s


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
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError("Connection test query returned no results")
                db, schema = result
                logger.info(f"Connected to database: {db}, current schema: {schema}")

    def _get_connection(self):
        """Create a new independent database connection.

        Each call returns a fresh connection, so concurrent tool calls are safe
        and will not interfere with each other.
        """
        logger.debug("Creating new database connection")
        return psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password
        )

    def execute_query(
        self, query: str, params: dict[str, Any] | None = None, row_limit: int | None = None
    ) -> tuple[list[dict[str, Any]], bool]:
        """Execute a read-only query and return (rows, truncated).

        Fetches row_limit + 1 rows to accurately detect whether more data exists.
        Returns at most row_limit rows; truncated is True if extra rows were available.
        """
        truncated_query = (query[:200] + "...") if len(query) > 200 else query
        logger.debug(f"Executing query: {truncated_query.strip()}")
        if row_limit:
            logger.debug(f"Row limit: {row_limit}")

        with closing(self._get_connection()) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                try:
                    if params:
                        cur.execute(query, list(params.values()))
                    else:
                        cur.execute(query)
                except psycopg2.Error as e:
                    conn.rollback()
                    raise ValueError(f"Database error ({e.pgcode}): {e.pgerror or e}") from e
                if _strip_leading_comments(query).upper().startswith(ALLOWED_READ_PREFIXES):
                    if row_limit:
                        results = cur.fetchmany(row_limit + 1)
                        truncated = len(results) > row_limit
                        if truncated:
                            results = results[:row_limit]
                    else:
                        results = cur.fetchall()
                        truncated = False
                    logger.debug(f"Query returned {len(results)} rows (truncated={truncated})")
                    return [dict(row) for row in results], truncated
                else:
                    conn.rollback()
                    logger.warning("Attempted write operation. Rolling back.")
                    raise ValueError("Only read operations are allowed")