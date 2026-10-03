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
  // Cuestionario VARK: un paso a la vez sobre el mismo <form>
  // Los pasos se ocultan con `hidden`, que no excluye sus casillas del envío:
  // HTMX serializa el formulario completo igual que sin JS.
  // ------------------------------------------------------------------------
  const VARK_KEY = "repasai-vark-borrador";

  function initVarkStepper(form) {
    const steps = Array.from(form.querySelectorAll("[data-step]"));
    const total = Number(form.dataset.total) || steps.length - 2;
    const last = steps.length - 1;
    const prevBtn = form.querySelector("[data-vark-prev]");
    const nextBtn = form.querySelector("[data-vark-next]");
    const nextLabel = form.querySelector("[data-vark-next-label]");
    const label = form.querySelector("[data-vark-label]");
    const count = form.querySelector("[data-vark-count]");
    const fill = form.querySelector("[data-vark-fill]");
    const live = form.querySelector("[data-vark-live]");
    const resumen = form.querySelector("[data-vark-resumen]");
    const vacio = form.querySelector("[data-vark-vacio]");
    const mapa = Array.from(form.querySelectorAll("[data-goto]"));
    const errorBox = form.querySelector("#form-error");
    let current = 0;

    const boxes = (i) => Array.from(steps[i].querySelectorAll('input[type="checkbox"]'));
    const isAnswered = (i) => boxes(i).some((b) => b.checked);
    const answeredCount = () => {
      let n = 0;
      for (let i = 1; i <= total; i++) if (isAnswered(i)) n++;
      return n;
    };

    // Borrador en sessionStorage: una recarga accidental en el celular no
    // borra lo ya respondido. Se descarta al enviar con éxito.
    function save() {
      const data = { paso: current, marcadas: [] };
      form.querySelectorAll('input[type="checkbox"]:checked').forEach((b) =>
        data.marcadas.push(b.name + "=" + b.value)
      );
      ["rango_etario", "genero", "carrera"].forEach((n) => {
        if (form.elements[n]) data[n] = form.elements[n].value;
      });
      try {
        sessionStorage.setItem(VARK_KEY, JSON.stringify(data));
      } catch (e) { /* sin almacenamiento: el borrador no persiste */ }
    }

    function restore() {
      let data = null;
      try {
        data = JSON.parse(sessionStorage.getItem(VARK_KEY) || "null");
      } catch (e) { data = null; }
      if (!data) return 0;
      (data.marcadas || []).forEach((pair) => {
        const [name, value] = pair.split("=");
        const box = form.querySelector(`input[name="${name}"][value="${value}"]`);
        if (box) box.checked = true;
      });
      ["rango_etario", "genero", "carrera"].forEach((n) => {
        if (form.elements[n] && data[n] != null) form.elements[n].value = data[n];
      });
      return Math.min(Math.max(Number(data.paso) || 0, 0), last);
    }

    function updateMeta() {
      const n = answeredCount();
      count.textContent = `${n} de ${total} respondidas`;

      if (current === 0) nextLabel.textContent = "Comenzar";
      else if (current === total) nextLabel.textContent = "Revisar";
      else nextLabel.textContent = isAnswered(current) ? "Siguiente" : "Saltar";

      mapa.forEach((btn) => {
        const i = Number(btn.dataset.goto);
        const ok = isAnswered(i);
        btn.classList.toggle("is-answered", ok);
        btn.setAttribute("aria-label", `Pregunta ${i}: ${ok ? "respondida" : "en blanco"}`);
      });

      if (resumen) {
        const blancos = total - n;
        resumen.textContent =
          n === 0
            ? "Todavía no marcas ninguna alternativa."
            : `Respondiste ${n} de ${total} situaciones` +
              (blancos ? ` y dejaste ${blancos} en blanco. Está bien: también es parte del instrumento.` : ". ¡Bien hecho!");
      }
      // Si el servidor ya explicó el problema en #form-error, el aviso propio sobra.
      const serverError = errorBox && errorBox.textContent.trim() !== "";
      if (vacio) vacio.hidden = n !== 0 || serverError;
    }

    function show(i, opts = {}) {
      const dir = i >= current ? "next" : "prev";
      current = i;
      steps.forEach((s, k) => {
        s.hidden = k !== i;
        s.classList.remove("enter-next", "enter-prev");
      });
      const step = steps[i];
      if (!opts.instant && !prefersReducedMotion()) {
        void step.offsetWidth; // reinicia la animación de entrada
        step.classList.add(dir === "next" ? "enter-next" : "enter-prev");
      }

      const pct = (i / last) * 100;
      fill.style.width = `${pct}%`;
      label.textContent =
        i === 0 ? "Antes de empezar" : i === last ? "Revisión final" : `Pregunta ${i} de ${total}`;
      live.textContent = label.textContent;

      prevBtn.disabled = i === 0;
      nextBtn.hidden = i === last;
      form.classList.toggle("is-final", i === last);
      updateMeta();
      save();

      if (!opts.instant) {
        const focusTarget = step.querySelector("[data-step-focus]");
        if (focusTarget) focusTarget.focus({ preventScroll: true });
        const top = form.getBoundingClientRect().top + window.scrollY - 80;
        if (window.scrollY > top) window.scrollTo({ top, behavior: prefersReducedMotion() ? "auto" : "smooth" });
      }
    }

    prevBtn.addEventListener("click", () => current > 0 && show(current - 1));
    nextBtn.addEventListener("click", () => current < last && show(current + 1));
    mapa.forEach((btn) => btn.addEventListener("click", () => show(Number(btn.dataset.goto))));

    form.addEventListener("change", () => {
      // Un error del envío anterior ya no describe las respuestas actuales.
      if (errorBox) errorBox.innerHTML = "";
      updateMeta();
      save();
    });

    // Atajos: 1–4 marcan/desmarcan la alternativa; Enter avanza.
    form.addEventListener("keydown", (e) => {
      if (current < 1 || current > total) return;
      if (e.target.matches('input[type="text"], select, textarea')) return;
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const n = Number(e.key);
      if (n >= 1 && n <= 4) {
        const box = boxes(current)[n - 1];
        if (box) {
          box.checked = !box.checked;
          box.dispatchEvent(new Event("change", { bubbles: true }));
          box.focus();
          e.preventDefault();
        }
      } else if (e.key === "Enter" && e.target.matches('input[type="checkbox"]')) {
        e.preventDefault();
        show(current + 1);
      }
    });

    // Éxito: el servidor responde 204 + HX-Redirect; se descarta el borrador.
    // Tiene que ser beforeOnLoad: HTMX navega por HX-Redirect antes de
    // disparar afterRequest.
    form.addEventListener("htmx:beforeOnLoad", (e) => {
      if (e.detail.xhr && e.detail.xhr.status === 204) {
        try { sessionStorage.removeItem(VARK_KEY); } catch (err) { /* nada */ }
      }
    });

    // Un error del servidor llega a #form-error, en el paso final: se trae a la vista.
    form.addEventListener("htmx:afterSwap", (e) => {
      if (e.detail.target && e.detail.target.id === "form-error" && e.detail.target.textContent.trim()) {
        updateMeta();
        e.detail.target.scrollIntoView({ block: "center", behavior: prefersReducedMotion() ? "auto" : "smooth" });
      }
    });

    form.classList.add("is-stepper");
    show(restore(), { instant: true });
  }

  // ------------------------------------------------------------------------
  // Registro de módulos
  // ------------------------------------------------------------------------
  const modules = [
    ["[data-theme-toggle]", initThemeToggle],
    ["[data-vark-stepper]", initVarkStepper],
  ];

  function init(root) {
    modules.forEach(([selector, fn]) => each(root, selector, fn));
    syncThemeButtons();
  }

  document.addEventListener("htmx:load", (event) => init(event.target));
  document.addEventListener("DOMContentLoaded", () => init(document));
})();
