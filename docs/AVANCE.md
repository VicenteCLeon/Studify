# Studify — Estado de avance

> Documento vivo. Se actualiza al cierre de cada fase para que cualquier sesión de trabajo
> (o cualquier persona) pueda retomar el proyecto sin releer todo el hilo de conversación.
> Última actualización: **11-ago-2026**, cierre del motor de generación de la Fase 3 (contrato, validador de seis reglas, prompt maestro, bucle de reparación y `POST /api/capsulas`).

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
migradas sobre Postgres, el motor VARK completo (scoring → pesos → jerarquía → reglas) y los 43
diagnósticos reales cargados.
Además, se construyó el **andamiaje inicial de la UI (Fase 4)** utilizando Jinja2, HTMX y Vanilla CSS, con 5 vistas principales (flujo estudiante y docente) conectadas — todavía con datos *mock*.

**Núcleo de la Fase 2 cerrado** (sección 5 septies): ingesta de PDF/PPTX con trazabilidad de
página, curación humana con estados reales y **retriever determinista sin embeddings**.

**Motor de generación de la Fase 3 cerrado** (sección 5 octies): contrato Pydantic de la
microcápsula, validador con las seis reglas de rechazo, prompt maestro en cuatro bloques,
bucle de reparación y `POST /api/capsulas` con caché y versionado.
**198 tests en verde**; `ruff` limpio salvo 21 avisos preexistentes en los routers mock de la UI.

Dos cosas que faltan y **no son código**: `LLM_API_KEY` sigue vacío en el `.env`, y no hay
material curricular real cargado. El motor completo está escrito y probado con un LLM falso;
lo que falta para el criterio de término de la Fase 3 (≥95% de cápsulas válidas, prueba de
diferenciación entre los cuatro perfiles, bake-off de modelos) son **mediciones**, y esas
exigen la credencial y una unidad real.

Queda una discrepancia abierta: las tablas 16.2/16.3 del informe no se reproducen desde el CSV (sección 5 ter) — es un problema del informe, no del código.

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

### 3 ter. Los 43 diagnósticos reales cargados en la Máquina 1 (10-ago-2026)

`data/data_cuestionarios_43.csv` (no versionado — está en `.gitignore`) llegó a esta máquina y se
cargó con `python scripts/import_vark_csv.py data/data_cuestionarios_43.csv --reset`. El
`--dry-run` previo reprodujo exactamente los promedios ya documentados en la sección 5 ter
(V=5,44 A=7,37 R=7,23 K=7,91), confirmando que es el mismo dataset que en la máquina de Patricio.
`--reset` solo toca `estudiante` (con CASCADE a diagnóstico/respuestas/configuración) — no afecta
`objetivo_aprendizaje`, `documento_fuente` ni `fragmento`. Reemplazó 28 diagnósticos que eran
ruido de `test_api_diagnosticos.py` (crea diagnósticos y no los limpia) por los 43 reales.
Verificado: `estudiante`, `diagnostico_vark` y `configuracion_contenido` quedaron en 43 cada una.

**Distinción importante para no confundir en sesiones futuras:** este CSV son las **respuestas
del cuestionario VARK** (dato de estudiantes). No es el **catálogo de objetivos de aprendizaje**
que la Fase 3 necesita (`codigo_objetivo, asignatura, unidad, tema, descripcion,
nivel_taxonomico`, cargado con `scripts/cargar_objetivos.py`) — son dos CSV distintos con
propósitos distintos. Ese sigue sin existir en ninguna máquina.

De paso se eliminó un documento huérfano (`documento_fuente` id 46, `'otro_nombre'`) que había
quedado de una corrida end-to-end fallida durante la verificación de la Fase 2.

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
│     ├─ ec6446cc3c52_*.py  # Fase 1: las 8 entidades. Aplicada y verificada reversible.
│     ├─ 8eb6f0399fee_*.py  # Fase 1: estudiante.genero a VARCHAR(50)
│     └─ 8010505ef66e_*.py  # Fase 3: huella_generacion + modelo_llm. ⚠️ corregida a mano:
│                           #   autogenerate quería borrar el índice GIN de FTS
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
│  │  ├─ schemas.py      # ✅ contratos Pydantic del perfilamiento
│  │  ├─ schemas_knowledge.py  # ✅ contratos de la base de conocimiento (Fase 2)
│  │  ├─ schemas_capsulas.py   # ✅ contratos de la generación (Fase 3)
│  │  └─ routers/
│  │     ├─ diagnostics.py  # ✅ POST /api/diagnosticos, GET /api/diagnosticos/{id}
│  │     ├─ knowledge.py    # ✅ documentos, fragmentos, curación, catálogo, recuperar
│  │     └─ capsules.py     # ✅ POST /api/capsulas (+ caché, ?regenerar, historial)
│  ├─ knowledge/         # ✅ ingesta y curación (Fase 2)
│  │  ├─ extract.py      #    PDF/PPTX → bloques con página y detección de encabezados
│  │  ├─ chunker.py      #    bloques → fragmentos recuperables (fronteras duras)
│  │  ├─ ingest.py       #    persistencia + dedup por SHA-256 + almacén de archivos
│  │  └─ curation.py     #    validar / descartar / asignar objetivo / editar texto
│  ├─ rag/               # ✅ recuperación determinista (Fase 2) + prompt (Fase 3)
│  │  ├─ retriever.py    #    SQL por id_objetivo + FTS español + orden por canal VARK
│  │  ├─ orchestrator.py #    ✅ ensamblado del prompt maestro + huella de caché
│  │  └─ prompts/
│  │     └─ maestro.py   #    ✅ plantillas + directiva VARK → instrucción estructural
│  ├─ generation/        # ✅ motor de generación (Fase 3)
│  │  ├─ schemas.py      #    contrato de la microcápsula (reglas 1, 3 y 4)
│  │  ├─ idioma.py       #    detección de deriva de idioma (regla 6)
│  │  ├─ validator.py    #    parser tolerante + reglas 2, 5 y 6 + realimentación
│  │  └─ generator.py    #    cliente LLM (inyectable) + bucle de reparación
│  └─ web/               # ✅ UI mínima con HTMX + Jinja2 (templates/ + static/ + routers/)
├─ tests/
│  ├─ conftest.py        # ✅ fixtures compartidas (necesita_bd, db, almacen_temporal)
│  ├─ test_health.py     # smoke test de Semana 0
│  ├─ test_vark.py       # ✅ 44 tests del motor VARK, contrastados contra el informe
│  ├─ test_api_diagnosticos.py   # ✅ 15 tests del endpoint (se saltan sin Postgres)
│  ├─ test_knowledge_ingesta.py  # ✅ 22 tests de extracción y chunking (sin BD)
│  ├─ test_knowledge_persistencia.py  # ✅ 6 tests de ingesta contra Postgres
│  ├─ test_curacion_retriever.py      # ✅ 17 tests de curación y determinismo
│  ├─ material.py                # ✅ material de prueba compartido de la Fase 3 (no es un test)
│  ├─ test_generacion_contrato.py     # ✅ 42 tests del contrato y las 6 reglas (sin BD ni LLM)
│  ├─ test_prompt_maestro.py          # ✅ 23 tests del prompt y la huella (sin BD ni LLM)
│  ├─ test_generador.py               # ✅ 15 tests del bucle de reparación (LLM falso)
│  └─ test_api_capsulas.py            # ✅ 14 tests del endpoint (Postgres, LLM falso)
├─ scripts/
│  ├─ import_vark_csv.py   # ✅ carga los 43 diagnósticos reales (--dry-run, --reset)
│  └─ cargar_objetivos.py  # ✅ carga el catálogo curricular desde CSV (--dry-run)
├─ data/                  # vacío (.gitkeep), ignorado por git salvo el .gitkeep
└─ docs/
   ├─ seminario_titulo.md # el informe fuente (subido el 06-ago-2026, antes no estaba en el repo)
   ├─ PLAN_DESARROLLO.md  # plan completo de 10 semanas, decisiones pendientes, riesgos
   └─ AVANCE.md           # este archivo
```

**Nota importante:** ya no queda ningún paquete vacío. `db/`, `vark/`, `knowledge/`, `rag/`,
`generation/` y `api/` tienen lógica real y tests. Lo que falta es material real y credencial,
no código.

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

## 5 sexies. UI Mínima Funcional (07-ago-2026)

Se adelantó el desarrollo de un andamiaje visual para la Fase 4 creando una maqueta UI funcional para interactuar con el motor.
- **Tecnologías:** FastAPI (servidor), Jinja2 (plantillas renderizadas en servidor), HTMX (interactividad, reemplazo de fragmentos sin SPA) y Vanilla CSS (diseño limpio, premium, sin frameworks pesados).
- **Flujo Estudiante:** Vistas creadas y enrutadas (con datos *mock*) para el Cuestionario VARK (`vark.html`), Resultados del Perfil (`profile.html`), Catálogo de Temas en cascada (`catalog.html`) y el Visor de Microcápsulas (`viewer.html` con quiz interactivo).
- **Flujo Docente:** Panel de Curación (`curation.html`) preparado para subir documentos (PDF/PPTX) y una bandeja interactiva para revisar/aprobar/rechazar fragmentos extraídos de la base de conocimiento.
- **Infraestructura Web:** Configurado el montaje estático (`/static`), directrices en `deps.py`, endpoints en `student.py` y `teacher.py`, resolviendo problemas de firmas con `TemplateResponse` de las versiones recientes de FastAPI/Starlette.

---

## 5 septies. Fase 2 — Ingesta, curación y retriever determinista (10-ago-2026)

Cierra el núcleo de la base de conocimiento: entra un PDF/PPTX oficial, sale material curado
que el retriever puede recuperar de forma determinista y trazable.

### Arquitectura en tres capas

Se separó en tres módulos en vez del `ingest.py` único que proponía el plan, porque la
fragmentación es la decisión que más impacta la calidad del RAG y conviene poder ajustarla y
testearla sin volver a parsear archivos:

| Módulo | Responsabilidad | Depende de Postgres |
|---|---|---|
| `knowledge/extract.py` | Archivo → bloques con página y marca de encabezado | No |
| `knowledge/chunker.py` | Bloques → fragmentos recuperables | No |
| `knowledge/ingest.py` | Persistencia, dedup, almacén de archivos | Sí |

### Decisiones tomadas en la Fase 2

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Fragmento objetivo de ~180 palabras** (máx. 350, mín. 40) | Fragmentar por página o por párrafo | La cápsula mide 150–300 palabras y se genera *a partir* del fragmento. Uno más corto no alcanza a sostenerlas y el LLM rellena inventando —alucinación por falta de contexto, no por exceso—; uno más largo rompe la correspondencia «un fragmento ↔ un objetivo» del cap. 12. |
| **El encabezado es frontera dura**: siempre abre fragmento nuevo | Cerrar solo al llegar al tamaño objetivo | Unir dos secciones distintas en un fragmento destruye la correspondencia temática, que es lo único que hace recuperable el material. Se aplica aunque el fragmento anterior quede corto. |
| **Detección de encabezados por tamaño de fuente relativo** (moda del documento × 1,15, y ≤ 15 palabras) | Umbral absoluto de tamaño | Cada apunte usa su propia tipografía: un umbral fijo marca todo como título en un documento de letra grande y nada en uno de letra chica. La moda se pondera por caracteres para que muchos títulos cortos no desplacen al cuerpo real. |
| **La tabla va siempre en su propio fragmento** | Mezclarla con la prosa circundante | Para un perfil visual la tabla comparativa es el recurso que pide la tabla 11.1; fundida en un párrafo se vuelve irrecuperable. |
| **No se puede validar un fragmento sin objetivo asignado** | Permitirlo y asignar después | El retriever recupera por `id_objetivo`. Un fragmento validado con `id_objetivo = NULL` queda inalcanzable para siempre: aprobado, sin error visible y sin llegar nunca a una cápsula. Es el fallo silencioso más fácil de cometer revisando decenas de fragmentos seguidos. |
| **El retriever filtra `documento.estado_curacion != 'rechazado'`**, no `== 'validado'` | Exigir el estado positivo | Con el criterio positivo, una curación fragmento a fragmento sin marcar el documento completo devolvería cero resultados en silencio. En negativo, rechazar un documento sí retira su material aunque los fragmentos estuvieran validados. |
| **Validar un fragmento promueve el documento a `validado`** | Dejar el estado del documento a cargo del curador | Si no, el documento queda "pendiente" para siempre y el panel muestra trabajo terminado como si estuviera por hacer. |
| **Descartar no borra** | `DELETE` del fragmento | El cap. 12 exige trazabilidad del proceso de curación: saber qué se descartó (y que se revisó) es parte de eso. |
| **`DELETE /api/documentos/{id}` se rechaza si el documento fundamentó cápsulas** | Permitir el borrado siempre | La FK es `ON DELETE SET NULL`: borrar no daría error, dejaría cápsulas con la fuente en blanco y rompería en silencio la auditabilidad del cap. 13. Para retirar material ya usado está `estado_curacion = 'rechazado'`. |
| **El catálogo oculta los objetivos sin material validado** | Mostrar todos los temas | Un tema sin fragmentos validados no puede producir una cápsula fundamentada: llevaría al estudiante a un error o a contenido inventado. |
| **El canal VARK reordena, no filtra** | Devolver solo los tipos preferidos del canal | Si un perfil visual recibiera solo tablas, un apunte sin tablas no daría nada. La preferencia sube los tipos afines y conserva el resto. |
| **Los archivos se copian a `data/documentos/<sha256>.<ext>`** | Guardar la ruta original del docente | `ruta_archivo` debe seguir siendo válida aunque el docente mueva o borre su copia. Nombrar por hash evita además colisiones entre archivos llamados igual. |

### Bug encontrado inspeccionando la salida, no por los tests

Los 21 tests iniciales pasaban en verde y aun así **el texto extraído de todo PDF venía
corrupto**: PyMuPDF entrega una `line` por renglón y se estaban uniendo con `""`, de modo que la
última palabra de un renglón quedaba pegada a la primera del siguiente (`parareducir`,
`nocontienen`, `ningunatributo`). Los tests de estructura —encabezados, páginas, numeración— no
lo veían porque la estructura era correcta; solo apareció al imprimir el texto de un documento
realista. Corregido uniendo las líneas con `"\n"` (que `normalizar` convierte después en espacio
y aprovecha para deshacer los guiones de corte) y con test de regresión que verifica que todo
token del texto extraído exista en el original.

Habría degradado el full-text search en español y le habría entregado texto corrupto al LLM en
la Fase 3, sin ningún síntoma visible salvo cápsulas de mala calidad.

### Verificación end-to-end contra el servidor real

Los 45 tests nuevos (22 sin BD + 6 de ingesta + 17 de curación/retriever) se complementaron con
una corrida completa por HTTP sobre `uvicorn`, que confirmó las invariantes que importan:

1. El catálogo **no muestra** un objetivo sin material validado.
2. Reingerir el mismo archivo con otro nombre → **409** (dedup por contenido).
3. `GET /api/recuperar` devuelve **vacío antes de curar** — la barrera del cap. 12/13.
4. Validar sin objetivo → **422** con el motivo explicado.
5. Tras curar, la recuperación entrega los fragmentos **con su cita** (`documento, p. N`).
6. **Determinismo:** tres llamadas idénticas devuelven `[161, 162]` en el mismo orden.
7. El full-text search en español acota de 2 a 1 fragmento con `"dependencia parcial claves"`.

### Limitación conocida

La deduplicación es por SHA-256 de los **bytes**, así que detecta el mismo archivo subido dos
veces pero **no una reexportación** del mismo documento: un PDF regenerado lleva otro
`/CreationDate` embebido y por lo tanto otro hash. Si el docente vuelve a exportar el apunte
desde PowerPoint, entra como documento nuevo y sus fragmentos conviven con los anteriores en el
retriever. Mitigarlo pide comparar el texto extraído y no los bytes.

---

## 5 octies. Fase 3 — Motor de generación (11-ago-2026)

Cierra el motor completo: entra un `(id_estudiante, id_objetivo)` y sale una microcápsula
validada, en español, con quiz y con fuentes verificables contra el material curado.

### Módulos nuevos

| Módulo | Responsabilidad | Necesita LLM |
|---|---|---|
| `generation/schemas.py` | Contrato Pydantic de la microcápsula (reglas 1, 3 y 4 del plan §3) | No |
| `generation/idioma.py` | Detección de deriva de idioma (regla 6) | No |
| `generation/validator.py` | Parser tolerante + reglas 2, 5 y 6 + realimentación | No |
| `rag/prompts/maestro.py` | Plantillas y traducción de directivas VARK a instrucciones | No |
| `rag/orchestrator.py` | Ensamblado del prompt y huella de caché | No |
| `generation/generator.py` | Llamada al modelo y bucle de reparación | Solo el cliente real |
| `api/routers/capsules.py` | `POST /api/capsulas`, historial y consulta por id | Solo al generar |

**Solo una línea del motor habla con el modelo.** Todo lo demás —contrato, validación, prompt,
bucle de reparación, caché— se ejerce con un cliente falso, sin red y sin costo. Por eso los
94 tests nuevos corren en una máquina sin `LLM_API_KEY`.

### Decisiones tomadas en la Fase 3

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Detección de idioma por conteo de palabras funcionales**, escrita a mano | `langdetect` u otra librería | `langdetect` es probabilístico y, sin fijarle la semilla, **devuelve resultados distintos entre corridas sobre el mismo texto**. Meter no-determinismo dentro del validador contradice el argumento del cap. 13 y haría que un mismo JSON se acepte o rechace según la corrida. El problema real es acotado —distinguir español de inglés y de chino— y con listas de marcadores es exacto y explicable. |
| **Las palabras clave de SQL quedan fuera de la lista de marcadores del inglés** (`from`, `where`, `select`, `in`, `on`, `as`, `not`, `all`, `and`, `or`, `by`, `if`) | Usar una lista de stopwords estándar | Una cápsula legítima en español sobre bases de datos contiene todas esas palabras. Con la lista estándar, el validador rechazaría por «deriva al inglés» justo el contenido de la asignatura que se está usando de piloto. Hay un test que cubre ese caso. |
| **Escape por ortografía española** (tildes, ñ, ¿, ¡) cuando el ratio de palabras funcionales es bajo | Solo el umbral de ratio | Un perfil visual puede recibir una cápsula casi toda de tabla y glosario, donde apenas hay palabras funcionales. Sin el escape sería un falso rechazo sistemático contra los perfiles V. |
| **`documento` y `pagina` de las fuentes se reescriben con los valores de la base** | Confiar en lo que redactó el modelo | Si la cápsula cita el fragmento 161, la procedencia la afirma el sistema consultando `fragmento`/`documento_fuente`. Así la trazabilidad del cap. 13 es verdadera por construcción y no depende de que el modelo copie bien un número de página. Cuántas veces la corrigió queda como métrica. |
| **`PromptMaestro` acarrea los fragmentos que embebió** | Que el llamador se los pase por separado al validador | Si fueran dos listas distintas, la regla 5 podría rechazar una cita legítima o —peor— dejar pasar una inventada. Toda la tesis se apoya en que esa comprobación sea exacta. |
| **El bloque de perfil pide bloques concretos, no adjetivos de tono** | «Redacta de forma visual / práctica» | Es la mitigación que el propio plan §5 fija para el riesgo de que las cuatro cápsulas salgan indistinguibles. Cada directiva de `vark/rules.py` se traduce a una instrucción que nombra un `tipo` del contrato y una cantidad, de modo que la diferencia es comprobable en la cápsula resultante. |
| **El prompt nunca nombra el canal ni la etiqueta del perfil** | Decirle «este estudiante es kinestésico» | El cap. 17.2 prohíbe persistir la etiqueta, y además nombrarla invita al modelo a comentar el estilo de aprendizaje en vez de aplicarlo. Hay un test que lo verifica. |
| **`palabras_texto` se redondea a tramos de 10 antes de entrar al prompt** | Usar el valor exacto | La huella de caché se calcula sobre lo que entra al prompt. Sin redondear, casi cada estudiante tendría su propio tramo y el caché no serviría: en una cohorte de 43 se pagarían 43 generaciones del mismo tema. Pedir «aproximadamente 247» y «aproximadamente 250» da cápsulas indistinguibles. |
| **La huella incluye los fragmentos y el modelo**, no solo objetivo y configuración | La definición literal del plan §4 | Ambos cambian la salida: si el docente valida material nuevo, la cápsula cacheada dejó de reflejar el material disponible; y el bake-off corre la misma configuración contra tres modelos, que sin esto se pisarían en el caché. |
| **Caché compartido entre estudiantes del mismo tramo, copiando la fila** | Compartir la misma fila, o cachear solo por estudiante | Se ahorra la llamada al modelo, que es lo caro, pero cada estudiante conserva su propia fila: la tabla 17.8 vincula cada cápsula a un estudiante y el A/B de la Fase 5 necesita saber qué vio cada uno. |
| **`get_cliente_llm` devuelve `None` si falta la credencial**, en vez de abortar con 503 | Levantar 503 dentro de la dependencia | Las dependencias de FastAPI se resuelven **antes** del handler: abortar ahí dejaría sin servir también las cápsulas que ya estaban en caché y no necesitan al modelo. El 503 se levanta recién cuando se comprueba que hay que generar. Con el `.env` actual (sin key) la demo puede seguir mostrando lo ya generado. |
| **La actividad se guarda en `mini_quiz_json`, aparte de `contenido_json`** | Meter la cápsula entera en `contenido_json` | La tabla 17.8 declara las dos columnas por separado; dejar una en NULL apartaría el modelo físico del diccionario de datos del informe sin ninguna ganancia. |
| **Dos columnas nuevas en `microcapsula_generada`** (`huella_generacion`, `modelo_llm`) | Guardar la huella dentro de `contenido_json` | La huella se consulta en cada petición y un `->>` sobre JSONB no aprovecha índice. `modelo_llm` hace legible una cápsula guardada: el bake-off deja en la misma tabla las cápsulas de los tres modelos y sin la columna no hay forma de saber cuál produjo cada una. **Son un añadido a la tabla 17.8 del informe** y hay que declararlo en el capítulo 17. |

### Decisión de regeneración: se versiona, no se sobrescribe

Cierra la decisión 5 de la sección 7, que estaba marcada como «se decide en la Fase 3».

`POST /api/capsulas` devuelve por defecto la cápsula ya generada para la misma huella;
`?regenerar=true` produce una versión nueva y **conserva la anterior**. Se descartó sobrescribir
porque el bake-off de la Fase 3 (mismo prompt × 3 modelos × 4 perfiles) y la validación docente
de la Fase 5 comparan varias cápsulas del mismo objetivo, y sobrescribir las haría desaparecer.

### Dos cosas que encontró la inspección, no los tests

1. **El autogenerate de Alembic volvió a proponer borrar el índice GIN de full-text search.**
   La migración `8010505ef66e` salió con un `drop_index('ix_fragmento_contenido_fts')` en el
   `upgrade` y su `create_index` en el `downgrade` — o sea, destruir el índice del retriever al
   migrar hacia adelante. Es el mismo defecto ya advertido en la sección 5 (autogenerate no ve
   los índices definidos por expresión), y esta vez se cumplió. Ambas líneas se quitaron a mano
   y la migración quedó verificada reversible: `head → downgrade -1 → upgrade head` deja las dos
   columnas nuevas y el índice FTS intacto en los tres estados. **Si alguien regenera esta
   migración, hay que volver a quitarlas.**

2. **El prompt le pedía al modelo un bloque que no existe.** Imprimiendo el prompt ensamblado
   para un perfil K se vio la línea «Componentes prácticos (bloques `ejemplo_resuelto` o
   `lista_pasos`): 3» junto a solo **dos** instrucciones de bloque. La causa: con `p_K ≥ 40%` la
   tabla 11.1 cuenta tres componentes —ejemplo aplicado, secuencia paso a paso y actividad
   «inténtalo tú»— pero el tercero es la **actividad de cierre**, que no es un bloque de
   `contenido`. Tal como estaba, el modelo tenía que inventarse un tercer bloque para cuadrar la
   cuenta. Corregido en la redacción del bloque de perfil, con test de regresión. Los tests no
   lo veían porque cada pieza era correcta por separado.

### Qué cubren los 94 tests nuevos

- `test_generacion_contrato.py` (42): las seis reglas de rechazo, el parser tolerante
  (cercas Markdown, preámbulo del modelo, coma colgante, llave dentro de una cadena, respuesta
  truncada) y los casos límite del detector de idioma.
- `test_prompt_maestro.py` (23): sincronía entre módulos —toda directiva de `vark/rules.py`
  tiene instrucción, todo campo del contrato aparece en el prompt—, diferenciación entre los
  cuatro perfiles y las propiedades de la huella de caché.
- `test_generador.py` (15): el bucle de reparación completo con cliente falso, incluidos los
  cuatro modos de fallo que tiene que poder reparar.
- `test_api_capsulas.py` (14, requieren Postgres): lo que el endpoint rechaza, el caché en sus
  dos niveles, el versionado y el comportamiento sin credencial.

Dos de ellos existen para detectar **desincronización entre módulos**, que es el fallo que no
produce ningún error y sí cápsulas peores: si alguien agrega una regla a `vark/rules.py` sin
traducirla en `rag/prompts/maestro.py`, ese elemento del perfil desaparecería de la cápsula sin
dejar rastro; y si el contrato cambia sin que cambie el prompt, se gastarían los dos reintentos
en cada llamada. Ambos casos fallan la suite ahora.

### Lo que falta para cerrar la Fase 3 según su criterio de término

El criterio del plan es «`POST /api/capsulas` devuelve una cápsula válida ≥95% de las veces» más
la prueba de diferenciación entre las cuatro cápsulas VARK. Nada de eso se puede **medir**
todavía: falta `LLM_API_KEY` y falta material real. El motor está completo y el prompt está
construido para que la diferenciación ocurra —hay tests que prueban que los cuatro perfiles
producen prompts distintos y estructuralmente distintos—, pero que las **cápsulas** resulten
distinguibles es una observación empírica pendiente.

---

## 6. Pendiente inmediato

Los dos primeros son ahora los que bloquean todo lo demás: el motor está escrito y probado,
pero **no se ha ejecutado nunca contra un modelo real ni sobre material real**.

0. **Conseguir la credencial del LLM y ponerla en `LLM_API_KEY`.** Con el `.env` actual
   (`llm_api_key` vacío) `POST /api/capsulas` responde 503 y no se puede medir nada del criterio
   de término de la Fase 3. Con la key, la primera corrida real es directa: el endpoint ya está
   montado y el bake-off solo necesita cambiar `LLM_MODEL`/`LLM_BASE_URL` entre las tres
   candidatas. **Primera cosa que hay que mirar en esa corrida:** si las cuatro cápsulas VARK
   del mismo objetivo se distinguen entre sí. Si no, el plan §5 ya fija la mitigación —
   instrucciones estructurales, no adjetivos de tono— y el prompt ya está construido así, de
   modo que lo que habría que ajustar son las instrucciones de
   `rag/prompts/maestro.py::INSTRUCCION_POR_DIRECTIVA`, no el motor.
1. **Cargar material real de la base de conocimiento** (distinto de los diagnósticos VARK, que
   ya están cargados — ver sección 3 ter). El pipeline está probado con documentos sintéticos;
   falta la unidad real de una asignatura. Techo duro del plan: **una unidad, 40–60 fragmentos**.
   El catálogo se carga con `python scripts/cargar_objetivos.py data/objetivos.csv` (ese CSV
   todavía no existe) y los documentos por `POST /api/documentos`.
   Sin esto la Fase 3 no tiene nada real que recuperar: 0 objetivos, 0 fragmentos validados.
2. **Conectar la UI de Patricio a los endpoints reales.** `web/routers/teacher.py` y
   `student.py` siguen con `MOCK_FRAGMENTS` en memoria; ya existen `/api/documentos`,
   `/api/fragmentos`, `/api/catalogo`, `/api/recuperar` y ahora `/api/capsulas` para
   reemplazarlos. `viewer.html` es el que más trabajo pide: hoy renderiza un HTML fijo y tiene
   que pasar a recorrer los bloques de `contenido` según su `tipo` (párrafo, tabla, esquema,
   glosario…) y a mostrar las dos formas de actividad (`quiz_mc` e `intentalo_tu`).
3. **`tagger.py` (etiquetado asistido por LLM)** quedó fuera de esta entrega porque
   `LLM_API_KEY` está vacío. Hoy el curador asigna el objetivo a mano: funciona, pero es lento.
   Cuando exista la key, el tagger solo debe **proponer**, nunca decidir.
4. Los **21 avisos de `ruff`** en `web/deps.py`, `web/routers/student.py` y
   `web/routers/teacher.py` (orden de imports, `Optional` en vez de `X | None`, líneas largas en
   el HTML inline) vienen del commit `12e00be` y no se tocaron para no pisar trabajo ajeno.
   Desaparecen al conectar esos routers a la API real.
5. **Resolver la discrepancia de las tablas 16.2/16.3** con la profesora guía: o se corrige el
   informe con los valores recalculados, o aparece la planilla original que explique la
   diferencia. El código ya entrega los números reales; el informe es lo que habría que ajustar.
6. Para la Fase 4 (UI) va a faltar el **enunciado** de cada uno de los 16 ítems:
   `instrumento.py` guarda las 4 alternativas de cada pregunta pero no su texto, porque para
   calificar no hace falta. Están en el encabezado del CSV cuando se necesiten.

~~Ratificar `palabras_texto`~~ ✅ **Aprobado por el equipo el 06-ago-2026** — queda la
interpolación lineal sobre C_texto tal como está implementada.

---

## 7. Decisiones de diseño aún abiertas (no bloquean la Semana 0, sí bloquean partes de la Fase 1/3)

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
3. **Fragmentos no textuales** (tablas, diagramas): ✅ **parcialmente cerrada en la Fase 2.** Las
   tablas de PPTX se serializan a texto (`tipo_fragmento = 'tabla'`, filas separadas por `|`) y
   van en su propio fragmento, de modo que el retriever y el FTS las ven. Sigue abierto el caso
   de **imágenes y diagramas**: necesitan una descripción textual escrita durante la curación en
   `metadatos_json`, y hoy la ingesta simplemente los omite.
4. ~~**Selección de tema por el estudiante**~~ ✅ **Cerrada en la Fase 2:** `GET /api/catalogo`
   devuelve el árbol asignatura → unidad → tema, ocultando por defecto los objetivos sin
   material validado (parámetro `solo_con_material`).
5. ~~**Regeneración de cápsulas**~~ ✅ **Cerrada en la Fase 3 (11-ago-2026): se versiona.**
   `POST /api/capsulas` devuelve por defecto la cápsula cacheada para la misma huella; con
   `?regenerar=true` genera una versión nueva y conserva la anterior. El motivo está en la
   sección 5 octies: el bake-off de la Fase 3 y la validación docente de la Fase 5 comparan
   varias cápsulas del mismo objetivo, y sobrescribir las haría desaparecer.

---

## 8. Correcciones detectadas en el informe (`seminario_titulo.md`), no aplicadas aún

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
- **(Nueva, Fase 3)** La tabla 17.8 se amplió con dos columnas que el informe no declara:
  `huella_generacion VARCHAR(64)` (clave de caché, indexada) y `modelo_llm VARCHAR(60)`. La
  primera es lo que permite no volver a pagarle al LLM por una cápsula ya generada; la segunda
  es lo que hace legible una cápsula guardada cuando el bake-off deja en la misma tabla las de
  los tres modelos candidatos. Hay que agregarlas al diccionario de datos del capítulo 17.
- **(Nueva, Fase 3)** El cap. 11.1 no distingue entre los componentes prácticos que son
  **bloques de contenido** y el que es la **actividad de cierre**. Con `p_K ≥ 40%` la tabla 11.1
  cuenta tres —ejemplo aplicado, secuencia paso a paso y actividad «inténtalo tú»— pero el
  tercero no es un bloque del cuerpo de la cápsula. Conviene que el informe lo diga
  explícitamente, porque leído al pie de la letra pide tres bloques donde solo corresponden dos.
- **(Nueva)** La tabla 17.1 define `ano_ingreso INT` ("año de ingreso a la universidad"), pero
  el formulario preguntó el **año de carrera** ("4° año o superior (semestres 7+)"). No son el
  mismo dato y uno no se deriva del otro, así que la columna se carga en `NULL`. Hay que decidir
  si se cambia el atributo del modelo a "año de carrera" (que es lo que efectivamente se
  recolectó y lo que usa el cap. 16.1) o si se agrega la pregunta al instrumento.

---

## 9. Cómo retomar el trabajo (para una sesión nueva)

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
