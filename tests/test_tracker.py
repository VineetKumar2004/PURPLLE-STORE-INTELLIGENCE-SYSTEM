"""Tests for the StoreTracker virtual-tripwire logic."""
from app.tracker import StoreTracker


def test_entry_crossing():
    """Left→right crossing triggers an entry event."""
    t = StoreTracker()
    frame_w, frame_h = 1000, 500
    # First point: left of line (x=100, line at 120)
    assert t.update(1, 100, 250, 1, frame_w, frame_h) is None
    # Second point: right of line (x=130)
    ev = t.update(1, 130, 250, 2, frame_w, frame_h)
    assert ev is not None
    assert ev.event_type == "entry"
    assert ev.track_id == 1
    assert t.entry_count == 1


def test_exit_crossing():
    """Right→left crossing triggers an exit event."""
    t = StoreTracker()
    fw, fh = 1000, 500
    t.update(2, 130, 250, 1, fw, fh)
    ev = t.update(2, 100, 250, 2, fw, fh)
    assert ev is not None
    assert ev.event_type == "exit"
    assert t.exit_count == 1


def test_no_crossing():
    """Movement that doesn't cross the line produces no event."""
    t = StoreTracker()
    fw, fh = 1000, 500
    t.update(3, 200, 250, 1, fw, fh)
    ev = t.update(3, 210, 250, 2, fw, fh)
    assert ev is None


def test_reentry_detection():
    """A track that enters twice is flagged as re-entry."""
    t = StoreTracker()
    fw, fh = 1000, 500
    # First entry
    t.update(10, 100, 250, 1, fw, fh)
    e1 = t.update(10, 130, 250, 2, fw, fh)
    assert e1.event_type == "entry"
    assert e1.meta.get("is_reentry") is False

    # Exit
    t.update(10, 130, 250, 3, fw, fh)
    t.update(10, 100, 250, 4, fw, fh)

    # Re-entry
    t.update(10, 100, 250, 5, fw, fh)
    e2 = t.update(10, 130, 250, 6, fw, fh)
    assert e2.event_type == "entry"
    assert e2.meta.get("is_reentry") is True
    assert t.reentry_count == 1


def test_zone_classification():
    assert StoreTracker.classify_zone(50, 1000) == "entrance"
    assert StoreTracker.classify_zone(300, 1000) == "floor_left"
    assert StoreTracker.classify_zone(600, 1000) == "floor_center"
    assert StoreTracker.classify_zone(900, 1000) == "counter"


def test_staff_detection():
    """A track present in >75% of frames should be classified as staff."""
    t = StoreTracker()
    fw, fh = 1000, 500
    # Simulate 100 frames of updates for track 99
    for f in range(1, 101):
        t.update(99, 500, 250, f, fw, fh)

    staff_ids, _ = t.finalize(total_frames=300, fps=25.0)  # 300/3=100 effective
    assert 99 in staff_ids
