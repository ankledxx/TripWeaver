import json
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class WeatherService:
    """Get and cache daily weather data from Open-Meteo."""

    def __init__(self, database):
        self.database = database

    def get_trip_weather(self, trip):
        dates = self.get_trip_dates(trip.start_date, trip.end_date)
        locations = self.get_trip_locations(trip)
        cached_rows = self.database.load_weather(trip.id)
        cached_by_key = {}
        for row in cached_rows:
            key = (row["location"], row["weather_date"])
            cached_by_key[key] = row

        errors = []
        for location in locations:
            if self.has_fresh_cache(cached_by_key, location, dates):
                continue

            try:
                weather_rows = self.fetch_location_weather(location, dates)
                self.database.save_weather(trip.id, weather_rows)
                for row in weather_rows:
                    key = (row["location"], row["weather_date"])
                    cached_by_key[key] = row
            except Exception:
                errors.append(location)

        location_weather = []
        for location in locations:
            days = []
            missing_dates = []
            missing_values = False
            refresh_error = False

            if location in errors:
                refresh_error = True

            for weather_date in dates:
                key = (location, weather_date)
                if key in cached_by_key:
                    weather_row = cached_by_key[key]
                    days.append(weather_row)
                    if self.has_missing_value(weather_row):
                        missing_values = True
                else:
                    days.append(self.make_empty_weather_row(location, weather_date))
                    missing_dates.append(weather_date)

            reasons = []
            if missing_dates:
                reasons.append(self.get_missing_date_reason(missing_dates))
            if missing_values:
                reasons.append(
                    "Some weather values are unavailable from Open-Meteo. "
                    "Try refreshing and retrying."
                )
            if refresh_error and not missing_dates:
                reasons.append(
                    "The latest weather data could not be refreshed. "
                    "Cached values are shown. Try refreshing and retrying."
                )

            location_weather.append({
                "location": location,
                "days": days,
                "reasons": reasons,
            })

        return {
            "locations": location_weather,
            "errors": errors,
        }

    def make_empty_weather_row(self, location, weather_date):
        """Create a placeholder for a date without weather data."""

        return {
            "location": location,
            "weather_date": weather_date,
            "weather_code": None,
            "temperature_min": None,
            "temperature_max": None,
            "precipitation_probability": None,
            "precipitation_sum": None,
            "uv_index": None,
            "wind_speed": None,
            "sunrise": None,
            "sunset": None,
        }

    def has_missing_value(self, weather_row):
        """Return True when one weather value is missing."""

        fields = [
            "weather_code",
            "temperature_min",
            "temperature_max",
            "precipitation_probability",
            "precipitation_sum",
            "uv_index",
            "wind_speed",
            "sunrise",
            "sunset",
        ]

        for field in fields:
            if weather_row.get(field) is None:
                return True

        return False

    def get_missing_date_reason(self, missing_dates):
        """Explain why some requested dates have no forecast."""

        today = date.today()
        forecast_last_day = today + timedelta(days=16)
        missing_day_objects = []
        for weather_date in missing_dates:
            missing_day_objects.append(
                datetime.strptime(weather_date, "%Y-%m-%d").date()
            )

        if all(day > forecast_last_day for day in missing_day_objects):
            return (
                "Forecast data is only available up to 16 days ahead. "
                "Check again when the travel date is closer."
            )

        if all(day < today for day in missing_day_objects):
            return (
                "These travel dates have already passed. "
                "Historical weather data is not available here."
            )

        if any(day > forecast_last_day for day in missing_day_objects):
            return (
                "Some travel dates are outside the 16-day forecast range. "
                "Check again when those dates are closer."
            )

        return "Weather data for some dates could not be loaded. Try refreshing and retrying."

    def get_trip_locations(self, trip):
        return [trip.destination]

    def get_trip_dates(self, start_date, end_date):
        first_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        last_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        dates = []
        current_date = first_date
        while current_date <= last_date:
            dates.append(current_date.isoformat())
            current_date = current_date + timedelta(days=1)
        return dates

    def has_fresh_cache(self, cached_by_key, location, dates):
        current_time = datetime.utcnow()
        for weather_date in dates:
            key = (location, weather_date)
            if key not in cached_by_key:
                return False
            fetched_at = cached_by_key[key].get("fetched_at", "")
            try:
                saved_time = datetime.fromisoformat(fetched_at)
            except ValueError:
                return False
            if current_time - saved_time > timedelta(hours=6):
                return False
        return True

    def fetch_location_weather(self, location, dates):
        coordinates = self.find_coordinates(location)
        parameters = {
            "latitude": coordinates["latitude"],
            "longitude": coordinates["longitude"],
            "daily": (
                "weather_code,temperature_2m_min,temperature_2m_max,"
                "precipitation_probability_max,precipitation_sum,"
                "uv_index_max,wind_speed_10m_max,sunrise,sunset"
            ),
            "timezone": "auto",
            "start_date": dates[0],
            "end_date": dates[-1],
        }
        response = self.request_json(
            "https://api.open-meteo.com/v1/forecast?"
            + urlencode(parameters)
        )

        daily = response.get("daily", {})
        weather_rows = []
        fetched_at = datetime.utcnow().replace(microsecond=0).isoformat()
        returned_dates = daily.get("time", [])
        for index, weather_date in enumerate(returned_dates):
            weather_rows.append({
                "location": location,
                "weather_date": weather_date,
                "latitude": coordinates["latitude"],
                "longitude": coordinates["longitude"],
                "timezone": response.get("timezone", ""),
                "weather_code": self.get_daily_value(daily, "weather_code", index),
                "temperature_min": self.get_daily_value(daily, "temperature_2m_min", index),
                "temperature_max": self.get_daily_value(daily, "temperature_2m_max", index),
                "precipitation_probability": self.get_daily_value(daily, "precipitation_probability_max", index),
                "precipitation_sum": self.get_daily_value(daily, "precipitation_sum", index),
                "uv_index": self.get_daily_value(daily, "uv_index_max", index),
                "wind_speed": self.get_daily_value(daily, "wind_speed_10m_max", index),
                "sunrise": self.get_daily_value(daily, "sunrise", index),
                "sunset": self.get_daily_value(daily, "sunset", index),
                "fetched_at": fetched_at,
            })
        return weather_rows

    def find_coordinates(self, location):
        parameters = {
            "name": location,
            "count": 1,
            "language": "en",
            "format": "json",
        }
        response = self.request_json(
            "https://geocoding-api.open-meteo.com/v1/search?"
            + urlencode(parameters)
        )
        results = response.get("results", [])
        if not results:
            raise ValueError("Location not found")
        return {
            "latitude": results[0]["latitude"],
            "longitude": results[0]["longitude"],
        }

    def request_json(self, url):
        request = Request(url, headers={"User-Agent": "TripWeaver/1.0"})
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_daily_value(self, daily, name, index):
        values = daily.get(name, [])
        if index >= len(values):
            return None
        return values[index]

    def get_weather_label(self, weather_code):
        if weather_code is None:
            return "Weather unavailable"

        labels = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return labels.get(weather_code, "Weather information available")
