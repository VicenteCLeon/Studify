# Migración del frontend a React — estado y continuación

> Documento de traspaso. Escrito el **27-ago-2026** al cerrar la sesión en que se hizo la
> migración, para que otra sesión (u otra persona) pueda continuar sin releer el hilo.
>
> El detalle de *por qué* se tomó cada decisión está en [`AVANCE.md`](AVANCE.md) sección
> 5 duovicies. Este archivo es el operativo: **qué quedó hecho, qué falta, y en qué orden**.

---

## 0. Resumen en tres frases

Las ocho pantallas —cuatro del estudiante, cuatro del docente— están migradas a React +
TypeScript + Vite y funcionan de punta a punta contra el servidor real. La interfaz Jinja
anterior **sigue montada y funcionando** en `/student/*` y `/teacher/*`, a propósito: React
ocupa `/` y no colisiona con ella. Lo que falta no es construir, es **decidir cuándo retirar
la interfaz vieja** y cerrar los flecos que quedaron listados abajo.

**366 tests en verde. `npx tsc --noEmit` limpio. Build de producción: 215 KB (67 KB gzip).**

---

## 1. Cómo levantar el sistema

### Desarrollo (dos procesos, con recarga en caliente)

```powershell
# Terminal 1 — API
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn studify.main:app --reload --app-dir src     # → 127.0.0.1:8000

# Terminal 2 — frontend
cd frontend
npm install        # solo la primera vez
npm run dev        # → 127.0.0.1:5173
```

Vite hace de proxy de `/api`, `/health` y `/static` hacia uvicorn, así que **el navegador ve un
solo origen** y la cookie de sesión funciona igual que en producción.

### Producción / demo (un solo proceso)

```powershell
cd frontend; npm run build          # compila a src/studify/web/spa/
uvicorn studify.main:app --app-dir src   # → 127.0.0.1:8000 sirve API + SPA
```

- Credenciales del docente: **`admin` / `admin123`** (valor de fábrica, ver `AVANCE.md`
  pendiente n.º 7 — hay que cambiarlas antes de exponer el sistema).
- `GET /health` incluye `spa.construida`, que dice si el build existe.
- **Si nadie corre `npm run build`, la app no queda sin interfaz:** `/` redirige al flujo Jinja
  de siempre.

---

## 2. Qué quedó hecho

### 2.1 Backend — la lógica que no tenía API

El obstáculo real de la migración no era el frontend. `PLAN_DESARROLLO.md` afirma que «todo
pasa por `/api/*`»; para el estudiante era cierto, para el docente **no**: ~240 líneas de
cálculo vivían dentro de handlers que devolvían HTML.

| Archivo | Estado | Qué contiene |
|---|---|---|
| `src/studify/analytics/panel.py` | **nuevo** | `cobertura_curricular`, `fragmentos_sin_clasificar`, `rendimiento_actividades`, `promedio_vark_cohorte`, `barras_cohorte` — movidas desde `web/routers/teacher.py` |
| `src/studify/analytics/simulador.py` | **nuevo** | `perfil_puro`, `generar_capsula_pura`, `columna_error` |
| `src/studify/api/routers/panel.py` | **nuevo** | `GET /api/analiticas`, `POST /api/simulador/generar`, `POST /api/simulador/comparar` |
| `src/studify/api/routers/ui.py` | **nuevo** | Instrumento, sesión del estudiante, perfil legible, corrección del quiz, textos |
| `src/studify/api/schemas_panel.py`, `schemas_ui.py` | **nuevos** | Contratos de lo anterior |
| `web/routers/teacher.py` | modificado | Ya no calcula: delega en `studify.analytics`. Perdió ~240 líneas |
| `api/routers/knowledge.py` | modificado | `+POST /api/fragmentos/etiquetar` (el tagger, que solo se podía disparar desde HTML) |
| `web/routers/auth.py` | modificado | `+router_api`: login/logout del docente en JSON |
| `api/schemas_capsulas.py` | modificado | `CapsulaOut.objetivo` — las insignias del visor |
| `api/schemas_knowledge.py` | modificado | `FragmentoEnCuracion.sugerido_*` — la propuesta del tagger |
| `main.py` | modificado | Monta la SPA y el comodín de rutas del cliente |

**La regla que se siguió:** el cálculo vive en `studify/analytics/` y lo consumen **las dos**
interfaces. Es lo único que garantiza que el panel Jinja y el de React no se contradigan
mientras convivan.

### 2.2 Frontend

```
frontend/
├─ package.json / tsconfig.json / vite.config.ts
├─ index.html
└─ src/
   ├─ main.tsx, App.tsx            # entrada y rutas
   ├─ styles.css                   # copia del style.css existente (no se usó Tailwind)
   ├─ api/client.ts                # fetch con credentials: same-origin
   ├─ api/types.ts                 # espejo TS de los esquemas Pydantic
   ├─ hooks/useApi.ts              # carga + acción, ~60 líneas, sin librería externa
   ├─ contexts/SesionDocente.tsx   # equivalente del procesador de contexto de Jinja
   ├─ components/                  # Layout, Alerta, BarrasVark, CapsulaVista
   └─ pages/
      ├─ student/  Vark, Perfil, Catalogo, Visor
      └─ teacher/  Login, Curacion, Analiticas, Simulador
```

| Ruta React | Reemplaza a |
|---|---|
| `/vark` | `/student/vark` |
| `/perfil` | `/student/profile` |
| `/catalogo` | `/student/catalog` |
| `/visor/:idObjetivo` | `/student/viewer/{id}` |
| `/docente/login` | `/teacher/login` |
| `/docente/curacion` | `/teacher/curation` |
| `/docente/analiticas` | `/teacher/analytics` |
| `/docente/simulador` | `/teacher/simulator` |

### 2.3 Lo que se verificó

- **366 tests** (339 + 27 nuevos: `test_api_ui.py` 15, `test_api_panel.py` 12).
- Contra el **servidor real** con `curl` y un cliente HTTP con cookies, no solo `TestClient`:
  flujo completo del estudiante (sesión vacía → cuestionario → cookie → perfil K=100% unimodal
  con 193 palabras y 3 componentes prácticos → catálogo → logout), login del docente por JSON,
  `/api/analiticas` sobre datos reales, y la bandeja de curación.
- Que el comodín de la SPA **no** se coma `/api/*`, `/student/*`, `/teacher/*`, `/docs` ni
  `/health`, y que recargar en `/docente/analiticas` o `/visor/186` funcione.
- Los datos de prueba se borraron: la base quedó en 43 estudiantes / 43 diagnósticos.

### 2.4 Dos bugs que encontró la verificación

1. **Una ruta `/api/*` inexistente devolvía la SPA con 200.** El comodín se tragaba los `/api`
   mal escritos y un script recibía HTML creyendo que la llamada funcionó. Corregido: levanta
   404. *(Salió al hacer un GET contra un endpoint que solo acepta POST.)*
2. **`FragmentoEnCuracion` no exponía la sugerencia del tagger.** La bandeja Jinja la leía del
   ORM; el esquema no la incluía. La curación en React habría perdido esa función **en
   silencio**. Corregido con tres campos planos.

---

## 3. Qué falta — en orden de prioridad

### 3.1 🔴 Usar React de verdad y decidir el retiro de Jinja

**Es lo primero y lo único que bloquea al resto.** Ahora mismo conviven dos interfaces sobre la
misma lógica, que es el doble de superficie para que una quede atrás.

1. Levantar el sistema y **recorrer las ocho pantallas a mano** con los datos reales que ya
   están cargados (5 objetivos de "Diseño de UX", 48 fragmentos pendientes, 43 diagnósticos).
2. Lo único que **no** se probó contra el modelo real es la **generación de una cápsula desde
   React** (`/visor/:id`) y el **simulador** — se evitó a propósito para no gastar créditos de
   DeepSeek. La ruta está verificada con cliente falso en los tests; falta la corrida real.
3. Cuando esté claro que React cubre todo, retirar:
   - `src/studify/web/routers/student.py`, `teacher.py`
   - `src/studify/web/templates/` (16 archivos)
   - `tests/test_web_estudiante.py`, `test_web_docente.py`, `test_web_simulador.py` (~55 tests)

   ⚠️ **Antes de borrar esos tests, comprobar que cada invariante que protegen tenga un
   equivalente en `test_api_ui.py` / `test_api_panel.py`.** Varias son del informe y no de la
   pantalla — el fragmento validado sin objetivo queda inalcanzable para siempre, la clave del
   quiz no viaja al navegador, la matriz VARK no se filtra al cliente. Perder esos tests al
   borrar plantillas sería el peor resultado posible de esta migración.
   - `web/deps.py` y el procesador de contexto `es_docente` quedarían sin uso.
   - `web/routers/auth.py` conservaría `requiere_docente_api` y `router_api`; se podrían
     retirar `requiere_docente`, `get_login`, `post_login` y `post_logout` (los HTML).

### 3.2 🟡 Flecos conocidos de la migración

| Fleco | Detalle |
|---|---|
| **La tarjeta VARK de la cohorte no se pinta** | `GET /api/analiticas` devuelve `vark_barras` y el componente `BarrasVark` existe, pero `Analiticas.tsx` no la muestra — porque la plantilla Jinja actual tampoco (se quitó en una edición previa a esta sesión). Si se quiere de vuelta, son ~10 líneas: los datos ya llegan. |
| **El textarea de `intentalo_tu` no envía nada** | Igual que en Jinja: la actividad abierta no tiene respuesta que corregir, el servidor solo registra el intento y devuelve la respuesta esperada. El texto que escribe el estudiante nunca se guardó, ni antes ni ahora. Si debiera guardarse, es una función nueva, no un bug de la migración. |
| **Los tipos TS se mantienen a mano** | `frontend/src/api/types.ts` es el espejo de los esquemas Pydantic, con el archivo de origen anotado en cada bloque. Si se toca un esquema del backend, hay que tocar el tipo. Se aceptó a cambio de no agregar un generador de OpenAPI al build. |
| **`GET /api/objetivos` lo llama el simulador** | Es un endpoint del docente (está guardado), y el simulador lo usa para llenar el selector. Correcto, pero conviene tenerlo presente si alguna vez se abre esa ruta. |

### 3.3 🟢 Mejoras que la migración habilita pero no incluye

Ninguna es necesaria; se listan porque ahora son baratas y antes no lo eran.

- **Estados de carga por pantalla**: hoy cada vista muestra un texto simple. Con los datos ya
  tipados, poner esqueletos o barras de progreso es cosmético y acotado.
- **Reintentar la generación desde el visor**: el endpoint acepta `?regenerar=true` y la UI no
  lo ofrece (tampoco lo ofrecía Jinja).
- **Simular perfiles reales de la cohorte**: el pendiente n.º 10 de `AVANCE.md` sigue abierto —
  el simulador solo hace perfiles puros. La API (`POST /api/simulador/generar`) recibe un canal,
  así que soportar un vector completo pediría cambiar el contrato.

---

## 4. Lo que **no** cambió y conviene no romper

- **La sesión sigue en una cookie `httpOnly` firmada con HMAC** (`web/sesion.py`). No hay
  ningún token en `localStorage`, y eso es deliberado: es lo que hace que un XSS no pueda
  robar la sesión. Si alguna vez se separa el frontend a otro origen, esto se pierde — ver la
  tabla de decisiones en `AVANCE.md` 5 duovicies.
- **`/api/*` está separado por rol** desde el 26-ago (pendiente n.º 17): los 13 endpoints de
  curación y analítica exigen credenciales; los del estudiante quedan abiertos. El test
  `test_solo_lo_del_estudiante_queda_abierto_en_la_api` tiene una **lista blanca explícita**:
  si agregas un endpoint abierto a `/api`, ese test falla hasta que lo justifiques ahí. Es a
  propósito.
- **La matriz de puntuación VARK no se filtra al cliente** (cap. 17.1) y **`indice_correcta`
  nunca viaja al navegador**. Hay un test para cada una, y ambos comprueban sobre el **texto
  crudo** de la respuesta, no sobre el JSON parseado.

---

## 5. Estado del resto del proyecto (contexto, no es de esta migración)

Lo urgente sigue siendo lo mismo que antes del 27-ago, y **la migración no lo movió**:

- **Fase 5 (evaluación empírica A/B, encuestas TAM): no ha empezado.** Es el capítulo de
  resultados de la tesis. El horizonte del plan termina el **09-oct-2026**.
- **El perfil R genera al 55%**, contra el ≥95% que exige el criterio de término de la Fase 3
  (pendiente n.º 15).
- Conversaciones pendientes con la profesora guía: tablas 16.2/16.3, OA secundarios, embeddings.

La lista completa y al día está en [`AVANCE.md`](AVANCE.md) sección 6.

---

## 6. Órdenes útiles

```powershell
# Backend
pytest -q                                  # 366 tests
ruff check src/studify tests               # limpio salvo web/textos.py:33 (preexistente)

# Frontend
cd frontend
npx tsc --noEmit                           # typecheck estricto
npm run build                              # → src/studify/web/spa/

# Ver qué rutas de /api están abiertas y cuáles exigen docente
pytest tests/test_web_auth.py -q
```
