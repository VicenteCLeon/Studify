# Studify — Estado de avance

> Documento vivo. Se actualiza al cierre de cada fase para que cualquier sesión de trabajo
> (o cualquier persona) pueda retomar el proyecto sin releer todo el hilo de conversación.
> Última actualización: **06-ago-2026**, avance parcial de Fase 1 (modelo de datos + motor VARK).

---

## 0. Qué es este proyecto (resumen para contexto rápido)

Studify es el prototipo funcional del Seminario de Título *"Generación de micro-aprendizaje
educativo mediante IA generativa, basado en estilos de aprendizaje del estudiante"* (Patricio
Hernández Vergara, Vicente Cisternas León — PUCV, profesora guía Sandra Cano Mazuera).

Genera **microcápsulas educativas** (150–300 palabras, 3–7 min de consumo, con quiz de cierre)
adaptadas al perfil VARK del estudiante (Visual / Auditivo / Lector-escritor / Kinestésico),
ancladas mediante **RAG estructurado sobre base de datos relacional** — es decir, sin
embeddings ni búsqueda vectorial: la recuperación de fragmentos de conocimiento se hace con
SQL determinista sobre metadatos curados, para garantizar trazabilidad y control curricular.

El documento fuente de todo el diseño es [`seminario_titulo.md`](seminario_titulo.md)
(el informe de avance ya entregado). El plan de implementación derivado de ese informe está en
[`PLAN_DESARROLLO.md`](PLAN_DESARROLLO.md) — **léase antes de tocar código**, ahí están las
decisiones de arquitectura, el roadmap de 10 semanas y las decisiones pendientes.

Este archivo (`AVANCE.md`) es el complemento: qué se hizo realmente, qué se verificó, qué
quedó pendiente y qué decisiones se tomaron sobre la marcha.

---

## 1. Estado actual en una frase

**Semana 0 completa** (`fbf4b3f`, pusheada a `origin/main` —
https://github.com/VicenteCLeon/Studify.git) y **Fase 1 cerrada**: las 8 entidades del cap. 17
migradas sobre Postgres, el motor VARK completo (scoring → pesos → jerarquía → reglas), los 43
diagnósticos reales cargados y `POST /api/diagnosticos` devolviendo la `configuracion_contenido`
completa. **59 tests en verde**, `ruff` limpio. Queda una discrepancia abierta: las tablas
16.2/16.3 del informe no se reproducen desde el CSV (sección 5 ter) — es un problema del
informe, no del código.

---

## 2. Decisiones tomadas y por qué

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **PostgreSQL 16** | MySQL (que el informe cap. 14 menciona como opción) | `JSONB` nativo para `contenido_json`/`mini_quiz_json`/`metadatos_json` (tablas 17.4, 17.7, 17.8) y full-text search en español sin extensiones. **Verificado**: `to_tsvector('spanish', …)` aplica stemming correcto ("generación"→`gener`, "validadas"→`valid`) y `plainto_tsquery` matchea. |
| **Postgres nativo (winget)**, no Docker | Docker Desktop | Windows 11 Home requiere WSL2 + reinicio para Docker Desktop. Postgres nativo fue más rápido de poner en marcha. El `docker-compose.yml` se dejó igual creado y con las mismas credenciales (`studify`/`studify`/db `studify`), por si en algún momento se prefiere esa vía o se necesita reproducir el entorno en la otra máquina del equipo. |
| **Endpoints FastAPI síncronos** (`def`, no `async def`) + SQLAlchemy síncrono | Async con `asyncpg`/`AsyncSession` | FastAPI corre los `def` en su threadpool, así que el I/O bloqueante (BD, llamadas al LLM) no bloquea el event loop. Evita el error más común en prototipos: mezclar código sync dentro de handlers async y bloquear el server. |
| **LlamaIndex acotado** a `BaseRetriever` custom + `PromptTemplate` + conector LLM | `VectorStoreIndex` (el uso "por defecto" de LlamaIndex) | Usar el índice vectorial estándar contradiría la tesis central del proyecto (RAG estructurado, no semántico). LlamaIndex se usa solo como capa de orquestación de prompt, no de recuperación. |
| **Cliente LLM único vía interfaz OpenAI-compatible** (`llama-index-llms-openai-like`) | SDKs nativos de cada proveedor | DeepSeek, Qwen y GLM (los "LLMs chinos" que el equipo decidió usar) exponen todos una API compatible con OpenAI. Un solo cliente, modelo intercambiable por variable de entorno (`LLM_BASE_URL`, `LLM_MODEL`), sin tocar código. La elección final entre los tres se hace con datos en un bake-off programado para la Fase 3. |
| **`/health` reporta la BD caída en vez de fallar (500)** | Que el endpoint dependa de la BD para responder | Permite distinguir "la app no levanta" de "falta Postgres" al diagnosticar. Los tests (`tests/test_health.py`) corren sin necesidad de una base de datos activa. |
| **UI mínima con Jinja2 + HTMX** servida por el mismo FastAPI (aún no implementada) | Streamlit / SPA React desde el inicio | Cero build step, todo pasa por `/api/*`, así que una UI más completa después no obliga a rediseñar el backend. Streamlit habría sido un callejón sin salida para la UI final. React queda para una fase posterior si el tiempo lo permite. |
| **`data/*` en `.gitignore`, no `data/`** | `.gitignore` con solo `data/` | Git no permite re-incluir un archivo (`!data/.gitkeep`) cuyo directorio padre está excluido por completo. Con `data/*` + `!data/.gitkeep` el directorio sí se versiona vacío. |

---

## 2 bis. Decisiones tomadas en la Fase 1 (06-ago-2026)

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Cortes de la tabla 11.1 sobre los porcentajes VARK crudos**, no sobre los C_* | La propuesta original del plan (`recursos_visuales = 0 si C_visual<15, 1 si <25, 2 si ≥25`) | La tabla 11.1 del informe está escrita sobre `p_V`/`p_K` ("p_V ≥ 40% → dos recursos visuales"), no sobre los C_*. Cortar sobre C_visual contradiría al informe: un perfil con `p_V = 40%` exacto da `C_visual = 24,5`, que con el corte propuesto entregaría 1 recurso visual en vez de los 2 que exige la tabla. Cierra la decisión pendiente n.º 1 de `PLAN_DESARROLLO.md` §6. |
| **`palabras_texto` interpolado sobre el rango alcanzable de C_texto** | Interpolar sobre 0–100 | Los C_* **no** recorren 0–100: cada uno tiene un rango acotado (`C_texto ∈ [40,75]`, `C_visual ∈ [10,45]`, `C_narrativo ∈ [5,30]`, `C_practico ∈ [5,25]`), porque los coeficientes de cada columna suman 1,00. Tratar un C_* como porcentaje daría umbrales mal calibrados. Único parámetro del motor no determinado por el informe; **aprobado por el equipo el 06-ago-2026**. |
| **Regla 7 leída como `> 20%` estricto** | `≥ 20%` | "Tres o más dimensiones **sobre** el 20%". Con el criterio inclusivo, un perfil `{0V, 20A, 20R, 60K}` —claramente dominado por K— quedaría multimodal solo porque dos canales tocan el borde exacto. |
| **El tono lo fija el canal dominante; "mixto" solo para perfiles planos** | Que `es_multimodal` fuerce siempre tono mixto | Las reglas 1–5 y la 7 de la tabla 11.1 **se solapan**: `{0V, 21A, 21R, 58K}` cumple ambas a la vez (tres canales sobre 20% y uno sobre 40%), porque el dominante puede ser uno de los tres. Verificado por fuerza bruta sobre la grilla del símplex: 15.960 casos de solapamiento. Se aplican en capas —las reglas 1–5 deciden elementos de contenido, la 6–7 solo la etiqueta de modalidad. |
| **Reparto del residuo por resto mayor** en la normalización a porcentajes | Redondeo simple por canal | El cap. 11.2 exige `p_V+p_A+p_R+p_K = 100` como igualdad estricta y hay un CHECK en la tabla que lo replica. Redondear cada canal por separado no lo garantiza: `{1,1,1,0}` da tres veces 33,33 y suma 99,99. |
| **`TIMESTAMP WITH TIME ZONE`** para todas las fechas | `DATETIME` literal del informe | El informe usa notación MySQL. Un `TIMESTAMP` sin zona en Postgres deja la interpretación a merced del huso de la sesión, y los dos computadores del equipo no tienen por qué compartirlo. |
| **CHECK constraints en vez de `ENUM` nativo** para los vocabularios controlados | `ENUM` de Postgres | Agregar un valor a un `ENUM` exige `ALTER TYPE`; un CHECK se cambia en una migración normal. En un prototipo que todavía está afinando estados, eso importa. |
| **`alembic/versions/` excluido de ruff** | Reformatear las migraciones a mano | Las escribe `--autogenerate` con su propio formato; cualquier arreglo manual se perdería en la siguiente regeneración. |

---

## 3. Qué se instaló y verificó en esta máquina (05-ago-2026)

Entorno de partida: **sin Python, sin Docker, sin Node**, solo Git y winget disponibles.

| Herramienta | Versión instalada | Método |
|---|---|---|
| Python | 3.12.10 | `winget install --id Python.Python.3.12 -e` |
| PostgreSQL | 16.14 | `winget install --id PostgreSQL.PostgreSQL.16 -e` — quedó como servicio Windows `postgresql-x64-16`, `Status: Running`, `StartType: Automatic` |

Base de datos creada manualmente (superusuario `postgres`, password por defecto de winget:
`postgres` — **es solo local, cambiar si se expone algo**):

```sql
CREATE ROLE studify LOGIN PASSWORD 'studify';
CREATE DATABASE studify OWNER studify;
```

Coincide exactamente con las credenciales de `docker-compose.yml` y con `DATABASE_URL` en
`.env.example`, así que ambas vías (nativa o Docker) son intercambiables sin editar `.env`.

**Verificaciones realizadas (no solo "se instaló", sino "se probó que funciona"):**

1. `python -m venv .venv` + `pip install -e ".[dev]"` → instala sin errores. Versiones clave
   resueltas: `fastapi==0.141.1`, `sqlalchemy==2.0.51`, `alembic==1.19.0`, `psycopg==3.3.4`,
   `pydantic==2.13.4`, `llama-index-core==0.14.23`, `llama-index-llms-openai-like==0.7.2`.
2. `pytest` → **2 passed** (`tests/test_health.py`, corre sin BD activa).
3. `ruff check .` → **All checks passed** (se corrigió un orden de imports en `alembic/env.py`
   con `ruff check . --fix`).
4. `GET /health` contra la base **real** (no mockeada) → `{"status": "ok", "database":
   {"reachable": true, "error": null}, "llm": {"model": "deepseek-chat", "api_key_configured":
   false}}`.
5. `alembic current` → conecta correctamente a la BD (todavía sin revisiones, es lo esperado
   en esta fase).
6. Full-text search en español, probado directo contra Postgres vía SQLAlchemy:
   `to_tsvector('spanish', 'La generación aumentada por recuperación ancla el contenido en
   fuentes institucionales validadas')` → stemming correcto, y
   `@@ plainto_tsquery('spanish', 'fuentes validadas')` → `True`.

### 3 bis. Segundo computador del equipo (06-ago-2026)

El proyecto ya corre en una segunda máquina, en la ruta
`C:\Users\vleon\Documents\proyectos\SpotCheck\Studify` (la de la sección anterior era
`e:\code\Studify\Studify`). Diferencias que conviene tener presentes:

| | Máquina 1 | Máquina 2 |
|---|---|---|
| Python | 3.12.10 | **3.14.5** |
| PostgreSQL | 16.14 nativo | 16.x nativo (servicio `postgresql-x64-16`) |
| Clave del superusuario `postgres` | `postgres` (default de winget) | **distinta** — la fijó el instalador, no es la default |

**Python 3.14 no dio problemas**: todas las dependencias resolvieron con wheels `cp314`
(incluidos `numpy`, `psycopg-binary` y `pydantic-core`, que son los que compilan). Las versiones
de librerías quedaron idénticas a las de la máquina 1: `fastapi==0.141.1`, `sqlalchemy==2.0.51`,
`alembic==1.19.0`, `psycopg==3.3.4`, `pydantic==2.13.4`, `llama-index-core==0.14.23`. Aun así,
`pyproject.toml` declara `requires-python = ">=3.11"` y no fija una versión exacta, así que
ambas máquinas son válidas.

El rol y la base se crearon igual que en la máquina 1 (mismas credenciales `studify`/`studify`),
por lo que `DATABASE_URL` del `.env` es la misma en ambas y no hay que editar nada al cambiar de
computador.

**Ojo con `seminario_titulo.md`:** el informe **no estaba versionado** (quedó solo en la máquina
1) y sin él no se puede escribir ni el modelo de datos ni el motor VARK. Se subió a
`docs/seminario_titulo.md` el 06-ago-2026 y el enlace de la sección 0 se corrigió en
consecuencia. No volver a sacarlo del repo.

---

## 4. Estructura del repositorio (estado real, no aspiracional)

```
Studify/
├─ .env.example          # plantilla — LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, DATABASE_URL, etc.
├─ .env                  # copia local, NO versionada (ya creada en esta máquina)
├─ .gitignore
├─ .gitattributes
├─ README.md             # instrucciones de instalación y arranque
├─ docker-compose.yml    # Postgres 16 alternativo a la instalación nativa
├─ pyproject.toml        # dependencias + config de ruff/pytest
├─ alembic.ini
├─ alembic/
│  ├─ env.py             # lee DATABASE_URL desde studify.config; importa models para autogenerate
│  ├─ script.py.mako
│  └─ versions/
│     └─ ec6446cc3c52_*.py  # Fase 1: las 8 entidades. Aplicada y verificada reversible.
├─ src/studify/
│  ├─ main.py            # app FastAPI + endpoint /health
│  ├─ config.py          # Settings (pydantic-settings, lee .env)
│  ├─ db/
│  │  ├─ base.py         # DeclarativeBase compartida
│  │  ├─ session.py      # engine + SessionLocal + get_db() síncronos
│  │  └─ models.py       # ✅ las 8 entidades del cap. 17
│  ├─ vark/              # ✅ motor completo
│  │  ├─ scoring.py      #    16 ítems → puntajes crudos → vector porcentual
│  │  ├─ weighting.py    #    fórmulas C_* del cap. 11.2 + rangos alcanzables
│  │  ├─ hierarchy.py    #    canal primario/secundario/multimodalidad (derivado)
│  │  └─ rules.py        #    tabla 11.1 → configuracion_contenido + directivas de prompt
│  │  └─ instrumento.py  #    matriz de puntuación: las 64 alternativas → canal
│  ├─ api/
│  │  ├─ schemas.py      # ✅ contratos Pydantic de la API
│  │  └─ routers/
│  │     └─ diagnostics.py  # ✅ POST /api/diagnosticos, GET /api/diagnosticos/{id}
│  ├─ knowledge/         # paquete vacío (solo __init__.py) — Fase 2
│  ├─ rag/               # paquete vacío (solo __init__.py) — Fase 3
│  │  └─ prompts/        # NO EXISTE AÚN
│  ├─ generation/        # paquete vacío (solo __init__.py) — Fase 3
│  └─ web/               # NO EXISTE AÚN (templates/ + static/) — Fase 4
├─ tests/
│  ├─ test_health.py     # smoke test de Semana 0
│  ├─ test_vark.py       # ✅ 44 tests del motor VARK, contrastados contra el informe
│  └─ test_api_diagnosticos.py  # ✅ 15 tests del endpoint (los de BD se saltan sin Postgres)
├─ scripts/
│  └─ import_vark_csv.py  # ✅ carga los 43 diagnósticos reales (--dry-run, --reset)
├─ data/                  # vacío (.gitkeep), ignorado por git salvo el .gitkeep
└─ docs/
   ├─ seminario_titulo.md # el informe fuente (subido el 06-ago-2026, antes no estaba en el repo)
   ├─ PLAN_DESARROLLO.md  # plan completo de 10 semanas, decisiones pendientes, riesgos
   └─ AVANCE.md           # este archivo
```

**Nota importante:** los directorios `knowledge/`, `rag/`, `generation/` y `api/routers/`
siguen siendo paquetes Python vacíos (solo `__init__.py`) — andamiaje de la Semana 0, no
implementación. `db/` y `vark/` sí tienen lógica real.

---

## 5. Qué se hizo y se verificó en la Fase 1 (06-ago-2026)

**Modelo de datos — las 8 entidades del cap. 17, migradas y aplicadas.**

- `src/studify/db/models.py` transcribe las tablas 17.1–17.8 a SQLAlchemy 2.0, adaptando los
  tipos MySQL del informe a Postgres (`DATETIME`→`TIMESTAMPTZ`, `TINYINT`→`SMALLINT`,
  `JSON`→`JSONB`, `DECIMAL`→`NUMERIC`).
- Migración `ec6446cc3c52`, generada con `--autogenerate` y **verificada reversible**:
  `upgrade head` → 9 tablas → `downgrade base` → solo queda `alembic_version` → `upgrade head`
  → 9 tablas otra vez.
- Índice GIN de full-text search en español añadido **a mano** a la migración: autogenerate
  **no emite los índices definidos por expresión**. Verificado en la BD como
  `gin (to_tsvector('spanish'::regconfig, contenido_texto))`. ⚠️ Si alguien regenera esta
  migración desde cero, hay que volver a agregarlo.

**Motor VARK — completo, 41 tests.**

`scoring.py` (cap. 10) → `weighting.py` (cap. 11.2) → `hierarchy.py` (cap. 17.2) →
`rules.py` (tabla 11.1). Los tests no comprueban valores sacados del propio código: cada uno
contrasta contra una afirmación concreta del informe.

Verificaciones que encontraron algo (no solo "pasa el test"):

1. **Los C_* suman exactamente 100** para cualquier vector de entrada, porque los coeficientes
   de cada canal suman 1,00 (V: 0,40+0,45+0,05+0,10; A, R y K análogos). Confirmado
   numéricamente. Esto hace que los pesos sean interpretables como reparto del énfasis
   instruccional — y hay un test que lo protege si alguien edita la matriz.
2. **Los C_* no recorren 0–100**, cada uno tiene un rango acotado (ver tabla de decisiones).
   Es el motivo por el que se descartó la propuesta de cortes del plan.
3. **Las reglas 1–5 y la 7 de la tabla 11.1 se solapan**, y no se arregla cambiando `≥` por `>`:
   el canal dominante puede ser uno de los tres que superan el 20% (`{0V, 21A, 21R, 58K}`).
   Comprobado por fuerza bruta sobre la grilla del símplex → 15.960 casos. Se resolvió
   aplicándolas en capas, no como alternativas excluyentes.
4. **Bug encontrado por la prueba end-to-end, no por los tests unitarios:** un perfil multimodal
   `{33,34V / 33,33A / 0R / 33,33K}` recibía una sola directiva de prompt
   (`recurso_visual_complementario`), porque la rama multimodal solo se aplicaba si ninguna otra
   regla había disparado. Contradecía la regla 7 ("cápsula equilibrada integrando los cuatro
   registros"). Corregido y con test de regresión.
5. **End-to-end contra Postgres real:** calificar → reglas → persistir en `estudiante` +
   `diagnostico_vark` + `respuesta_vark` + `configuracion_contenido`, con el caso de redondeo
   más incómodo (`{1,1,0,1}` → 33,34/33,33/0/33,33). El CHECK de suma=100 lo acepta, y el
   `ON DELETE CASCADE` limpia las cuatro tablas.

Estado de las verificaciones: **41 tests VARK + 2 de salud = 43 passed**, `ruff check .` limpio,
`/health` con `database.reachable: true`.

---

## 5 ter. Carga de los 43 diagnósticos reales (06-ago-2026)

Los 43 registros del Google Forms (`data/data_cuestionarios_43.csv`, no versionado) están
cargados en Postgres: 43 estudiantes, 43 diagnósticos, **1.202 respuestas individuales**, 43
configuraciones. Los porcentajes suman 100 exacto en las 43 filas.

El importador es `scripts/import_vark_csv.py` (con `--dry-run` y `--reset`). La matriz de
puntuación vive en `src/studify/vark/instrumento.py`, no en el script, porque es la definición
del instrumento y no un detalle de la carga.

### El mapeo alternativa→canal está verificado por dos vías independientes

1. **Semántica:** cada alternativa describe un canal sin ambigüedad.
2. **Posicional:** Google Forms exporta las selecciones múltiples en el orden en que las
   opciones aparecen en el formulario. Reconstruido ese orden desde las respuestas reales, los
   **16 ítems presentan sus alternativas en el orden V, A, R, K sin excepción**.

Las dos vías coinciden en los 64 textos. No es el mapeo lo que falla.

### ⚠️ Las tablas 16.2 y 16.3 del informe NO se reproducen desde el CSV

**El dataset es el correcto**: todos los sociodemográficos del cap. 16.1 calzan al número —
n=43, Ing. Informática n=23, género 27/14/2, año de carrera 20/9/7/7.

| | Informe | Calculado desde el CSV |
|---|---|---|
| Promedios, muestra total | V=3,1 A=6,2 R=5,8 K=6,5 | **V=5,44 A=7,37 R=7,23 K=7,91** |
| Promedios, Ing. Informática | V=3,65 A=6,57 R=5,17 K=7,96 | **V=6,30 A=7,87 R=6,22 K=9,61** |
| Ranking, muestra total | K > A > R > V | **K > A > R > V** ✅ coincide |
| Ranking, Ing. Informática | K > A > R > V | K > A > **V > R** (R y V casi empatados: 6,22 vs 6,30) |
| Moda de perfil | A+K | K (unimodal) |

**Lo que sí se sostiene, y es lo que importa para el código:** el cap. 16.4 fija
`perfil = K→A` como parámetro por defecto del prompt, y **eso se reproduce exactamente** —
K primario, A secundario, en ambos segmentos. La conclusión de diseño del informe es correcta
aunque sus números intermedios no cuadren.

**Por qué no cuadran.** Los promedios del informe implican ~21,6 selecciones por persona; el
CSV tiene **28,0** (mín. 16, máx. 58). Se probaron cuatro reglas de conteo —todas las marcas,
solo la primera, tope de 2 por ítem, solo ítems de respuesta única— y ninguna se acerca: la
mejor deja un error acumulado de 4,6 puntos. **Los números publicados no salen de este CSV con
ninguna regla de conteo razonable.** Queda como discrepancia abierta a resolver con el equipo y
la profesora guía; lo más probable es que la tabulación original se haya hecho a mano o sobre
un export parcial.

### Criterio de clasificación de perfiles (decidido el 06-ago-2026)

Un canal está **activo** si empata con el máximo o queda a ≤10 puntos porcentuales de él. Con
dos activos el perfil es bimodal; con tres o más, multimodal.

Esto **reemplaza** la implementación anterior, que usaba la fila 7 de la tabla 11.1 («tres o más
dimensiones sobre el 20%») para etiquetar. Ese umbral es absoluto y no relativo al máximo, así
que marcaba como multimodal a perfiles claramente dominados: `{0V, 21A, 21R, 58K}` quedaba
multimodal pese a que A y R están a 37 puntos de K. La fila 7 se conserva, pero como regla de
**contenido** (qué bloques incluir), que es donde el informe la usa.

---

## 5 quinquies. `POST /api/diagnosticos` — el flujo completo por HTTP

Con esto la Fase 1 queda cerrada según su criterio de término. Archivos nuevos:

- `src/studify/api/schemas.py` — contratos Pydantic de entrada/salida.
- `src/studify/api/routers/diagnostics.py` — `POST /api/diagnosticos` y
  `GET /api/diagnosticos/{id}`, conectados en `main.py` con `include_router`.

**El cliente no conoce la matriz de puntuación.** El cuestionario se responde por posición
(«ítem 3, alternativa b») y es el servidor quien traduce eso a un canal, vía
`instrumento.canal_por_posicion()`. Si la matriz cambiara, se recalculan los perfiles desde
`respuesta_vark` sin tocar el frontend ni volver a aplicar el cuestionario — que es exactamente
para lo que el cap. 17.1 justifica esa tabla.

**La jerarquía se recalcula al leer, no se guarda.** `GET /api/diagnosticos/{id}` deriva canal
primario/secundario y modalidad desde los porcentajes almacenados, cumpliendo el cap. 17.2: la
interpretación categórica no puede quedar desincronizada del vector porque no existe como dato.

Verificado contra el servidor real (no solo con `TestClient`): un perfil `{A=40, K=60}` devuelve
201 con la configuración completa. Caso interesante que confirma el diseño en capas — queda
**unimodal K** (diferencia de 20 > 10) pero sus directivas incluyen igual las auditivas, porque
`p_A = 40` dispara la fila 4 de la tabla 11.1 con independencia de la etiqueta de modalidad.

Los tests que tocan la base **se saltan solos si Postgres no está levantado**, mismo criterio que
`test_health.py`, para que `pytest` siga verde en una máquina recién clonada.

---

## 6. Pendiente inmediato

1. **Resolver la discrepancia de las tablas 16.2/16.3** con la profesora guía: o se corrige el
   informe con los valores recalculados, o aparece la planilla original que explique la
   diferencia. El código ya entrega los números reales; el informe es lo que habría que ajustar.
2. Empezar la **Fase 2** (base de conocimiento e ingesta), que según el plan es la que más se
   subestima. Techo duro: una unidad de una asignatura, 40–60 fragmentos.
3. Para la Fase 4 (UI) va a faltar el **enunciado** de cada uno de los 16 ítems:
   `instrumento.py` guarda las 4 alternativas de cada pregunta pero no su texto, porque para
   calificar no hace falta. Están en el encabezado del CSV cuando se necesiten.

~~Ratificar `palabras_texto`~~ ✅ **Aprobado por el equipo el 06-ago-2026** — queda la
interpolación lineal sobre C_texto tal como está implementada.

---

## 6. Decisiones de diseño aún abiertas (no bloquean la Semana 0, sí bloquean partes de la Fase 1/3)

Copiadas y mantenidas en sincronía con `PLAN_DESARROLLO.md` sección 6 — resumen aquí para no
tener que saltar de archivo:

1. ~~**Cortes numéricos de C_\* a enteros.**~~ ✅ **Cerrada en la Fase 1.** Se cortó sobre los
   porcentajes VARK crudos y no sobre los C_*, descartando la propuesta del plan (ver tabla de
   decisiones de la Fase 1 y el docstring de `vark/rules.py`). El único parámetro sin base
   directa en el informe (`palabras_texto`, interpolado sobre C_texto) también quedó aprobado
   por el equipo el 06-ago-2026.
2. ~~**`audio_activo`**~~ ✅ **Cerrada en la Fase 1:** queda fuera de alcance. El campo existe en
   el modelo por fidelidad a la tabla 17.4 pero se persiste siempre en `False`, y el canal
   auditivo se atiende con redacción conversacional (`tono_narrativo = 'oral'`). Falta
   declararlo como trabajo futuro en el informe final.
3. **Fragmentos no textuales** (tablas, diagramas): se resuelven guardando una descripción
   textual en `metadatos_json` durante la curación; esa descripción es lo que se inyecta al
   LLM, `ruta_recurso` es solo para renderizar en la UI.
4. **Selección de tema por el estudiante** — falta definir/endpoint `GET /api/catalogo`
   (asignatura → unidad → objetivo). No está en el informe original.
5. **Regeneración de cápsulas** — ¿se versiona o se sobreescribe si el estudiante pide otra
   cápsula del mismo objetivo? Sin definir.

---

## 7. Correcciones detectadas en el informe (`seminario_titulo.md`), no aplicadas aún

Estas no bloquean código, pero quedaron identificadas para el informe final (ver
`PLAN_DESARROLLO.md` sección 7 para el detalle completo):

- Referencias cruzadas desfasadas (cap. 16.4 remite a "sección 12.2" debiendo ser 11.2; cap. 17
  remite a "sección 14" y "sección 12.3" inexistentes; cap. 17.1 remite a secciones 10/11
  cuando corresponden a 9/10).
- Resumen (condicional: "se espera que contribuya") vs. Abstract (indicativo: "effectively
  improves") inconsistentes en el tiempo verbal / grado de certeza.
- Cita de Saha et al. sobre duración de clases: "50 a 70 minutos" (cap. 11.1) vs. "50 a 75
  minutos" (cap. 2) — verificar contra la fuente original.
- Tabla 16.2 (muestra total) sin columna de porcentaje, a diferencia de la tabla de Ing.
  Informática — homologar formato.
- Distribución por año (cap. 16.1): 20+9+7+7=43 pero 47+21+16+16=100 solo por redondeo —
  aclarar con nota al pie.
- **(Nueva, detectada al implementar el motor VARK)** El criterio de multimodalidad está
  definido dos veces y de forma no equivalente: cap. 10 («empates o diferencias mínimas», sin
  cuantificar, sobre puntajes crudos) contra cap. 11.1 («diferencia ≤ 10 puntos porcentuales»,
  cuantificado, sobre el vector porcentual). No son intercambiables: 10 puntos porcentuales
  sobre ~16 selecciones equivalen a ~1,6 selecciones de diferencia, mientras que "empate" exige
  diferencia 0. Unificar en el informe final dejando el criterio del cap. 11.1, que es el
  implementado.
- **(Nueva)** Las reglas de la tabla 11.1 no son mutuamente excluyentes: las filas 1–5
  (umbrales por canal) y la fila 7 (tres o más dimensiones sobre 20%) pueden cumplirse a la vez,
  porque el canal dominante puede ser uno de los tres que superan el umbral —p. ej.
  `{0V, 21A, 21R, 58K}`. Conviene que el informe diga explícitamente que se aplican en capas
  (las 1–5 fijan los elementos de contenido, la 6–7 solo la etiqueta de modalidad) y no como
  alternativas.
- **(Nueva, la más importante)** **Las tablas 16.2 y 16.3 no se reproducen desde el CSV de
  respuestas**, pese a que el dataset es verificablemente el mismo (todos los sociodemográficos
  del cap. 16.1 calzan). Detalle completo en la sección 5 ter. Hay que decidir con la profesora
  guía si se corrigen los valores publicados.
- **(Nueva)** La tabla 17.1 declara `genero VARCHAR(20)`, pero el propio instrumento ofrece la
  alternativa **"No Binario / otra identidad"**, de 27 caracteres, que no cabe. Corregido en el
  modelo con `VARCHAR(50)` (migración `8eb6f0399fee`); falta corregir el diccionario de datos
  del informe.
- **(Nueva)** La tabla 17.1 define `ano_ingreso INT` ("año de ingreso a la universidad"), pero
  el formulario preguntó el **año de carrera** ("4° año o superior (semestres 7+)"). No son el
  mismo dato y uno no se deriva del otro, así que la columna se carga en `NULL`. Hay que decidir
  si se cambia el atributo del modelo a "año de carrera" (que es lo que efectivamente se
  recolectó y lo que usa el cap. 16.1) o si se agrega la pregunta al instrumento.

---

## 8. Cómo retomar el trabajo (para una sesión nueva)

```powershell
# Máquina 1: e:\code\Studify\Studify
# Máquina 2: C:\Users\vleon\Documents\proyectos\SpotCheck\Studify
cd <la ruta que corresponda>
.\.venv\Scripts\Activate.ps1

alembic upgrade head          # deja el esquema al día antes de tocar nada
uvicorn studify.main:app --reload --app-dir src
# → http://127.0.0.1:8000/health  y  http://127.0.0.1:8000/docs

pytest
ruff check .
```

Si `.venv` no existe (máquina nueva): seguir `README.md` sección "Puesta en marcha" completa,
incluyendo la creación del rol/base de Postgres (comando en README sección "Crear el rol y la
base"). Ojo con dos cosas que costaron tiempo en la máquina 2:

- La clave del superusuario `postgres` **no siempre es `postgres`**: depende de lo que se haya
  puesto al instalar. Si `psql -U postgres` rechaza la conexión, esa es la causa.
- El rol y la base se crean con estos dos comandos, y las credenciales deben ser exactamente
  estas para que el `.env` funcione sin editarlo en ninguna de las dos máquinas:

  ```sql
  CREATE ROLE studify LOGIN PASSWORD 'studify';
  CREATE DATABASE studify OWNER studify;
  ```

**Orden de lectura recomendado para contexto:** este archivo → `docs/PLAN_DESARROLLO.md` →
`seminario_titulo.md` (el informe fuente) → código en `src/studify/`.
