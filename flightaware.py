"""Look up details on a specific flight using the FlightAware AeroAPI."""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

AEROAPI_URL = "https://aeroapi.flightaware.com/aeroapi"
# The API key is kept in the git-ignored credentials/ folder so it never gets committed
API_KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials", "aeroAPIkey.txt")

# Flights to watch, as IATA idents (2-letter airline code + flight number).
# alert.py also uses this list to decide which planes to text about.
TRACKED_FLIGHTS = [
    "EM7275",  # Empire Airlines 7275
    "FX1123",  # FedEx 1123
    "FX1106",  # FedEx 1106
]


def load_api_key():
    """Read the AeroAPI key, stripping the trailing newline most editors add."""
    with open(API_KEY_PATH) as f:
        return f.read().strip()


def get_flights(ident):
    """Return recent and scheduled flights for an ident (e.g. EM7275 or CFS7275), newest first."""
    # AeroAPI authenticates with the key in an "x-apikey" header. One flight
    # number usually maps to several flights (one per day, over roughly the
    # past and next few days), so this returns a list.
    resp = requests.get(
        f"{AEROAPI_URL}/flights/{ident}",
        headers={"x-apikey": load_api_key()},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("flights", [])


def pick_current_flight(flights):
    """Prefer a flight in the air, then the most recent one that has departed, then the next scheduled."""
    # "actual_off" is takeoff time and "actual_on" is landing time, so a flight
    # that has taken off but not landed is in the air right now.
    for f in flights:
        if f["actual_off"] and not f["actual_on"] and not f["cancelled"]:
            return f
    # The list is newest first, so the first flight that took off is the latest one
    for f in flights:
        if f["actual_off"]:
            return f
    # Nothing has flown yet, so every flight is in the future. Since the list
    # is newest first, the last one is the earliest scheduled, i.e. the next
    # to depart.
    return flights[-1] if flights else None


def local_time(iso, tz):
    """Format an ISO UTC timestamp in the airport's local timezone."""
    if not iso:
        return "-"
    # AeroAPI times end in "Z" (UTC). fromisoformat only accepts "Z" on
    # Python 3.11+, so swap it for the equivalent "+00:00" offset.
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.astimezone(ZoneInfo(tz)).strftime("%a %b %d %I:%M %p %Z")


def print_flight(f):
    """Print a detailed summary of one flight."""
    # origin/destination can be null (e.g. a diverted or unknown airport), so
    # fall back to empty dicts and UTC to keep the lookups below from crashing.
    # Departure times are shown in the origin's timezone, arrivals in the destination's.
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
    # Delays come back in seconds; show them in minutes
    if f["departure_delay"] or f["arrival_delay"]:
        print(f"Delay:       departure {(f['departure_delay'] or 0) // 60} min, "
              f"arrival {(f['arrival_delay'] or 0) // 60} min")
    if f["route"]:
        print(f"Route:       {f['route']}")
    if f["route_distance"]:
        print(f"Distance:    {f['route_distance']} mi")
    # filed_altitude is in hundreds of feet, which is how flight levels are
    # written (350 -> FL350 = 35,000 ft)
    if f["filed_altitude"]:
        print(f"Filed:       FL{f['filed_altitude']:03d} at {f['filed_airspeed']} kt")


def show_flight(ident):
    """Print details for the most relevant flight, then a one-line list of every flight on record."""
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
    # Usage: python flightaware.py [IDENT ...]
    # With no arguments, look up every flight in TRACKED_FLIGHTS
    idents = sys.argv[1:] or TRACKED_FLIGHTS
    for i, ident in enumerate(idents):
        if i:  # put a divider between flights, but not before the first one
            print("\n" + "=" * 60 + "\n")
        show_flight(ident)


if __name__ == "__main__":
    main()
