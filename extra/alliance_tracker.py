"""Fetch live aircraft near Fort Worth Alliance Airport (KAFW) from the OpenSky Network API."""

import json
import math
import os

import requests

# Fort Worth Alliance Airport (KAFW)
AIRPORT_LAT = 32.9876
AIRPORT_LON = -97.3188
RADIUS_MILES = 15  # default search radius when this script is run on its own

# OpenSky's live positions endpoint, and the OAuth2 server that issues the
# access tokens it requires
STATES_URL = "https://opensky-network.org/api/states/all"
TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
# Git-ignored file holding the OpenSky API client's id and secret. It lives in
# credentials/ at the project root, one level up from this extra/ folder.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(PROJECT_DIR, "credentials", "credentials.json")

# OpenSky returns each aircraft (a "state vector") as a plain list rather than
# a dict, to keep responses small. These names match the list positions, so
# dict(zip(STATE_FIELDS, s)) turns one into a readable dict.
# Units: altitudes in meters, velocity in m/s, true_track in degrees from north.
STATE_FIELDS = [
    "icao24", "callsign", "origin_country", "time_position", "last_contact",
    "longitude", "latitude", "baro_altitude", "on_ground", "velocity",
    "true_track", "vertical_rate", "sensors", "geo_altitude", "squawk",
    "spi", "position_source",
]


def bounding_box(lat, lon, radius_miles):
    """Return (lamin, lomin, lamax, lomax) for a box around a point."""
    # One degree of latitude is about 69 miles everywhere. Degrees of longitude
    # get narrower toward the poles, shrinking by cos(latitude), so more
    # degrees are needed to cover the same number of miles.
    dlat = radius_miles / 69.0
    dlon = radius_miles / (69.0 * math.cos(math.radians(lat)))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


def distance_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in statute miles."""
    # Haversine formula: the shortest distance over the Earth's surface
    r = 3958.8  # Earth's mean radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_credentials():
    """Read clientId/clientSecret from credentials/credentials.json."""
    with open(CREDENTIALS_PATH) as f:
        creds = json.load(f)
    return creds["clientId"], creds["clientSecret"]


def get_token():
    """Get an OAuth2 access token using the client credentials."""
    # The "client credentials" flow trades the id/secret for a short-lived
    # token, which is then sent as a Bearer header on API requests.
    # A new token is requested on every call, which keeps things simple at
    # the cost of one extra request per poll.
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
    """Return aircraft within radius_miles of KAFW as dicts, closest first."""
    # OpenSky only filters by a lat/lon box, so request the box that encloses
    # the circle, then drop the planes in its corners below.
    lamin, lomin, lamax, lomax = bounding_box(AIRPORT_LAT, AIRPORT_LON, radius_miles)
    headers = {"Authorization": f"Bearer {get_token()}"}

    resp = requests.get(
        STATES_URL,
        params={"lamin": lamin, "lomin": lomin, "lamax": lamax, "lomax": lomax},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    # "states" is null (not an empty list) when no aircraft are in the box
    states = resp.json().get("states") or []

    planes = []
    for s in states:
        plane = dict(zip(STATE_FIELDS, s))
        # Skip aircraft that are broadcasting but haven't reported a position
        if plane["latitude"] is None or plane["longitude"] is None:
            continue
        # Callsigns are padded with trailing spaces (e.g. "FDX1123 ") or missing
        plane["callsign"] = (plane["callsign"] or "").strip()
        plane["distance_miles"] = distance_miles(
            AIRPORT_LAT, AIRPORT_LON, plane["latitude"], plane["longitude"]
        )
        if plane["distance_miles"] <= radius_miles:
            planes.append(plane)

    planes.sort(key=lambda p: p["distance_miles"])
    return planes


def main():
    """Print a table of every aircraft near Alliance."""
    planes = get_planes_near_alliance()
    print(f"{len(planes)} aircraft within {RADIUS_MILES} mi of Alliance Airport (KAFW)\n")
    print(f"{'CALLSIGN':<10} {'ICAO24':<8} {'DIST mi':>7} {'ALT ft':>7} {'SPD kt':>6} {'HDG':>4}  STATUS")
    for p in planes:
        # Prefer barometric altitude (what pilots and ATC use), falling back to
        # GPS altitude. Any value can be missing, so show "-" when it is.
        alt_m = p["baro_altitude"] if p["baro_altitude"] is not None else p["geo_altitude"]
        alt_ft = f"{alt_m * 3.28084:.0f}" if alt_m is not None else "-"  # meters -> feet
        spd_kt = f"{p['velocity'] * 1.94384:.0f}" if p["velocity"] is not None else "-"  # m/s -> knots
        hdg = f"{p['true_track']:.0f}" if p["true_track"] is not None else "-"
        status = "ground" if p["on_ground"] else "airborne"
        print(
            f"{p['callsign'] or '?':<10} {p['icao24']:<8} {p['distance_miles']:>7.1f} "
            f"{alt_ft:>7} {spd_kt:>6} {hdg:>4}  {status}"
        )


if __name__ == "__main__":
    main()
