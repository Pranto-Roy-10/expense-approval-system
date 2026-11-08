// Shared by every page: theme toggle and header border on scroll.
(function () {
  "use strict";

  var root = document.documentElement;

  var toggle = document.querySelector("[data-theme-toggle]");
  function syncToggle() {
    var dark = root.dataset.theme === "dark";
    toggle.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    toggle.setAttribute("aria-pressed", String(dark));
  }
  syncToggle();
  toggle.addEventListener("click", function () {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) {}
    syncToggle();
  });

  // Toasts: leave when their timer bar runs out (CSS pauses it on hover/focus) or when closed.
  document.querySelectorAll("[data-toast]").forEach(function (toast) {
    var leave = function () {
      if (toast.classList.contains("is-leaving")) return;
      toast.classList.add("is-leaving");
      toast.addEventListener("animationend", function (e) {
        if (e.target !== toast) return; // the timer bar's own animationend bubbles up too
        var stack = toast.parentNode;
        toast.remove();
        if (stack && !stack.children.length) stack.remove();
      });
    };
    toast.querySelector(".toast-timer").addEventListener("animationend", leave);
    toast.querySelector("[data-toast-close]").addEventListener("click", leave);
  });

  var header = document.querySelector(".site-header");
  if (!header) return; // signed-in pages use the sidebar instead
  function onScroll() { header.classList.toggle("is-scrolled", window.scrollY > 8); }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
})();
