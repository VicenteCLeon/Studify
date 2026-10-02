/* ==========================================================================
   RepasAi — comportamiento de la interfaz
   --------------------------------------------------------------------------
   Sin dependencias ni build. Reglas:

   - Mejora progresiva: todo flujo funciona sin este archivo; el JS solo
     agrega comodidad (tema, stepper, flashcards…).
   - Nada de funciones globales ni onclick en el HTML: cada módulo engancha
     elementos marcados con data-* y se inicializa en `htmx:load`, que HTMX
     dispara para la página inicial y para cada fragmento que inserta. Así el
     mismo código sirve para el visor del estudiante y para la cápsula que el
     simulador del docente inyecta por HTMX.
   - Cada elemento se inicializa una sola vez (data-js-ready).
   ========================================================================== */

(function () {
  "use strict";

  const THEME_KEY = "repasai-theme";
  const prefersReducedMotion = () =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /** Ejecuta `fn(el)` una vez por cada elemento que calce con `selector`. */
  function each(root, selector, fn) {
    const scope = root && root.querySelectorAll ? root : document;
    const nodes = [];
    if (scope.matches && scope.matches(selector)) nodes.push(scope);
    scope.querySelectorAll(selector).forEach((n) => nodes.push(n));
    nodes.forEach((el) => {
      if (el.dataset.jsReady) return;
      el.dataset.jsReady = "1";
      fn(el);
    });
  }

  // ------------------------------------------------------------------------
  // Tema claro/oscuro
  // El <head> ya aplicó la preferencia guardada antes de pintar (sin parpadeo);
  // acá solo se maneja el botón.
  // ------------------------------------------------------------------------
  function currentTheme() {
    const explicit = document.documentElement.dataset.theme;
    if (explicit === "light" || explicit === "dark") return explicit;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function syncThemeButtons() {
    const dark = currentTheme() === "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(dark));
      btn.setAttribute("aria-label", dark ? "Usar modo claro" : "Usar modo oscuro");
      btn.title = dark ? "Usar modo claro" : "Usar modo oscuro";
    });
  }

  function initThemeToggle(btn) {
    btn.addEventListener("click", () => {
      const next = currentTheme() === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch (e) {
        /* almacenamiento bloqueado: el cambio dura lo que la página */
      }
      syncThemeButtons();
    });
  }

  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", syncThemeButtons);

  // ------------------------------------------------------------------------
  // Registro de módulos
  // ------------------------------------------------------------------------
  const modules = [
    ["[data-theme-toggle]", initThemeToggle],
  ];

  function init(root) {
    modules.forEach(([selector, fn]) => each(root, selector, fn));
    syncThemeButtons();
  }

  document.addEventListener("htmx:load", (event) => init(event.target));
  document.addEventListener("DOMContentLoaded", () => init(document));
})();
