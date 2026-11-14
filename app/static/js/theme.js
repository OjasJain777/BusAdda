(() => {
  const themeKey = "busadda-theme";
  const root = document.documentElement;
  try {
    root.dataset.theme = localStorage.getItem(themeKey) === "light" ? "light" : "dark";
  } catch {
    root.dataset.theme = "dark";
  }
  function update() {
    const dark = root.dataset.theme === "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    });
    document.querySelectorAll("[data-theme-name]").forEach((label) => {
      label.textContent = dark ? "Dark" : "Light";
    });
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#071522" : "#f3f7fa");
  }
  document.addEventListener("DOMContentLoaded", update);
  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-theme-toggle]")) return;
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    try { localStorage.setItem(themeKey, root.dataset.theme); } catch { /* theme still applies */ }
    update();
  });
})();
