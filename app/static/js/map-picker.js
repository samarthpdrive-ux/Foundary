(() => {
  const element = document.getElementById('report-map');
  if (!element || !window.L) return;

  const latField = document.getElementById('latitude');
  const lngField = document.getElementById('longitude');
  const locateButton = document.getElementById('use-current-location');
  const status = document.getElementById('location-status');
  const clearButton = document.getElementById('clear-map-marker');
  const initialLat = Number(element.dataset.lat);
  const initialLng = Number(element.dataset.lng);
  const hasInitial = element.dataset.lat !== '' && element.dataset.lng !== '' && Number.isFinite(initialLat) && Number.isFinite(initialLng);
  const map = L.map(element).setView(hasInitial ? [initialLat, initialLng] : [20, 0], hasInitial ? 15 : 2);
  L.tileLayer(element.dataset.tileUrl, {maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);

  let marker = null;
  let accuracyCircle = null;

  const setMarker = (latlng, {accuracy = null, zoom = 16} = {}) => {
    latField.value = latlng.lat.toFixed(6);
    lngField.value = latlng.lng.toFixed(6);
    if (!marker) {
      marker = L.marker(latlng, {draggable: true}).addTo(map);
      marker.on('dragend', () => {
        const point = marker.getLatLng();
        latField.value = point.lat.toFixed(6);
        lngField.value = point.lng.toFixed(6);
        if (accuracyCircle) {
          map.removeLayer(accuracyCircle);
          accuracyCircle = null;
        }
        if (status) status.textContent = 'Pin adjusted. The selected point will be saved with the report.';
      });
    } else {
      marker.setLatLng(latlng);
    }
    if (accuracyCircle) map.removeLayer(accuracyCircle);
    accuracyCircle = accuracy === null ? null : L.circle(latlng, {
      radius: accuracy,
      color: '#e7ec69',
      fillColor: '#e7ec69',
      fillOpacity: 0.12,
      weight: 2,
    }).addTo(map);
    map.setView(latlng, zoom);
  };

  if (hasInitial) setMarker(L.latLng(initialLat, initialLng));

  map.on('click', event => {
    setMarker(event.latlng, {zoom: Math.max(map.getZoom(), 15)});
    if (status) status.textContent = 'Map pin selected. The selected point will be saved with the report.';
  });

  locateButton?.addEventListener('click', () => {
    if (!window.isSecureContext || !navigator.geolocation) {
      if (status) status.textContent = 'Location access needs HTTPS or localhost and a browser that supports location.';
      return;
    }

    locateButton.disabled = true;
    locateButton.textContent = 'Finding your location…';
    if (status) status.textContent = 'Your browser may ask for permission. Waiting for a high-accuracy location fix…';

    navigator.geolocation.getCurrentPosition(
      position => {
        const point = L.latLng(position.coords.latitude, position.coords.longitude);
        const accuracy = Math.max(1, position.coords.accuracy || 1);
        const zoom = Math.max(15, Math.min(19, Math.round(18 - Math.log2(Math.max(accuracy, 5) / 10))));
        setMarker(point, {accuracy, zoom});
        if (status) status.textContent = `Location selected. Browser accuracy is about ${Math.round(accuracy)} m. Drag the pin to adjust it. Exact coordinates stay private; public pins are rounded.`;
        locateButton.disabled = false;
        locateButton.textContent = 'Update my current location';
      },
      error => {
        const messages = {
          1: 'Location permission was denied. Allow location for this site in your browser settings to try again.',
          2: 'Your device could not determine a location. Check location services or choose a point on the map.',
          3: 'Location lookup timed out. Try again outdoors or choose a point on the map.',
        };
        if (status) status.textContent = messages[error.code] || 'Location could not be read. Choose a point on the map instead.';
        locateButton.disabled = false;
        locateButton.textContent = 'Try current location again';
      },
      {enableHighAccuracy: true, maximumAge: 0, timeout: 20000},
    );
  });

  clearButton?.addEventListener('click', () => {
    latField.value = '';
    lngField.value = '';
    if (marker) { map.removeLayer(marker); marker = null; }
    if (accuracyCircle) { map.removeLayer(accuracyCircle); accuracyCircle = null; }
    if (status) status.textContent = 'Map pin cleared. No coordinates will be saved with this report.';
  });
})();
