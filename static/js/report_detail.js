(function () {
    const mapEl = document.getElementById('detailMap');
    // الإحداثيات قادمة من خصائص data-* التي سنضيفها
    const lat = mapEl.dataset.lat;
    const lng = mapEl.dataset.lng;
  
    if (lat && lng) {
      const map = L.map(mapEl);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                  { attribution: '© OpenStreetMap' }).addTo(map);
  
      L.marker([lat, lng]).addTo(map)
        .bindPopup(mapEl.dataset.cat || 'Report')
        .openPopup();
  
      map.setView([lat, lng], 17);
    } else {
      mapEl.innerHTML =
        '<div class="h-100 d-flex justify-content-center align-items-center text-muted">No location provided</div>';
    }
  })();
  