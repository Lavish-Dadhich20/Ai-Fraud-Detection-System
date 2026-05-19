"""
geo_online.py
--------------
Online geocoding using OpenCage API.
Falls back gracefully if API fails.

Get API key from:
https://opencagedata.com
"""

import requests

API_KEY = "88a4f5bbc2a04db2b6b2d39592cd5cfe"   # ← PASTE YOUR KEY HERE


def resolve_location_online(name: str):
    """
    Resolve any location name to (lat, lon, display_name)
    using OpenCage Geocoding API.
    """
    url = "https://api.opencagedata.com/geocode/v1/json"

    params = {
        "q": name,
        "key": API_KEY,
        "limit": 1,
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if not data.get("results"):
            raise ValueError(f"Location '{name}' not found (API returned empty).")

        result = data["results"][0]
        lat = result["geometry"]["lat"]
        lon = result["geometry"]["lng"]
        display = result["formatted"]

        return lat, lon, display

    except Exception as e:
        raise ValueError(f"Online lookup failed for '{name}': {e}")