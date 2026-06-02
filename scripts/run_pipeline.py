"""Pipeline runner script — invoked by entrypoint.sh before starting the API."""
import os
from app.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline(
        video_path=os.environ.get("VIDEO_PATH", "input/video.mp4"),
        sales_path=os.environ.get("SALES_PATH", "input/sales.csv"),
        db_path=os.environ.get("DB_PATH", "store_intelligence.db"),
        store_id=os.environ.get("STORE_ID", "ST1008"),
        video_date=os.environ.get("VIDEO_DATE", "2026-04-10"),
    )
