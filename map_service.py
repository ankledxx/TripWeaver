import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class MapServiceError(Exception):
    """Show a readable map service error to the Flask route."""


class MapService:
    """Search places and create routes using OpenStreetMap services."""

    def __init__(self):
        self.place_cache = {}
        self.route_cache = {}
        self.place_cache_seconds = 3600
        self.route_cache_seconds = 86400

    def search_places(self, search_text, destination):
        """Return a small list of places inside the trip destination."""

        cache_key = (search_text.casefold(), destination.casefold())
        cached_places = self.get_cached(self.place_cache, cache_key, self.place_cache_seconds)
        if cached_places is not None:
            return cached_places

        search_query = search_text + ", " + destination
        parameters = {
            "q": search_query,
            "format": "jsonv2",
            "limit": 5,
            "addressdetails": 1,
            "accept-language": "en",
        }
        url = "https://nominatim.openstreetmap.org/search?" + urlencode(parameters)
        try:
            response = self.request_json(url)
        except MapServiceError:
            raise
        except Exception:
            raise MapServiceError(
                "The place service is unavailable. Check your internet connection and try again."
            )

        places = []
        try:
            for result in response:
                places.append({
                    "name": result.get("name") or result.get("display_name", "Place"),
                    "display_name": result.get("display_name", ""),
                    "latitude": float(result["lat"]),
                    "longitude": float(result["lon"]),
                })
        except (TypeError, KeyError, ValueError):
            raise MapServiceError(
                "The place service returned invalid data. Try a more specific search."
            )

        self.place_cache[cache_key] = (time.time(), places)

        return places

    def get_route(self, points):
        """Return a GeoJSON route for points in their activity order."""

        if len(points) < 2:
            return None

        cache_key = []
        for point in points:
            cache_key.append((point["latitude"], point["longitude"]))
        cache_key = tuple(cache_key)
        cached_geometry = self.get_cached(
            self.route_cache,
            cache_key,
            self.route_cache_seconds,
        )
        if cached_geometry is not None:
            return cached_geometry

        coordinates = []
        for point in points:
            coordinates.append(
                str(point["longitude"]) + "," + str(point["latitude"])
            )

        coordinate_text = ";".join(coordinates)
        url = (
            "https://router.project-osrm.org/route/v1/driving/"
            + coordinate_text
            + "?overview=full&geometries=geojson&steps=false"
        )
        try:
            response = self.request_json(url)
        except MapServiceError:
            raise
        except Exception:
            raise MapServiceError(
                "The road route service is unavailable right now."
            )

        if response.get("code") != "Ok":
            raise MapServiceError("The road route service could not create a route.")

        routes = response.get("routes", [])
        if not routes:
            raise MapServiceError("The road route service returned no route.")

        geometry = routes[0].get("geometry")
        self.route_cache[cache_key] = (time.time(), geometry)
        return geometry

    def get_cached(self, cache, key, max_age):
        """Return a cached value while it is still fresh."""

        if key not in cache:
            return None

        saved_time, value = cache[key]
        if time.time() - saved_time > max_age:
            del cache[key]
            return None

        return value

    def request_json(self, url):
        request = Request(
            url,
            headers={
                "User-Agent": "TripWeaver/1.0 (COMP9001 final project)",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise MapServiceError(
                "The map service rejected the request (HTTP %s)." % error.code
            )
        except (URLError, TimeoutError):
            raise MapServiceError(
                "The map service is unavailable. Check your internet connection and try again."
            )
