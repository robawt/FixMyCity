"""Synthetic Hyderabad context dataset. ALL data here is SYNTHETIC demo data,
never live municipal data. Every API response carrying it must say so."""
import math
from datetime import datetime

SYNTHETIC_LABEL = "SYNTHETIC demo data — not live municipal data"

# name, lat, lng, jurisdiction key, road_type, pois, flood_hotspot
ZONES = [
    {"name": "Hitech City",   "lat": 17.4435, "lng": 78.3772, "jurisdiction": "cyberabad",
     "road_type": "arterial", "pois": {"transit": True, "hospital": False, "school": False}, "flood_hotspot": True},
    {"name": "Gachibowli",    "lat": 17.4400, "lng": 78.3489, "jurisdiction": "cyberabad",
     "road_type": "arterial", "pois": {"transit": False, "hospital": True, "school": True}, "flood_hotspot": False},
    {"name": "Madhapur",      "lat": 17.4483, "lng": 78.3915, "jurisdiction": "cyberabad",
     "road_type": "arterial", "pois": {"transit": True, "hospital": False, "school": False}, "flood_hotspot": False},
    {"name": "Banjara Hills", "lat": 17.4156, "lng": 78.4347, "jurisdiction": "ghmc",
     "road_type": "arterial", "pois": {"transit": False, "hospital": True, "school": False}, "flood_hotspot": False},
    {"name": "Ameerpet",      "lat": 17.4375, "lng": 78.4482, "jurisdiction": "ghmc",
     "road_type": "arterial", "pois": {"transit": True, "hospital": False, "school": True}, "flood_hotspot": False},
    {"name": "Secunderabad",  "lat": 17.4399, "lng": 78.4983, "jurisdiction": "ghmc",
     "road_type": "arterial", "pois": {"transit": True, "hospital": True, "school": False}, "flood_hotspot": False},
    {"name": "Malkajgiri",    "lat": 17.4528, "lng": 78.5270, "jurisdiction": "malkajgiri",
     "road_type": "collector", "pois": {"transit": True, "hospital": False, "school": True}, "flood_hotspot": False},
    {"name": "Dilsukhnagar",  "lat": 17.3688, "lng": 78.5247, "jurisdiction": "ghmc",
     "road_type": "collector", "pois": {"transit": True, "hospital": False, "school": True}, "flood_hotspot": True},
    {"name": "LB Nagar",      "lat": 17.3457, "lng": 78.5522, "jurisdiction": "ghmc",
     "road_type": "arterial", "pois": {"transit": True, "hospital": True, "school": False}, "flood_hotspot": False},
    {"name": "Charminar",     "lat": 17.3616, "lng": 78.4747, "jurisdiction": "ghmc",
     "road_type": "local", "pois": {"transit": False, "hospital": True, "school": True}, "flood_hotspot": True},
]

WEATHER = {"condition": "light rain", "rainfall_mm_hr": 2.5, "synthetic": True}


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def traffic_level(hour: int) -> str:
    if hour in (8, 9, 10, 17, 18, 19, 20):
        return "high"
    if hour >= 23 or hour <= 5:
        return "low"
    return "moderate"


def get_context(lat: float, lng: float, ts: datetime | None = None) -> dict:
    ts = ts or datetime.now()
    zone = min(ZONES, key=lambda z: haversine_m(lat, lng, z["lat"], z["lng"]))
    dist = haversine_m(lat, lng, zone["lat"], zone["lng"])
    in_zone = dist <= 3000
    return {
        "zone": zone["name"] if in_zone else "Unknown area",
        "jurisdiction": zone["jurisdiction"] if in_zone else "ghmc",
        "road_type": zone["road_type"] if in_zone else "local",
        "pois": zone["pois"] if in_zone else {"school": False, "hospital": False, "transit": False},
        "flood_hotspot": zone["flood_hotspot"] if in_zone else False,
        "traffic": traffic_level(ts.hour),
        "weather": WEATHER,
        "synthetic": True,
        "label": SYNTHETIC_LABEL,
    }
