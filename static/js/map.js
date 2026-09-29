(function () {
  const mapEl = document.getElementById("reports-map");
  if (!mapEl || typeof L === "undefined") return;
  const reports = window.SAFE_STREET_REPORTS || [];
  const map = L.map("reports-map").setView([17.385, 78.4867], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  const colors = { high: "#b42318", medium: "#c2410c", low: "#157347" };
  const layers = [];

  function colorFor(sev) {
    return colors[(sev || "").toLowerCase()] || "#10233a";
  }

  function render() {
    layers.forEach((l) => map.removeLayer(l));
    layers.length = 0;
    const sev = (document.getElementById("filter-severity").value || "").toLowerCase();
    const dmg = (document.getElementById("filter-damage").value || "").toLowerCase();
    const status = document.getElementById("filter-status").value || "";
    const bounds = [];
    reports.forEach(function (row) {
      if (sev && String(row.severity || "").toLowerCase() !== sev) return;
      if (dmg && String(row.damage_type || "").toLowerCase().indexOf(dmg) === -1) return;
      if (status && row.status !== status) return;
      const lat = Number(row.latitude);
      const lng = Number(row.longitude);
      if (Number.isNaN(lat) || Number.isNaN(lng)) return;
      const marker = L.circleMarker([lat, lng], {
        radius: 9,
        color: colorFor(row.severity),
        fillColor: colorFor(row.severity),
        fillOpacity: 0.85,
      }).addTo(map);
      const detailUrl = "/reports/" + encodeURIComponent(row.public_id || "");
      marker.bindPopup(
        "<strong>Road Damage</strong><br>" +
          (row.damage_type || "Damage") +
          "<br>" +
          (row.severity_label || "Priority not set") +
          "<br>" +
          (row.location_name || "—") +
          "<br>Reported: " +
          (row.date_label || String(row.created_at || "").slice(0, 10)) +
          "<br>Status: " +
          (row.status_label || "Submitted") +
          '<br><a href="' +
          detailUrl +
          '">View Report</a>'
      );
      layers.push(marker);
      bounds.push([lat, lng]);
    });
    if (bounds.length) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 15 });
  }

  ["filter-severity", "filter-damage", "filter-status"].forEach(function (id) {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", render);
    if (el) el.addEventListener("change", render);
  });

  const search = document.getElementById("map-search");
  const searchStatus = document.getElementById("map-search-status");
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
            if (searchStatus) searchStatus.textContent = "No matching place found.";
            return;
          }
          map.setView([rows[0].lat, rows[0].lon], 14);
          if (searchStatus) searchStatus.textContent = rows[0].display_name;
        })
        .catch(function () {
          if (searchStatus) searchStatus.textContent = "Location search is unavailable right now.";
        });
    });
  }

  render();
})();
