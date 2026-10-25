"""Tests for flightaware.py's pure helpers (no AeroAPI calls)."""

import flightaware as fa


def flight(name, off=None, on=None, cancelled=False):
    return {"name": name, "actual_off": off, "actual_on": on, "cancelled": cancelled}


def test_pick_prefers_airborne_flight():
    flights = [flight("future"), flight("airborne", off="t"), flight("landed", off="t", on="t")]
    assert fa.pick_current_flight(flights)["name"] == "airborne"


def test_pick_falls_back_to_latest_departed():
    flights = [flight("future"), flight("landed-recent", off="t", on="t"), flight("landed-old", off="t", on="t")]
    assert fa.pick_current_flight(flights)["name"] == "landed-recent"


def test_pick_next_scheduled_when_nothing_has_flown():
    flights = [flight("later"), flight("next")]
    assert fa.pick_current_flight(flights)["name"] == "next"


def test_pick_empty():
    assert fa.pick_current_flight([]) is None


def test_local_time_converts_utc():
    assert fa.local_time("2026-01-15T18:30:00Z", "America/Chicago") == "Thu Jan 15 12:30 PM CST"


def test_local_time_missing():
    assert fa.local_time(None, "UTC") == "-"
