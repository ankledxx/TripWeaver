"""TripWeaver - a beginner-friendly Flask project."""

import json
import os
import uuid
from datetime import datetime
from database import Database
from locations import COUNTRY_CITIES
from weather_service import WeatherService
from map_service import MapService, MapServiceError

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

# These paths point to folders inside the project folder.
BASE_FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_FOLDER, "data")
DATA_FILE = os.path.join(DATA_FOLDER, "trips.json")
DATABASE_FILE = os.path.join(DATA_FOLDER, "tripweaver.db")

database = Database(DATABASE_FILE)
database.create_tables()

app = Flask(__name__)
app.config["SECRET_KEY"] = "tripweaver-local-demo-key"


@app.template_filter("weather_number")
def weather_number(value, decimal_places=0):

    if value is None:
        return "—"

    if decimal_places == 1:
        return "%.1f" % value

    return "%.0f" % value


@app.template_filter("weather_measure")
def weather_measure(value, decimal_places=0, unit=""):

    if value is None:
        return "—"

    return weather_number(value, decimal_places) + unit


@app.template_filter("weather_time")
def weather_time(value):

    if not value:
        return "—"

    return value[11:16]


def make_id():
    """Make a short ID for a trip or activity."""

    return uuid.uuid4().hex[:8]


def read_date(value, field_name):
    """Turn text into a date, or show a useful error."""

    for date_format in ["%d/%m/%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(value, date_format).date()
        except (TypeError, ValueError):
            continue

    raise ValueError("Please enter a valid " + field_name + " (dd/mm/yyyy).")


def read_time(value, field_name):
    """Turn text into a time, or show a useful error."""

    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        raise ValueError("Please enter a valid " + field_name + ".")


def read_money(value, field_name):
    """Turn text into a non-negative number."""

    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("Please enter a valid " + field_name + ".")

    if amount < 0:
        raise ValueError(field_name.capitalize() + " cannot be negative.")

    return round(amount, 2)


def read_location(country, city):
    """Validate a selected country and its matching city."""

    if country not in COUNTRY_CITIES:
        raise ValueError("Please select a country.")
    if city not in COUNTRY_CITIES[country]:
        raise ValueError("Please select a city from the selected country.")
    return city + ", " + country


def read_place(place_name, latitude, longitude):
    """Validate the place selected from the map search results."""

    place_name = place_name.strip()
    if not place_name:
        raise ValueError("Please search for and select a place.")

    try:
        latitude_value = float(latitude)
        longitude_value = float(longitude)
    except (TypeError, ValueError):
        raise ValueError("Please search for and select a place.")

    if latitude_value < -90 or latitude_value > 90:
        raise ValueError("Please select a valid place.")
    if longitude_value < -180 or longitude_value > 180:
        raise ValueError("Please select a valid place.")

    return place_name, latitude_value, longitude_value


class Activity:
    """Store the information about one activity."""

    def __init__(self, title, activity_date, start_time, end_time, category, cost=0, notes="", activity_id=None, location="", place_name="", latitude=None, longitude=None, place_destination=""):
        self.id = activity_id or make_id()
        self.title = title
        self.activity_date = activity_date
        self.start_time = start_time
        self.end_time = end_time
        self.category = category
        self.cost = cost
        self.notes = notes
        self.location = location
        self.place_name = place_name
        self.latitude = latitude
        self.longitude = longitude
        self.place_destination = place_destination or location

    def to_dict(self):
        """Convert this Activity object into a dictionary for JSON."""

        return {
            "id": self.id,
            "title": self.title,
            "activity_date": self.activity_date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "category": self.category,
            "cost": self.cost,
            "notes": self.notes,
            "location": self.location,
            "place_name": self.place_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "place_destination": self.place_destination,
        }

    def overlaps(self, other_activity):
        """Return True when this activity overlaps another activity."""

        if self.activity_date != other_activity.activity_date:
            return False

        first_start = read_time(self.start_time, "start time")
        first_end = read_time(self.end_time, "end time")
        second_start = read_time(other_activity.start_time, "start time")
        second_end = read_time(other_activity.end_time, "end time")

        if first_start < second_end and second_start < first_end:
            return True

        return False

    def get_duration_minutes(self):
        '''calculate the duration of the activity in minutes.'''

        start_time = datetime.strptime(self.start_time, "%H:%M")
        end_time = datetime.strptime(self.end_time, "%H:%M")

        duration = end_time - start_time

        return int(duration.total_seconds() / 60)

    def get_duration_label(self):
        '''display the label of time of the activity '''

        duration = self.get_duration_minutes()
        hours = int(duration // 60)
        minutes = int(duration % 60)

        if hours == 0:
            return f"{minutes}m"
        if minutes == 0:
            return f"{hours}h"
        return f"{hours}h {minutes}m"


def activity_from_dict(data):
    """Create an Activity object from saved JSON data."""

    return Activity(
        data["title"],
        data["activity_date"],
        data["start_time"],
        data["end_time"],
        data.get("category", "Other"),
        float(data.get("cost", 0)),
        data.get("notes", ""),
        data.get("id"),
        data.get("location", ""),
        data.get("place_name", ""),
        data.get("latitude"),
        data.get("longitude"),
        data.get("place_destination", data.get("location", "")),
    )


class Trip:
    """Store one trip and the activities inside it."""

    def __init__(self, name, destination, start_date, end_date, budget, activities=None, trip_id=None, country="", city=""):
        self.id = trip_id or make_id()
        self.name = name
        self.country = country
        self.city = city
        self.destination = destination
        self.set_location(country, city)
        self.start_date = start_date
        self.end_date = end_date
        self.budget = budget

        if activities is None:
            self.activities = []
        else:
            self.activities = activities

        for activity in self.activities:
            activity.location = self.destination

    def set_location(self, country, city):
        if country and city:
            self.country = country
            self.city = city
            self.destination = city + ", " + country
            return

        self.country = ""
        parts = self.destination.split(",")
        self.city = parts[0].strip()
        if len(parts) > 1:
            self.country = parts[-1].strip()

    def get_location_label(self):
        if self.country:
            return self.city + ", " + self.country
        return self.city

    def get_location_mismatches(self):
        """Return activities that need their map place checked again."""

        mismatches = []
        for activity in self.activities:
            if not activity.place_name:
                mismatches.append(activity)
            elif activity.place_destination != self.destination:
                mismatches.append(activity)
        return mismatches

    def add_activity(self, activity):
        """Add one Activity object to this trip."""

        activity.location = self.destination
        self.activities.append(activity)

    def get_total_cost(self):
        """Calculate the total cost of all activities."""

        total = 0
        for activity in self.activities:
            total = total + activity.cost
        return round(total, 2)

    def get_daily_cost(self, target_date):
        """Calculate the daily cost of all activities."""

        daily_cost = 0
        for activity in self.activities:
            if activity.activity_date == target_date:
                daily_cost = daily_cost + activity.cost
        return round(daily_cost, 2)


    def get_budget_remaining(self):
        """Calculate how much budget is left."""

        return round(self.budget - self.get_total_cost(), 2)

    def get_budget_percent(self):
        """Calculate the percentage of the budget already used."""

        if self.budget <= 0:
            return 0

        percentage = round(self.get_total_cost() / self.budget * 100)
        if percentage > 100:
            return 100
        return percentage

    def get_conflicts(self):
        """Return pairs of activities that overlap."""

        conflicts = []

        for first_index in range(len(self.activities)):
            first_activity = self.activities[first_index]

            for second_index in range(first_index + 1, len(self.activities)):
                second_activity = self.activities[second_index]

                if first_activity.overlaps(second_activity):
                    conflicts.append((first_activity, second_activity))

        return conflicts

    def get_sorted_activities(self):
        """Return activities ordered by date and start time."""

        activities = self.activities.copy()
        activities.sort(key=lambda activity: (activity.activity_date, activity.start_time))
        return activities

    def get_activities_on_date(self, target_date):
        '''caculate the activities on date'''

        result = []

        for activity in self.activities:
            if activity.activity_date == target_date:
                result.append(activity)

        return result



    def to_dict(self):
        """Convert this Trip object into a dictionary for JSON."""

        activity_data = []
        for activity in self.activities:
            activity_data.append(activity.to_dict())

        return {
            "id": self.id,
            "name": self.name,
            "destination": self.destination,
            "country": self.country,
            "city": self.city,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "budget": self.budget,
            "activities": activity_data,
        }

    def get_category_costs(self):
        '''display different costs of all activities.'''

        category_costs = {}

        for activity in self.activities:
            if activity.category in category_costs:
                category_costs[activity.category] += activity.cost
            else:
                category_costs[activity.category] = activity.cost
        return category_costs

    def get_category_percentages(self):
        '''display percentages of costs of all activities.'''

        percentages = {}
        total_cost = self.get_total_cost()

        if total_cost == 0:
            return percentages
        for activity in self.activities:
            if activity.category in percentages:
                percentages[activity.category] += activity.cost / total_cost * 100
                if percentages[activity.category] >= 100:
                    percentages[activity.category] = 100
            else:
                percentages[activity.category] = activity.cost / total_cost * 100
        return percentages

    def find_activity(self, activity_id):
        '''Find a specific activity by its ID.'''

        for activity in self.activities:
            if activity.id == activity_id:
                return activity
        return None

    def get_activities_by_category(self, category):
        '''find all activities that belong to a specific category.'''

        matching_activities = []

        for activity in self.activities:
            if activity.category == category:
                matching_activities.append(activity)
        return matching_activities

    def get_trip_days(self):
        '''calculate trip days.'''

        start_date = read_date(self.start_date, "start date")
        end_date = read_date(self.end_date, "end date")

        return (end_date - start_date).days + 1

    def get_average_daily_cost(self):
        '''calculate average daily cost of all activities.'''

        total_cost = self.get_total_cost()

        if total_cost == 0:
            return 0

        return round(total_cost / self.get_trip_days(), 2)

    def get_total_activity_minutes(self):
        '''calculate total minutes of all activities.'''

        total_minutes = 0
        for activity in self.activities:
            total_minutes += activity.get_duration_minutes()

        return total_minutes

    def update_details(self, name, destination, start_date, end_date, budget, country="", city=""):
        '''update trips details with new data.'''
        self.name = name
        self.destination = destination
        self.set_location(country, city)
        self.start_date = start_date
        self.end_date = end_date
        self.budget = budget
        for activity in self.activities:
            activity.location = self.destination

    def get_free_time_slots(self, target_date):
        '''search free time between activities'''

        # find suitable activities of indicated date
        target_activities =  []
        free_time_slots = []
        for activity in self.activities:
            if activity.activity_date == target_date:
                target_activities.append(activity)
        if len(target_activities) <= 1:
            return free_time_slots

        # make sure activities are ordered
        target_activities.sort(key=lambda activity: activity.start_time)
        latest_start_time = target_activities[0].end_time

        # find the free time gap between activities
        for i in range(len(target_activities) - 1):
            end_time = target_activities[i + 1].start_time
            next_start_time = target_activities[i + 1].end_time
            if latest_start_time < end_time:
                free_time = (latest_start_time, end_time)
                free_time_slots.append(free_time)

            # update current latest activity end time
            if next_start_time > latest_start_time:
                latest_start_time = next_start_time
        return free_time_slots

    def get_daily_summary(self, target_date):
        '''summarise activities and costs for one date.'''

        activities = self.get_activities_on_date(target_date)
        total_minutes = 0

        for activity in activities:
            total_minutes += activity.get_duration_minutes()

        return {
            "date": target_date,
            "activity_count": len(activities),
            "cost": self.get_daily_cost(target_date),
            "activity_minutes": total_minutes,
            "free_time_slots": self.get_free_time_slots(target_date),
        }








def trip_from_dict(data):
    """Create a Trip object from saved JSON data."""

    activities = []
    for activity_data in data.get("activities", []):
        activities.append(activity_from_dict(activity_data))

    return Trip(
        data["name"],
        data["destination"],
        data["start_date"],
        data["end_date"],
        float(data.get("budget", 0)),
        activities,
        data.get("id"),
        data.get("country", ""),
        data.get("city", ""),
    )


class TripStore:
    """Load and save Trip objects using SQLite, with JSON migration support."""

    def __init__(self, file_path, database=None):
        self.file_path = file_path
        self.database = database
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if self.database is not None:
            self.database.create_tables()

    def load_json_data(self):
        if not os.path.exists(self.file_path):
            return None

        try:
            file_object = open(self.file_path, "r", encoding="utf-8")
            saved_data = json.load(file_object)
            file_object.close()
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            raise RuntimeError("The saved trip data is invalid.")

        return saved_data

    def load(self):
        if self.database is None:
            saved_data = self.load_json_data()
            if saved_data is None:
                trips = self.create_demo_data()
                self.save(trips)
                return trips

            trips = []
            for trip_data in saved_data:
                trips.append(trip_from_dict(trip_data))
            return trips

        if self.database.get_setting("storage_initialized") != "yes":
            saved_data = self.load_json_data()
            if saved_data is None:
                trips = self.create_demo_data()
            else:
                trips = []
                for trip_data in saved_data:
                    trips.append(trip_from_dict(trip_data))

            self.database.save_trips(trips)
            self.database.set_setting("storage_initialized", "yes")
            return trips

        saved_data = self.database.load_data()
        trips = []
        for trip_data in saved_data:
            trips.append(trip_from_dict(trip_data))
        return trips

    def save(self, trips):
        if self.database is not None:
            self.database.save_trips(trips)
            self.database.set_setting("storage_initialized", "yes")
            return

        saved_data = []
        for trip in trips:
            saved_data.append(trip.to_dict())

        file_object = open(self.file_path, "w", encoding="utf-8")
        json.dump(saved_data, file_object, indent=2)
        file_object.close()

    def add_trip(self, trip):
        if self.database is not None:
            self.database.insert_trip(trip)
            self.database.set_setting("storage_initialized", "yes")
            return

        trips = self.load()
        trips.append(trip)
        self.save(trips)

    def update_trip(self, trip):
        if self.database is not None:
            return self.database.update_trip(trip)

        trips = self.load()
        for saved_trip in trips:
            if saved_trip.id == trip.id:
                saved_trip.update_details(
                    trip.name,
                    trip.destination,
                    trip.start_date,
                    trip.end_date,
                    trip.budget,
                )
        self.save(trips)
        return True

    def add_activity(self, trip_id, activity):
        if self.database is not None:
            self.database.insert_activity(trip_id, activity)
            return

        trips = self.load()
        trip = find_trip(trips, trip_id)
        if trip is not None:
            trip.add_activity(activity)
            self.save(trips)

    def update_activity(self, trip_id, activity):
        if self.database is not None:
            return self.database.update_activity(trip_id, activity)

        trips = self.load()
        trip = find_trip(trips, trip_id)
        if trip is None:
            return False
        saved_activity = trip.find_activity(activity.id)
        if saved_activity is None:
            return False
        saved_activity.title = activity.title
        saved_activity.activity_date = activity.activity_date
        saved_activity.start_time = activity.start_time
        saved_activity.end_time = activity.end_time
        saved_activity.category = activity.category
        saved_activity.cost = activity.cost
        saved_activity.notes = activity.notes
        saved_activity.location = activity.location
        saved_activity.place_name = activity.place_name
        saved_activity.latitude = activity.latitude
        saved_activity.longitude = activity.longitude
        saved_activity.place_destination = activity.place_destination
        self.save(trips)
        return True

    def delete_activity(self, trip_id, activity_id):
        if self.database is not None:
            return self.database.delete_activity(trip_id, activity_id)

        trips = self.load()
        trip = find_trip(trips, trip_id)
        if trip is None:
            return False
        old_count = len(trip.activities)
        trip.activities = [
            activity
            for activity in trip.activities
            if activity.id != activity_id
        ]
        if len(trip.activities) == old_count:
            return False
        self.save(trips)
        return True

    def create_demo_data(self):
        breakfast = Activity(
            "Circular Quay breakfast",
            "2026-10-10",
            "09:00",
            "10:00",
            "Food",
            35,
            "Start the trip with a relaxed breakfast.",
            "demo-1",
        )
        museum = Activity(
            "Museum of Sydney",
            "2026-10-10",
            "10:30",
            "13:00",
            "Attraction",
            28,
            "Allow extra time for the harbour exhibits.",
            "demo-2",
        )
        walk = Activity(
            "Harbour walk",
            "2026-10-10",
            "15:00",
            "17:00",
            "Outdoor",
            0,
            "A flexible afternoon activity.",
            "demo-3",
        )

        activities = [breakfast, museum, walk]
        demo_trip = Trip(
            "Sydney Weekend Escape",
            "Sydney, Australia",
            "2026-10-10",
            "2026-10-12",
            650,
            activities,
            "demo-trip",
        )
        return [demo_trip]

    def delete_trip(self, trip_id):
        if self.database is not None:
            return self.database.delete_trip(trip_id)

        trips = self.load()
        trip_temps = []
        flag = 0
        for trip in trips:
            if trip.id == trip_id:
                flag = 1
                continue
            else:
                trip_temps.append(trip)
        self.save(trip_temps)
        if flag == 0:
            return False
        return True


store = TripStore(DATA_FILE, database)
weather_service = WeatherService(database)
map_service = MapService()
app.jinja_env.filters["weather_label"] = weather_service.get_weather_label


def find_trip(trips, trip_id):
    for trip in trips:
        if trip.id == trip_id:
            return trip
    return None


def date_label(value):
    try:
        return read_date(value, "date").strftime("%a, %d %b")
    except ValueError:
        return value


app.jinja_env.filters["date_label"] = date_label


@app.route("/")
def index():
    all_trips = store.load()
    query = request.args.get("query", "").strip()
    trip_filter = request.args.get("filter", "all")
    sort_order = request.args.get("sort", "start_asc")
    trips = []

    for trip in all_trips:
        search_text = (
            trip.name + " " + trip.destination + " "
            + trip.country + " " + trip.city
        ).casefold()

        if query and query.casefold() not in search_text:
            continue

        if trip_filter == "conflicts" and not trip.get_conflicts():
            continue
        if trip_filter == "over_budget" and trip.get_budget_remaining() >= 0:
            continue
        if trip_filter == "within_budget" and trip.get_budget_remaining() < 0:
            continue

        trips.append(trip)

    if sort_order == "start_desc":
        trips.sort(key=lambda trip: trip.start_date, reverse=True)
    elif sort_order == "end_asc":
        trips.sort(key=lambda trip: trip.end_date)
    elif sort_order == "end_desc":
        trips.sort(key=lambda trip: trip.end_date, reverse=True)
    else:
        trips.sort(key=lambda trip: trip.start_date)

    total_activities = 0
    total_budget = 0
    total_spend = 0

    for trip in all_trips:
        total_activities = total_activities + len(trip.activities)
        total_budget = total_budget + trip.budget
        total_spend = total_spend + trip.get_total_cost()

    return render_template(
        "index.html",
        trips=trips,
        all_trips=all_trips,
        query=query,
        trip_filter=trip_filter,
        sort_order=sort_order,
        total_activities=total_activities,
        total_budget=total_budget,
        total_spend=total_spend,
    )


@app.route("/trip/new", methods=["GET", "POST"])
def create_trip():
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            country = request.form.get("country", "").strip()
            city = request.form.get("city", "").strip()
            destination = read_location(country, city)
            start_date = read_date(request.form.get("start_date", ""), "start date")
            end_date = read_date(request.form.get("end_date", ""), "end date")
            budget = read_money(request.form.get("budget", ""), "budget")

            if not name:
                raise ValueError("Trip name is required.")
            if end_date < start_date:
                raise ValueError("End date cannot be before the start date.")
        except ValueError as error:
            flash(str(error), "error")
            return render_template(
                "trip_form.html",
                form=request.form,
                country_cities=COUNTRY_CITIES,
            ), 400

        new_trip = Trip(
            name,
            destination,
            start_date.isoformat(),
            end_date.isoformat(),
            budget,
            country=country,
            city=city,
        )
        store.add_trip(new_trip)
        flash("Trip created successfully.", "success")
        return redirect(url_for("trip_detail", trip_id=new_trip.id))

    return render_template(
        "trip_form.html",
        form={},
        country_cities=COUNTRY_CITIES,
    )


@app.post("/trip/<trip_id>/delete")
def delete_trip(trip_id):
    if store.delete_trip(trip_id):
        flash("Trip deleted.", "success")
    else:
        flash("Trip not found.", "error")

    return redirect(url_for("index"))


@app.route("/trip/<trip_id>/edit", methods=["GET", "POST"])
def edit_trip(trip_id):
    trips = store.load()
    trip = find_trip(trips, trip_id)

    if trip is None:
        flash("Trip not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            country = request.form.get("country", "").strip()
            city = request.form.get("city", "").strip()
            destination = read_location(country, city)
            start_date = read_date(request.form.get("start_date", ""), "start date")
            end_date = read_date(request.form.get("end_date", ""), "end date")
            budget = read_money(request.form.get("budget", ""), "budget")

            if not name:
                raise ValueError("Trip name is required.")
            if end_date < start_date:
                raise ValueError("End date must be on or after start date.")
        except ValueError as error:
            flash(str(error), "error")
            return render_template(
                "trip_form.html",
                form=request.form,
                trip=trip,
                edit_mode=True,
                country_cities=COUNTRY_CITIES,
            ), 400

        old_destination = trip.destination
        trip.update_details(
            name,
            destination,
            start_date.isoformat(),
            end_date.isoformat(),
            budget,
            country,
            city,
        )
        store.update_trip(trip)
        if old_destination != trip.destination and trip.activities:
            flash(
                "Trip updated. Please review and reselect activity places because the trip destination changed.",
                "warning",
            )
        else:
            flash("Trip updated successfully.", "success")
        return redirect(url_for("trip_detail", trip_id=trip.id))

    return render_template(
        "trip_form.html",
        form={},
        trip=trip,
        edit_mode=True,
        country_cities=COUNTRY_CITIES,
    )


@app.route("/trip/<trip_id>")
def trip_detail(trip_id):
    trips = store.load()
    trip = find_trip(trips, trip_id)

    if trip is None:
        flash("Trip not found.", "error")
        return redirect(url_for("index"))

    weather = weather_service.get_trip_weather(trip)
    location_mismatches = trip.get_location_mismatches()

    conflicts = trip.get_conflicts()
    conflict_activity_ids = []
    for first_activity, second_activity in conflicts:
        if first_activity.id not in conflict_activity_ids:
            conflict_activity_ids.append(first_activity.id)
        if second_activity.id not in conflict_activity_ids:
            conflict_activity_ids.append(second_activity.id)

    daily_plans = []
    activity_dates = []
    category_costs = trip.get_category_costs()
    category_percentages = trip.get_category_percentages()
    selected_category = request.args.get("category", "All").strip()
    categories = []

    all_sorted_activities = trip.get_sorted_activities()
    for activity in all_sorted_activities:
        if activity.category not in categories:
            categories.append(activity.category)

    if selected_category == "All" or selected_category not in categories:
        activities_to_display = all_sorted_activities
        selected_category = "All"
    else:
        filtered_activities = trip.get_activities_by_category(selected_category)
        activities_to_display = []
        for activity in all_sorted_activities:
            if activity in filtered_activities:
                activities_to_display.append(activity)

    for activity in activities_to_display:
        if activity.activity_date not in activity_dates:
            activity_dates.append(activity.activity_date)

    for activity_date in activity_dates:
        daily_plans.append(
            {
                "date": activity_date,
                "activities": [
                    activity
                    for activity in activities_to_display
                    if activity.activity_date == activity_date
                ],
                "cost": sum(
                    activity.cost
                    for activity in activities_to_display
                    if activity.activity_date == activity_date
                ),
                "free_time_slots": (
                    trip.get_free_time_slots(activity_date)
                    if selected_category == "All"
                    else []
                ),
            }
        )

    return render_template(
        "trip_detail.html",
        trip=trip,
        conflicts=conflicts,
        daily_plans=daily_plans,
        category_costs=category_costs,
        category_percentages=category_percentages,
        categories=categories,
        selected_category=selected_category,
        activities_to_display=activities_to_display,
        conflict_activity_ids=conflict_activity_ids,
        weather=weather,
        location_mismatches=location_mismatches,
    )


@app.get("/trip/<trip_id>/places/search")
def search_places(trip_id):
    """Search for places near the trip destination."""

    trips = store.load()
    trip = find_trip(trips, trip_id)
    if trip is None:
        return jsonify({"error": "Trip not found."}), 404

    search_text = request.args.get("q", "").strip()
    if len(search_text) < 2:
        return jsonify({"places": []})

    try:
        places = map_service.search_places(search_text, trip.destination)
    except MapServiceError as error:
        return jsonify({"error": str(error)}), 503
    except Exception:
        return jsonify({
            "error": "The place service returned an unexpected response. Try again."
        }), 503

    return jsonify({"places": places})


@app.get("/trip/<trip_id>/map-data")
def trip_map_data(trip_id):
    """Return saved activity points for the trip map."""

    trips = store.load()
    trip = find_trip(trips, trip_id)
    if trip is None:
        return jsonify({"error": "Trip not found."}), 404

    activities = []
    for activity in trip.get_sorted_activities():
        if activity.latitude is None or activity.longitude is None:
            continue
        activities.append({
            "id": activity.id,
            "title": activity.title,
            "date": activity.activity_date,
            "start_time": activity.start_time,
            "end_time": activity.end_time,
            "place_name": activity.place_name or activity.location,
            "latitude": activity.latitude,
            "longitude": activity.longitude,
        })

    return jsonify({"activities": activities})


@app.get("/trip/<trip_id>/route")
def trip_route(trip_id):
    """Return a road route for one day, or points for a direct-line fallback."""

    trips = store.load()
    trip = find_trip(trips, trip_id)
    if trip is None:
        return jsonify({"error": "Trip not found."}), 404

    target_date = request.args.get("date", "").strip()
    points = []
    for activity in trip.get_sorted_activities():
        if activity.activity_date != target_date:
            continue
        if activity.latitude is None or activity.longitude is None:
            continue
        points.append({
            "title": activity.title,
            "latitude": activity.latitude,
            "longitude": activity.longitude,
        })

    if len(points) < 2:
        return jsonify({"geometry": None, "fallback": False, "points": points})

    try:
        geometry = map_service.get_route(points)
        return jsonify({
            "geometry": geometry,
            "fallback": False,
            "points": points,
        })
    except Exception:
        return jsonify({
            "geometry": None,
            "fallback": True,
            "points": points,
        })


@app.route("/trip/<trip_id>/activity/new", methods=["GET", "POST"])
def create_activity(trip_id):
    trips = store.load()
    trip = find_trip(trips, trip_id)

    if trip is None:
        flash("Trip not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        try:
            title = request.form.get("title", "").strip()
            activity_date = read_date(request.form.get("activity_date", ""), "activity date")
            start_time = read_time(request.form.get("start_time", ""), "start time")
            end_time = read_time(request.form.get("end_time", ""), "end time")
            category = request.form.get("category", "Other")
            cost = read_money(request.form.get("cost", "0"), "cost")
            notes = request.form.get("notes", "").strip()
            place_name, latitude, longitude = read_place(
                request.form.get("place_name", ""),
                request.form.get("place_latitude", ""),
                request.form.get("place_longitude", ""),
            )

            trip_start = read_date(trip.start_date, "trip start date")
            trip_end = read_date(trip.end_date, "trip end date")

            if not title:
                raise ValueError("Activity title is required.")
            if end_time <= start_time:
                raise ValueError("End time must be after start time.")
            if activity_date < trip_start or activity_date > trip_end:
                raise ValueError("Activity date must be inside the trip dates.")
        except ValueError as error:
            flash(str(error), "error")
            return render_template("activity_form.html", trip=trip, form=request.form), 400

        new_activity = Activity(
            title,
            activity_date.isoformat(),
            start_time.strftime("%H:%M"),
            end_time.strftime("%H:%M"),
            category,
            cost,
            notes,
            location=trip.destination,
            place_name=place_name,
            latitude=latitude,
            longitude=longitude,
            place_destination=trip.destination,
        )
        store.add_activity(trip.id, new_activity)
        flash("Activity added. Check the timeline for conflicts.", "success")
        return redirect(url_for("trip_detail", trip_id=trip.id))

    return render_template("activity_form.html", trip=trip, form={})


@app.route("/trip/<trip_id>/activity/<activity_id>/edit", methods=["GET", "POST"])
def edit_activity(trip_id, activity_id):
    trips = store.load()
    trip = find_trip(trips, trip_id)

    if trip is None:
        flash("Trip not found.", "error")
        return redirect(url_for("index"))

    activity = trip.find_activity(activity_id)

    if activity is None:
        flash("Activity not found.", "error")
        return redirect(url_for("trip_detail", trip_id=trip.id))

    if request.method == "POST":
        try:
            title = request.form.get("title", "").strip()
            activity_date = read_date(request.form.get("activity_date", ""), "activity date")
            start_time = read_time(request.form.get("start_time", ""), "start time")
            end_time = read_time(request.form.get("end_time", ""), "end time")
            category = request.form.get("category", "Other")
            cost = read_money(request.form.get("cost", "0"), "cost")
            notes = request.form.get("notes", "").strip()
            place_name, latitude, longitude = read_place(
                request.form.get("place_name", ""),
                request.form.get("place_latitude", ""),
                request.form.get("place_longitude", ""),
            )

            trip_start = read_date(trip.start_date, "trip start date")
            trip_end = read_date(trip.end_date, "trip end date")

            if not title:
                raise ValueError("Activity title is required.")
            if end_time <= start_time:
                raise ValueError("End time must be after start time.")
            if activity_date < trip_start or activity_date > trip_end:
                raise ValueError("Activity date must be inside the trip dates.")
        except ValueError as error:
            flash(str(error), "error")
            return render_template(
                "activity_edit.html",
                trip=trip,
                activity=activity,
                form=request.form,
            ), 400

        activity.title = title
        activity.location = trip.destination
        activity.place_name = place_name
        activity.latitude = latitude
        activity.longitude = longitude
        activity.place_destination = request.form.get(
            "place_destination",
            activity.place_destination,
        ).strip()
        activity.activity_date = activity_date.isoformat()
        activity.start_time = start_time.strftime("%H:%M")
        activity.end_time = end_time.strftime("%H:%M")
        activity.category = category
        activity.cost = cost
        activity.notes = notes
        store.update_activity(trip.id, activity)
        flash("Activity updated successfully.", "success")
        return redirect(url_for("trip_detail", trip_id=trip.id))

    return render_template("activity_edit.html", trip=trip, activity=activity, form={})


@app.post("/trip/<trip_id>/activity/<activity_id>/delete")
def delete_activity(trip_id, activity_id):
    trips = store.load()
    trip = find_trip(trips, trip_id)

    if trip is None:
        flash("Trip not found.", "error")
        return redirect(url_for("index"))

    if not store.delete_activity(trip.id, activity_id):
        flash("Activity not found.", "error")
    else:
        flash("Activity removed.", "success")

    return redirect(url_for("trip_detail", trip_id=trip.id))


if __name__ == "__main__":
    os.makedirs(DATA_FOLDER, exist_ok=True)
    app.run(debug=True)
