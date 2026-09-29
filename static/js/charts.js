function makeBar(id, labels, values, title) {
  const el = document.getElementById(id);
  if (!el || !window.SAFE_STREET_STATS) return;
  new Chart(el, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: title, data: values, backgroundColor: "#1c7a6d" }],
    },
    options: {
      plugins: { legend: { display: false }, title: { display: true, text: title } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function makeDoughnut(id, labels, values, title) {
  const el = document.getElementById(id);
  if (!el || !window.SAFE_STREET_STATS) return;
  new Chart(el, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: ["#1c7a6d", "#c2410c", "#10233a", "#c9a227"] }],
    },
    options: { plugins: { title: { display: true, text: title } } },
  });
}

(function () {
  const stats = window.SAFE_STREET_STATS;
  if (!stats) return;
  const types = Object.keys(stats.types || {});
  makeBar("chart-types", types, types.map((k) => stats.types[k]), "Damage Type Distribution");
  makeDoughnut(
    "chart-severity",
    ["High", "Medium", "Low"],
    [stats.high || 0, stats.medium || 0, stats.low || 0],
    "Severity Distribution"
  );
  makeDoughnut(
    "chart-status",
    ["Submitted", "Under Review", "Resolved"],
    [stats.pending || 0, stats.under_review || 0, stats.resolved || 0],
    "Reports by status"
  );
  const days = Object.keys(stats.by_day || {});
  makeBar("chart-time", days, days.map((k) => stats.by_day[k]), "Reports Over Time");
})();
