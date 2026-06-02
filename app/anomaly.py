"""
Anomaly detector — evaluates operational risk rules against the events
table and inserts anomaly events.
"""
import json
import sqlite3
from datetime import datetime

from loguru import logger
from app.events import Event, insert_event


def run_anomaly_detection(
    conn: sqlite3.Connection,
    data_source: str,
    conversion_rate: float,
) -> int:
    """
    Evaluate anomaly rules and insert flagged events.
    Returns the number of anomalies detected.
    """
    cursor = conn.cursor()
    anomalies_inserted = 0

    # Clear previous anomaly events to avoid duplicates on re-run
    cursor.execute("DELETE FROM events WHERE event_type = 'anomaly'")
    conn.commit()

    now_iso = datetime.now().isoformat()

    # --- Rule 1: Low conversion rate (<8%) ---
    if conversion_rate < 8.0:
        _insert_anomaly(conn, now_iso, {
            "type": "low_conversion",
            "description": f"Conversion rate is {conversion_rate}% (target >8%)",
            "severity": "high",
        })
        anomalies_inserted += 1

    # --- Rule 2: Data gap (events separated by >30 min) ---
    cursor.execute("""
        SELECT timestamp FROM events
        WHERE event_type IN ('entry', 'exit')
        ORDER BY timestamp ASC
    """)
    timestamps = [row["timestamp"] for row in cursor.fetchall()]
    if len(timestamps) >= 2:
        for i in range(1, len(timestamps)):
            try:
                t0 = datetime.fromisoformat(timestamps[i - 1])
                t1 = datetime.fromisoformat(timestamps[i])
                gap_minutes = (t1 - t0).total_seconds() / 60.0
                if gap_minutes > 30:
                    _insert_anomaly(conn, timestamps[i], {
                        "type": "data_gap",
                        "description": (
                            f"No events for {gap_minutes:.0f} min "
                            f"({timestamps[i-1]} → {timestamps[i]})"
                        ),
                        "severity": "medium",
                    })
                    anomalies_inserted += 1
            except (ValueError, TypeError):
                continue

    # --- Rule 3: Overcrowding (>25 concurrent visitors in any hour) ---
    cursor.execute("""
        SELECT substr(timestamp, 12, 2) AS hour,
               COUNT(DISTINCT track_id) AS visitors
        FROM events
        WHERE event_type = 'entry' AND is_staff = 0
        GROUP BY hour
        HAVING visitors > 25
    """)
    for row in cursor.fetchall():
        _insert_anomaly(conn, now_iso, {
            "type": "overcrowding",
            "description": f"High traffic ({row['visitors']} visitors) at hour {row['hour']}:xx",
            "severity": "medium",
        })
        anomalies_inserted += 1

    # --- Rule 4: Dead period (zero entries in an operational hour 10-22) ---
    cursor.execute("""
        SELECT substr(timestamp, 12, 2) AS hour,
               COUNT(*) AS cnt
        FROM events
        WHERE event_type = 'entry' AND is_staff = 0
        GROUP BY hour
    """)
    active_hours = {row["hour"] for row in cursor.fetchall()}
    for h in range(10, 22):
        h_str = f"{h:02d}"
        if h_str not in active_hours:
            _insert_anomaly(conn, now_iso, {
                "type": "dead_period",
                "description": f"No entries detected during hour {h_str}:00-{h+1:02d}:00",
                "severity": "low",
            })
            anomalies_inserted += 1

    # --- Rule 5: Synthetic data warning ---
    if data_source == "synthetic":
        _insert_anomaly(conn, now_iso, {
            "type": "synthetic_fallback",
            "description": "Pipeline ran in synthetic mode (no video file provided)",
            "severity": "low",
        })
        anomalies_inserted += 1

    # --- Rule 6: High staff ratio ---
    cursor.execute("SELECT COUNT(DISTINCT track_id) FROM events WHERE is_staff = 1")
    staff = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(DISTINCT track_id) FROM events WHERE is_staff = 0 AND event_type = 'entry'")
    visitors = cursor.fetchone()[0] or 0
    if visitors > 0 and staff / visitors > 0.2:
        _insert_anomaly(conn, now_iso, {
            "type": "high_staff_ratio",
            "description": f"Staff-to-visitor ratio is {staff}/{visitors} ({staff/visitors*100:.0f}%)",
            "severity": "low",
        })
        anomalies_inserted += 1

    logger.info(f"Anomaly detection complete: {anomalies_inserted} anomalies flagged.")
    return anomalies_inserted


def _insert_anomaly(
    conn: sqlite3.Connection, timestamp: str, meta: dict
) -> None:
    insert_event(conn, Event(
        event_type="anomaly",
        timestamp=timestamp,
        meta=meta,
    ))
