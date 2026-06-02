"""
StoreTracker — virtual-tripwire crossing detector.

The tracker maintains per-track coordinate history and evaluates each
centroid against a vertical entry line at ENTRY_LINE_RATIO (12 %) of
frame width.  Crossings from left→right are entries; right→left are exits.

Zone classification:
  entrance     x < 15 %
  floor_left   15 – 50 %
  floor_center 50 – 80 %
  counter      > 80 %
"""
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from app.events import Event


class StoreTracker:
    """Real-time visitor tracker with tripwire, re-entry, and staff logic."""

    ENTRY_LINE_RATIO = 0.12          # tripwire at 12 % of frame width
    STAFF_PRESENCE_THRESHOLD = 0.75  # >75 % of processed frames → staff
    MIN_STAFF_UPDATES = 30           # minimum observations

    def __init__(self):
        # track_id → list of (cx, cy, frame_no)
        self.tracks: Dict[int, List[Tuple[float, float, int]]] = defaultdict(list)
        self.seen_visitor_ids: Set[int] = set()
        self.entry_count = 0
        self.exit_count = 0
        self.reentry_count = 0

    # ------------------------------------------------------------------
    # Zone helpers
    # ------------------------------------------------------------------
    @staticmethod
    def classify_zone(cx: float, frame_width: float) -> str:
        ratio = cx / frame_width
        if ratio < 0.15:
            return "entrance"
        if ratio < 0.50:
            return "floor_left"
        if ratio < 0.80:
            return "floor_center"
        return "counter"

    # ------------------------------------------------------------------
    # Core update — called once per tracked centroid per frame
    # ------------------------------------------------------------------
    def update(
        self,
        track_id: int,
        cx: float,
        cy: float,
        frame_no: int,
        frame_width: float,
        frame_height: float,
    ) -> Optional[Event]:
        """
        Append the centroid and check for a tripwire crossing.
        Returns an Event if a crossing was detected, else None.
        """
        history = self.tracks[track_id]
        history.append((cx, cy, frame_no))

        if len(history) < 2:
            return None

        line_x = self.ENTRY_LINE_RATIO * frame_width
        prev_cx = history[-2][0]

        # Crossing check
        crossed_right = prev_cx < line_x <= cx   # entry
        crossed_left  = prev_cx > line_x >= cx   # exit

        if not (crossed_right or crossed_left):
            return None

        zone = self.classify_zone(cx, frame_width)

        if crossed_right:
            is_reentry = track_id in self.seen_visitor_ids
            if is_reentry:
                self.reentry_count += 1
            else:
                self.entry_count += 1
                self.seen_visitor_ids.add(track_id)
            return Event(
                event_type="entry",
                track_id=track_id,
                frame_number=frame_no,
                x=cx, y=cy,
                zone=zone,
                meta={"is_reentry": is_reentry},
            )

        # crossed_left → exit
        self.exit_count += 1
        return Event(
            event_type="exit",
            track_id=track_id,
            frame_number=frame_no,
            x=cx, y=cy,
            zone=zone,
        )

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------
    def finalize(
        self, total_frames: int, fps: float = 25.0
    ) -> Tuple[Set[int], Dict[int, float]]:
        """
        After all frames are processed:
          1. Identify staff (present in >75 % of sampled frames).
          2. Compute per-track dwell times in seconds.
        Returns (staff_ids, dwell_seconds_by_track).
        """
        # effective frames = total / 3 because we sample every 3rd frame
        effective_frames = max(total_frames / 3, 1)

        staff_ids: Set[int] = set()
        dwell: Dict[int, float] = {}

        for tid, pts in self.tracks.items():
            n_updates = len(pts)
            if n_updates >= self.MIN_STAFF_UPDATES:
                presence_ratio = n_updates / effective_frames
                if presence_ratio >= self.STAFF_PRESENCE_THRESHOLD:
                    staff_ids.add(tid)

            if n_updates >= 2:
                first_frame = pts[0][2]
                last_frame  = pts[-1][2]
                dwell[tid] = (last_frame - first_frame) / fps

        return staff_ids, dwell
