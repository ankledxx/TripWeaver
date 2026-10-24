document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-place-picker]').forEach((picker) => {
    const searchUrl = picker.dataset.searchUrl;
    const searchInput = picker.querySelector('[data-place-search]');
    const searchButton = picker.querySelector('[data-search-place]');
    const results = picker.querySelector('[data-place-results]');
    const selectedPlace = picker.querySelector('[data-selected-place]');
    const placeName = picker.querySelector('[data-place-name]');
    const latitude = picker.querySelector('[data-place-latitude]');
    const longitude = picker.querySelector('[data-place-longitude]');
    const placeDestination = picker.querySelector('[data-place-destination]');

    const showSelectedPlace = () => {
      selectedPlace.textContent = placeName.value || 'No place selected';
    };

    const showMessage = (message) => {
      results.textContent = message;
      results.hidden = false;
    };

    searchButton.addEventListener('click', async () => {
      const query = searchInput.value.trim();
      if (query.length < 2) {
        showMessage('Enter at least two characters to search.');
        return;
      }

      searchButton.disabled = true;
      searchButton.textContent = 'Searching...';
      results.textContent = '';
      results.hidden = false;

      try {
        const response = await fetch(`${searchUrl}?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (!response.ok || data.error) {
          showMessage(data.error || 'Place search is temporarily unavailable.');
          return;
        }

        if (!data.places || data.places.length === 0) {
          showMessage('No places found. Try a more specific search.');
          return;
        }

        results.innerHTML = '';
        data.places.forEach((place) => {
          const resultButton = document.createElement('button');
          resultButton.type = 'button';
          resultButton.className = 'place-result';

          const name = document.createElement('strong');
          name.textContent = place.name;
          const address = document.createElement('span');
          address.textContent = place.display_name;
          resultButton.appendChild(name);
          resultButton.appendChild(address);

          resultButton.addEventListener('click', () => {
            results.querySelectorAll('.place-result').forEach((button) => {
              button.classList.remove('place-result-selected');
              button.setAttribute('aria-pressed', 'false');
            });
            resultButton.classList.add('place-result-selected');
            resultButton.setAttribute('aria-pressed', 'true');
            placeName.value = place.name;
            latitude.value = place.latitude;
            longitude.value = place.longitude;
            placeDestination.value = picker.dataset.tripDestination;
            searchInput.value = place.name;
            showSelectedPlace();
          });

          results.appendChild(resultButton);
        });
      } catch (error) {
        showMessage('Place search is temporarily unavailable. Try again.');
      } finally {
        searchButton.disabled = false;
        searchButton.textContent = 'Search';
      }
    });

    searchInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        searchButton.click();
      }
    });

    showSelectedPlace();
  });

  const mapSection = document.querySelector('[data-trip-map]');
  if (!mapSection || typeof L === 'undefined') {
    return;
  }

  const tripId = mapSection.dataset.tripId;
  const mapElement = mapSection.querySelector('#trip-map');
  const status = mapSection.querySelector('[data-map-status]');
  const legend = mapSection.querySelector('[data-map-legend]');

  const formatDate = (value) => {
    const parts = value.split('-');
    if (parts.length !== 3) {
      return value;
    }
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  };

  const addDayLegend = (date, colour) => {
    const item = document.createElement('span');
    item.className = 'map-legend-item';
    item.innerHTML = '<span class="map-legend-dot"></span>';
    item.lastChild.style.backgroundColor = colour;
    const label = document.createElement('strong');
    label.textContent = formatDate(date);
    item.appendChild(label);
    legend.appendChild(item);
  };

  const loadMap = async () => {
    try {
      const response = await fetch(`/trip/${tripId}/map-data`);
      const data = await response.json();
      if (!response.ok || data.error) {
        status.textContent = data.error || 'The activity map could not be loaded.';
        mapElement.hidden = true;
        return;
      }

      if (!data.activities || data.activities.length === 0) {
        status.textContent = 'Select a place for an activity to show it on the map.';
        mapElement.hidden = true;
        return;
      }

      const map = L.map(mapElement);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(map);

      const colours = ['#3867ff', '#00a98f', '#d94f4f', '#8d5cff', '#d18b25'];
      const groups = {};
      const bounds = [];

      data.activities.forEach((activity, index) => {
        if (!groups[activity.date]) {
          groups[activity.date] = [];
        }
        groups[activity.date].push(activity);
        bounds.push([activity.latitude, activity.longitude]);

        const marker = L.marker(
          [activity.latitude, activity.longitude],
          {
            icon: L.divIcon({
              className: 'map-number-marker',
              html: String(index + 1),
              iconSize: [30, 30],
              iconAnchor: [15, 15],
            }),
          },
        ).addTo(map);
        const popup = document.createElement('div');
        const popupTitle = document.createElement('strong');
        popupTitle.textContent = activity.title;
        popup.appendChild(popupTitle);
        popup.appendChild(document.createElement('br'));
        popup.appendChild(document.createTextNode(activity.place_name));
        popup.appendChild(document.createElement('br'));
        popup.appendChild(document.createTextNode(
          `${formatDate(activity.date)} · ${activity.start_time}–${activity.end_time}`,
        ));
        marker.bindPopup(popup);
      });

      const dates = Object.keys(groups).sort();
      const routeRequests = dates.map(async (date, index) => {
        const colour = colours[index % colours.length];
        addDayLegend(date, colour);
        const response = await fetch(`/trip/${tripId}/route?date=${encodeURIComponent(date)}`);
        const route = await response.json();
        let linePoints = [];

        if (route.geometry && route.geometry.coordinates) {
          linePoints = route.geometry.coordinates.map((point) => [point[1], point[0]]);
        } else if (route.points) {
          linePoints = route.points.map((point) => [point.latitude, point.longitude]);
        }

        if (linePoints.length >= 2) {
          L.polyline(linePoints, {
            color: colour,
            weight: 4,
            opacity: route.fallback ? 0.55 : 0.85,
            dashArray: route.fallback ? '8 8' : null,
          }).addTo(map);
        }

        return route.fallback;
      });

      const fallbackRoutes = await Promise.all(routeRequests);
      map.fitBounds(bounds, { padding: [30, 30] });
      status.textContent = fallbackRoutes.includes(true)
        ? 'Map loaded. Some segments are shown as direct lines because the road route service was unavailable.'
        : 'Map loaded. Numbered markers follow your activity order.';
    } catch (error) {
      status.textContent = 'The activity map is temporarily unavailable. Try refreshing the page.';
      mapElement.hidden = true;
    }
  };

  loadMap();
});
