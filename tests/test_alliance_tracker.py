"""Tests for extra/alliance_tracker.py. OpenSky requests are replaced with fakes."""

import pytest

from extra import alliance_tracker as at


def test_distance_to_self_is_zero():
    assert at.distance_miles(at.AIRPORT_LAT, at.AIRPORT_LON, at.AIRPORT_LAT, at.AIRPORT_LON) == 0


def test_distance_alliance_to_dfw():
    # KAFW to KDFW is roughly 18 statute miles
    assert at.distance_miles(at.AIRPORT_LAT, at.AIRPORT_LON, 32.8998, -97.0403) == pytest.approx(17.5, abs=1.5)


def test_bounding_box_contains_radius():
    lamin, lomin, lamax, lomax = at.bounding_box(at.AIRPORT_LAT, at.AIRPORT_LON, 15)
    # The box edges should be about 15 miles from the center
    assert at.distance_miles(at.AIRPORT_LAT, at.AIRPORT_LON, lamax, at.AIRPORT_LON) == pytest.approx(15, rel=0.01)
    assert at.distance_miles(at.AIRPORT_LAT, at.AIRPORT_LON, at.AIRPORT_LAT, lomax) == pytest.approx(15, rel=0.01)
    assert lamin < at.AIRPORT_LAT < lamax and lomin < at.AIRPORT_LON < lomax


def state(callsign, lat, lon):
    """Build an OpenSky state vector list with the given callsign and position."""
    s = [None] * len(at.STATE_FIELDS)
    s[at.STATE_FIELDS.index("callsign")] = callsign
    s[at.STATE_FIELDS.index("latitude")] = lat
    s[at.STATE_FIELDS.index("longitude")] = lon
    return s


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


@pytest.fixture
def opensky(monkeypatch):
    """Serve the given states from a fake OpenSky API."""
    monkeypatch.setattr(at, "get_token", lambda: "token")

    def serve(states):
        monkeypatch.setattr(at.requests, "get", lambda *a, **kw: FakeResponse({"states": states}))

    return serve


def test_get_planes_filters_sorts_and_cleans(opensky):
    lat, lon = at.AIRPORT_LAT, at.AIRPORT_LON
    lamin, lomin, lamax, lomax = at.bounding_box(lat, lon, 15)
    opensky([
        state("FDX1123 ", lat + 0.1, lon),       # ~7 mi, trailing space
        state(None, lat + 0.01, lon),             # ~0.7 mi, no callsign
        state("CORNER", lamax - 0.01, lomax - 0.01),  # inside the box, outside the circle
        state("NOPOS", None, None),               # no position reported
    ])
    planes = at.get_planes_near_alliance(15)
    assert [p["callsign"] for p in planes] == ["", "FDX1123"]


def test_get_planes_handles_null_states(opensky):
    opensky(None)
    assert at.get_planes_near_alliance(15) == []
