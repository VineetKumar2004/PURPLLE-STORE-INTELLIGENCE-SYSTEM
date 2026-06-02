"""
Database module — SQLite with WAL mode for concurrent reads during pipeline writes.

Tables:
  events         — raw entry/exit/anomaly events from the CV pipeline
  metrics_cache  — pre-computed JSON metrics for fast API reads
  pipeline_status — single-row status tracker
"""
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection(db_path: str) -> sqlite3.Connection:
    """Return a connection with WAL journal and row-factory enabled."""
    conn = sqlite3.connect(db_path, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    """Create tables if they don't exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT    NOT NULL,
            track_id    INTEGER,
            timestamp   TEXT    NOT NULL,
            frame_number INTEGER,
            x           REAL,
            y           REAL,
            is_staff    INTEGER DEFAULT 0,
            zone        TEXT,
            meta        TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics_cache (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            computed_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_status (
            id          INTEGER PRIMARY KEY,
            status      TEXT NOT NULL,
            data_source TEXT,
            started_at  TEXT,
            finished_at TEXT,
            error_msg   TEXT
        )
    """)

    # Seed pipeline_status if empty
    cursor.execute("SELECT COUNT(*) FROM pipeline_status")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO pipeline_status (id, status) VALUES (1, 'pending')"
        )

    conn.commit()
    conn.close()
    logger.debug(f"Database initialised at {db_path}")


# ---------------------------------------------------------------------------
# Pipeline status
# ---------------------------------------------------------------------------

def get_pipeline_status(conn: sqlite3.Connection) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM pipeline_status WHERE id = 1").fetchone()
    if row is None:
        return {"status": "pending", "data_source": None,
                "started_at": None, "finished_at": None, "error_msg": None}
    return dict(row)


def update_pipeline_status(
    conn: sqlite3.Connection,
    status: str,
    data_source: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    error_msg: Optional[str] = None,
) -> None:
    conn.execute("""
        UPDATE pipeline_status
        SET status = ?, data_source = ?, started_at = ?,
            finished_at = ?, error_msg = ?
        WHERE id = 1
    """, (status, data_source, started_at, finished_at, error_msg))
    conn.commit()


# ---------------------------------------------------------------------------
# Metrics cache
# ---------------------------------------------------------------------------

def set_cache_metric(conn: sqlite3.Connection, key: str, value: Any) -> None:
    """Upsert a metric into the cache as JSON."""
    conn.execute("""
        INSERT INTO metrics_cache (key, value, computed_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value, computed_at = excluded.computed_at
    """, (key, json.dumps(value), datetime.now().isoformat()))
    conn.commit()


def get_cache_metric(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    """Read a metric from the cache, returning *default* if missing."""
    row = conn.execute(
        "SELECT value FROM metrics_cache WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return default
