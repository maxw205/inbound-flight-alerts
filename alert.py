"""Text me (via Twilio) when a tracked flight gets near Fort Worth Alliance Airport (KAFW)."""

import json
import os
import sys
import time

import requests

from flightaware import TRACKED_FLIGHTS
from extra.alliance_tracker import get_planes_near_alliance   # was: from main import ...
TWILIO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials", "twilio.json")

ALERT_RADIUS_MILES = 75
POLL_SECONDS = 60
REALERT_HOURS = 6  # don't text about the same flight again within this window

TWILIO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twilio.json")

# OpenSky reports ICAO callsigns (FDX1123), FlightAware idents here are IATA (FX1123)
IATA_TO_ICAO_AIRLINE = {
    "EM": "CFS",  # Empire Airlines
    "FX": "FDX",  # FedEx
}


def to_icao_callsign(ident):
    prefix, number = ident[:2], ident[2:]
    return IATA_TO_ICAO_AIRLINE.get(prefix, prefix) + number


def send_text(body):
    with open(TWILIO_PATH) as f:
        cfg = json.load(f)
    resp = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{cfg['accountSid']}/Messages.json",
        auth=(cfg["accountSid"], cfg["authToken"]),
        data={"From": cfg["fromNumber"], "To": cfg["toNumber"], "Body": body},
        timeout=15,
    )
    if not resp.ok:
        err = resp.json()
        raise RuntimeError(f"Twilio error {err.get('code')}: {err.get('message')} ({err.get('more_info')})")


def alert_message(ident, plane):
    alt_m = plane["baro_altitude"] if plane["baro_altitude"] is not None else plane["geo_altitude"]
    parts = [f"{ident} is {plane['distance_miles']:.0f} mi from Alliance"]
    if alt_m is not None:
        parts.append(f"{alt_m * 3.28084:,.0f} ft")
    if plane["velocity"]:
        mph = plane["velocity"] * 2.23694
        parts.append(f"{plane['velocity'] * 1.94384:.0f} kt")
        parts.append(f"~{plane['distance_miles'] / mph * 60:.0f} min out")
    return ", ".join(parts) + "."


def check_once(tracked, alerted):
    """Poll OpenSky once and text about any tracked flight newly within range."""
    now = time.time()
    for plane in get_planes_near_alliance(ALERT_RADIUS_MILES):
        ident = tracked.get(plane["callsign"])
        if not ident or plane["on_ground"]:
            continue
        if now - alerted.get(ident, 0) < REALERT_HOURS * 3600:
            continue
        msg = alert_message(ident, plane)
        send_text(msg)
        alerted[ident] = now
        print(f"{time.strftime('%H:%M:%S')} texted: {msg}")


def main():
    if "--test" in sys.argv:
        send_text("Test from Inbound Flight Alerts: Twilio is set up.")
        print("Test text sent.")
        return

    tracked = {to_icao_callsign(i): i for i in TRACKED_FLIGHTS}
    alerted = {}
    print(f"Watching {', '.join(TRACKED_FLIGHTS)} within {ALERT_RADIUS_MILES} mi of KAFW "
          f"(checking every {POLL_SECONDS}s). Ctrl+C to stop.")
    while True:
        try:
            check_once(tracked, alerted)
        except requests.RequestException as e:
            print(f"{time.strftime('%H:%M:%S')} request failed, will retry: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
