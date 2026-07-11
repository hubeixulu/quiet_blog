(function () {
  "use strict";
  try {
    if (localStorage.theme === "dark" || (!("theme" in localStorage) && matchMedia("(prefers-color-scheme:dark)").matches)) {
      document.documentElement.classList.add("dark");
    }
  } catch (error) { /* Storage may be unavailable in privacy mode. */ }

  document.addEventListener("DOMContentLoaded", function () {
    var button = document.getElementById("theme");
    if (!button) return;
    button.addEventListener("click", function () {
      document.documentElement.classList.toggle("dark");
      try { localStorage.theme = document.documentElement.classList.contains("dark") ? "dark" : "light"; }
      catch (error) { /* Theme still works for the current page. */ }
    });
  });
})();
