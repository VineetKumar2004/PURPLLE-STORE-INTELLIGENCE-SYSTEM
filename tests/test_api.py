"""Tests for FastAPI endpoints."""
import os
import pytest
from fastapi.testclient import TestClient

# Point to an ephemeral test DB before importing the app
os.environ["DB_PATH"] = "test_store_intelligence.db"
os.environ["VIDEO_PATH"] = "input/nonexistent.mp4"
os.environ["SALES_PATH"] = "input/sales.csv"

from app.main import app  # noqa: E402
from app.db import init_db  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db(os.environ["DB_PATH"])
    yield
    if os.path.exists(os.environ["DB_PATH"]):
        try:
            os.remove(os.environ["DB_PATH"])
        except OSError:
            pass


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "pipeline_status" in data


def test_metrics_pending():
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["total_footfall"] == 0
    assert data["store_id"] == "ST1008"


def test_funnel_pending():
    r = client.get("/funnel")
    assert r.status_code == 200
    data = r.json()
    assert len(data["stages"]) == 4


def test_events_empty():
    r = client.get("/events?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["events"] == []


def test_anomalies_empty():
    r = client.get("/anomalies")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_hourly_pending():
    r = client.get("/hourly")
    assert r.status_code == 200
    assert len(r.json()["hours"]) == 13  # 10:00 to 22:00


def test_zones_pending():
    r = client.get("/zones")
    assert r.status_code == 200
    assert len(r.json()["zones"]) == 4


def test_sales_summary_pending():
    r = client.get("/sales/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total_transactions"] == 0


def test_dashboard_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "Store Intelligence" in r.text or "DOCTYPE" in r.text


def test_pipeline_trigger():
    r = client.post("/pipeline/run")
    assert r.status_code == 200
    assert r.json()["status"] == "started"
