(function () {
  const mapEl = document.getElementById("picker-map");
  if (!mapEl || typeof L === "undefined") return;

  const latInput = document.getElementById("latitude");
  const lonInput = document.getElementById("longitude");
  const nameInput = document.getElementById("location_name");
  const summary = document.getElementById("selected-summary");
  const geoBtn = document.getElementById("use-geo");
  const geoStatus = document.getElementById("geo-status");
  const search = document.getElementById("place-search");

  const startLat = parseFloat(latInput.value) || 17.385;
  const startLon = parseFloat(lonInput.value) || 78.4867;
  const map = L.map("picker-map").setView([startLat, startLon], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);
  let marker = L.marker([startLat, startLon], { draggable: true }).addTo(map);

  function updateSummary() {
    summary.textContent = nameInput.value || "Location not set yet";
  }

  function setLatLng(lat, lng, label) {
    latInput.value = Number(lat).toFixed(6);
    lonInput.value = Number(lng).toFixed(6);
    marker.setLatLng([lat, lng]);
    map.setView([lat, lng], 15);
    if (label) nameInput.value = label;
    updateSummary();
  }

  marker.on("dragend", function (e) {
    const p = e.target.getLatLng();
    setLatLng(p.lat, p.lng);
  });
  map.on("click", function (e) {
    setLatLng(e.latlng.lat, e.latlng.lng);
  });

  if (geoBtn) {
    geoBtn.addEventListener("click", function () {
      if (!navigator.geolocation) {
        geoStatus.textContent = "Geolocation is not available in this browser.";
        return;
      }
      geoStatus.textContent = "Waiting for location permission…";
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          setLatLng(pos.coords.latitude, pos.coords.longitude, nameInput.value || "Current location");
          geoStatus.textContent = "Current location captured with your permission.";
        },
        function () {
          geoStatus.textContent = "Permission denied or location unavailable. Enter an address or use the map.";
        }
      );
    });
  }

  if (search) {
    search.addEventListener("keydown", function (event) {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const q = search.value.trim();
      if (!q) return;
      fetch("https://nominatim.openstreetmap.org/search?format=json&q=" + encodeURIComponent(q), {
        headers: { Accept: "application/json" },
      })
        .then((r) => r.json())
        .then((rows) => {
          if (!rows.length) {
            geoStatus.textContent = "No matching place found.";
            return;
          }
          setLatLng(rows[0].lat, rows[0].lon, rows[0].display_name);
        })
        .catch(function () {
          geoStatus.textContent = "Place search failed. Type an address or click the map.";
        });
    });
  }

  nameInput.addEventListener("input", updateSummary);
  updateSummary();
})();
