document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach((message) => {
    window.setTimeout(() => {
      message.style.opacity = '0';
      message.style.transform = 'translateY(-4px)';
      window.setTimeout(() => message.remove(), 250);
    }, 4500);
  });

  const deleteModal = document.querySelector('#delete-activity-modal');
  const confirmDeleteButton = document.querySelector('[data-confirm-delete-activity]');
  const closeDeleteButtons = document.querySelectorAll('[data-close-delete-modal]');
  let pendingDeleteForm = null;

  if (deleteModal && confirmDeleteButton) {
    const title = document.querySelector('#delete-activity-title');
    const category = document.querySelector('#delete-activity-category');
    const date = document.querySelector('#delete-activity-date');
    const time = document.querySelector('#delete-activity-time');
    const cost = document.querySelector('#delete-activity-cost');
    const location = document.querySelector('#delete-activity-location');
    const notes = document.querySelector('#delete-activity-notes');

    document.querySelectorAll('[data-open-delete-activity]').forEach((button) => {
      button.addEventListener('click', () => {
        pendingDeleteForm = button.closest('form');
        title.textContent = button.dataset.activityTitle;
        category.textContent = button.dataset.activityCategory;
        date.textContent = button.dataset.activityDate;
        time.textContent = button.dataset.activityTime;
        cost.textContent = button.dataset.activityCost;
        location.textContent = button.dataset.activityLocation;
        notes.textContent = button.dataset.activityNotes || 'No notes added.';
        notes.classList.toggle('empty-note', !button.dataset.activityNotes);
        deleteModal.hidden = false;
        document.body.classList.add('modal-open');
        confirmDeleteButton.focus();
      });
    });

    const closeDeleteModal = () => {
      deleteModal.hidden = true;
      pendingDeleteForm = null;
      document.body.classList.remove('modal-open');
    };

    closeDeleteButtons.forEach((button) => {
      button.addEventListener('click', closeDeleteModal);
    });

    confirmDeleteButton.addEventListener('click', () => {
      if (pendingDeleteForm) {
        pendingDeleteForm.submit();
      }
    });

    deleteModal.addEventListener('click', (event) => {
      if (event.target === deleteModal) {
        closeDeleteModal();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !deleteModal.hidden) {
        closeDeleteModal();
      }
    });
  }

  const deleteTripModal = document.querySelector('#delete-trip-modal');
  const confirmDeleteTripButton = document.querySelector('[data-confirm-delete-trip]');
  const closeDeleteTripButtons = document.querySelectorAll('[data-close-delete-trip-modal]');
  let pendingDeleteTripForm = null;

  if (deleteTripModal && confirmDeleteTripButton) {
    const name = document.querySelector('#delete-trip-name');
    const destination = document.querySelector('#delete-trip-destination');
    const dates = document.querySelector('#delete-trip-dates');
    const activities = document.querySelector('#delete-trip-activities');
    const cost = document.querySelector('#delete-trip-cost');
    const conflicts = document.querySelector('#delete-trip-conflicts');

    document.querySelectorAll('[data-open-delete-trip]').forEach((button) => {
      button.addEventListener('click', () => {
        pendingDeleteTripForm = button.closest('form');
        name.textContent = button.dataset.tripName;
        destination.textContent = button.dataset.tripDestination;
        dates.textContent = button.dataset.tripDates;
        activities.textContent = button.dataset.tripActivities;
        cost.textContent = button.dataset.tripCost;
        const conflictCount = Number(button.dataset.tripConflicts);
        conflicts.textContent = conflictCount === 0 ? 'No conflicts' : `${conflictCount} conflict${conflictCount === 1 ? '' : 's'}`;
        conflicts.classList.toggle('delete-trip-conflict', conflictCount > 0);
        deleteTripModal.hidden = false;
        document.body.classList.add('modal-open');
        confirmDeleteTripButton.focus();
      });
    });

    const closeDeleteTripModal = () => {
      deleteTripModal.hidden = true;
      pendingDeleteTripForm = null;
      document.body.classList.remove('modal-open');
    };

    closeDeleteTripButtons.forEach((button) => {
      button.addEventListener('click', closeDeleteTripModal);
    });

    confirmDeleteTripButton.addEventListener('click', () => {
      if (pendingDeleteTripForm) {
        pendingDeleteTripForm.submit();
      }
    });

    deleteTripModal.addEventListener('click', (event) => {
      if (event.target === deleteTripModal) {
        closeDeleteTripModal();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !deleteTripModal.hidden) {
        closeDeleteTripModal();
      }
    });
  }

  document.querySelectorAll('[data-clear-form]').forEach((button) => {
    button.addEventListener('click', () => {
      window.location.reload();
    });
  });

  const countryField = document.querySelector('#country');
  const cityField = document.querySelector('#city');
  const cityLabel = document.querySelector('#city-label');
  const countryCityData = document.querySelector('#country-city-data');

  if (countryField && cityField && countryCityData) {
    const countryCities = JSON.parse(countryCityData.textContent);
    const selectedCity = cityField.dataset.selectedCity;

    const updateCities = (cityToSelect) => {
      cityField.innerHTML = '';
      if (cityLabel) {
        if (countryField.value === 'China') {
          cityLabel.textContent = 'Province / region';
        } else {
          cityLabel.textContent = 'City';
        }
      }

      const emptyLabel = countryField.value === 'China'
        ? 'Select a province or region'
        : 'Select a city';
      addOption(cityField, '', emptyLabel);

      const cities = countryCities[countryField.value] || [];
      cities.forEach((city) => {
        addOption(cityField, city, city);
      });

      cityField.value = cityToSelect || '';
    };

    countryField.addEventListener('change', () => {
      updateCities('');
    });
    updateCities(selectedCity);
  }

  function addOption(select, value, label) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    select.appendChild(option);
  }

  function createSelect(className, label, required) {
    const select = document.createElement('select');
    select.className = className;
    select.setAttribute('aria-label', label);
    if (required) {
      select.required = true;
    }
    return select;
  }

  function getDateParts(value) {
    if (!value) {
      return ['', '', ''];
    }

    if (value.indexOf('/') !== -1) {
      const parts = value.split('/');
      return [parts[0], parts[1], parts[2]];
    }

    const parts = value.split('-');
    return [parts[2], parts[1], parts[0]];
  }

  document.querySelectorAll('.date-picker').forEach((field) => {
    const currentValue = field.value || field.getAttribute('value') || '';
    const dateParts = getDateParts(currentValue);
    const required = field.required;
    const wrapper = document.createElement('div');
    wrapper.className = 'date-selector-group';

    const daySelect = createSelect('date-selector', 'Day', required);
    const monthSelect = createSelect('date-selector', 'Month', required);
    const yearSelect = createSelect('date-selector year-selector', 'Year', required);
    addOption(daySelect, '', 'dd');
    addOption(monthSelect, '', 'mm');
    addOption(yearSelect, '', 'yyyy');

    for (let day = 1; day <= 31; day += 1) {
      addOption(daySelect, String(day).padStart(2, '0'), String(day).padStart(2, '0'));
    }
    for (let month = 1; month <= 12; month += 1) {
      addOption(monthSelect, String(month).padStart(2, '0'), String(month).padStart(2, '0'));
    }
    for (let year = 2000; year <= 2050; year += 1) {
      addOption(yearSelect, String(year), String(year));
    }

    daySelect.value = dateParts[0];
    monthSelect.value = dateParts[1];
    yearSelect.value = dateParts[2];
    wrapper.appendChild(daySelect);
    const firstSlash = document.createElement('span');
    firstSlash.textContent = '/';
    wrapper.appendChild(firstSlash);
    wrapper.appendChild(monthSelect);
    const secondSlash = document.createElement('span');
    secondSlash.textContent = '/';
    wrapper.appendChild(secondSlash);
    wrapper.appendChild(yearSelect);
    field.type = 'hidden';
    field.required = false;
    field.insertAdjacentElement('afterend', wrapper);

    const updateDate = () => {
      if (daySelect.value && monthSelect.value && yearSelect.value) {
        field.value = `${daySelect.value}/${monthSelect.value}/${yearSelect.value}`;
      } else {
        field.value = '';
      }
    };
    daySelect.addEventListener('change', updateDate);
    monthSelect.addEventListener('change', updateDate);
    yearSelect.addEventListener('change', updateDate);
    updateDate();
  });

  document.querySelectorAll('.time-picker').forEach((field) => {
    const currentValue = field.value || field.getAttribute('value') || '09:00';
    const timeParts = currentValue.split(':');
    const required = field.required;
    const wrapper = document.createElement('div');
    wrapper.className = 'time-selector-group';
    const hourSelect = createSelect('time-selector', 'Hour', required);
    const minuteSelect = createSelect('time-selector', 'Minute', required);
    addOption(hourSelect, '', 'hh');
    addOption(minuteSelect, '', 'mm');

    for (let hour = 0; hour <= 23; hour += 1) {
      const value = String(hour).padStart(2, '0');
      addOption(hourSelect, value, value);
    }
    for (let minute = 0; minute <= 59; minute += 1) {
      const value = String(minute).padStart(2, '0');
      addOption(minuteSelect, value, value);
    }

    hourSelect.value = timeParts[0];
    minuteSelect.value = timeParts[1];
    wrapper.appendChild(hourSelect);
    const colon = document.createElement('span');
    colon.textContent = ':';
    wrapper.appendChild(colon);
    wrapper.appendChild(minuteSelect);
    field.type = 'hidden';
    field.required = false;
    field.insertAdjacentElement('afterend', wrapper);

    const updateTime = () => {
      if (hourSelect.value && minuteSelect.value) {
        field.value = `${hourSelect.value}:${minuteSelect.value}`;
      } else {
        field.value = '';
      }
    };
    hourSelect.addEventListener('change', updateTime);
    minuteSelect.addEventListener('change', updateTime);
    updateTime();
  });
});
