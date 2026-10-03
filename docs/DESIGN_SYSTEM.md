# RepasAi — Design system

Guía de la capa de presentación de la web (`src/studify/web/`). Describe los tokens, los
componentes y las convenciones que usa toda la UI desde el rediseño del 02-oct-2026
(`AVANCE.md`, sección 5 duovicies). **Léase antes de tocar un template o el CSS.**

> La marca visible es **RepasAi**. "Studify" sigue siendo el nombre del repo y del paquete.

Referencia viva: con el servidor levantado, **`/static/styleguide.html`** muestra la paleta,
los botones, badges, chips VARK, alertas, formularios, tablas, acordeón, skeleton y estados
vacíos, en claro y oscuro. Ninguna vista la enlaza.

---

## 1. Principios

| Principio | En la práctica |
|---|---|
| **Educativa, cálida, no corporativa** | Neutros tipo papel, primario verde azulado, acento coral "marcador", titulares serif. |
| **Sin build** | Jinja2 + HTMX + un CSS y un JS propios. Nada de Tailwind, npm ni bundlers. |
| **Mejora progresiva** | Todo flujo funciona sin JS (el cuestionario muestra los 16 ítems, las flashcards se ven como lista). El JS solo agrega comodidad. |
| **Mobile-first** | Se diseña a 390 px y se amplía. Sin scroll horizontal en ninguna vista. Objetivo táctil mínimo de 44 px. |
| **Accesible (WCAG AA)** | Contraste verificado, foco visible, `aria-*`, labels reales, `prefers-reduced-motion`. |
| **El color nunca va solo** | Cada canal VARK, estado o aviso lleva además ícono y texto. |

---

## 2. Dónde vive cada cosa

```
web/
├─ static/
│  ├─ css/app.css          # TODO el CSS, ordenado por capas (ver §3)
│  ├─ js/app.js            # comportamiento, sin dependencias (ver §6)
│  ├─ icons/sprite.svg     # 54 íconos de Lucide (ISC) como <symbol>
│  ├─ img/favicon.svg      # marca: cápsula en dos mitades
│  ├─ img/textura-escolar.svg  # textura de la marca original, monocroma (máscara CSS)
│  └─ styleguide.html      # referencia viva
└─ templates/
   ├─ base.html            # layout: head, header, nav, footer, tabbar móvil
   ├─ landing.html         # portada en "/"
   ├─ components/ui.html   # macros reutilizables (ver §5)
   ├─ components/_generando.html  # pantalla "Generando tu cápsula…"
   ├─ student/…            # cuestionario, perfil, catálogo, visor y parciales HTMX
   └─ teacher/…            # login, curación, analíticas, simulador y parciales HTMX
```

`app.css` está en **capas**; cada una solo usa lo de las anteriores:

1. **Tokens** (`:root`) · 2. **Tema oscuro** · 3. **Base** (reset, elementos HTML, foco) ·
4. **Layout** (container, stack, cluster, shell de la app) · 5. **Componentes** ·
6. **Pantallas** (una sección por vista: 6.1 landing … 6.7 panel docente) ·
7. **Utilidades** · 8. **Motion** (keyframes y `prefers-reduced-motion`).

Estilos nuevos de una vista van en su sección de la capa 6; si algo se repite en dos vistas,
sube a la capa 5 como componente.

---

## 3. Tokens

Siempre `var(--token)`; nunca un hexadecimal suelto en un template ni en una regla de pantalla.
Los colores se redefinen en modo oscuro, así que un hex fijo rompe ese modo.

### Color

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `--bg` / `--bg-subtle` | `#FBF8F3` / `#F4EFE6` | `#11161B` / `#151B21` | Fondo de página / bandas |
| `--surface` / `--surface-sunken` | `#FFFFFF` / `#F4EFE6` | `#182028` / `#0D1216` | Tarjetas / pozos, pistas de barras |
| `--border` / `--border-strong` | `#E7E0D4` / `#D3C9B8` | `#2A343E` / `#3A4651` | Bordes |
| `--text` / `--text-muted` / `--text-soft` | `#1F2933` / `#56606B` / `#646D78` | `#E9ECEF` / `#AAB4BF` / `#8D98A4` | Texto (todos ≥ 4,5:1) |
| `--primary` (+ `-hover`, `-soft`, `-text`, `-contrast`) | `#0F766E` | `#2CC5B1` | Acción principal, enlaces, foco |
| `--accent` (+ `-soft`, `-text`, `-contrast`) | `#F2795A` | `#FF8E70` | CTA destacados, subrayado marcador, activación |
| `--success` / `--danger` / `--warning` (+ `-soft`, `-text`) | | | Estados |

Reglas: texto sobre fondo → `--*-text` (nunca `--accent` como texto); fondo tintado → `--*-soft`;
texto sobre un relleno sólido de marca → `--*-contrast`.

### Tipografía

- **Display:** *Fraunces* (serif con eje óptico) para `h1`–`h4`, cifras grandes y la activación.
- **Texto:** *Figtree* para todo lo demás. Ambas desde Google Fonts, con fallback de sistema.
- Escala fluida: `--fs-xs` (12) · `sm` (14) · `base` (16) · `md` (17) · `lg` · `xl` · `2xl` · `3xl` · `4xl` (`clamp()`).
- Lectura larga: `--measure: 68ch`, interlineado 1,6–1,75.

### Espacio, forma, sombra, movimiento

- Espaciado en escala de 4 px: `--space-1` (4) … `--space-20` (80).
- Radios: `--radius-sm` 8 · `md` 12 · `lg` 18 · `xl` 24 · `full`. Botones y chips son píldora.
- Sombras cálidas y sutiles: `--shadow-xs` → `--shadow-lg`.
- Motion: `--ease-out`, `--ease-spring`, `--dur-fast` (120 ms) · `base` (200) · `slow` (360).
- Layout: `--container` 1160 px, `--gutter` fluido, `--header-h` y `--tabbar-h` 64 px.

### Modo oscuro

Por `prefers-color-scheme` y, si el usuario lo elige con el botón del header, por
`[data-theme="dark"|"light"]` en `<html>` (guardado en `localStorage`). Los dos bloques de
tokens oscuros de `app.css` (§2 del archivo) **deben mantenerse idénticos**. El tema se aplica
con un script inline en `<head>` antes del primer pintado, para que no haya destello.

---

## 4. Dimensiones VARK

| Canal | Token | Ícono | Aparece en |
|---|---|---|---|
| **V** · Visual | `--vark-v` azul | `eye` | tablas, esquemas |
| **A** · Auditivo | `--vark-a` ámbar | `headphones` | analogías, audio |
| **R** · Lectura / Escritura | `--vark-r` violeta | `book-open` | glosario |
| **K** · Kinestésico | `--vark-k` verde | `hand` | ejemplo resuelto, flashcards |

Cada canal tiene tres tonos: `--vark-x` (gráficos, ≥ 3:1), `--vark-x-text` (texto, ≥ 4,5:1) y
`--vark-x-soft` (fondos). **No se usan directo**: cualquier elemento con `data-canal="V|A|R|K"`
expone `--canal`, `--canal-text` y `--canal-soft`, y el componente se tiñe solo:

```html
<li class="perfil-barra" data-canal="K">…</li>     <!-- usa var(--canal) por dentro -->
{{ ui.vark_chip("K") }}                            <!-- chip con letra + nombre -->
{{ ui.vark_tile("A", size="lg") }}                 <!-- ícono en recuadro teñido -->
```

El **nombre** de cada canal sale de `textos.NOMBRE_CANAL` (global de Jinja, ver `deps.py`); el
ícono vive en `components/ui.html`. Excepción deliberada: las alternativas del **cuestionario**
no se tiñen por canal, porque eso filtraría al navegador la matriz letra→canal (cap. 17.1).

---

## 5. Componentes

Macros en `templates/components/ui.html` (`{% import "components/ui.html" as ui %}`):

| Macro | Produce |
|---|---|
| `ui.icon(nombre, label=None, cls="")` | `<svg class="icon">` del sprite. Decorativo (`aria-hidden`) salvo que se pase `label`. |
| `ui.vark_chip(canal, nombre=None, size="", con_icono=False)` | Chip teñido del canal. |
| `ui.vark_tile(canal, size="")` | Ícono del canal en recuadro teñido. |
| `ui.badge(texto, variant, icono=None)` | Badge `primary · accent · success · danger · warning · neutral`. |
| `{% call ui.alert(kind, titulo) %}…{% endcall %}` | Aviso con ícono. `kind`: `ok · error · warning · info`. Error → `role="alert"`; el resto, `role="status"`. |
| `{% call ui.empty_state(icono, titulo, tone, heading) %}…{% endcall %}` | Estado vacío o de error centrado. |
| `ui.page_header(titulo, bajada, eyebrow, eyebrow_icon)` | Encabezado de página. |
| `ui.progress(valor, etiqueta, canal=None)` | Barra con `role="progressbar"`. |
| `ui.spinner(etiqueta)` | Spinner para indicadores HTMX. |

Clases de componente más usadas (capa 5 de `app.css`):

- **Botones:** `.btn` + `.btn-primary · -accent · -secondary · -ghost · -success · -danger`, tamaños `.btn-sm · .btn-lg`, `.btn-block`, `.btn-icon`.
- **Superficies:** `.card` (`.card-flat`, `.card-sunken`, `.card-interactive`), `.stat`.
- **Formularios:** `.form-group`, `.form-label`, `.form-control`, `.form-hint`, `.form-grid`; opciones en tarjeta con `.choice-group` > `label.choice` > `input` (casilla o radio).
- **Datos:** `.table-container` > `.table`; con `.table-stack` + `data-label` en cada `<td>`, la tabla se apila como tarjetas bajo 720 px.
- **Otros:** `.accordion` (`<details>`), `.skeleton`, `.empty-state`, `.back-link`, `.eyebrow`, `.marker`.
- **Layout:** `.container`, `.stack`, `.cluster`, `.auto-grid` (`--grid-min`).

Para agregar un ícono: copiar el contenido interior del SVG de [lucide.dev](https://lucide.dev)
en un `<symbol id="i-nombre" viewBox="0 0 24 24">` nuevo de `sprite.svg`, en orden alfabético.

---

## 6. HTMX y JavaScript

- **Sin scripts inline, `onclick` ni funciones globales.** Cada comportamiento es un módulo de
  `app.js` que se engancha a un atributo `data-*` y se inicializa en `htmx:load` (que HTMX
  dispara para la página inicial y para cada fragmento que inserta). Así el mismo código sirve
  en el visor y en la cápsula que el simulador inyecta. Cada elemento se inicializa una vez.

  | Atributo | Módulo |
  |---|---|
  | `data-theme-toggle` | botón de tema |
  | `data-vark-stepper` | cuestionario de a una pregunta (con borrador en `sessionStorage`) |
  | `data-catalog-filter` | buscador del catálogo |
  | `data-study-link` | abre "Generando tu cápsula…" al ir al visor |
  | `data-flashcards` | mazo de tarjetas (lee la lista que dibujó el servidor) |
  | `data-multiquiz` | arma `answer` ("0,2,1") en `htmx:configRequest` |
  | `data-extracto` | recorta el fragmento citado con "Ver completo" |

- **Carga:** `.htmx-indicator` se muestra mientras hay petición; un botón dentro de un form en
  curso se atenúa y no admite doble clic; `.idle-only` se oculta durante la petición.
- **Los errores de formulario viajan como HTML con estado 200** (HTMX no intercambia 4xx) y se
  dibujan con las clases de alerta.
- **`.js-only`** marca controles que solo tienen sentido con JS; `base.html` pone
  `<html class="js">` y sin JS se ocultan.

---

## 7. Contratos que no se pueden romper

Los tests y los routers dependen de este marcado. Cambiarlo rompe la suite o un flujo:

- Clases `alerta`, `alerta-ok`, `alerta-error`, `badge-success`, `badge-danger`, `badge-primary`
  (las emite `student._error()` y las buscan los tests).
- En el visor, literal: `<ol class="lista-bloque">`, `<table class="table">`, `<dl class="glosario">`.
- `student/_capsula.html` **en simulación**: sin ningún `<form` ni `<head` (por eso usa `<div>`
  y no `<header>` para sus encabezados internos), con la alternativa correcta `checked`.
- El HTML del estudiante nunca incluye `indice_correcta` ni `retroalimentacion`.
- Cuestionario: casillas (`type="checkbox"`, nunca radio) con `name="qN" value="a|b|c|d"` en ese orden.
- Ids/targets HTMX: `#form-error`, `#feedback-result`, `#objetivo-status`, `#upload-status`,
  `#tag-status`, `#bandeja` (escucha `fragmentos-actualizados`), `#simulator-result`; cada fila
  de la bandeja es un `<tr>` autocontenido (`hx-target="closest tr"`, `outerHTML`).
- Cabecera: «Soy docente» y `/teacher/login` sin sesión; pestañas del docente y `/teacher/logout`
  solo con sesión.

---

## 8. Accesibilidad — checklist por vista nueva

- [ ] Un `h1` por página; jerarquía de títulos sin saltos.
- [ ] Todo `input`/`select` con `<label>` (o `aria-label` si va en una tabla).
- [ ] Íconos decorativos con `aria-hidden`; los que informan, con `label`.
- [ ] Nada se comunica solo con color.
- [ ] Navegable con teclado, con foco visible (no quitar `:focus-visible`).
- [ ] Contenido que llega por HTMX anunciado (`role="status"`/`aria-live`) cuando importa.
- [ ] Animaciones neutralizadas por `prefers-reduced-motion` (la capa 8 ya lo hace globalmente).
- [ ] Sin scroll horizontal a 390 px; objetivos táctiles ≥ 44 px.
- [ ] Probada en claro **y** oscuro.
