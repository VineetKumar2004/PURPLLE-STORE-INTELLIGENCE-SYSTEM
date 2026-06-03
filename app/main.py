"""
FastAPI REST API for the Purplle Store Intelligence System.

Endpoints:
  GET  /health         — system and pipeline status
  GET  /metrics        — key performance indicators
  GET  /funnel         — 4-stage conversion funnel
  GET  /events         — paginated entry/exit/anomaly logs
  GET  /anomalies      — operational warnings
  GET  /hourly         — hourly traffic + revenue breakdown
  GET  /zones          — zone visit distribution
  GET  /sales/summary  — salesperson, brand, and category stats
  GET  /               — HTML dashboard
  GET  /video          — serve annotated or raw video
  POST /pipeline/run   — trigger background pipeline execution
"""
import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from loguru import logger

from app.db import get_connection, init_db, get_pipeline_status, get_cache_metric

app = FastAPI(title="Purplle Store Intelligence API", version="1.0")

DB_PATH = os.environ.get("DB_PATH", "store_intelligence.db")
STORE_ID = os.environ.get("STORE_ID", "ST1008")
VIDEO_DATE = os.environ.get("VIDEO_DATE", "2026-04-10")

# If running on Vercel, copy SQLite DB to /tmp to allow read-write WAL mode
if os.environ.get("VERCEL"):
    import shutil
    tmp_db_path = "/tmp/store_intelligence.db"
    os.makedirs(os.path.dirname(tmp_db_path), exist_ok=True)
    if not os.path.exists(tmp_db_path):
        src_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "store_intelligence.db")
        if os.path.exists(src_db_path):
            try:
                shutil.copy2(src_db_path, tmp_db_path)
                logger.info(f"Copied database from {src_db_path} to {tmp_db_path}")
            except Exception as e:
                logger.error(f"Failed to copy database to /tmp: {e}")
        else:
            logger.warning(f"Original database not found at {src_db_path}")
    DB_PATH = tmp_db_path

init_db(DB_PATH)


def _db():
    return get_connection(DB_PATH)


# ======================================================================
# Health
# ======================================================================

@app.get("/health")
def health():
    conn = _db()
    try:
        info = get_pipeline_status(conn)
        video_path = os.environ.get("VIDEO_PATH", "input/video.mp4")
        return {
            "status": "ok",
            "pipeline_status": info["status"],
            "data_source": info["data_source"],
            "store_id": STORE_ID,
            "processed_at": info["finished_at"],
            "video_exists": os.path.exists(video_path) and os.path.getsize(video_path) > 0,
        }
    finally:
        conn.close()


# ======================================================================
# Metrics
# ======================================================================

_METRICS_KEYS = [
    ("total_footfall", 0), ("unique_buyers", 0), ("total_transactions", 0),
    ("conversion_rate", 0.0), ("avg_dwell_time_minutes", 0.0),
    ("peak_hour", "19:00-20:00"), ("peak_footfall_hour", "19:00-20:00"),
    ("staff_count", 0), ("total_entries", 0), ("total_exits", 0),
    ("re_entries", 0), ("total_gmv", 0.0), ("total_nmv", 0.0),
    ("top_brand", ""), ("top_category", ""), ("busiest_zone", ""),
]


@app.get("/metrics")
def metrics():
    conn = _db()
    try:
        info = get_pipeline_status(conn)
        result = {"date": VIDEO_DATE, "store_id": STORE_ID, "data_source": info["data_source"]}
        if info["status"] == "pending":
            for k, default in _METRICS_KEYS:
                result[k] = default
        else:
            for k, default in _METRICS_KEYS:
                result[k] = get_cache_metric(conn, k, default)
        return result
    finally:
        conn.close()


# ======================================================================
# Funnel
# ======================================================================

@app.get("/funnel")
def funnel():
    conn = _db()
    try:
        info = get_pipeline_status(conn)
        if info["status"] == "pending":
            return {
                "date": VIDEO_DATE,
                "stages": [
                    {"stage": "Estimated Passers-by", "count": 0, "conversion_from_prev": None, "drop_pct": None},
                    {"stage": "Store Entrants", "count": 0, "conversion_from_prev": 0.0, "drop_pct": 0.0},
                    {"stage": "Engaged Browsers (dwell > 3 min)", "count": 0, "conversion_from_prev": 0.0, "drop_pct": 0.0},
                    {"stage": "Buyers (completed transaction)", "count": 0, "conversion_from_prev": 0.0, "drop_pct": 0.0},
                ],
                "overall_conversion_rate": 0.0,
            }
        return {
            "date": get_cache_metric(conn, "date", VIDEO_DATE),
            "stages": get_cache_metric(conn, "funnel_stages", []),
            "overall_conversion_rate": get_cache_metric(conn, "overall_conversion_rate", 0.0),
        }
    finally:
        conn.close()


# ======================================================================
# Events (paginated)
# ======================================================================

@app.get("/events")
def events(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    event_type: Optional[str] = Query(default=None),
    zone: Optional[str] = Query(default=None),
):
    conn = _db()
    try:
        query = "SELECT id, event_type, track_id, timestamp, frame_number, x, y, is_staff, zone, meta FROM events WHERE 1=1"
        params: list = []
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if zone:
            query += " AND zone = ?"
            params.append(zone)

        count_q = query.replace(
            "SELECT id, event_type, track_id, timestamp, frame_number, x, y, is_staff, zone, meta",
            "SELECT COUNT(*)",
        )
        total = conn.execute(count_q, params).fetchone()[0]

        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
        params += [limit, offset]
        rows = conn.execute(query, params).fetchall()

        events_list = []
        for r in rows:
            meta = None
            if r["meta"]:
                try:
                    meta = json.loads(r["meta"])
                except Exception:
                    meta = {}
            events_list.append({
                "id": r["id"], "event_type": r["event_type"],
                "track_id": r["track_id"], "timestamp": r["timestamp"],
                "frame_number": r["frame_number"],
                "x": r["x"], "y": r["y"],
                "is_staff": r["is_staff"], "zone": r["zone"], "meta": meta,
            })
        return {"total": total, "limit": limit, "offset": offset, "events": events_list}
    finally:
        conn.close()


# ======================================================================
# Anomalies
# ======================================================================

@app.get("/anomalies")
def anomalies():
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT timestamp, meta FROM events WHERE event_type = 'anomaly' ORDER BY timestamp"
        ).fetchall()
        result = []
        for r in rows:
            meta = {}
            if r["meta"]:
                try:
                    meta = json.loads(r["meta"])
                except Exception:
                    pass
            result.append({
                "type": meta.get("type", "unknown"),
                "timestamp": r["timestamp"],
                "description": meta.get("description", ""),
                "severity": meta.get("severity", "low"),
            })
        return {"total": len(result), "anomalies": result}
    finally:
        conn.close()


# ======================================================================
# Hourly
# ======================================================================

@app.get("/hourly")
def hourly():
    conn = _db()
    try:
        info = get_pipeline_status(conn)
        if info["status"] == "pending":
            return {"date": VIDEO_DATE, "hours": [
                {"hour": f"{h:02d}:00", "visitors": 0, "transactions": 0, "gmv": 0.0}
                for h in range(10, 23)
            ]}
        hv = get_cache_metric(conn, "hourly_visitors", {})
        ht = get_cache_metric(conn, "hourly_transactions", {})
        hr = get_cache_metric(conn, "hourly_revenue", {})
        return {
            "date": get_cache_metric(conn, "date", VIDEO_DATE),
            "hours": [
                {
                    "hour": f"{h:02d}:00",
                    "visitors": int(hv.get(str(h), 0)),
                    "transactions": int(ht.get(str(h), 0)),
                    "gmv": float(hr.get(str(h), 0.0)),
                }
                for h in range(10, 23)
            ],
        }
    finally:
        conn.close()


# ======================================================================
# Zones
# ======================================================================

@app.get("/zones")
def zones():
    conn = _db()
    try:
        info = get_pipeline_status(conn)
        if info["status"] == "pending":
            return {"zones": [
                {"zone": z, "visitor_count": 0, "avg_dwell_seconds": 0.0, "pct_of_total": 0.0}
                for z in ["entrance", "floor_left", "floor_center", "counter"]
            ]}
        return {"zones": get_cache_metric(conn, "zones_list", [])}
    finally:
        conn.close()


# ======================================================================
# Sales summary
# ======================================================================

@app.get("/sales/summary")
def sales_summary():
    conn = _db()
    try:
        info = get_pipeline_status(conn)
        if info["status"] == "pending":
            return {
                "total_transactions": 0, "unique_customers": 0,
                "total_gmv": 0.0, "total_nmv": 0.0, "avg_basket_size": 0.0,
                "top_brands": [], "top_categories": [],
                "salesperson_performance": [], "hourly_revenue": {},
            }
        hr = get_cache_metric(conn, "hourly_revenue", {})
        return {
            "total_transactions": get_cache_metric(conn, "total_transactions", 0),
            "unique_customers": get_cache_metric(conn, "unique_buyers", 0),
            "total_gmv": get_cache_metric(conn, "total_gmv", 0.0),
            "total_nmv": get_cache_metric(conn, "total_nmv", 0.0),
            "avg_basket_size": get_cache_metric(conn, "avg_basket_size", 0.0),
            "top_brands": get_cache_metric(conn, "top_brands_list", []),
            "top_categories": get_cache_metric(conn, "top_categories_list", []),
            "salesperson_performance": get_cache_metric(conn, "salesperson_performance", []),
            "hourly_revenue": {str(k): float(v) for k, v in hr.items()},
        }
    finally:
        conn.close()


# ======================================================================
# Dashboard + Video + Pipeline trigger
# ======================================================================

@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard template missing</h1>")


@app.get("/video")
def video():
    video_path = os.environ.get("VIDEO_PATH", "input/video.mp4")
    annotated = os.path.join(os.path.dirname(video_path), "annotated_video.mp4")
    if os.path.exists(annotated) and os.path.getsize(annotated) > 0:
        return FileResponse(annotated, media_type="video/mp4")
    if os.path.exists(video_path):
        return FileResponse(video_path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="No video file found")


@app.post("/pipeline/run")
def trigger_pipeline(background_tasks: BackgroundTasks):
    from app.pipeline import run_pipeline  # lazy import — heavy deps
    background_tasks.add_task(
        run_pipeline,
        video_path=os.environ.get("VIDEO_PATH", "input/video.mp4"),
        sales_path=os.environ.get("SALES_PATH", "input/sales.csv"),
        db_path=DB_PATH,
        store_id=STORE_ID,
        video_date=VIDEO_DATE,
    )
    return {"status": "started"}
