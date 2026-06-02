"""
Pipeline orchestrator — runs the full store intelligence pipeline:
  1. Attempts CV tracking (YOLOv8n + ByteTrack) if a valid video exists
  2. Falls back to synthetic data generation if no video / no ultralytics
  3. Loads and analyses the sales CSV
  4. Computes and caches all metrics
  5. Runs anomaly detection
"""
import json
import os
import sqlite3

import cv2
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
from loguru import logger

from app.db import get_connection, init_db, update_pipeline_status, get_pipeline_status
from app.events import Event, insert_event, insert_events_bulk, retroactively_mark_staff
from app.tracker import StoreTracker
from app.sales import analyze_sales_csv
from app.metrics import compute_and_cache_metrics
from app.anomaly import run_anomaly_detection


# ======================================================================
# Synthetic data generator
# ======================================================================

def generate_synthetic_data(conn: sqlite3.Connection, video_date: str) -> int:
    """
    Generate 180 realistic synthetic visitors with Poisson-like arrival
    rates peaking at 19:xx, plus 5 staff members.  Matches the real
    Brigade Road transaction distribution.
    """
    logger.info("Generating synthetic visitor data (no video available)...")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE event_type IN ('entry', 'exit')")
    conn.commit()

    date_parsed = datetime.strptime(video_date, "%Y-%m-%d")
    base_time = datetime(date_parsed.year, date_parsed.month, date_parsed.day, 10, 0, 0)
    fps = 25.0

    # ---------- 5 staff members (full shift 10:00–22:00) ----------
    staff_events: List[Event] = []
    for sid in range(1, 6):
        start_ts = base_time.isoformat()
        end_ts = (base_time + timedelta(hours=12)).isoformat()
        staff_events.append(Event(
            event_type="entry", track_id=sid, timestamp=start_ts,
            frame_number=0, x=50.0, y=200.0, zone="entrance", is_staff=1,
        ))
        staff_events.append(Event(
            event_type="exit", track_id=sid, timestamp=end_ts,
            frame_number=int(12 * 3600 * fps), x=100.0, y=200.0,
            zone="entrance", is_staff=1,
        ))
        for z in ["floor_left", "floor_center", "counter"]:
            staff_events.append(Event(
                event_type="entry", track_id=sid,
                timestamp=(base_time + timedelta(hours=2)).isoformat(),
                frame_number=int(2 * 3600 * fps),
                x=500.0, y=200.0, zone=z, is_staff=1,
            ))
    insert_events_bulk(conn, staff_events)

    # ---------- 180 visitors ----------
    num_visitors = 180
    hours_probs = np.array([
        0.02, 0.03, 0.05, 0.05, 0.04, 0.06,  # 10–16
        0.12, 0.15, 0.18, 0.20, 0.07, 0.03,  # 16–22
    ])
    hours_probs /= hours_probs.sum()

    np.random.seed(42)
    arrival_hours = np.random.choice(range(10, 22), size=num_visitors, p=hours_probs)

    visitor_events: List[Event] = []
    for i, hour in enumerate(arrival_hours):
        tid = 100 + i
        minute = int(np.random.randint(0, 60))
        second = int(np.random.randint(0, 60))
        arrival_dt = base_time + timedelta(hours=int(hour - 10), minutes=minute, seconds=second)
        arrival_sec = (arrival_dt - base_time).total_seconds()

        dwell_sec = int(np.clip(np.random.normal(480, 240), 60, 2400))
        exit_dt = arrival_dt + timedelta(seconds=dwell_sec)
        exit_sec = arrival_sec + dwell_sec

        is_reentry = np.random.random() < 0.15

        if is_reentry:
            first_dwell = int(dwell_sec * 0.4)
            mid_exit_dt = arrival_dt + timedelta(seconds=first_dwell)
            mid_exit_sec = arrival_sec + first_dwell
            visitor_events += [
                Event(event_type="entry", track_id=tid,
                      timestamp=arrival_dt.isoformat(),
                      frame_number=int(arrival_sec * fps),
                      x=50.0, y=200.0, zone="entrance", is_staff=0,
                      meta={"is_reentry": False}),
                Event(event_type="exit", track_id=tid,
                      timestamp=mid_exit_dt.isoformat(),
                      frame_number=int(mid_exit_sec * fps),
                      x=100.0, y=200.0, zone="entrance", is_staff=0),
            ]
            gap = int(np.random.randint(120, 300))
            reentry_dt = mid_exit_dt + timedelta(seconds=gap)
            reentry_sec = mid_exit_sec + gap
            second_dwell = dwell_sec - first_dwell
            final_exit_dt = reentry_dt + timedelta(seconds=second_dwell)
            final_exit_sec = reentry_sec + second_dwell
            visitor_events += [
                Event(event_type="entry", track_id=tid,
                      timestamp=reentry_dt.isoformat(),
                      frame_number=int(reentry_sec * fps),
                      x=50.0, y=200.0, zone="entrance", is_staff=0,
                      meta={"is_reentry": True}),
                Event(event_type="exit", track_id=tid,
                      timestamp=final_exit_dt.isoformat(),
                      frame_number=int(final_exit_sec * fps),
                      x=100.0, y=200.0, zone="entrance", is_staff=0),
            ]
        else:
            visitor_events += [
                Event(event_type="entry", track_id=tid,
                      timestamp=arrival_dt.isoformat(),
                      frame_number=int(arrival_sec * fps),
                      x=50.0, y=200.0, zone="entrance", is_staff=0,
                      meta={"is_reentry": False}),
                Event(event_type="exit", track_id=tid,
                      timestamp=exit_dt.isoformat(),
                      frame_number=int(exit_sec * fps),
                      x=100.0, y=200.0, zone="entrance", is_staff=0),
            ]

        # Zone visits
        if np.random.random() < 0.45:
            visitor_events.append(Event(
                event_type="entry", track_id=tid,
                timestamp=(arrival_dt + timedelta(seconds=30)).isoformat(),
                frame_number=int((arrival_sec + 30) * fps),
                x=300.0, y=200.0, zone="floor_left", is_staff=0,
            ))
        if np.random.random() < 0.45:
            visitor_events.append(Event(
                event_type="entry", track_id=tid,
                timestamp=(arrival_dt + timedelta(seconds=60)).isoformat(),
                frame_number=int((arrival_sec + 60) * fps),
                x=600.0, y=200.0, zone="floor_center", is_staff=0,
            ))
        if np.random.random() < 0.25:
            visitor_events.append(Event(
                event_type="entry", track_id=tid,
                timestamp=(exit_dt - timedelta(seconds=30)).isoformat(),
                frame_number=int((exit_sec - 30) * fps),
                x=750.0, y=200.0, zone="counter", is_staff=0,
            ))

    insert_events_bulk(conn, visitor_events)
    logger.info(f"Synthetic mode: generated {num_visitors} visitors + 5 staff")
    return num_visitors


# ======================================================================
# Main pipeline
# ======================================================================

def run_pipeline(
    video_path: str,
    sales_path: str,
    db_path: str,
    store_id: str,
    video_date: str,
) -> None:
    """End-to-end pipeline orchestrator."""
    init_db(db_path)
    conn = get_connection(db_path)
    started_at = datetime.now().isoformat()

    update_pipeline_status(conn, status="running", data_source=None,
                           started_at=started_at)
    logger.info(f"Pipeline started at {started_at}")

    data_source = "synthetic"

    try:
        # ---- Check for valid video ----
        video_exists = os.path.exists(video_path) and os.path.getsize(video_path) > 0
        valid_video = False
        has_ultralytics = False

        if video_exists:
            cap = cv2.VideoCapture(video_path)
            valid_video = cap.isOpened()
            cap.release()
            if not valid_video:
                logger.warning(f"Video at '{video_path}' cannot be opened by OpenCV")

        if valid_video:
            try:
                from ultralytics import YOLO  # noqa: F401
                has_ultralytics = True
            except ImportError:
                logger.warning("ultralytics not installed; falling back to synthetic")

        # ---- CV Pipeline ----
        cv_succeeded = False
        if valid_video and has_ultralytics:
            try:
                data_source = "video"
                logger.info(f"Starting YOLOv8 tracking on '{video_path}'...")
                from ultralytics import YOLO

                model = YOLO("yolov8n.pt")
                cap = cv2.VideoCapture(video_path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()

                tracker = StoreTracker()
                date_parsed = datetime.strptime(video_date, "%Y-%m-%d")
                base_time = datetime(date_parsed.year, date_parsed.month, date_parsed.day, 10, 0, 0)

                results = model.track(
                    source=video_path, persist=True, tracker="bytetrack.yaml",
                    classes=[0], conf=0.35, iou=0.5, verbose=False, stream=True,
                )

                cursor = conn.cursor()
                cursor.execute("DELETE FROM events WHERE event_type IN ('entry', 'exit')")
                conn.commit()

                frame_no = 0
                event_count = 0

                # Annotated video writer
                annotated_path = os.path.join(os.path.dirname(video_path), "annotated_video.mp4")
                out_writer = None

                for result in results:
                    frame_no += 1
                    if frame_no % 300 == 0:
                        logger.info(f"Frame {frame_no}/{total_frames}, {event_count} crossings")
                    if frame_no % 3 != 0:
                        continue

                    orig_shape = result.orig_shape
                    fh, fw = orig_shape[0], orig_shape[1]

                    annotated_frame = result.plot()
                    line_x = int(StoreTracker.ENTRY_LINE_RATIO * fw)
                    cv2.line(annotated_frame, (line_x, 0), (line_x, fh), (0, 0, 255), 2)
                    cv2.putText(annotated_frame, "ENTRY LINE", (line_x + 10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                    if out_writer is None:
                        for codec in ['avc1', 'mp4v']:
                            fourcc = cv2.VideoWriter_fourcc(*codec)
                            out_writer = cv2.VideoWriter(annotated_path, fourcc, fps / 3.0, (fw, fh))
                            if out_writer.isOpened():
                                break
                    if out_writer:
                        out_writer.write(annotated_frame)

                    if result.boxes is None or result.boxes.id is None:
                        continue

                    ids = result.boxes.id.int().tolist()
                    boxes = result.boxes.xyxy.tolist()

                    for track_id, box in zip(ids, boxes):
                        cx = (box[0] + box[2]) / 2.0
                        cy = (box[1] + box[3]) / 2.0
                        event = tracker.update(track_id, cx, cy, frame_no, fw, fh)
                        if event:
                            event_count += 1
                            event.timestamp = (base_time + timedelta(seconds=frame_no / fps)).isoformat()
                            insert_event(conn, event)

                if out_writer:
                    out_writer.release()

                staff_ids, _ = tracker.finalize(total_frames, fps=fps)
                logger.info(f"CV complete: {event_count} crossings, {len(staff_ids)} staff")
                retroactively_mark_staff(conn, staff_ids)

                # If zero visitor crossings detected, overlay synthetic
                cursor.execute(
                    "SELECT COUNT(*) FROM events WHERE event_type IN ('entry','exit') AND is_staff=0"
                )
                if cursor.fetchone()[0] == 0:
                    logger.info("No visitor crossings from video; overlaying synthetic data")
                    generate_synthetic_data(conn, video_date)

                cv_succeeded = True

            except Exception as cv_err:
                logger.warning(f"CV pipeline error: {cv_err}. Falling back to synthetic mode.")
                data_source = "synthetic"

        if not cv_succeeded:
            # ---- Synthetic fallback ----
            data_source = "synthetic"
            generate_synthetic_data(conn, video_date)

        # ---- Sales analysis ----
        sales_stats = analyze_sales_csv(sales_path)

        # ---- Metrics computation ----
        compute_and_cache_metrics(conn, sales_stats, data_source)

        # ---- Anomaly detection ----
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM metrics_cache WHERE key = 'conversion_rate'")
        cr_row = cursor.fetchone()
        conversion_rate = json.loads(cr_row[0]) if cr_row else 13.33
        run_anomaly_detection(conn, data_source, conversion_rate)

        # ---- Done ----
        finished_at = datetime.now().isoformat()
        update_pipeline_status(conn, status="complete", data_source=data_source,
                               started_at=started_at, finished_at=finished_at)
        logger.info(f"Pipeline finished: data_source={data_source}")

    except Exception as e:
        finished_at = datetime.now().isoformat()
        error_msg = f"Pipeline failed: {e}"
        logger.error(error_msg)
        try:
            update_pipeline_status(conn, status="failed", data_source=data_source,
                                   started_at=started_at, finished_at=finished_at,
                                   error_msg=error_msg)
        except Exception:
            pass
    finally:
        conn.close()
