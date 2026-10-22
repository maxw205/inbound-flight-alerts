"""Fetch live aircraft near Fort Worth Alliance Airport (KAFW) from the OpenSky Network API."""

import json
import math
import os

import requests

# Fort Worth Alliance Airport (KAFW)
AIRPORT_LAT = 32.9876
AIRPORT_LON = -97.3188
RADIUS_MILES = 15

STATES_URL = "https://opensky-network.org/api/states/all"
TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")

# Field order of each state vector returned by /states/all
STATE_FIELDS = [
    "icao24", "callsign", "origin_country", "time_position", "last_contact",
    "longitude", "latitude", "baro_altitude", "on_ground", "velocity",
    "true_track", "vertical_rate", "sensors", "geo_altitude", "squawk",
    "spi", "position_source",
]


def bounding_box(lat, lon, radius_miles):
    """Return (lamin, lomin, lamax, lomax) for a box around a point."""
    dlat = radius_miles / 69.0
    dlon = radius_miles / (69.0 * math.cos(math.radians(lat)))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


def distance_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in statute miles."""
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_credentials():
    """Read clientId/clientSecret from credentials.json next to this script."""
    with open(CREDENTIALS_PATH) as f:
        creds = json.load(f)
    return creds["clientId"], creds["clientSecret"]


def get_token():
    """Get an OAuth2 access token using the client credentials."""
    client_id, client_secret = load_credentials()
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_planes_near_alliance(radius_miles=RADIUS_MILES):
    lamin, lomin, lamax, lomax = bounding_box(AIRPORT_LAT, AIRPORT_LON, radius_miles)
    headers = {"Authorization": f"Bearer {get_token()}"}

    resp = requests.get(
        STATES_URL,
        params={"lamin": lamin, "lomin": lomin, "lamax": lamax, "lomax": lomax},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    states = resp.json().get("states") or []

    planes = []
    for s in states:
        plane = dict(zip(STATE_FIELDS, s))
        if plane["latitude"] is None or plane["longitude"] is None:
            continue
        plane["callsign"] = (plane["callsign"] or "").strip()
        plane["distance_miles"] = distance_miles(
            AIRPORT_LAT, AIRPORT_LON, plane["latitude"], plane["longitude"]
        )
        if plane["distance_miles"] <= radius_miles:
            planes.append(plane)

    planes.sort(key=lambda p: p["distance_miles"])
    return planes


def main():
    planes = get_planes_near_alliance()
    print(f"{len(planes)} aircraft within {RADIUS_MILES} mi of Alliance Airport (KAFW)\n")
    print(f"{'CALLSIGN':<10} {'ICAO24':<8} {'DIST mi':>7} {'ALT ft':>7} {'SPD kt':>6} {'HDG':>4}  STATUS")
    for p in planes:
        alt_m = p["baro_altitude"] if p["baro_altitude"] is not None else p["geo_altitude"]
        alt_ft = f"{alt_m * 3.28084:.0f}" if alt_m is not None else "-"
        spd_kt = f"{p['velocity'] * 1.94384:.0f}" if p["velocity"] is not None else "-"
        hdg = f"{p['true_track']:.0f}" if p["true_track"] is not None else "-"
        status = "ground" if p["on_ground"] else "airborne"
        print(
            f"{p['callsign'] or '?':<10} {p['icao24']:<8} {p['distance_miles']:>7.1f} "
            f"{alt_ft:>7} {spd_kt:>6} {hdg:>4}  {status}"
        )


if __name__ == "__main__":
    main()
