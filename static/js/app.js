(function () {
  const overlay = document.getElementById("loading-overlay");
  const toggle = document.getElementById("nav-toggle");
  const sidebar = document.getElementById("sidebar");

  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
  }

  document.querySelectorAll("form[data-loading]").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (!overlay) return;
      overlay.hidden = false;
    });
  });
})();
