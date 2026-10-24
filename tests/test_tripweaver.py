import tempfile
import unittest

from database import Database
from main import Activity, Trip, TripStore, app, read_date, read_location, read_money, read_place, weather_measure, weather_number, weather_time
from map_service import MapService
from weather_service import WeatherService


class TripWeaverCoreTests(unittest.TestCase):
    def setUp(self):
        self.trip = Trip(
            name="Test trip",
            destination="Sydney",
            start_date="2026-10-10",
            end_date="2026-10-12",
            budget=100,
        )

    def test_total_cost_and_budget_remaining(self):
        self.trip.activities.append(
            Activity("Museum", "2026-10-10", "09:00", "10:00", "Attraction", 25)
        )
        self.assertEqual(self.trip.get_total_cost(), 25)
        self.assertEqual(self.trip.get_budget_remaining(), 75)

    def test_overlapping_activities_are_detected(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:30", "Food"),
                Activity("Museum", "2026-10-10", "10:00", "12:00", "Attraction"),
            ]
        )
        self.assertEqual(len(self.trip.get_conflicts()), 1)

    def test_back_to_back_activities_do_not_conflict(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food"),
                Activity("Museum", "2026-10-10", "10:00", "12:00", "Attraction"),
            ]
        )
        self.assertEqual(len(self.trip.get_conflicts()), 0)

    def test_different_days_do_not_conflict(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:30", "Food"),
                Activity("Museum", "2026-10-11", "10:00", "12:00", "Attraction"),
            ]
        )
        self.assertEqual(self.trip.get_conflicts(), [])

    def test_negative_money_is_rejected(self):
        with self.assertRaises(ValueError):
            read_money("-1", "cost")

    def test_australian_date_input_is_supported(self):
        self.assertEqual(read_date("12/10/2026", "date").isoformat(), "2026-10-12")
        self.assertEqual(read_date("2026-10-12", "date").isoformat(), "2026-10-12")

    def test_country_and_city_create_a_precise_trip_location(self):
        trip = Trip(
            "Sydney trip",
            "",
            "2026-10-10",
            "2026-10-12",
            500,
            country="Australia",
            city="Sydney",
        )

        self.assertEqual(trip.destination, "Sydney, Australia")
        self.assertEqual(read_location("Australia", "Sydney"), "Sydney, Australia")
        self.assertEqual(read_location("China", "Guangdong"), "Guangdong, China")
        self.assertEqual(read_location("China", "Taiwan"), "Taiwan, China")
        self.assertEqual(read_location("China", "Hong Kong"), "Hong Kong, China")
        self.assertEqual(read_location("China", "Macau"), "Macau, China")
        with self.assertRaises(ValueError):
            read_location("Australia", "Paris")

    def test_selected_place_keeps_map_coordinates(self):
        place = read_place("Museum of Sydney", "-33.8568", "151.2153")

        self.assertEqual(place[0], "Museum of Sydney")
        self.assertEqual(place[1], -33.8568)
        self.assertEqual(place[2], 151.2153)

        with self.assertRaises(ValueError):
            read_place("", "", "")

    def test_activity_place_warning_stays_until_destination_is_checked(self):
        self.trip.destination = "Sydney, Australia"
        activity = Activity(
            "Museum",
            "2026-10-10",
            "09:00",
            "10:00",
            "Attraction",
            place_name="Museum of Sydney",
            latitude=-33.86,
            longitude=151.21,
            place_destination="Sydney, Australia",
        )
        self.trip.activities.append(activity)

        self.assertEqual(self.trip.get_location_mismatches(), [])
        self.trip.destination = "Melbourne, Australia"
        self.assertEqual(self.trip.get_location_mismatches(), [activity])

        activity.place_destination = "Melbourne, Australia"
        self.assertEqual(self.trip.get_location_mismatches(), [])

    def test_daily_cost(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food", 30),
                Activity("Museum", "2026-10-10", "10:00", "12:00", "Attraction", 20),
            ]
        )

        self.assertEqual(self.trip.get_daily_cost("2026-10-10"), 50)
        self.assertEqual(self.trip.get_daily_cost("2026-10-11"), 0)

    def test_get_activities_on_date(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food", 30),
                Activity("Museum", "2026-10-10", "10:00", "12:00", "Attraction", 20),
            ]
        )

        self.assertEqual(len(self.trip.get_activities_on_date("2026-10-11")), 0)
        self.assertEqual(len(self.trip.get_activities_on_date("2026-10-10")), 2)

    def test_get_category_costs(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food", 30),
                Activity("Lunch", "2026-10-10", "12:00", "13:00", "Food", 15),
                Activity("Museum", "2026-10-10", "10:00", "12:00", "Attraction", 20),
            ]
        )

        category_costs = self.trip.get_category_costs()
        self.assertEqual(len(category_costs), 2)
        self.assertEqual(category_costs["Food"], 45)
        self.assertEqual(category_costs["Attraction"], 20)

    def test_get_category_percentages(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food", 30),
                Activity("Lunch", "2026-10-10", "12:00", "13:00", "Food", 15),
                Activity("Museum", "2026-10-10", "10:00", "12:00", "Attraction", 20),
            ]
        )

        percentages = self.trip.get_category_percentages()
        self.assertAlmostEqual(percentages["Food"], 69.23, places=2)
        self.assertAlmostEqual(percentages["Attraction"], 30.77, places=2)

    def test_find_activity(self):
        activity = Activity("Museum", "2026-10-10", "09:00", "10:00", "Attraction")
        self.trip.add_activity(activity)

        self.assertIs(self.trip.find_activity(activity.id), activity)
        self.assertIsNone(self.trip.find_activity("missing-id"))

    def test_get_activities_by_category(self):
        breakfast = Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food")
        museum = Activity("Museum", "2026-10-10", "10:00", "12:00", "Attraction")
        lunch = Activity("Lunch", "2026-10-10", "12:00", "13:00", "Food")
        self.trip.activities.extend([breakfast, museum, lunch])

        food_activities = self.trip.get_activities_by_category("Food")

        self.assertEqual(len(food_activities), 2)
        self.assertIn(breakfast, food_activities)
        self.assertIn(lunch, food_activities)
        self.assertEqual(self.trip.get_activities_by_category("Transport"), [])

    def test_get_trip_days(self):
        self.assertEqual(self.trip.get_trip_days(), 3)

    def test_get_average_daily_cost(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food", 30),
                Activity("Museum", "2026-10-11", "10:00", "12:00", "Attraction", 20),
            ]
        )

        self.assertEqual(self.trip.get_average_daily_cost(), 16.67)

    def test_activity_duration_minutes(self):
        activity = Activity(
            "Museum", "2026-10-10", "09:00", "10:30", "Attraction"
        )

        self.assertEqual(activity.get_duration_minutes(), 90)
        self.assertIsInstance(activity.get_duration_minutes(), int)

    def test_activity_duration_label(self):
        activity = Activity(
            "Museum", "2026-10-10", "09:00", "10:30", "Attraction"
        )
        one_hour_activity = Activity(
            "Lunch", "2026-10-10", "12:00", "13:00", "Food"
        )
        short_activity = Activity(
            "Walk", "2026-10-10", "14:00", "14:45", "Outdoor"
        )

        self.assertEqual(activity.get_duration_label(), "1h 30m")
        self.assertEqual(one_hour_activity.get_duration_label(), "1h")
        self.assertEqual(short_activity.get_duration_label(), "45m")

    def test_get_total_activity_minutes(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food"),
                Activity("Museum", "2026-10-10", "10:30", "12:00", "Attraction"),
            ]
        )

        self.assertEqual(self.trip.get_total_activity_minutes(), 150)

    def test_delete_trip(self):
        with tempfile.TemporaryDirectory() as temporary_folder:
            file_path = temporary_folder + "\\trips.json"
            trip_store = TripStore(file_path)
            trip_store.save([self.trip])

            self.assertTrue(trip_store.delete_trip(self.trip.id))
            self.assertEqual(trip_store.load(), [])
            self.assertFalse(trip_store.delete_trip("missing-trip"))

    def test_json_data_can_be_migrated_to_sqlite(self):
        with tempfile.TemporaryDirectory() as temporary_folder:
            json_path = temporary_folder + "\\trips.json"
            database_path = temporary_folder + "\\tripweaver.db"
            json_store = TripStore(json_path)
            json_store.save([self.trip])

            database = Database(database_path)
            database_store = TripStore(json_path, database)
            migrated_trips = database_store.load()

            self.assertEqual(len(migrated_trips), 1)
            self.assertEqual(migrated_trips[0].name, "Test trip")
            self.assertEqual(len(migrated_trips[0].activities), 0)
            self.assertEqual(database.get_setting("storage_initialized"), "yes")

            database_store.save([])
            self.assertEqual(database_store.load(), [])

    def test_sqlite_crud_operations_for_trips_and_activities(self):
        with tempfile.TemporaryDirectory() as temporary_folder:
            json_path = temporary_folder + "\\trips.json"
            database_path = temporary_folder + "\\tripweaver.db"
            database = Database(database_path)
            database_store = TripStore(json_path, database)
            database_store.add_trip(self.trip)

            activity = Activity(
                "Museum",
                "2026-10-10",
                "10:00",
                "12:00",
                "Attraction",
                25,
                "Visit the main exhibition.",
                "activity-test",
            )
            database_store.add_activity(self.trip.id, activity)

            loaded_trip = database_store.load()[0]
            self.assertEqual(loaded_trip.name, "Test trip")
            self.assertEqual(loaded_trip.activities[0].title, "Museum")

            self.trip.update_details(
                "Updated trip",
                "Melbourne",
                "2026-10-11",
                "2026-10-13",
                250,
            )
            self.assertTrue(database_store.update_trip(self.trip))

            activity.title = "Updated museum"
            activity.cost = 30
            self.assertTrue(database_store.update_activity(self.trip.id, activity))

            updated_trip = database_store.load()[0]
            self.assertEqual(updated_trip.name, "Updated trip")
            self.assertEqual(updated_trip.activities[0].title, "Updated museum")
            self.assertEqual(updated_trip.activities[0].cost, 30)
            self.assertEqual(updated_trip.activities[0].location, "Melbourne")

            self.assertTrue(database_store.delete_activity(self.trip.id, activity.id))
            self.assertEqual(database_store.load()[0].activities, [])
            self.assertTrue(database_store.delete_trip(self.trip.id))
            self.assertEqual(database_store.load(), [])

    def test_update_details(self):
        self.trip.update_details(
            "Updated trip",
            "Melbourne",
            "2026-11-01",
            "2026-11-05",
            800,
        )

        self.assertEqual(self.trip.name, "Updated trip")
        self.assertEqual(self.trip.destination, "Melbourne")
        self.assertEqual(self.trip.start_date, "2026-11-01")
        self.assertEqual(self.trip.end_date, "2026-11-05")
        self.assertEqual(self.trip.budget, 800)

    def test_get_free_time_slots(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food"),
                Activity("Museum", "2026-10-10", "12:00", "13:30", "Attraction"),
                Activity("Walk", "2026-10-10", "15:00", "16:00", "Outdoor"),
            ]
        )

        self.assertEqual(
            self.trip.get_free_time_slots("2026-10-10"),
            [("10:00", "12:00"), ("13:30", "15:00")],
        )
        self.assertEqual(self.trip.get_free_time_slots("2026-10-11"), [])

    def test_free_time_slots_ignore_long_overlapping_activities(self):
        self.trip.activities.extend(
            [
                Activity("Long activity", "2026-10-10", "09:00", "20:00", "Other"),
                Activity("Short activity", "2026-10-10", "10:00", "11:00", "Other"),
                Activity("Another activity", "2026-10-10", "12:00", "13:00", "Other"),
            ]
        )

        self.assertEqual(self.trip.get_free_time_slots("2026-10-10"), [])

    def test_free_time_starts_after_overlapping_activities_end(self):
        self.trip.activities.extend(
            [
                Activity("Long activity", "2026-10-10", "09:00", "12:00", "Other"),
                Activity("Short activity", "2026-10-10", "10:00", "11:00", "Other"),
                Activity("Next activity", "2026-10-10", "13:00", "14:00", "Other"),
            ]
        )

        self.assertEqual(
            self.trip.get_free_time_slots("2026-10-10"),
            [("12:00", "13:00")],
        )

    def test_get_daily_summary(self):
        self.trip.activities.extend(
            [
                Activity("Breakfast", "2026-10-10", "09:00", "10:00", "Food", 30),
                Activity("Museum", "2026-10-10", "12:00", "13:30", "Attraction", 20),
            ]
        )

        summary = self.trip.get_daily_summary("2026-10-10")

        self.assertEqual(summary["date"], "2026-10-10")
        self.assertEqual(summary["activity_count"], 2)
        self.assertEqual(summary["cost"], 50)
        self.assertEqual(summary["activity_minutes"], 150)
        self.assertEqual(summary["free_time_slots"], [("10:00", "12:00")])

class WeatherServiceTests(unittest.TestCase):
    def test_open_meteo_daily_values_are_converted_to_weather_rows(self):
        with tempfile.TemporaryDirectory() as temporary_folder:
            database = Database(temporary_folder + "\\tripweaver.db")
            database.create_tables()
            service = WeatherService(database)
            responses = [
                {
                    "results": [
                        {"latitude": -33.86, "longitude": 151.20}
                    ]
                },
                {
                    "timezone": "Australia/Sydney",
                    "daily": {
                        "time": ["2026-10-10"],
                        "weather_code": [2],
                        "temperature_2m_min": [16.2],
                        "temperature_2m_max": [24.8],
                        "precipitation_probability_max": [30],
                        "precipitation_sum": [1.4],
                        "uv_index_max": [6.1],
                        "wind_speed_10m_max": [18.0],
                        "sunrise": ["2026-10-10T06:20"],
                        "sunset": ["2026-10-10T19:05"],
                    },
                },
            ]

            def fake_request_json(url):
                return responses.pop(0)

            service.request_json = fake_request_json
            rows = service.fetch_location_weather(
                "Sydney, Australia", ["2026-10-10"]
            )

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["temperature_min"], 16.2)
            self.assertEqual(rows[0]["temperature_max"], 24.8)
            self.assertEqual(rows[0]["precipitation_probability"], 30)
            self.assertEqual(rows[0]["uv_index"], 6.1)
            self.assertEqual(service.get_weather_label(2), "Partly cloudy")

    def test_missing_weather_values_are_displayed_safely(self):
        self.assertEqual(weather_number(None), "—")
        self.assertEqual(weather_number(12.56), "13")
        self.assertEqual(weather_number(12.56, 1), "12.6")
        self.assertEqual(weather_measure(None, 0, "°C"), "—")
        self.assertEqual(weather_measure(12.56, 1, " mm"), "12.6 mm")
        self.assertEqual(weather_time(None), "—")
        self.assertEqual(weather_time("2026-10-25T07:41"), "07:41")


class MapServiceTests(unittest.TestCase):
    def test_place_search_converts_coordinates(self):
        service = MapService()
        request_count = {"value": 0}

        def fake_request_json(url):
            request_count["value"] += 1
            return [{
                "name": "Museum of Sydney",
                "display_name": "Museum of Sydney, Australia",
                "lat": "-33.8568",
                "lon": "151.2153",
            }]

        service.request_json = fake_request_json

        places = service.search_places("Museum", "Sydney, Australia")
        cached_places = service.search_places("museum", "sydney, australia")

        self.assertEqual(places[0]["name"], "Museum of Sydney")
        self.assertEqual(places[0]["latitude"], -33.8568)
        self.assertEqual(places[0]["longitude"], 151.2153)
        self.assertEqual(cached_places, places)
        self.assertEqual(request_count["value"], 1)

    def test_route_returns_geojson_geometry(self):
        service = MapService()
        request_count = {"value": 0}

        def fake_request_json(url):
            request_count["value"] += 1
            return {
                "code": "Ok",
                "routes": [{
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[151.2, -33.8], [151.3, -33.9]],
                    }
                }],
            }

        service.request_json = fake_request_json

        points = [
            {"latitude": -33.8, "longitude": 151.2},
            {"latitude": -33.9, "longitude": 151.3},
        ]
        geometry = service.get_route(points)
        cached_geometry = service.get_route(points)

        self.assertEqual(geometry["type"], "LineString")
        self.assertEqual(len(geometry["coordinates"]), 2)
        self.assertEqual(cached_geometry, geometry)
        self.assertEqual(request_count["value"], 1)


class TripWeaverWebTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_dashboard_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Shape a better journey.", response.data)

    def test_dashboard_can_search_filter_and_sort_trips(self):
        search_response = self.client.get("/?query=London")
        conflict_response = self.client.get("/?filter=conflicts")
        sort_response = self.client.get("/?sort=start_desc")

        self.assertEqual(search_response.status_code, 200)
        self.assertIn(b"London graduation travel", search_response.data)
        self.assertIn(b"Search trips", search_response.data)
        self.assertIn(b"With conflicts", conflict_response.data)
        self.assertIn(b"Start date: latest", sort_response.data)

    def test_trip_detail_and_edit_pages_load(self):
        detail_response = self.client.get("/trip/demo-trip")
        edit_response = self.client.get("/trip/demo-trip/edit")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(edit_response.status_code, 200)
        self.assertIn(b"Edit trip", edit_response.data)
        self.assertIn(b"delete-activity-modal", detail_response.data)
        self.assertIn(b"Remove activity", detail_response.data)
        self.assertIn(b"Weather by location", detail_response.data)
        self.assertIn(b"Activity route", detail_response.data)
        self.assertIn(b"map.js", detail_response.data)

    def test_category_filter_loads(self):
        response = self.client.get("/trip/demo-trip?category=Food")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Filter by category", response.data)

    def test_navigation_and_new_trip_form(self):
        dashboard_response = self.client.get("/")
        new_trip_response = self.client.get("/trip/new")

        self.assertIn(b"nav-link-active", dashboard_response.data)
        self.assertIn(b"nav-link-button", dashboard_response.data)
        self.assertIn(b"data-clear-form", new_trip_response.data)
        self.assertIn(b'class="date-picker"', new_trip_response.data)
        self.assertIn(b'class="time-picker"', self.client.get("/trip/demo-trip/activity/new").data)
        self.assertIn(b'name="country"', new_trip_response.data)
        self.assertIn(b'name="city"', new_trip_response.data)
        self.assertIn(b'"China"', new_trip_response.data)
        self.assertIn(b'"Guangdong"', new_trip_response.data)
        self.assertNotIn(b'name="destination"', new_trip_response.data)
        self.assertNotIn(b'name="location"', self.client.get("/trip/demo-trip/activity/new").data)
        activity_response = self.client.get("/trip/demo-trip/activity/new")
        self.assertIn(b"data-place-picker", activity_response.data)
        self.assertIn(b"map.js", activity_response.data)

    def test_map_endpoints_have_safe_empty_responses(self):
        search_response = self.client.get("/trip/demo-trip/places/search?q=a")
        map_response = self.client.get("/trip/demo-trip/map-data")
        route_response = self.client.get("/trip/demo-trip/route?date=2026-10-10")

        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(search_response.json["places"], [])
        self.assertEqual(map_response.status_code, 200)
        self.assertIn("activities", map_response.json)
        self.assertEqual(route_response.status_code, 200)
        self.assertIn("points", route_response.json)

    def test_back_to_dashboard_links_are_visible_buttons(self):
        detail_response = self.client.get("/trip/demo-trip")
        new_trip_response = self.client.get("/trip/new")

        self.assertIn(b"back-link-button", detail_response.data)
        self.assertIn(b"back-link-button", new_trip_response.data)

    def test_dashboard_shows_conflict_status_label(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        page = response.data.lower()
        self.assertTrue(b"no conflicts" in page or b"conflict" in page)

    def test_dashboard_uses_trip_delete_modal(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"delete-trip-modal", response.data)
        self.assertIn(b"delete-trip-name", response.data)
        self.assertIn(b"delete-trip-destination", response.data)
        self.assertIn(b"data-confirm-delete-trip", response.data)
        self.assertNotIn(b"onsubmit=\"return confirm", response.data)

    def test_unknown_trip_redirects_to_dashboard(self):
        response = self.client.get("/trip/missing-trip")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/")


if __name__ == "__main__":
    unittest.main()
