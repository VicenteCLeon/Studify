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
  // Catálogo: filtro de temas en el cliente
  // ------------------------------------------------------------------------
  const normalize = (t) =>
    t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

  function initCatalogFilter(input) {
    const items = Array.from(document.querySelectorAll("[data-catalog-item]"));
    const groups = Array.from(document.querySelectorAll("[data-catalog-group]"));
    const count = document.querySelector("[data-catalog-count]");
    const empty = document.querySelector("[data-catalog-empty]");
    const openState = new Map();
    groups.forEach((g) => g.tagName === "DETAILS" && openState.set(g, g.open));
    items.forEach((it) => (it.dataset.norm = normalize(it.dataset.search || "")));

    input.addEventListener("input", () => {
      const terms = normalize(input.value.trim()).split(/\s+/).filter(Boolean);
      let visibles = 0;
      items.forEach((it) => {
        const ok = terms.every((t) => it.dataset.norm.includes(t));
        it.hidden = !ok;
        if (ok) visibles++;
      });
      // Grupos sin coincidencias se ocultan; los que tienen se abren mientras
      // se busca y vuelven a su estado original al borrar la búsqueda.
      groups.forEach((g) => {
        const any = g.querySelector("[data-catalog-item]:not([hidden])");
        g.hidden = !any;
        if (g.tagName === "DETAILS") g.open = terms.length ? !!any : openState.get(g);
      });
      if (empty) empty.hidden = visibles !== 0;
      if (count) {
        count.textContent = terms.length
          ? `${visibles} resultado${visibles === 1 ? "" : "s"}`
          : `${items.length} tema${items.length === 1 ? "" : "s"} disponible${items.length === 1 ? "" : "s"}`;
      }
    });
  }

  // ------------------------------------------------------------------------
  // "Generando tu cápsula…": ocupa la espera del GET al visor
  // ------------------------------------------------------------------------
  let generandoTimer = null;

  function openGenerando(link) {
    const layer = document.querySelector("[data-generando]");
    if (!layer) return;
    layer.querySelector("[data-generando-codigo]").textContent = link.dataset.codigo || "OA";
    layer.querySelector("[data-generando-tema]").textContent = link.dataset.tema || "Tema seleccionado";
    const pasos = Array.from(layer.querySelectorAll("[data-paso]"));
    const live = layer.querySelector("[data-generando-live]");
    let i = 0;
    const marcar = () => {
      pasos.forEach((p, k) => {
        p.classList.toggle("is-done", k < i);
        p.classList.toggle("is-active", k === i);
      });
      if (live && pasos[i]) live.textContent = pasos[i].textContent;
    };
    marcar();
    layer.hidden = false;
    document.body.classList.add("is-generando");
    requestAnimationFrame(() => layer.classList.add("is-open"));
    layer.querySelector('[role="dialog"]').focus({ preventScroll: true });
    clearInterval(generandoTimer);
    // Avanza hasta el último paso y se queda ahí: no promete un final que no
    // controla (la página llega cuando el modelo termina).
    generandoTimer = setInterval(() => {
      if (i < pasos.length - 1) {
        i++;
        marcar();
      }
    }, 2600);
  }

  function closeGenerando() {
    const layer = document.querySelector("[data-generando]");
    clearInterval(generandoTimer);
    document.body.classList.remove("is-generando");
    if (!layer) return;
    layer.classList.remove("is-open");
    layer.hidden = true;
  }

  function initStudyLink(link) {
    link.addEventListener("click", (e) => {
      // Abrir en otra pestaña no deja esta página esperando.
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      if (document.body.classList.contains("is-generando")) {
        e.preventDefault(); // evita el doble clic mientras ya se genera
        return;
      }
      openGenerando(link);
    });
  }

  // Al volver con "atrás" el navegador puede restaurar la página tal cual
  // quedó (bfcache), con la capa abierta: se cierra.
  window.addEventListener("pageshow", closeGenerando);

  // ------------------------------------------------------------------------
  // Cápsula: tarjetas de repaso (flashcards)
  // Lee los textos de la lista que el servidor ya dibujó (visible sin JS) y
  // arma el mazo interactivo encima. Enter/Espacio voltea (es un <button>);
  // las flechas cambian de tarjeta.
  // ------------------------------------------------------------------------
  function initFlashcards(root) {
    const items = Array.from(root.querySelectorAll("[data-fc-lista] > li")).map((li) => ({
      anverso: li.querySelector(".fc-anverso").textContent,
      reverso: li.querySelector(".fc-reverso").textContent,
    }));
    if (!items.length) return;
    const card = root.querySelector("[data-fc-card]");
    const front = root.querySelector("[data-fc-front]");
    const back = root.querySelector("[data-fc-back]");
    const backFace = root.querySelector(".flashcard-reverso");
    const frontFace = root.querySelector(".flashcard-frente");
    const counter = root.querySelector("[data-fc-counter]");
    const fill = root.querySelector("[data-fc-fill]");
    const prev = root.querySelector("[data-fc-prev]");
    const next = root.querySelector("[data-fc-next]");
    const live = root.querySelector("[data-fc-live]");
    let i = 0;
    let flipped = false;

    function setFlipped(value) {
      flipped = value;
      card.classList.toggle("is-flipped", flipped);
      card.setAttribute("aria-pressed", String(flipped));
      // Solo la cara visible se expone al lector de pantalla.
      frontFace.setAttribute("aria-hidden", String(flipped));
      backFace.setAttribute("aria-hidden", String(!flipped));
      if (live) live.textContent = flipped ? `Respuesta: ${items[i].reverso}` : "";
    }

    function render() {
      front.textContent = items[i].anverso;
      back.textContent = items[i].reverso;
      counter.textContent = `${i + 1} / ${items.length}`;
      fill.style.width = `${((i + 1) / items.length) * 100}%`;
      prev.disabled = i === 0;
      next.disabled = i === items.length - 1;
      card.setAttribute("aria-label", `Tarjeta ${i + 1} de ${items.length}. ${items[i].anverso}. Activa para voltear.`);
      root.classList.toggle("is-last", i === items.length - 1);
    }

    function go(delta) {
      const target = i + delta;
      if (target < 0 || target >= items.length) return;
      const swap = () => {
        i = target;
        render();
        if (live) live.textContent = `Tarjeta ${i + 1} de ${items.length}`;
      };
      if (flipped) {
        setFlipped(false);
        // Espera a que la tarjeta vuelva antes de cambiar el texto.
        setTimeout(swap, prefersReducedMotion() ? 0 : 220);
      } else {
        swap();
      }
    }

    card.addEventListener("click", () => setFlipped(!flipped));
    prev.addEventListener("click", () => go(-1));
    next.addEventListener("click", () => go(1));
    root.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight") { go(1); e.preventDefault(); }
      else if (e.key === "ArrowLeft") { go(-1); e.preventDefault(); }
    });

    root.classList.add("is-ready");
    render();
    setFlipped(false);
  }

  // ------------------------------------------------------------------------
  // Cápsula: cuestionario de varias preguntas
  // El servidor espera todas las respuestas juntas en `answer` ("0,2,1").
  // ------------------------------------------------------------------------
  function initMultiQuiz(form) {
    const total = Number(form.dataset.total) || 0;
    form.addEventListener("htmx:configRequest", (e) => {
      const answers = [];
      for (let k = 0; k < total; k++) {
        const sel = form.querySelector(`input[name="preg_${k}"]:checked`);
        if (sel) answers.push(sel.value);
      }
      e.detail.parameters.answer = answers.join(",");
    });
  }

  // ------------------------------------------------------------------------
  // Referencias: extracto del fragmento recortado con "Ver completo"
  // ------------------------------------------------------------------------
  function initExtracto(quote) {
    const btn = quote.parentElement.querySelector("[data-extracto-toggle]");
    if (!btn) return;
    quote.classList.add("is-clamped");
    // Si el texto cabe entero, el botón sobra.
    requestAnimationFrame(() => {
      if (quote.scrollHeight <= quote.clientHeight + 2) {
        quote.classList.remove("is-clamped");
        return;
      }
      btn.hidden = false;
      const label = btn.querySelector("[data-extracto-label]");
      btn.addEventListener("click", () => {
        const open = quote.classList.toggle("is-clamped") === false;
        btn.setAttribute("aria-expanded", String(open));
        label.textContent = open ? "Ver menos" : "Ver fragmento completo";
      });
    });
  }

  // ------------------------------------------------------------------------
  // Registro de módulos
  // ------------------------------------------------------------------------
  const modules = [
    ["[data-theme-toggle]", initThemeToggle],
    ["[data-vark-stepper]", initVarkStepper],
    ["[data-catalog-filter]", initCatalogFilter],
    ["[data-study-link]", initStudyLink],
    ["[data-flashcards]", initFlashcards],
    ["[data-multiquiz]", initMultiQuiz],
    ["[data-extracto]", initExtracto],
  ];

  function init(root) {
    modules.forEach(([selector, fn]) => each(root, selector, fn));
    syncThemeButtons();
  }

  document.addEventListener("htmx:load", (event) => init(event.target));
  document.addEventListener("DOMContentLoaded", () => init(document));
})();
