"""Print all FedEx aircraft currently flying over the United States, using the OpenSky Network API."""

import requests

from main import STATE_FIELDS, STATES_URL, get_token

FEDEX_CALLSIGN_PREFIX = "FDX"

# (lamin, lomin, lamax, lomax) boxes covering the US
US_REGIONS = {
    "Contiguous US": (24.5, -125.0, 49.5, -66.9),
    "Alaska": (51.0, -180.0, 71.5, -129.0),
    "Hawaii": (18.5, -161.0, 22.5, -154.5),
}


def us_region(lat, lon):
    """Return the US region name containing the point, or None."""
    for name, (lamin, lomin, lamax, lomax) in US_REGIONS.items():
        if lamin <= lat <= lamax and lomin <= lon <= lomax:
            return name
    return None


def get_fedex_planes_in_us():
    # One worldwide query costs the same API credits as a single US-sized box,
    # so fetch everything once and filter locally.
    resp = requests.get(
        STATES_URL,
        headers={"Authorization": f"Bearer {get_token()}"},
        timeout=30,
    )
    resp.raise_for_status()
    states = resp.json().get("states") or []

    planes = []
    for s in states:
        plane = dict(zip(STATE_FIELDS, s))
        plane["callsign"] = (plane["callsign"] or "").strip()
        if not plane["callsign"].startswith(FEDEX_CALLSIGN_PREFIX):
            continue
        if plane["latitude"] is None or plane["longitude"] is None:
            continue
        plane["region"] = us_region(plane["latitude"], plane["longitude"])
        if plane["region"]:
            planes.append(plane)

    planes.sort(key=lambda p: p["callsign"])
    return planes


def main():
    planes = get_fedex_planes_in_us()
    print(f"{len(planes)} FedEx aircraft over the United States\n")
    print(f"{'CALLSIGN':<10} {'ICAO24':<8} {'LAT':>8} {'LON':>9} {'ALT ft':>7} {'SPD kt':>6} {'HDG':>4}  STATUS    REGION")
    for p in planes:
        alt_m = p["baro_altitude"] if p["baro_altitude"] is not None else p["geo_altitude"]
        alt_ft = f"{alt_m * 3.28084:.0f}" if alt_m is not None else "-"
        spd_kt = f"{p['velocity'] * 1.94384:.0f}" if p["velocity"] is not None else "-"
        hdg = f"{p['true_track']:.0f}" if p["true_track"] is not None else "-"
        status = "ground" if p["on_ground"] else "airborne"
        print(
            f"{p['callsign']:<10} {p['icao24']:<8} {p['latitude']:>8.3f} {p['longitude']:>9.3f} "
            f"{alt_ft:>7} {spd_kt:>6} {hdg:>4}  {status:<9} {p['region']}"
        )


if __name__ == "__main__":
    main()
