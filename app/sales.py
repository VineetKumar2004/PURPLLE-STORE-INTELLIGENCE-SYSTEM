"""
Sales CSV analyser — reads Brigade Road POS exports and returns
aggregate statistics used by the metrics engine.
"""
import os
from typing import Any, Dict

import pandas as pd
from loguru import logger


def analyze_sales_csv(csv_path: str) -> Dict[str, Any]:
    """
    Parse the sales CSV and compute summary stats.

    Returns a dict with keys used by compute_and_cache_metrics().
    If the file is missing, returns sensible zero-state defaults.
    """
    if not os.path.exists(csv_path):
        logger.warning(f"Sales CSV not found at '{csv_path}'; returning zeros.")
        return _empty_stats()

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        logger.error(f"Failed to read sales CSV: {exc}")
        return _empty_stats()

    # --- filter to sales rows only ---
    if "invoice_type" in df.columns:
        df = df[df["invoice_type"].str.strip().str.lower() == "sales"]

    # --- basic counts ---
    total_rows = len(df)
    unique_invoices = df["invoice_number"].nunique() if "invoice_number" in df.columns else 0
    unique_customers = df["customer_number"].nunique() if "customer_number" in df.columns else 0

    # --- monetary ---
    gmv = float(df["GMV"].astype(float).sum()) if "GMV" in df.columns else 0.0
    nmv = float(df["NMV"].astype(float).sum()) if "NMV" in df.columns else 0.0

    # --- basket size ---
    if "invoice_number" in df.columns and "qty" in df.columns:
        basket = df.groupby("invoice_number")["qty"].sum()
        avg_basket = round(float(basket.mean()), 2)
    else:
        avg_basket = 0.0

    # --- hourly distributions ---
    hourly_txns: Dict[str, int] = {}
    hourly_revenue: Dict[str, float] = {}
    if "order_time" in df.columns:
        df["_hour"] = pd.to_datetime(df["order_time"], format="%H:%M:%S", errors="coerce").dt.hour
        for h in range(10, 23):
            mask = df["_hour"] == h
            hourly_txns[str(h)] = int(df.loc[mask, "invoice_number"].nunique())
            hourly_revenue[str(h)] = round(float(df.loc[mask, "GMV"].astype(float).sum()), 2) if "GMV" in df.columns else 0.0

    # --- top brands ---
    top_brands = []
    if "brand_name" in df.columns and "GMV" in df.columns:
        brand_gmv = df.groupby("brand_name")["GMV"].sum().sort_values(ascending=False).head(5)
        top_brands = [{"brand": b, "gmv": round(float(v), 2)} for b, v in brand_gmv.items()]

    # --- top categories ---
    top_categories = []
    if "dep_name" in df.columns and "GMV" in df.columns:
        cat_gmv = df.groupby("dep_name")["GMV"].sum().sort_values(ascending=False).head(5)
        top_categories = [{"category": c, "gmv": round(float(v), 2)} for c, v in cat_gmv.items()]

    # --- salesperson performance ---
    salesperson_perf = []
    if "salesperson_name" in df.columns and "invoice_number" in df.columns:
        sp = df.groupby("salesperson_name").agg(
            transactions=("invoice_number", "nunique"),
            total_gmv=("GMV", lambda s: round(float(s.astype(float).sum()), 2)),
        ).sort_values("transactions", ascending=False).reset_index()
        salesperson_perf = sp.to_dict(orient="records")

    # --- peak hour ---
    peak_hour = "19:00-20:00"
    if hourly_txns:
        peak_h = max(hourly_txns, key=hourly_txns.get)
        peak_hour = f"{int(peak_h):02d}:00-{int(peak_h)+1:02d}:00"

    # --- top brand / category names ---
    top_brand_name = top_brands[0]["brand"] if top_brands else ""
    top_category_name = top_categories[0]["category"] if top_categories else ""

    return {
        "total_rows": total_rows,
        "total_transactions": unique_invoices,
        "unique_buyers": unique_customers,
        "total_gmv": round(gmv, 2),
        "total_nmv": round(nmv, 2),
        "avg_basket_size": avg_basket,
        "hourly_transactions": hourly_txns,
        "hourly_revenue": hourly_revenue,
        "top_brands_list": top_brands,
        "top_categories_list": top_categories,
        "salesperson_performance": salesperson_perf,
        "peak_hour": peak_hour,
        "top_brand": top_brand_name,
        "top_category": top_category_name,
    }


def _empty_stats() -> Dict[str, Any]:
    return {
        "total_rows": 0,
        "total_transactions": 0,
        "unique_buyers": 0,
        "total_gmv": 0.0,
        "total_nmv": 0.0,
        "avg_basket_size": 0.0,
        "hourly_transactions": {},
        "hourly_revenue": {},
        "top_brands_list": [],
        "top_categories_list": [],
        "salesperson_performance": [],
        "peak_hour": "19:00-20:00",
        "top_brand": "",
        "top_category": "",
    }
