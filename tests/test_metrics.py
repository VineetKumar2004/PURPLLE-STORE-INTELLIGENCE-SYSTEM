"""Tests for the metrics engine."""
import pytest
from app.db import get_connection, init_db, get_cache_metric
from app.events import Event, insert_events_bulk
from app.metrics import compute_and_cache_metrics


@pytest.fixture
def populated_db(tmp_path):
    """Create a DB with some visitor events."""
    path = str(tmp_path / "metrics_test.db")
    init_db(path)
    conn = get_connection(path)
    events = [
        Event(event_type="entry", track_id=100, timestamp="2026-04-10T14:00:00",
              frame_number=1000, x=50, y=200, zone="entrance", is_staff=0),
        Event(event_type="exit", track_id=100, timestamp="2026-04-10T14:10:00",
              frame_number=16000, x=100, y=200, zone="entrance", is_staff=0),
        Event(event_type="entry", track_id=101, timestamp="2026-04-10T19:00:00",
              frame_number=50000, x=50, y=200, zone="entrance", is_staff=0),
        Event(event_type="exit", track_id=101, timestamp="2026-04-10T19:05:00",
              frame_number=57500, x=100, y=200, zone="entrance", is_staff=0),
        Event(event_type="entry", track_id=1, timestamp="2026-04-10T10:00:00",
              frame_number=0, x=50, y=200, zone="entrance", is_staff=1),
    ]
    insert_events_bulk(conn, events)
    yield conn
    conn.close()


def test_footfall_excludes_staff(populated_db):
    sales = {"total_transactions": 1, "unique_buyers": 1, "total_gmv": 500.0,
             "total_nmv": 400.0, "avg_basket_size": 2.0,
             "hourly_transactions": {}, "hourly_revenue": {},
             "top_brands_list": [], "top_categories_list": [],
             "salesperson_performance": [], "peak_hour": "19:00-20:00",
             "top_brand": "TestBrand", "top_category": "skin"}
    compute_and_cache_metrics(populated_db, sales, "synthetic")

    footfall = get_cache_metric(populated_db, "total_footfall", 0)
    assert footfall == 2  # track 100 and 101, not track 1 (staff)

    staff_count = get_cache_metric(populated_db, "staff_count", 0)
    assert staff_count == 1


def test_conversion_rate(populated_db):
    sales = {"total_transactions": 1, "unique_buyers": 1, "total_gmv": 500.0,
             "total_nmv": 400.0, "avg_basket_size": 2.0,
             "hourly_transactions": {}, "hourly_revenue": {},
             "top_brands_list": [], "top_categories_list": [],
             "salesperson_performance": [], "peak_hour": "19:00-20:00",
             "top_brand": "", "top_category": ""}
    compute_and_cache_metrics(populated_db, sales, "synthetic")

    cr = get_cache_metric(populated_db, "conversion_rate", 0.0)
    assert cr == 50.0  # 1 buyer / 2 visitors = 50%
