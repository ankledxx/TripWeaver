import os
import sqlite3


class Database:
    def __init__(self, file_path):
        self.file_path = file_path

        folder = os.path.dirname(file_path)
        if folder:
            os.makedirs(folder, exist_ok=True)

    def connect(self):
        connection = sqlite3.connect(self.file_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create_tables(self):
        connection = self.connect()

        connection.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                destination TEXT NOT NULL,
                country TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                budget REAL NOT NULL
            )
        """)

        trip_columns = connection.execute(
            "PRAGMA table_info(trips)"
        ).fetchall()
        trip_column_names = []
        for column in trip_columns:
            trip_column_names.append(column["name"])
        if "country" not in trip_column_names:
            connection.execute(
                "ALTER TABLE trips ADD COLUMN country TEXT NOT NULL DEFAULT ''"
            )
        if "city" not in trip_column_names:
            connection.execute(
                "ALTER TABLE trips ADD COLUMN city TEXT NOT NULL DEFAULT ''"
            )

        connection.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id TEXT PRIMARY KEY,
                trip_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                activity_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                cost REAL NOT NULL,
                notes TEXT,
                location TEXT NOT NULL DEFAULT '',
                place_name TEXT NOT NULL DEFAULT '',
                latitude REAL,
                longitude REAL,
                place_destination TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (trip_id) REFERENCES trips(id)
                    ON DELETE CASCADE
            )
        """)

        activity_columns = connection.execute(
            "PRAGMA table_info(activities)"
        ).fetchall()
        column_names = []
        for column in activity_columns:
            column_names.append(column["name"])
        if "location" not in column_names:
            connection.execute(
                "ALTER TABLE activities ADD COLUMN location TEXT NOT NULL DEFAULT ''"
            )
        if "place_name" not in column_names:
            connection.execute(
                "ALTER TABLE activities ADD COLUMN place_name TEXT NOT NULL DEFAULT ''"
            )
        if "latitude" not in column_names:
            connection.execute(
                "ALTER TABLE activities ADD COLUMN latitude REAL"
            )
        if "longitude" not in column_names:
            connection.execute(
                "ALTER TABLE activities ADD COLUMN longitude REAL"
            )
        if "place_destination" not in column_names:
            connection.execute(
                "ALTER TABLE activities ADD COLUMN place_destination TEXT NOT NULL DEFAULT ''"
            )
        connection.execute("""
            UPDATE activities
            SET place_destination = location
            WHERE place_destination = ''
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS weather_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id TEXT NOT NULL,
                location TEXT NOT NULL,
                weather_date TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                timezone TEXT,
                weather_code INTEGER,
                temperature_min REAL,
                temperature_max REAL,
                precipitation_probability REAL,
                precipitation_sum REAL,
                uv_index REAL,
                wind_speed REAL,
                sunrise TEXT,
                sunset TEXT,
                fetched_at TEXT NOT NULL,
                UNIQUE (trip_id, location, weather_date),
                FOREIGN KEY (trip_id) REFERENCES trips(id)
                    ON DELETE CASCADE
            )
        """)

        connection.commit()
        connection.close()

    def load_data(self):
        connection = self.connect()
        trip_rows = connection.execute("""
            SELECT id, name, destination, country, city,
                   start_date, end_date, budget
            FROM trips
            ORDER BY rowid
        """).fetchall()
        activity_rows = connection.execute("""
            SELECT id, trip_id, title, category, activity_date,
                   start_time, end_time, cost, notes, location,
                   place_name, latitude, longitude, place_destination
            FROM activities
            ORDER BY rowid
        """).fetchall()
        connection.close()

        activities_by_trip = {}
        for activity_row in activity_rows:
            activity_data = dict(activity_row)
            trip_id = activity_data.pop("trip_id")
            if trip_id not in activities_by_trip:
                activities_by_trip[trip_id] = []
            activities_by_trip[trip_id].append(activity_data)

        saved_data = []
        for trip_row in trip_rows:
            trip_data = dict(trip_row)
            trip_data["activities"] = activities_by_trip.get(trip_data["id"], [])
            saved_data.append(trip_data)

        return saved_data

    def get_setting(self, name):
        connection = self.connect()
        row = connection.execute(
            "SELECT value FROM settings WHERE name = ?",
            (name,),
        ).fetchone()
        connection.close()

        if row is None:
            return None
        return row["value"]

    def set_setting(self, name, value):
        connection = self.connect()
        connection.execute("""
            INSERT OR REPLACE INTO settings (name, value)
            VALUES (?, ?)
        """, (name, value))
        connection.commit()
        connection.close()

    def save_trips(self, trips):
        connection = self.connect()

        connection.execute("DELETE FROM activities")
        connection.execute("DELETE FROM trips")

        for trip in trips:
            connection.execute("""
                INSERT INTO trips
                (id, name, destination, country, city,
                 start_date, end_date, budget)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trip.id,
                trip.name,
                trip.destination,
                trip.country,
                trip.city,
                trip.start_date,
                trip.end_date,
                trip.budget,
            ))

            for activity in trip.activities:
                connection.execute("""
                    INSERT INTO activities
                    (id, trip_id, title, category, activity_date,
                     start_time, end_time, cost, notes, location,
                     place_name, latitude, longitude, place_destination)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    activity.id,
                    trip.id,
                    activity.title,
                    activity.category,
                    activity.activity_date,
                    activity.start_time,
                    activity.end_time,
                    activity.cost,
                    activity.notes,
                    activity.location,
                    activity.place_name,
                    activity.latitude,
                    activity.longitude,
                    activity.place_destination,
                ))

        connection.commit()
        connection.close()

    def insert_trip(self, trip):
        connection = self.connect()
        connection.execute("""
            INSERT INTO trips
            (id, name, destination, country, city,
             start_date, end_date, budget)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trip.id,
            trip.name,
            trip.destination,
            trip.country,
            trip.city,
            trip.start_date,
            trip.end_date,
            trip.budget,
        ))
        connection.commit()
        connection.close()

    def update_trip(self, trip):
        connection = self.connect()
        result = connection.execute("""
            UPDATE trips
            SET name = ?, destination = ?, country = ?, city = ?,
                start_date = ?, end_date = ?, budget = ?
            WHERE id = ?
        """, (
            trip.name,
            trip.destination,
            trip.country,
            trip.city,
            trip.start_date,
            trip.end_date,
            trip.budget,
            trip.id,
        ))
        connection.execute(
            "UPDATE activities SET location = ? WHERE trip_id = ?",
            (trip.destination, trip.id),
        )
        connection.commit()
        connection.close()
        return result.rowcount > 0

    def delete_trip(self, trip_id):
        connection = self.connect()
        result = connection.execute(
            "DELETE FROM trips WHERE id = ?",
            (trip_id,),
        )
        connection.commit()
        connection.close()
        return result.rowcount > 0

    def insert_activity(self, trip_id, activity):
        connection = self.connect()
        connection.execute("""
            INSERT INTO activities
            (id, trip_id, title, category, activity_date,
             start_time, end_time, cost, notes, location,
             place_name, latitude, longitude, place_destination)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            activity.id,
            trip_id,
            activity.title,
            activity.category,
            activity.activity_date,
            activity.start_time,
            activity.end_time,
            activity.cost,
            activity.notes,
            activity.location,
            activity.place_name,
            activity.latitude,
            activity.longitude,
            activity.place_destination,
        ))
        connection.commit()
        connection.close()

    def update_activity(self, trip_id, activity):
        connection = self.connect()
        result = connection.execute("""
            UPDATE activities
            SET title = ?, category = ?, activity_date = ?,
                start_time = ?, end_time = ?, cost = ?, notes = ?, location = ?,
                place_name = ?, latitude = ?, longitude = ?, place_destination = ?
            WHERE id = ? AND trip_id = ?
        """, (
            activity.title,
            activity.category,
            activity.activity_date,
            activity.start_time,
            activity.end_time,
            activity.cost,
            activity.notes,
            activity.location,
            activity.place_name,
            activity.latitude,
            activity.longitude,
            activity.place_destination,
            activity.id,
            trip_id,
        ))
        connection.commit()
        connection.close()
        return result.rowcount > 0

    def delete_activity(self, trip_id, activity_id):
        connection = self.connect()
        result = connection.execute("""
            DELETE FROM activities
            WHERE id = ? AND trip_id = ?
        """, (activity_id, trip_id))
        connection.commit()
        connection.close()
        return result.rowcount > 0

    def load_weather(self, trip_id):
        connection = self.connect()
        rows = connection.execute("""
            SELECT location, weather_date, latitude, longitude, timezone,
                   weather_code, temperature_min, temperature_max,
                   precipitation_probability, precipitation_sum, uv_index,
                   wind_speed, sunrise, sunset, fetched_at
            FROM weather_cache
            WHERE trip_id = ?
            ORDER BY location, weather_date
        """, (trip_id,)).fetchall()
        connection.close()

        weather_rows = []
        for row in rows:
            weather_rows.append(dict(row))
        return weather_rows

    def save_weather(self, trip_id, weather_rows):
        connection = self.connect()
        for weather in weather_rows:
            connection.execute("""
                INSERT OR REPLACE INTO weather_cache
                (trip_id, location, weather_date, latitude, longitude,
                 timezone, weather_code, temperature_min, temperature_max,
                 precipitation_probability, precipitation_sum, uv_index,
                 wind_speed, sunrise, sunset, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trip_id,
                weather["location"],
                weather["weather_date"],
                weather["latitude"],
                weather["longitude"],
                weather.get("timezone", ""),
                weather.get("weather_code"),
                weather.get("temperature_min"),
                weather.get("temperature_max"),
                weather.get("precipitation_probability"),
                weather.get("precipitation_sum"),
                weather.get("uv_index"),
                weather.get("wind_speed"),
                weather.get("sunrise", ""),
                weather.get("sunset", ""),
                weather["fetched_at"],
            ))
        connection.commit()
        connection.close()
