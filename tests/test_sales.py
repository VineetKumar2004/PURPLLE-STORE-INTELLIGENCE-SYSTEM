"""Tests for the sales CSV analyser."""
import os
import csv
import pytest
from app.sales import analyze_sales_csv


@pytest.fixture
def sample_csv(tmp_path):
    """Write a small sales CSV for testing."""
    path = str(tmp_path / "sales.csv")
    rows = [
        {
            "order_id": "1001", "invoice_number": "INV001", "invoice_type": "sales",
            "order_date": "10-04-2026", "order_time": "16:55:36",
            "store_id": "ST1008", "store_name": "Brigade_Bangalore", "city": "Bangalore",
            "customer_name": "Alice", "customer_number": "9000000001",
            "product_name": "Lipstick", "brand_name": "Faces Canada",
            "dep_name": "makeup", "sub_category": "Lip Color",
            "salesperson_name": "Raj", "qty": "2", "GMV": "800", "NMV": "600",
            "coupon_amount": "0", "item_promotion": "200",
        },
        {
            "order_id": "1002", "invoice_number": "INV002", "invoice_type": "sales",
            "order_date": "10-04-2026", "order_time": "19:21:55",
            "store_id": "ST1008", "store_name": "Brigade_Bangalore", "city": "Bangalore",
            "customer_name": "Bob", "customer_number": "9000000002",
            "product_name": "Shampoo", "brand_name": "Good Vibes",
            "dep_name": "bath-and-body", "sub_category": "Shampoo",
            "salesperson_name": "Priya", "qty": "1", "GMV": "400", "NMV": "350",
            "coupon_amount": "50", "item_promotion": "0",
        },
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_basic_stats(sample_csv):
    stats = analyze_sales_csv(sample_csv)
    assert stats["total_transactions"] == 2
    assert stats["unique_buyers"] == 2
    assert stats["total_gmv"] == 1200.0
    assert stats["total_nmv"] == 950.0


def test_top_brand(sample_csv):
    stats = analyze_sales_csv(sample_csv)
    assert stats["top_brand"] == "Faces Canada"


def test_missing_file():
    stats = analyze_sales_csv("/nonexistent/path.csv")
    assert stats["total_transactions"] == 0
    assert stats["total_gmv"] == 0.0


def test_salesperson_performance(sample_csv):
    stats = analyze_sales_csv(sample_csv)
    assert len(stats["salesperson_performance"]) == 2
    names = {sp["salesperson_name"] for sp in stats["salesperson_performance"]}
    assert "Raj" in names
    assert "Priya" in names


def test_basket_size(sample_csv):
    stats = analyze_sales_csv(sample_csv)
    # INV001 has qty=2, INV002 has qty=1, avg = 1.5
    assert stats["avg_basket_size"] == 1.5
