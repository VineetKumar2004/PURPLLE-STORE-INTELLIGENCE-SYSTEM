"""
Event data-class and bulk-insert helpers.
"""
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class Event:
    """A single telemetry event (entry, exit, or anomaly)."""
    event_type: str
    track_id: Optional[int] = None
    timestamp: str = ""
    frame_number: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    zone: Optional[str] = None
    is_staff: int = 0
    meta: Optional[Dict[str, Any]] = field(default_factory=dict)


def insert_event(conn: sqlite3.Connection, event: Event) -> None:
    """Insert a single event."""
    conn.execute("""
        INSERT INTO events (event_type, track_id, timestamp, frame_number,
                            x, y, is_staff, zone, meta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event.event_type, event.track_id, event.timestamp,
        event.frame_number, event.x, event.y, event.is_staff,
        event.zone, json.dumps(event.meta) if event.meta else None,
    ))
    conn.commit()


def insert_events_bulk(conn: sqlite3.Connection, events: List[Event]) -> None:
    """Batch-insert events for performance."""
    rows = [
        (e.event_type, e.track_id, e.timestamp, e.frame_number,
         e.x, e.y, e.is_staff, e.zone,
         json.dumps(e.meta) if e.meta else None)
        for e in events
    ]
    conn.executemany("""
        INSERT INTO events (event_type, track_id, timestamp, frame_number,
                            x, y, is_staff, zone, meta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()


def retroactively_mark_staff(
    conn: sqlite3.Connection, staff_ids: Set[int]
) -> None:
    """Update is_staff=1 for all events belonging to identified staff track IDs."""
    if not staff_ids:
        return
    placeholders = ",".join("?" for _ in staff_ids)
    conn.execute(
        f"UPDATE events SET is_staff = 1 WHERE track_id IN ({placeholders})",
        list(staff_ids),
    )
    conn.commit()
