(() => {
  const element = document.getElementById('community-map');
  if (!element || !window.L) return;
  let items = [];
  try { items = JSON.parse(element.dataset.items || '[]'); } catch { return; }
  const center = items.length ? [items[0].lat, items[0].lng] : [20, 0];
  const map = L.map(element).setView(center, items.length ? 11 : 2);
  L.tileLayer(element.dataset.tileUrl, {maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
  const bounds = [];
  items.forEach(item => {
    const point = [item.lat, item.lng];
    bounds.push(point);
    const lost = item.type === 'LOST';
    const marker = L.circleMarker(point, {radius: 9, color: lost ? '#e7ec69' : '#888a80', fillColor: lost ? '#e7ec69' : '#33352f', fillOpacity: 0.9, weight: 2}).addTo(map);
    const popup = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = item.title;
    const location = document.createElement('p');
    location.textContent = `${lost ? 'Lost' : 'Found'} ${item.exact ? 'at the shared exact location' : `near ${item.location}`} · ${item.date}`;
    const link = document.createElement('a');
    link.href = item.url;
    link.textContent = 'View report';
    popup.append(title, location, link);
    marker.bindPopup(popup);
  });
  if (bounds.length > 1) map.fitBounds(bounds, {padding: [28, 28], maxZoom: 13});
})();
