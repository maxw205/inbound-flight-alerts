"""Look up details on a specific flight using the FlightAware AeroAPI."""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

AEROAPI_URL = "https://aeroapi.flightaware.com/aeroapi"
API_KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aeroAPIkey.txt")
TRACKED_FLIGHTS = [
    "EM7275",  # Empire Airlines 7275
    "FX1123",  # FedEx 1123
    "FX1106",  # FedEx 1106
]


def load_api_key():
    with open(API_KEY_PATH) as f:
        return f.read().strip()


def get_flights(ident):
    """Return recent and scheduled flights for an ident (e.g. EM7275 or CFS7275), newest first."""
    resp = requests.get(
        f"{AEROAPI_URL}/flights/{ident}",
        headers={"x-apikey": load_api_key()},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("flights", [])


def pick_current_flight(flights):
    """Prefer a flight in the air, then the most recent one that has departed, then the next scheduled."""
    for f in flights:
        if f["actual_off"] and not f["actual_on"] and not f["cancelled"]:
            return f
    for f in flights:
        if f["actual_off"]:
            return f
    return flights[-1] if flights else None


def local_time(iso, tz):
    """Format an ISO UTC timestamp in the airport's local timezone."""
    if not iso:
        return "-"
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.astimezone(ZoneInfo(tz)).strftime("%a %b %d %I:%M %p %Z")


def print_flight(f):
    origin, dest = f["origin"] or {}, f["destination"] or {}
    otz = origin.get("timezone") or "UTC"
    dtz = dest.get("timezone") or "UTC"

    print(f"Flight:      {f['ident_iata'] or f['ident']} ({f['ident_icao']})")
    print(f"Status:      {f['status']} ({f['progress_percent']}% complete)")
    print(f"Aircraft:    {f['aircraft_type']}  reg {f['registration']}")
    print(f"From:        {origin.get('name')} ({origin.get('code_iata')}), {origin.get('city')}")
    print(f"To:          {dest.get('name')} ({dest.get('code_iata')}), {dest.get('city')}")
    print(f"Scheduled:   departs {local_time(f['scheduled_off'], otz)}")
    print(f"             arrives {local_time(f['scheduled_on'], dtz)}")
    print(f"Actual/Est:  departs {local_time(f['actual_off'] or f['estimated_off'], otz)}")
    print(f"             arrives {local_time(f['actual_on'] or f['estimated_on'], dtz)}")
    if f["departure_delay"] or f["arrival_delay"]:
        print(f"Delay:       departure {(f['departure_delay'] or 0) // 60} min, "
              f"arrival {(f['arrival_delay'] or 0) // 60} min")
    if f["route"]:
        print(f"Route:       {f['route']}")
    if f["route_distance"]:
        print(f"Distance:    {f['route_distance']} mi")
    if f["filed_altitude"]:
        print(f"Filed:       FL{f['filed_altitude']:03d} at {f['filed_airspeed']} kt")


def show_flight(ident):
    flights = get_flights(ident)
    if not flights:
        print(f"No flights found for {ident}")
        return

    print_flight(pick_current_flight(flights))

    print(f"\nAll {len(flights)} flights on record for {ident}:")
    for f in flights:
        origin, dest = f["origin"] or {}, f["destination"] or {}
        when = local_time(f["scheduled_off"], origin.get("timezone") or "UTC")
        print(f"  {when:<26} {origin.get('code_iata')} -> {dest.get('code_iata')}  "
              f"{f['registration'] or '-':<8} {f['status']}")


def main():
    idents = sys.argv[1:] or TRACKED_FLIGHTS
    for i, ident in enumerate(idents):
        if i:
            print("\n" + "=" * 60 + "\n")
        show_flight(ident)


if __name__ == "__main__":
    main()
