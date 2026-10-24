# TripWeaver

TripWeaver is a local travel itinerary planner for the COMP9001 Final Project. It helps users create trips, manage activities, view a timeline, monitor a budget, identify overlapping activities, and find free time between scheduled activities.

## Requirements

- Python 3.10 or newer
- Flask 2.3.3

## Run the project

From this folder:

```text
python -m pip install -r requirements.txt
python main.py
```

Open `http://127.0.0.1:5000` in a browser.

The first run creates `data/tripweaver.db` with a small demonstration trip. If an older `data/trips.json` file is present, it is imported into SQLite once and kept as a backup. The project uses SQLite, so it does not require a separate database server or an internet connection after Flask is installed.

## Current features

- Dashboard with trip, activity, and budget summaries
- Create, edit, and delete trips
- Add, edit, and remove activities
- Timeline view sorted by date and start time
- Activity duration labels and total planned activity time
- Overlap detection for activities on the same day
- Free-time detection that handles overlapping activities
- Category spending totals, percentages, and progress bars
- Category filtering for the itinerary timeline
- Daily cost and daily itinerary summaries
- Open-Meteo weather forecasts for every trip and activity location
- Country and city selection with city options filtered by country
- Activity locations derived automatically from the selected trip location
- Daily minimum and maximum temperatures, rain probability, rainfall, UV index, wind, sunrise, and sunset
- SQLite weather caching with a graceful offline fallback
- Map view with numbered activity markers and daily activity routes
- Place selection through Nominatim search instead of free-text activity locations
- Clear warnings when a trip destination changes and existing activity places need review
- Persistent activity-place warnings that disappear only after the activity is matched to the current trip destination
- Friendly messages for empty search results, network failures, and invalid map responses
- Short-lived in-memory caching for place searches and road routes
- SQLite persistence through `data/tripweaver.db`
- One-time migration from the older `data/trips.json` file
- Automated tests for the core planning logic

## COMP9001 concepts demonstrated

- Basic classes and objects: `Trip`, `Activity`, and `TripStore`
- Basic constructors using `__init__`
- Functions and modular decomposition
- Lists, dictionaries, JSON migration, and SQLite data storage
- `try/except` validation through readable `ValueError` handling
- Nested loops for conflict detection
- Ordinary class methods such as `add_activity`, `get_total_cost`, and `get_conflicts`
- Flask routes, HTML forms, Jinja templates, and CSS layout
- Input validation for dates, times, names, and non-negative costs

## Reproducibility notes

The tutor can reproduce the current version by installing the single pinned dependency in `requirements.txt` and running `python main.py`. The application uses a local SQLite database and does not require a separate database server. Weather display requires an internet connection to Open-Meteo; if the service is unavailable, the application keeps cached results and shows a clear notice. The map uses Leaflet from its public CDN, OpenStreetMap tiles, Nominatim place search, and OSRM road routes. Map display therefore requires an internet connection and must keep the visible OpenStreetMap attribution. If place search or road routing is unavailable, saved markers remain available and the interface falls back to direct lines between selected points. Nominatim is used only after the user presses Search, not as an autocomplete service. Place searches are cached for one hour and routes for one day while the Flask process is running. Any future dependency will be recorded here with setup instructions and a sample-data fallback.
