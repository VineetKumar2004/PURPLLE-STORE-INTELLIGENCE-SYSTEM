"""
Fallback data for Vercel cloud deployment.
Pre-computed metrics from the synthetic pipeline run on 2026-04-10.
Used when the SQLite database is unavailable or empty.
"""

FALLBACK_PIPELINE_STATUS = {
    "status": "complete",
    "data_source": "synthetic",
    "started_at": "2026-06-03T01:52:28",
    "finished_at": "2026-06-03T01:53:01",
    "error_msg": None,
}

FALLBACK_METRICS = {
    "date": "2026-04-10",
    "store_id": "ST1008",
    "data_source": "video",
    "total_footfall": 180,
    "unique_buyers": 21,
    "total_transactions": 24,
    "conversion_rate": 11.67,
    "avg_dwell_time_minutes": 9.32,
    "peak_hour": "19:00-20:00",
    "peak_footfall_hour": "19:00-20:00",
    "staff_count": 5,
    "total_entries": 816,
    "total_exits": 418,
    "re_entries": 636,
    "total_gmv": 44920.0,
    "total_nmv": 34831.74,
    "top_brand": "Faces Canada",
    "top_category": "makeup",
    "busiest_zone": "entrance",
    "avg_basket_size": 4.88,
}

FALLBACK_HOURLY = [
    {"hour": "10:00", "visitors": 3, "transactions": 0, "gmv": 0.0},
    {"hour": "11:00", "visitors": 8, "transactions": 0, "gmv": 0.0},
    {"hour": "12:00", "visitors": 10, "transactions": 2, "gmv": 13014.0},
    {"hour": "13:00", "visitors": 10, "transactions": 2, "gmv": 597.0},
    {"hour": "14:00", "visitors": 12, "transactions": 1, "gmv": 225.0},
    {"hour": "15:00", "visitors": 13, "transactions": 3, "gmv": 2166.0},
    {"hour": "16:00", "visitors": 27, "transactions": 3, "gmv": 7541.0},
    {"hour": "17:00", "visitors": 23, "transactions": 2, "gmv": 2373.0},
    {"hour": "18:00", "visitors": 30, "transactions": 3, "gmv": 3962.0},
    {"hour": "19:00", "visitors": 35, "transactions": 5, "gmv": 13069.0},
    {"hour": "20:00", "visitors": 16, "transactions": 1, "gmv": 1199.0},
    {"hour": "21:00", "visitors": 5, "transactions": 2, "gmv": 774.0},
    {"hour": "22:00", "visitors": 0, "transactions": 0, "gmv": 0.0},
]

FALLBACK_ZONES = [
    {"zone": "entrance", "visitor_count": 180, "avg_dwell_seconds": 559.1, "pct_of_total": 100.0},
    {"zone": "floor_left", "visitor_count": 81, "avg_dwell_seconds": 0.0, "pct_of_total": 45.0},
    {"zone": "floor_center", "visitor_count": 78, "avg_dwell_seconds": 0.0, "pct_of_total": 43.3},
    {"zone": "counter", "visitor_count": 40, "avg_dwell_seconds": 0.0, "pct_of_total": 22.2},
]

FALLBACK_FUNNEL = [
    {"stage": "Estimated Passers-by", "count": 450, "conversion_from_prev": None, "drop_pct": None},
    {"stage": "Store Entrants", "count": 180, "conversion_from_prev": 40.0, "drop_pct": 60.0},
    {"stage": "Engaged Browsers (dwell > 3 min)", "count": 167, "conversion_from_prev": 92.8, "drop_pct": 7.2},
    {"stage": "Buyers (completed transaction)", "count": 21, "conversion_from_prev": 12.6, "drop_pct": 87.4},
]

FALLBACK_ANOMALIES = [
    {"type": "overcrowding", "description": "High traffic (27 visitors) at hour 16:xx", "severity": "medium", "timestamp": "2026-04-10T16:00:00"},
    {"type": "overcrowding", "description": "High traffic (30 visitors) at hour 18:xx", "severity": "medium", "timestamp": "2026-04-10T18:00:00"},
    {"type": "overcrowding", "description": "High traffic (35 visitors) at hour 19:xx", "severity": "medium", "timestamp": "2026-04-10T19:00:00"},
    {"type": "synthetic_fallback", "description": "Pipeline ran in synthetic mode (no video file provided)", "severity": "low", "timestamp": "2026-04-10T10:00:00"},
]

FALLBACK_SALES_SUMMARY = {
    "avg_basket_size": 4.88,
    "total_gmv": 44920.0,
    "total_nmv": 34831.74,
    "top_brands_list": [
        {"brand": "Faces Canada", "gmv": 20933.0},
        {"brand": "NY Bae", "gmv": 3070.0},
        {"brand": "Good Vibes", "gmv": 2871.0},
        {"brand": "DERMDOC", "gmv": 2340.0},
        {"brand": "COSRX", "gmv": 2300.0},
    ],
    "top_categories_list": [
        {"category": "makeup", "gmv": 28803.0},
        {"category": "skin", "gmv": 11808.0},
        {"category": "hair", "gmv": 2398.0},
        {"category": "personal-care", "gmv": 899.0},
        {"category": "bath-and-body", "gmv": 763.0},
    ],
    "salesperson_performance": [
        {"salesperson_name": "Shashikala .", "transactions": 7, "total_gmv": 5001.0},
        {"salesperson_name": "Zufishan Khazra", "transactions": 7, "total_gmv": 21871.0},
        {"salesperson_name": "kasthuri v", "transactions": 5, "total_gmv": 8410.0},
        {"salesperson_name": "Priya v", "transactions": 3, "total_gmv": 4988.0},
        {"salesperson_name": "Naziya Begum", "transactions": 2, "total_gmv": 4637.0},
    ],
}
