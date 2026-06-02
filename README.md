# Purplle Store Intelligence System

This repository implements the **Store Intelligence System** for the Purplle Tech Challenge 2026 (Round 2). The system processes CCTV camera video streams to count footfalls, tracks zones (shelves and counters), filters staff via presence heuristics, and integrates store transactions to calculate conversion rates and raise operational alerts.

---

## Quick Start

### 1. Set Up Files
Place your video file and sales CSV inside the `input/` folder:
```bash
git clone <repo>
cd purplle-store-intelligence

# Copy files (if you have them)
cp /path/to/video.mp4 input/video.mp4
cp /path/to/sales.csv input/sales.csv
```

### 2. Run with Docker Compose
```bash
docker compose up --build
```
The pipeline automatically runs on startup. Once complete, the FastAPI server launches on `http://localhost:8000`.

---

## Execution Without a Video File
If no video file is provided at `input/video.mp4`, the pipeline automatically falls back to **Synthetic Mode**. It generates realistic, Poisson-distributed customer entry/exit events that match the real Brigade Road transactions distribution, allowing all API endpoints to return valid data.

---

## API Endpoints

All responses are returned as structured JSON.

*   `GET /health`: Returns status checks and current pipeline execution state.
*   `GET /metrics`: Returns core retail parameters (conversion rates, footfall, average dwell, peak hours, total transactions).
*   `GET /funnel`: Returns a 4-stage monotonic marketing funnel (Passers-by → Entrants → Engaged → Buyers).
*   `GET /events`: Returns paginated entry/exit logs with filters for `event_type` and `zone`.
*   `GET /anomalies`: Returns operational warnings (e.g., overcrowding, low conversion, telemetry outages).
*   `GET /hourly`: Returns hourly visitor, invoice, and GMV breakdown maps.
*   `GET /zones`: Returns traffic shares and dwell averages by shelf zone.
*   `GET /sales/summary`: Returns salesperson totals, top categories, and top brand GMVs.

---

## Architecture Overview
The system uses **YOLOv8n** detection combined with **ByteTrack** to follow visitors. Coordinates are fed to a virtual tripwire check to record entries and exits. Business statistics are cached in an SQLite database and queried in real-time by a **FastAPI** server.

---

## Running Tests

Run the test suite inside the Docker container:
```bash
docker compose run store-intelligence pytest tests/ -v
```

To run tests locally:
```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```
