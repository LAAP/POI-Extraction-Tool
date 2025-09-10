import requests
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

def geocode_address(address):
    """
    Geocodes an address to latitude and longitude.
    """
    try:
        geolocator = Nominatim(user_agent="poi_tool", timeout=10)
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except Exception as e:
        print(f"Error geocoding address: {e}")
        return None, None

def get_pois(latitude, longitude, distance_km=0.5):
    """
    Fetch POIs using the Overpass API within a square bounding box
    centered at (latitude, longitude) and extending distance_km in each
    cardinal direction.

    Returns a pandas DataFrame with columns: name, category, latitude,
    longitude, distance_from_center_km.
    """
    # Compute bounding box (south, west, north, east)
    north = geodesic(kilometers=distance_km).destination((latitude, longitude), 0).latitude
    south = geodesic(kilometers=distance_km).destination((latitude, longitude), 180).latitude
    east = geodesic(kilometers=distance_km).destination((latitude, longitude), 90).longitude
    west = geodesic(kilometers=distance_km).destination((latitude, longitude), 270).longitude

    south_west_north_east = (south, west, north, east)

    # Define categories of interest
    categories = ["amenity", "shop", "leisure", "tourism", "historic"]

    # Build Overpass QL query. Use out center to get centroids for ways/relations
    bbox_str = f"{south_west_north_east[0]},{south_west_north_east[1]},{south_west_north_east[2]},{south_west_north_east[3]}"
    selectors = []
    for key in categories:
        selectors.append(f"node[\"{key}\"]({bbox_str});")
        selectors.append(f"way[\"{key}\"]({bbox_str});")
        selectors.append(f"relation[\"{key}\"]({bbox_str});")
    union = "\n  ".join(selectors)

    overpass_query = f"""
    [out:json][timeout:30];
    (
      {union}
    );
    out center tags;
    """.strip()

    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": overpass_query},
            headers={"User-Agent": "poi_tool/1.0 (contact: example@example.com)"},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        elements = data.get("elements", [])
        if not elements:
            return pd.DataFrame()

        results = []
        for el in elements:
            tags = el.get("tags", {})

            # Determine coordinates for node vs way/relation
            if el.get("type") == "node":
                poi_lat = el.get("lat")
                poi_lon = el.get("lon")
            else:
                center = el.get("center") or {}
                poi_lat = center.get("lat")
                poi_lon = center.get("lon")

            if poi_lat is None or poi_lon is None:
                continue

            # Determine best category present in tags
            category = "N/A"
            for cat in categories:
                if cat in tags:
                    category = cat
                    break

            name = tags.get("name", "N/A")
            dist_km = geodesic((latitude, longitude), (poi_lat, poi_lon)).km

            results.append({
                "name": name,
                "category": category,
                "latitude": poi_lat,
                "longitude": poi_lon,
                "distance_from_center_km": dist_km,
            })

        return pd.DataFrame(results)
    except Exception as e:
        print(f"An error occurred while fetching POIs: {e}")
        return pd.DataFrame()
