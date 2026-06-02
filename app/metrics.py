"""
Metrics engine — reads events + sales stats and writes pre-computed
JSON to the metrics_cache table for fast API retrieval.
"""
import sqlite3
from typing import Any, Dict

from loguru import logger
from app.db import set_cache_metric


def compute_and_cache_metrics(
    conn: sqlite3.Connection,
    sales_stats: Dict[str, Any],
    data_source: str,
) -> None:
    """
    Aggregate visitor events with sales data and cache every metric.
    """
    cursor = conn.cursor()

    # ---- visitor counts (exclude staff) ----
    cursor.execute(
        "SELECT COUNT(DISTINCT track_id) FROM events "
        "WHERE event_type = 'entry' AND is_staff = 0"
    )
    total_footfall = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT COUNT(*) FROM events "
        "WHERE event_type = 'entry' AND is_staff = 0"
    )
    total_entries = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT COUNT(*) FROM events "
        "WHERE event_type = 'exit' AND is_staff = 0"
    )
    total_exits = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT COUNT(DISTINCT track_id) FROM events WHERE is_staff = 1"
    )
    staff_count = cursor.fetchone()[0] or 0

    # re-entries = total entries − unique track ids
    re_entries = max(0, total_entries - total_footfall)

    # ---- conversion rate ----
    unique_buyers = sales_stats.get("unique_buyers", 0)
    conversion_rate = round(
        (unique_buyers / total_footfall * 100) if total_footfall > 0 else 0.0, 2
    )

    # ---- dwell time (approximate from entry→exit per track) ----
    cursor.execute("""
        SELECT track_id,
               MIN(frame_number) AS first_frame,
               MAX(frame_number) AS last_frame
        FROM events
        WHERE is_staff = 0 AND frame_number IS NOT NULL
        GROUP BY track_id
        HAVING COUNT(*) >= 2
    """)
    dwell_rows = cursor.fetchall()
    if dwell_rows:
        fps = 25.0
        dwells = [(r["last_frame"] - r["first_frame"]) / fps / 60.0 for r in dwell_rows]
        avg_dwell = round(sum(dwells) / len(dwells), 2)
    else:
        avg_dwell = 0.0

    # ---- hourly visitor distribution ----
    hourly_visitors: Dict[str, int] = {}
    for h in range(10, 23):
        prefix = f"2026-04-10T{h:02d}"
        cursor.execute(
            "SELECT COUNT(DISTINCT track_id) FROM events "
            "WHERE event_type = 'entry' AND is_staff = 0 "
            "AND timestamp LIKE ?",
            (f"{prefix}%",),
        )
        hourly_visitors[str(h)] = cursor.fetchone()[0] or 0

    # ---- peak footfall hour ----
    if hourly_visitors:
        peak_h = max(hourly_visitors, key=hourly_visitors.get)
        peak_footfall_hour = f"{int(peak_h):02d}:00-{int(peak_h)+1:02d}:00"
    else:
        peak_footfall_hour = "19:00-20:00"

    # ---- zone distribution ----
    zones_list = []
    for z in ["entrance", "floor_left", "floor_center", "counter"]:
        cursor.execute(
            "SELECT COUNT(DISTINCT track_id) FROM events "
            "WHERE zone = ? AND is_staff = 0",
            (z,),
        )
        count = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT track_id,
                   MIN(frame_number) AS f_min,
                   MAX(frame_number) AS f_max
            FROM events
            WHERE zone = ? AND is_staff = 0
            GROUP BY track_id
        """, (z,))
        zone_rows = cursor.fetchall()
        if zone_rows:
            dwell_secs = [
                (r["f_max"] - r["f_min"]) / 25.0
                for r in zone_rows
                if r["f_max"] is not None and r["f_min"] is not None
            ]
            avg_d = round(sum(dwell_secs) / len(dwell_secs), 1) if dwell_secs else 0.0
        else:
            avg_d = 0.0

        pct = round(count / total_footfall * 100, 1) if total_footfall > 0 else 0.0
        zones_list.append({
            "zone": z,
            "visitor_count": count,
            "avg_dwell_seconds": avg_d,
            "pct_of_total": pct,
        })

    # ---- busiest zone ----
    busiest_zone = max(zones_list, key=lambda z: z["visitor_count"])["zone"] if zones_list else "entrance"

    # ---- funnel stages ----
    passers_by = int(total_footfall * 2.5)  # estimated foot traffic multiplier
    entrants = total_footfall
    # engaged = dwell > 3 min
    cursor.execute("""
        SELECT COUNT(DISTINCT track_id) FROM (
            SELECT track_id,
                   (MAX(frame_number) - MIN(frame_number)) / 25.0 / 60.0 AS dwell_min
            FROM events
            WHERE is_staff = 0 AND frame_number IS NOT NULL
            GROUP BY track_id
            HAVING dwell_min > 3.0
        )
    """)
    engaged = cursor.fetchone()[0] or 0

    stages = [
        {"stage": "Estimated Passers-by", "count": passers_by,
         "conversion_from_prev": None, "drop_pct": None},
        {"stage": "Store Entrants", "count": entrants,
         "conversion_from_prev": round(entrants / passers_by * 100, 1) if passers_by else 0.0,
         "drop_pct": round((1 - entrants / passers_by) * 100, 1) if passers_by else 0.0},
        {"stage": "Engaged Browsers (dwell > 3 min)", "count": engaged,
         "conversion_from_prev": round(engaged / entrants * 100, 1) if entrants else 0.0,
         "drop_pct": round((1 - engaged / entrants) * 100, 1) if entrants else 0.0},
        {"stage": "Buyers (completed transaction)", "count": unique_buyers,
         "conversion_from_prev": round(unique_buyers / engaged * 100, 1) if engaged else 0.0,
         "drop_pct": round((1 - unique_buyers / engaged) * 100, 1) if engaged else 0.0},
    ]

    overall_conv = round(unique_buyers / passers_by * 100, 2) if passers_by else 0.0

    # ---- write everything to cache ----
    cache = {
        "date": "2026-04-10",
        "store_id": "ST1008",
        "total_footfall": total_footfall,
        "unique_buyers": unique_buyers,
        "total_transactions": sales_stats.get("total_transactions", 0),
        "conversion_rate": conversion_rate,
        "avg_dwell_time_minutes": avg_dwell,
        "peak_hour": sales_stats.get("peak_hour", "19:00-20:00"),
        "peak_footfall_hour": peak_footfall_hour,
        "staff_count": staff_count,
        "total_entries": total_entries,
        "total_exits": total_exits,
        "re_entries": re_entries,
        "total_gmv": sales_stats.get("total_gmv", 0.0),
        "total_nmv": sales_stats.get("total_nmv", 0.0),
        "top_brand": sales_stats.get("top_brand", ""),
        "top_category": sales_stats.get("top_category", ""),
        "busiest_zone": busiest_zone,
        "hourly_visitors": hourly_visitors,
        "hourly_transactions": sales_stats.get("hourly_transactions", {}),
        "hourly_revenue": sales_stats.get("hourly_revenue", {}),
        "zones_list": zones_list,
        "funnel_stages": stages,
        "overall_conversion_rate": overall_conv,
        "avg_basket_size": sales_stats.get("avg_basket_size", 0.0),
        "top_brands_list": sales_stats.get("top_brands_list", []),
        "top_categories_list": sales_stats.get("top_categories_list", []),
        "salesperson_performance": sales_stats.get("salesperson_performance", []),
    }

    for key, value in cache.items():
        set_cache_metric(conn, key, value)

    logger.info(
        f"Metrics cached — footfall={total_footfall}, conversion={conversion_rate}%, "
        f"GMV=₹{sales_stats.get('total_gmv', 0)}, staff={staff_count}"
    )
