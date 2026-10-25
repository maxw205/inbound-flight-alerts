"""Tests for alert.py. Network calls (OpenSky, Twilio) are replaced with fakes."""

import os

import pytest

import alert


def make_plane(callsign="FDX1123", distance=40.0, on_ground=False,
               baro=3000.0, geo=None, velocity=200.0):
    return {
        "callsign": callsign,
        "distance_miles": distance,
        "on_ground": on_ground,
        "baro_altitude": baro,
        "geo_altitude": geo,
        "velocity": velocity,
    }


def test_twilio_path_points_into_credentials_folder():
    assert os.path.basename(os.path.dirname(alert.TWILIO_PATH)) == "credentials"


@pytest.mark.parametrize("ident, expected", [
    ("FX1123", "FDX1123"),
    ("EM7275", "CFS7275"),
    ("AA100", "AA100"),  # unknown airline codes pass through unchanged
])
def test_to_icao_callsign(ident, expected):
    assert alert.to_icao_callsign(ident) == expected


def test_alert_message_full():
    # 3000 m = 9,843 ft; 200 m/s = 389 kt = 447 mph; 40 mi at 447 mph = ~5 min
    msg = alert.alert_message("FX1123", make_plane())
    assert msg == "FX1123 is 40 mi from Alliance, 9,843 ft, 389 kt, ~5 min out."


def test_alert_message_falls_back_to_geo_altitude():
    msg = alert.alert_message("FX1123", make_plane(baro=None, geo=1000.0))
    assert "3,281 ft" in msg


def test_alert_message_missing_altitude_and_speed():
    msg = alert.alert_message("FX1123", make_plane(baro=None, geo=None, velocity=None))
    assert msg == "FX1123 is 40 mi from Alliance."


@pytest.fixture
def sent(monkeypatch):
    """Capture texts instead of sending them through Twilio."""
    texts = []
    monkeypatch.setattr(alert, "send_text", texts.append)
    return texts


def use_planes(monkeypatch, planes):
    monkeypatch.setattr(alert, "get_planes_near_alliance", lambda radius: planes)


def test_check_once_alerts_tracked_airborne_flight(monkeypatch, sent):
    use_planes(monkeypatch, [make_plane()])
    alerted = {}
    alert.check_once({"FDX1123": "FX1123"}, alerted)
    assert len(sent) == 1 and sent[0].startswith("FX1123")
    assert "FX1123" in alerted


def test_check_once_ignores_untracked_and_grounded(monkeypatch, sent):
    use_planes(monkeypatch, [make_plane(callsign="UAL1"), make_plane(on_ground=True)])
    alert.check_once({"FDX1123": "FX1123"}, {})
    assert sent == []


def test_check_once_respects_realert_window(monkeypatch, sent):
    use_planes(monkeypatch, [make_plane()])
    now = 1_000_000.0
    monkeypatch.setattr(alert.time, "time", lambda: now)
    alerted = {"FX1123": now - 3600}  # texted an hour ago
    alert.check_once({"FDX1123": "FX1123"}, alerted)
    assert sent == []

    alerted["FX1123"] = now - alert.REALERT_HOURS * 3600 - 1  # window expired
    alert.check_once({"FDX1123": "FX1123"}, alerted)
    assert len(sent) == 1


def test_send_text_raises_on_twilio_error(monkeypatch, tmp_path):
    cfg = tmp_path / "twilio.json"
    cfg.write_text('{"accountSid": "AC1", "authToken": "t", "fromNumber": "+1", "toNumber": "+2"}')
    monkeypatch.setattr(alert, "TWILIO_PATH", str(cfg))

    class FakeResponse:
        ok = False

        def json(self):
            return {"code": 21211, "message": "Invalid 'To' number", "more_info": "url"}

    monkeypatch.setattr(alert.requests, "post", lambda *a, **kw: FakeResponse())
    with pytest.raises(RuntimeError, match="21211"):
        alert.send_text("hi")
