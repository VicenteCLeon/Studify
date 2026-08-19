# Studify — Estado de avance

> Documento vivo. Se actualiza al cierre de cada fase para que cualquier sesión de trabajo
> (o cualquier persona) pueda retomar el proyecto sin releer todo el hilo de conversación.
> Última actualización: **19-ago-2026** — **la microcápsula pasó a tener la estructura
> pedagógica de siete pasos** que definió la profesora guía, y el prompt le muestra al modelo
> los cuatro pesos C_* en crudo; ver sección 5 terdecies. Antes: alta de objetivos desde el
> panel del docente (14-ago, sección 5 duodecies), rebranding a "RepasAi" y fondo de marca
> (13-ago, sección 5 undecies) y panel de analíticas con tres bugs de fondo corregidos
> (12-ago, sección 5 decies).

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
Además, se construyó el **andamiaje inicial de la UI (Fase 4)** utilizando Jinja2, HTMX y Vanilla CSS, con 5 vistas principales (flujo estudiante y docente) — que en su momento usaban datos *mock* y hoy están conectadas al motor real (sección 5 nonies).

**Núcleo de la Fase 2 cerrado** (sección 5 septies): ingesta de PDF/PPTX con trazabilidad de
página, curación humana con estados reales y **retriever determinista sin embeddings**.

**Motor de generación de la Fase 3 cerrado** (sección 5 octies): contrato Pydantic de la
microcápsula, validador con las seis reglas de rechazo, prompt maestro en cuatro bloques,
bucle de reparación y `POST /api/capsulas` con caché y versionado. *(El contrato de la
microcápsula se reemplazó el 19-ago por la estructura de siete pasos — sección 5 terdecies;
el resto de esta sección sigue vigente.)*

**Fase 4 cerrada** (sección 5 nonies): la UI dejó de usar datos *mock*. El cuestionario
muestra los 16 ítems reales del instrumento, el diagnóstico se guarda de verdad, hay sesión
por cookie firmada, el perfil lee el vector y la configuración persistidos, el catálogo
consulta `objetivo_aprendizaje` ocultando lo que no tiene material curado, el visor invoca el
motor de generación y renderiza los siete tipos de bloque del contrato, el quiz se corrige
contra `mini_quiz_json`, y el panel del docente ingiere y cura material real.
**229 tests en verde y `ruff` limpio en todo el repositorio** (desaparecieron los 21 avisos
que arrastraban los routers mock).

**Fase 3 finalizada al 100% (incluyendo validación LLM):** Se agregó la credencial real de DeepSeek (`LLM_API_KEY`) al entorno y se cargó material curricular genuino (objetivo 369). El **bake-off de modelos** fue ejecutado exitosamente, obteniendo cápsulas 100% válidas en el primer intento con `deepseek-chat` (latencia ~5.5s) y quedando seleccionada definitivamente tras fallos de autorización de los otros candidatos (Qwen y GLM). ⚠️ Matiz sobre "bake-off": solo se pudo **medir** un modelo — Qwen y GLM fallaron por autorización, no por calidad — así que es más preciso decir que se seleccionó DeepSeek por ser el único candidato evaluable, no que ganó una comparación de tres.

**Panel de analíticas del docente (12-ago-2026, sección 5 decies):** se agregaron cinco vistas nuevas para el docente y se auditaron a fondo. Tres tenían fallos de fondo, no solo visuales: el simulador VARK generaba cápsulas rotas e indistinguibles de un perfil inválido, la métrica de aciertos del quiz podía inflarse por reintentos, y la cobertura curricular podía marcar en verde temas cuyo material el retriever ya no recupera. Las tres quedaron corregidas con 32 tests nuevos (261 en total) y una migración (`interaccion_quiz` con intentos numerados).

**Rebranding y fondo de marca (13-ago-2026, sección 5 undecies):** la UI pasó a llamarse "RepasAi" y toda la web tiene ahora una textura de fondo con íconos educativos. Es un cambio visual, sin código de dominio.

**Estructura pedagógica de siete pasos (19-ago-2026, sección 5 terdecies):** la profesora guía observó que el informe no define la estructura de una microcápsula y propuso una (OA → activación → concepto central → representación adaptativa VARK → ejemplo → pregunta de comprobación → retroalimentación). Está implementada: cada paso es ahora un campo obligatorio del contrato en vez de un bloque suelto dentro de una lista, y el prompt le muestra al modelo los cuatro pesos C_* en crudo además de las instrucciones estructurales. Verificado contra DeepSeek con material real: cápsula válida al primer intento, 247 palabras, los siete pasos en orden. **277 tests en verde.** Tres puntos de su lista quedaron fuera a propósito (embeddings, OA secundarios y el campo "contenido" del OA) — el detalle está en la sección 5 terdecies y en [`AUDITORIA_LISTA_PROFESORA_14AGO2026.md`](AUDITORIA_LISTA_PROFESORA_14AGO2026.md).

**Alta de objetivos desde el panel del docente (14-ago-2026, sección 5 duodecies):** `POST /api/objetivos` existía desde la Fase 2 pero no estaba conectado a ninguna pantalla — el catálogo solo se podía cargar por consola. Ahora hay un formulario en `/teacher/curation` que reutiliza el mismo handler; el script de carga masiva se conserva para sembrar un plan de estudios completo. **265 tests en verde** (261 + 4), `ruff` limpio. De paso se cargó el primer material curricular real del proyecto —5 objetivos de "Diseño de UX" y un PPTX con 40 fragmentos— aunque todavía sin curar, y se encontró que esta máquina tenía dos migraciones de Patricio sin aplicar (`/teacher/analytics` daba 500 hasta correr `alembic upgrade head`).

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
| **UI mínima con Jinja2 + HTMX** servida por el mismo FastAPI | Streamlit / SPA React desde el inicio | Cero build step, todo pasa por `/api/*`, así que una UI más completa después no obliga a rediseñar el backend. Streamlit habría sido un callejón sin salida para la UI final. React queda para una fase posterior si el tiempo lo permite. |
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
│     ├─ 8010505ef66e_*.py  # Fase 3: huella_generacion + modelo_llm. ⚠️ corregida a mano:
│     │                     #   autogenerate quería borrar el índice GIN de FTS
│     ├─ 5e11a9cf4a0b_*.py  # Fase 5: tabla interaccion_quiz
│     └─ 2fbc7391c0a3_*.py  # Fase 5: numero_intento + nulables. ⚠️ corregida a mano: mismo
│                           #   defecto del índice GIN, otra vez
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
│  │  ├─ schemas.py      #    contrato de la microcápsula: 7 pasos pedagógicos
│  │  ├─ idioma.py       #    detección de deriva de idioma (regla 6)
│  │  ├─ validator.py    #    parser tolerante + reglas 2, 5 y 6 + realimentación
│  │  └─ generator.py    #    cliente LLM (inyectable) + bucle de reparación
│  └─ web/               # ✅ UI mínima con HTMX + Jinja2 (Fase 4, conectada al motor)
│     ├─ deps.py         #    entorno Jinja2 compartido
│     ├─ sesion.py       #    ✅ cookie `id_estudiante` firmada con HMAC
│     ├─ textos.py       #    ⚠️ copy de la UI + enunciados PROVISIONALES de los 16 ítems
│     ├─ routers/
│     │  ├─ student.py   #    ✅ cuestionario, perfil, catálogo, visor, quiz e intentos (Fase 5)
│     │  └─ teacher.py   #    ✅ curación + analíticas + simulador VARK (Fase 5, sección 5 decies)
│     ├─ templates/
│     │  ├─ student/     #    _capsula.html (partial compartido con el simulador), _feedback, …
│     │  └─ teacher/     #    _bandeja, _fila, analytics.html, simulator.html
│     └─ static/css/
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
│  ├─ test_api_capsulas.py            # ✅ 14 tests del endpoint (Postgres, LLM falso)
│  ├─ test_web_estudiante.py          # ✅ 24 tests del flujo web del estudiante (Fase 4)
│  ├─ test_web_docente.py             # ✅ 7 tests del panel de curación (Fase 4)
│  ├─ test_web_simulador.py           # ✅ 8 tests del simulador VARK (Fase 5)
│  ├─ test_interaccion_quiz.py        # ✅ 12 tests de intentos numerados y ownership (Fase 5)
│  └─ test_cobertura_curricular.py    # ✅ 12 tests de cobertura por canal (Fase 5)
├─ scripts/
│  ├─ import_vark_csv.py   # ✅ carga los 43 diagnósticos reales (--dry-run, --reset)
│  ├─ cargar_objetivos.py  # ✅ carga el catálogo curricular desde CSV (--dry-run)
│  ├─ eval_runner.py       # ✅ batería de evaluación técnica / bake-off (Fase 3)
│  └─ reset_db.py          # ⚠️ drop_all sin confirmación — ver sección 6, punto 12
├─ data/                  # vacío (.gitkeep), ignorado por git salvo el .gitkeep
└─ docs/
   ├─ seminario_titulo.md # el informe fuente (subido el 06-ago-2026, antes no estaba en el repo)
   ├─ PLAN_DESARROLLO.md  # plan completo de 10 semanas, decisiones pendientes, riesgos
   └─ AVANCE.md           # este archivo
```

**Nota importante:** ya no queda ningún paquete vacío. `db/`, `vark/`, `knowledge/`, `rag/`,
`generation/` y `api/` tienen lógica real y tests. Adicionalmente, el material curricular real y la credencial han sido incorporados al entorno (el Bake-off concluyó exitosamente con DeepSeek).

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

> ⚠️ **Leer junto con la sección 5 terdecies (19-ago-2026).** La *forma* de la microcápsula que
> describe esta sección —`contenido[]`, una lista de bloques sueltos— fue reemplazada por la
> estructura pedagógica de siete pasos que definió la profesora guía. Todo lo demás de esta
> sección (las seis reglas del validador, el bucle de reparación, la huella de caché, el
> detector de idioma) sigue vigente tal cual.

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

## 5 nonies. Fase 4 — UI mínima funcional conectada al motor (11-ago-2026)

Cierra el pendiente n.º 2 de la sección 6: `web/routers/student.py` y `teacher.py` ya no
tienen `MOCK_FRAGMENTS` ni cápsulas escritas a mano. Cada vista llama al **mismo handler**
que expone `/api/*` en vez de reimplementarlo, de modo que la demo y la API no pueden
contradecirse: si cambia el cálculo del perfil, cambian las dos a la vez.

| Vista | Con qué se conectó |
|---|---|
| `GET /student/vark` | `vark/instrumento.py` — los 16 ítems y sus 64 alternativas reales |
| `POST /student/vark` | `crear_diagnostico`, el handler de `POST /api/diagnosticos` |
| `GET /student/profile` | `diagnostico_vigente` + `vark/rules.aplicar_reglas` + la fila de `configuracion_contenido` |
| `GET /student/catalog` | `catalogo`, el handler de `GET /api/catalogo` |
| `GET /student/viewer/{id_objetivo}` | `crear_capsula`, el handler de `POST /api/capsulas` |
| `POST /student/viewer/{id_capsula}/submit` | `mini_quiz_json.indice_correcta` de la fila persistida |
| `POST /teacher/curation/upload` | `subir_documento` → `knowledge/ingest.ingerir` |
| `POST /teacher/curation/{id}/approve` \| `/reject` | `knowledge/curation.validar` \| `descartar` |

### Decisiones tomadas en la Fase 4

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Casillas de verificación en el cuestionario**, no botones de radio | Un radio por ítem, como tenía la maqueta | El cap. 10 permite marcar **varias** alternativas por ítem y dejar ítems en blanco. Con radios ninguna de las dos cosas es expresable, y el instrumento aplicado por la web dejaría de ser el mismo que se aplicó por Google Forms a los 43 estudiantes ya cargados: los perfiles no serían comparables. |
| **Cookie `id_estudiante` firmada con HMAC** (stdlib) | Cookie con el id en claro; o `itsdangerous`; o sesión en servidor | Un entero en una cookie lo edita cualquiera: escribir `id_estudiante=7` bastaba para ver el perfil y las cápsulas de otra persona. La firma lo cierra sin agregar dependencia ni tabla de sesiones. No es autenticación —el sistema no tiene usuarios, el cap. 9 identifica por diagnóstico— pero sí impide la manipulación trivial. |
| **`SESSION_SECRET` opcional, con secreto efímero por proceso si falta** | Un secreto fijo escrito en el código | Firmar con un secreto público es lo mismo que no firmar. Si falta, la app funciona y las sesiones simplemente no sobreviven a un reinicio; queda documentado en `.env.example`. |
| **Repetir el cuestionario agrega un diagnóstico al mismo estudiante** | Crear un estudiante nuevo en cada intento | La tabla 17.2 admite varios diagnósticos por estudiante y la generación ya usa el más reciente. Si cada intento creara una persona, el A/B de la Fase 5 quedaría con la cohorte inflada de duplicados y las cápsulas de un mismo estudiante repartidas entre varios identificadores. |
| **El bloque `contenido` se recorre por `tipo` y se arma la etiqueta HTML que corresponde** | Que el modelo devuelva HTML | El contrato de `generation/schemas.py` es estructurado justamente para que la UI decida la presentación. Además, HTML del LLM inyectado con `\|safe` sería XSS con firma del proveedor. Jinja escapa todo lo que viene del modelo. |
| **`indice_correcta` y `retroalimentacion` no viajan al navegador** | Mandar la actividad completa y comparar en el cliente | Estarían en el código fuente de la página y el quiz dejaría de medir nada. La corrección se hace en el servidor contra `mini_quiz_json`. |
| **`submit` comprueba que la cápsula sea del estudiante de la sesión** | Corregir por id sin más | Sin la comprobación, iterar ids ajenos devolvería la alternativa correcta de cualquier cápsula. |
| **Los errores de formulario viajan como HTML con estado 200** | Devolver 4xx | HTMX solo intercambia contenido en respuestas exitosas: un 422 deja al estudiante mirando un formulario que no reacciona. |
| **El visor distingue tres fallos en pantalla** (sin credencial / sin material curado / el modelo no logró una cápsula válida) | Un único "no se pudo generar" | Cada uno lo arregla una persona distinta: el equipo con la `LLM_API_KEY`, el docente curando, o revisando el prompt. Con un mensaje genérico, la demo no dice qué hacer. |
| **El botón de validar va junto al selector de objetivo, en la misma fila** | Validar primero y asignar después | Es la regla de la Fase 2 llevada a la interfaz: un fragmento validado sin objetivo queda inalcanzable para siempre. `curation.validar` ya lo bloquea; ahora además no se puede ni intentar por descuido. |
| **`GET /api/catalogo` con `solo_con_material=True` también en la web** | Mostrar todos los temas y avisar al entrar | Ofrecer un tema sin material curado lleva a un error de generación o a contenido inventado (cap. 12/13). Con el catálogo vacío se explica qué falta y se enlaza al panel de curación. |

### Lo que encontró la inspección, no los tests

1. **XSS reflejado en el aviso de error del cuestionario.** El mensaje cita la alternativa
   recibida (`el ítem 1 trae una alternativa desconocida: 'z'`) y se estaba interpolando en
   HTML sin escapar, así que un POST con `q1=<script>…` devolvía ese script dentro de la
   página y el navegador lo ejecutaba — con la cookie de sesión ahí para robar. Corregido con
   `html.escape` y con test de regresión. Los tests no lo veían porque el mensaje era correcto.

2. **Faltan los enunciados de los 16 ítems.** `instrumento.py` guarda las 64 alternativas
   (que son las que se puntúan) pero no el texto de las preguntas, porque para calificar no
   hace falta, y el informe tampoco los transcribe. Están en el encabezado de
   `data/data_cuestionarios_43.csv`, que no está versionado. Para que la Fase 4 se pudiera
   mostrar se escribieron enunciados equivalentes, aislados en `web/textos.py` y marcados como
   **provisionales**. ⚠️ **Hay que reemplazarlos por los originales del CSV antes de aplicar
   el instrumento a estudiantes nuevos**, o los 43 diagnósticos ya cargados y los que entren
   por la web no habrán respondido exactamente la misma pregunta.

### Verificación

Además de los 31 tests nuevos (`test_web_estudiante.py` y `test_web_docente.py`), se hizo el
recorrido completo **contra uvicorn**, no con `TestClient`, para ejercitar de verdad las
cabeceras de HTMX, la cookie y la subida multipart:

1. Catálogo vacío al principio → explica que falta material curado.
2. Alta del objetivo curricular (es carga manual por diseño: cap. 12).
3. Subida de un PDF real desde el panel → 2 fragmentos, 2 páginas, 472 palabras, **todos
   pendientes**, y la bandeja se recarga sola vía `HX-Trigger`.
4. Validar sin objetivo → rechazado con el motivo, el fragmento **sigue pendiente**.
5. Validar con objetivo → `validado`, y el documento promovido a `validado`.
6. El mismo tema **ya aparece** en el catálogo del estudiante, con su conteo de fragmentos.
7. El visor renderiza la cápsula con los cuatro tipos de bloque en su etiqueta correcta
   (`<p>`, `<ol>`, `<table>`, `<dl>`), sus fuentes con documento y página, y el quiz corrige
   bien acierto y error. La segunda visita al mismo tema sale del caché.
8. Sin `LLM_API_KEY` el visor explica exactamente eso, que es el estado real de la máquina.

El paso 7 se verificó con un doble del cliente LLM aplicado sobre la app real
(`dependency_overrides`), sin tocar el repositorio: el motor está completo, lo que falta es
la credencial.

---

## 5 decies. Panel de analíticas del docente — auditoría y correcciones (12-ago-2026)

Antes de esta sesión ya existían cinco vistas nuevas para el docente, construidas sobre el
motor real: **Historial de cápsulas**, **Cobertura curricular**, **Rendimiento en quizzes**,
**Simulador VARK** y **Estilos de aprendizaje de la cohorte** (`web/routers/teacher.py`,
`web/templates/teacher/analytics.html` y `simulator.html`). No es una fase nueva del roadmap
de `PLAN_DESARROLLO.md` — se documenta bajo el rótulo "Fase 5" porque así lo llaman ya los
docstrings del código (`InteraccionQuiz`, `get_analytics`); ver la nota al final de esta
sección sobre el choque de nombres con la Fase 5 del plan.

Se pidió analizar el apartado completo y mejorar solo el gráfico VARK de la cohorte (el resto
de la UI quedaba fuera de alcance). El análisis encontró que tres de las cinco secciones no
eran solo mejorables: tenían **bugs que invalidaban lo que decían mostrar**. Se trabajaron en
tres tandas, cada una cerrada con tests antes de pasar a la siguiente.

### Corrección de UI (la única solicitada): gráfico VARK de la cohorte

Las barras usaban variables CSS que no existen en `style.css`
(`--color-visual`/`--color-aural`/`--color-read`/`--color-kinesthetic`): salían transparentes,
con las etiquetas fuera del contenedor (`top: -25px`) y texto blanco sobre fondo blanco.
Reemplazado por el mismo patrón de barras horizontales que ya usa `student/profile.html`, con
los colores y nombres de canal tomados de `web/textos.py` (`_barras_cohorte` en `teacher.py`)
para que docente y estudiante vean el mismo azul para "Visual".

### 1. Simulador VARK — cuatro bugs, no un problema de UI

El simulador pasaba `resultado.capsula` (un `Microcapsula`, sin `id_capsula` ni `origen`) al
mismo `viewer.html` que usa el estudiante:

| Bug | Efecto | Corrección |
|---|---|---|
| `hx-post="/student/viewer//submit"` (id vacío) | El botón "Revisar Respuesta" del simulador daba 404 | Se extrajo `student/_capsula.html`, un partial que ambas vistas incluyen; el simulador ya no ofrece formulario porque la cápsula simulada no está persistida |
| `capsula.origen` no existe en `Microcapsula` → siempre falso | El badge decía "Recuperada de caché" sobre una cápsula recién generada | Badge propio de simulación: `Simulación · perfil {canal} 100%` |
| `viewer.html` extiende `base.html` completo | HTMX inyectaba un `<head>` y una barra de navegación duplicados dentro de `#simulator-result` | El simulador renderiza el partial directo, no la página |
| Canal inválido → `PerfilVark(0,0,0,0)` | Rompe el invariante `v+a+r+k=100`; `derivar()` lo clasifica como multimodal con primario V y genera igual, pagando la llamada al LLM | Se valida contra `CANALES` antes de construir el perfil; error explícito sin llamar al modelo |

Ganancia adicional: como el docente sí necesita ver la clave de la actividad (a diferencia del
estudiante, para quien es una fuga de datos), `es_simulacion` ahora controla exactamente esa
diferencia en el mismo partial — antes era un flag del contexto que ninguna plantilla leía.

Tests: `tests/test_web_simulador.py` (8).

### 2. Métricas de quiz — la cifra podía inflarse por reintentos

El visor deja el formulario en pantalla después de la retroalimentación, así que un estudiante
puede cambiar la alternativa y reenviar. `interaccion_quiz` guardaba **cada intento con el
mismo peso**: quien insistía hasta acertar subía el "% de acierto" del curso igual que quien
acertó a la primera. Además `es_correcta`/`alternativa_seleccionada` eran `NOT NULL`, así que
las actividades `intentalo_tu` (perfiles K) no podían registrarse y esos objetivos
desaparecían del panel como si nadie los hubiera trabajado.

Corregido con la migración `2fbc7391c0a3`:

- `numero_intento` (calculado **en el servidor**, nunca por el cliente) + `UNIQUE(id_capsula,
  numero_intento)` para que un doble clic no duplique el intento.
- `es_correcta` y `alternativa_seleccionada` pasan a `NULL`-ables, para registrar las
  actividades abiertas sin acierto.
- El panel (`_rendimiento_actividades`) reporta el **acierto al primer intento** como métrica
  principal, con los reintentos como columna aparte (una señal de material que no se entiende
  a la primera, no ruido a descartar).
- `POST /api/capsulas/{id}/quiz` ahora exige `id_estudiante` y devuelve **403** si la cápsula
  no es de quien responde — antes cualquiera podía inflar las métricas del curso con `curl`.

Ojo con la auto-corrección respecto de lo que se dijo en el chat al proponer este punto: no se
agregó `id_estudiante` a `interaccion_quiz` como columna propia. Es derivable con un JOIN a
`microcapsula_generada` (una cápsula tiene un solo dueño) y duplicarlo solo habría abierto la
puerta a que las dos copias se desincronizaran.

Al regenerar la migración, Alembic volvió a proponer borrar el índice GIN de FTS
(`ix_fragmento_contenido_fts`) — el mismo defecto ya documentado en `8010505ef66e` y
`8eb6f0399fee` (autogenerate no ve índices por expresión). Se quitó a mano otra vez.

Tests: `tests/test_interaccion_quiz.py` (12).

### 3. Cobertura curricular — el falso verde

La consulta original contaba `estado_validacion == 'validado'` y nada más. El retriever exige
además `documento.estado_curacion != 'rechazado'`: un apunte retirado **después** de haber
curado sus fragmentos dejaba el tema en verde en el panel mientras el motor ya lo ignoraba. Se
resolvió compartiendo los filtros entre los dos (`retriever._filtros_recuperables()`, usado
tanto por `recuperar` como por el nuevo `inventario_por_objetivo`), así que no pueden volver a
divergir — hay un test que compara la cifra del panel contra `retriever.contar_disponibles`.

Dos mejoras más sobre la misma sección:

- **Desglose por canal.** `PREFERENCIA_POR_CANAL` (tabla 11.1) **reordena, no filtra**: un
  objetivo con solo fragmentos de tipo texto está perfecto para A y R, y deja al perfil V
  leyendo lo mismo que ellos — la cápsula sale igual, pero la adaptación no se nota. El panel
  ahora marca en ámbar el canal sin recursos de su tipo preferido, sin decir que ese perfil se
  queda sin cápsula (no es así).
- **Umbral en vez de binario**, atado a la constante real del retriever:
  `MINIMO_RECOMENDADO = LIMITE_POR_DEFECTO // 2` → 0 fragmentos = falta material, 1–3 = escaso,
  ≥4 = cubierto.

Auto-corrección respecto de lo propuesto en el chat: no se agregó una columna de "pendientes
por tema". El objetivo se asigna **al validar** (`curation.validar`), así que un fragmento
pendiente casi siempre tiene `id_objetivo = NULL` y todavía no pertenece a ningún tema — una
columna por objetivo habría dado cero en todas las filas. Quedó como aviso global
("`N` fragmentos ingeridos sin revisar", con enlace a la bandeja de curación).

Tests: `tests/test_cobertura_curricular.py` (12).

### Verificación

**261 tests en verde** (229 + 32 nuevos) y `ruff` limpio salvo un aviso de línea larga en
`web/textos.py:35` que ya arrastraba `main`. Los tres endpoints del docente responden 200 con
la base vacía (que es el estado real de esta máquina ahora mismo — ver sección 6, punto 1).

### Nota sobre el rótulo "Fase 5"

Esta sección usa "Fase 5" porque así etiquetó ya el código que se auditó (comentarios y
docstrings de `models.py`, `schemas_capsulas.py`, `teacher.py`). No es la Fase 5 de
`PLAN_DESARROLLO.md` §4 ("Evaluación y resultados": A/B pedagógico con estudiantes, encuesta
TAM, rúbrica docente) — ese trabajo sigue sin empezar. Lo construido acá (analíticas + panel
docente) es alcance adicional que no estaba en el plan de 10 semanas original. Ver
`PLAN_DESARROLLO.md` §4 para la nota equivalente.

### Pendiente de esta sección (no se llegó a implementar)

1. **Simulador con perfiles reales de la cohorte.** Hoy solo simula 100/0/0/0 puro, un perfil
   que no existe en ninguno de los 43 diagnósticos reales — el caso multimodal, el más
   frecuente en la cohorte, no se puede simular. Y falta la **comparación V/A/R/K lado a lado
   del mismo objetivo**, que es literalmente el criterio de término de la Fase 3 en
   `PLAN_DESARROLLO.md` §4 ("comparar visualmente cuatro cápsulas… si no se distinguen, la
   adaptación no está funcionando"). Hoy esa comparación se arma de a una cápsula por vez.
2. **Historial de cápsulas** no muestra `estado_validacion` (la tasa de validez real del LLM,
   el otro criterio de término de la Fase 3) ni persiste `intentos`/`segundos` de la
   generación — con esas dos columnas el panel reemplazaría al CSV del bake-off como evidencia
   viva.
3. **Higiene de repo:** `scripts/reset_db.py` sigue sin confirmación antes de `drop_all`; la
   base de datos está vacía en esta máquina (0 objetivos, 0 diagnósticos, 0 fragmentos, 0
   cápsulas) pese a lo que las secciones 3 ter/5 quinquies de arriba describen como cargado —
   hay que volver a correr `import_vark_csv.py` y `cargar_objetivos.py` antes de usar el panel
   con datos reales.

---

## 5 undecies. Rebranding a "RepasAi" y fondo de marca (13-ago-2026)

Cambios de UI hechos directamente por Vicente (commit `7b34ba3`, fuera de una sesión de
trabajo asistida) — se documentan acá para que este archivo siga reflejando el estado real de
la interfaz.

- **Renombrado en toda la web:** "Studify" → "RepasAi" (`base.html`: `<title>` y el enlace del
  logo en el header). Es solo el nombre visible en la UI — el paquete Python (`studify`), el
  repositorio, `PLAN_DESARROLLO.md` y el resto de la documentación siguen diciendo "Studify".
  Si el cambio de nombre se vuelve definitivo, falta decidir hasta dónde propagarlo.
- **Fondo de marca en toda la web:** textura repetible de íconos educativos (libro, lápiz,
  regla, compás, globo, letras sueltas "A"/"3") en verde y azul muy tenues, sobre un degradado
  casi blanco. Viene de `docs/School Background.dc.html` y quedó aplicado a `body` en
  `style.css` con `background-attachment: fixed`, para que se vea igual y quieta en toda la
  app y no se repita "por página". El header conserva su fondo blanco sólido (`--bg-surface`),
  así que la textura solo se nota detrás del contenido — no compite con la navegación.
- **Tarjeta del cuestionario VARK** (`student/vark.html`): `background-color: #fafffc` (blanco
  verdoso muy sutil), fijado a mano en hexadecimal y no con el token `--success-bg` —ese token
  lo usan también las alertas de éxito en curación, así que tocarlo habría cambiado otra
  pantalla sin querer.

Verificado por captura contra el servidor real en `/student/vark`, `/teacher/curation` y
`/teacher/analytics`: el fondo se ve consistente entre vistas y las tarjetas siguen legibles
encima.

---

## 5 duodecies. Alta de objetivos de aprendizaje desde el panel del docente (14-ago-2026)

Cierra una brecha entre lo que el backend ya podía hacer y lo que la UI ofrecía:
`POST /api/objetivos` existe desde la Fase 2, pero nunca se conectó a ninguna pantalla — la
única vía para agregar un objetivo era `scripts/cargar_objetivos.py`, pensado para sembrar un
catálogo completo, no para la tarea de treinta segundos de agregar un tema suelto.

- **`POST /teacher/curation/objetivos`** (`web/routers/teacher.py`): reutiliza `crear_objetivo`,
  el handler de la API, en vez de reimplementar la lógica — mismo patrón que ya usaba la subida
  de documentos con `subir_documento`. El control de código duplicado (`codigo_objetivo` es
  clave natural) viene incluido sin escribirlo dos veces.
- **Formulario nuevo en `teacher/curation.html`**, arriba de "Cargar nuevo documento" — es el
  paso 0 real del flujo de curación. Muestra cuántos objetivos hay en el catálogo y una lista
  desplegable con los existentes, para no tener que adivinar códigos ya usados.
- **Mensajes de validación traducidos** (`_explicar_campos`): Pydantic devuelve errores en
  inglés ("String should have at most 30 characters") y esta es una pantalla en español para un
  docente, no un cliente de API.
- **`scripts/cargar_objetivos.py` no se retira.** Sigue siendo la vía correcta para cargar un
  plan de estudios completo de una vez —nadie escribe 60 objetivos en un formulario, uno por
  uno—; el `--dry-run` y la actualización masiva por `codigo_objetivo` no tienen equivalente en
  la UI y no lo necesitan. Ambas vías escriben por el mismo camino (`crear_objetivo`), así que
  no pueden divergir ni duplicar un código entre sí.

Tests nuevos en `tests/test_web_docente.py` (4): creación desde el panel, disponibilidad
inmediata del objetivo para validar fragmentos, rechazo de código duplicado con el motivo
explicado, y mensaje de error en español (no el texto de Pydantic). **265 tests en verde**
(261 + 4), `ruff` limpio en todo lo tocado.

### Bug encontrado al levantar el servidor, no por los tests

Esta máquina tenía aplicada la migración de la Fase 3 (`8010505ef66e`) pero no las dos que
agregó Patricio después (`5e11a9cf4a0b` interaccion_quiz, `2fbc7391c0a3` intentos numerados):
`/teacher/analytics` daba **500** — `UndefinedTable: no existe la relación "interaccion_quiz"`.
`pytest` no lo detecta porque la suite corre contra el estado real de la BD, y una migración
faltante no es un caso que los tests simulen. Corregido con `alembic upgrade head`. Es
exactamente el escenario que ya describe la sección 9 ("dos computadores del equipo"): cuando
alguien más pushea migraciones nuevas, hay que acordarse de aplicarlas en la máquina local
antes de levantar el servidor — no pasa solo.

### Primer material curricular real cargado (parcial)

De paso quedó armado `data/objetivos.csv`: 5 objetivos de "Diseño de UX", Unidad 1, derivados
del contenido real de un PPTX ya subido (`01 - Introducción al diseño UX`, 40 fragmentos
extraídos). Avanza en parte el pendiente n.º 1 de la sección 6: el catálogo ya no está vacío y
hay material real esperando curación.

**Sigue sin curar.** Los 40 fragmentos están todos en `pendiente`, 0 en `validado` — cargar el
catálogo no es lo mismo que curar el material. Varios fragmentos del PPTX son solo el pie de
página con el correo de la profesora (`Dra. Daniela Quiñones Otey — daniela.quinones@pucv.cl`,
repetido en más de diez fragmentos distintos): conviene **rechazarlos** al revisar, no
validarlos, porque no aportan contenido y ensuciarían las cápsulas generadas sobre ese objetivo.

> **Actualización 19-ago-2026:** ya se curó. Los cinco objetivos tienen material validado —13
> fragmentos en "Diferencia entre diseño UX y UI", 10 en "Etapas del Design Thinking", 10 en
> "Diseño centrado en el usuario", 4 y 3 en los dos restantes—, de modo que el pendiente n.º 1
> de la sección 6 queda cerrado para esta asignatura.

---

## 5 terdecies. Estructura pedagógica de siete pasos (19-ago-2026)

La profesora guía revisó el avance y observó que **el informe no define qué estructura tiene
una microcápsula**. Propuso una, y esta sección la implementa. Es el cambio más profundo desde
la Fase 3: toca el contrato, el validador, el prompt, el visor y cinco archivos de tests.

La auditoría completa de su lista de revisión —punto por punto, con veredicto y ruta de archivo—
está en [`AUDITORIA_LISTA_PROFESORA_14AGO2026.md`](AUDITORIA_LISTA_PROFESORA_14AGO2026.md).
Esta sección documenta solo lo que se implementó de ahí.

### Qué cambió en el contrato

Antes la cápsula era `contenido[]`, una lista de bloques tipados que el modelo ordenaba a su
criterio. Ahora cada paso tiene su propio campo obligatorio:

| Paso | Campo | Antes |
|---|---|---|
| 1. OA | `objetivo_aprendizaje` | ya existía |
| 2. Activación | `activacion` | **no existía** |
| 3. Concepto central | `concepto_central` | un bloque más de `contenido[]`, sin etiqueta |
| 4. Representación adaptativa | `representacion_adaptativa[]` | ídem, mezclado con el resto |
| 5. Ejemplo / aplicación | `ejemplo` | tipo de bloque opcional |
| 6. Pregunta de comprobación | `actividad.pregunta` | ya existía |
| 7. Retroalimentación | `actividad.retroalimentacion` | ya existía |

**Por qué un campo por paso y no una lista con etiquetas.** Con la forma anterior, "falta la
activación" era algo que había que descubrir leyendo la cápsula; ahora es un error de
validación que el bucle de reparación corrige solo. Que el orden sea el correcto tampoco
depende ya de que el modelo se acuerde: lo fija el contrato.

### Decisiones tomadas en esta entrega

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **La adaptación VARK no se encierra en el paso 4** | Concentrarla toda ahí, que es lo que sugiere el diagrama de la profesora | `ejemplo` también es un bloque tipado, así que un perfil kinestésico recibe `lista_pasos` donde otro recibe un párrafo, y la actividad sigue cambiando a `intentalo_tu` con `p_K ≥ 40%`. Concentrar todo en el paso 4 habría dejado sin destino a varias directivas de `vark/rules.py` que la tabla 11.1 del informe sí exige — el «inténtalo tú» del perfil K y el glosario del lector-escritor se habrían perdido. |
| **El prompt muestra los cuatro pesos C_* en crudo *además* de las instrucciones estructurales** | Solo los porcentajes (literal a su plantilla), o seguir ocultándolos como hasta ahora | Su plantilla los pide explícitamente y son informativos —sobre todo dentro del paso 4, donde se mezclan los cuatro canales—, pero un modelo ignora con facilidad un «22,75 % de texto». Las instrucciones concretas («incluye una `tabla` de 3×2») siguen siendo las únicas que se pueden comprobar después en el JSON. Se dan las dos cosas: es estrictamente más información. |
| **Los C_* se muestran redondeados a un decimal** | Pasarlos con la precisión completa | El modelo no hace nada distinto con 22,75 que con 22,8, y la cifra larga invita a que la copie tal cual dentro del texto de la cápsula. |
| **La activación se valida como pregunta** (exige `?`) y se acota a 45 palabras | Aceptar cualquier texto en ese campo | Una «activación» sin interrogación es exposición, no activación; y si se alarga, invade el paso 3. Se comprueba el signo de cierre y no el de apertura porque los modelos omiten el «¿» inicial con frecuencia, y eso es un problema ortográfico, no pedagógico — gastar un reintento en ello sería desperdiciarlo. |
| **`concepto_central` es texto plano, no un bloque tipado** | Hacerlo un `BloqueContenido` como los otros | Lo que cambia entre perfiles es *cómo se refuerza* el concepto (paso 4), no la definición misma. El paso 3 es deliberadamente el mismo para los cuatro canales. |
| **Se borraron las 2 cápsulas existentes en vez de migrarlas** | Escribir una migración de datos o versionar el contrato | Eran dos filas de pruebas del bake-off. Una migración de `contenido_json` habría costado más que regenerarlas, y versionar el contrato para dos filas obsoletas habría dejado dos caminos de renderizado vivos para siempre. |
| **`bloques_legibles()` duplicado en `Microcapsula` y en `CapsulaOut`** | Un único helper compartido | El visor recibe indistintamente una `CapsulaOut` (flujo del estudiante, que lee de la base) o una `Microcapsula` (simulador del docente, que no persiste nada). Ambas tienen que responder lo mismo o la plantilla dejaría de servir para las dos. |

### Verificación contra el modelo real

No solo tests: se generó una cápsula real contra DeepSeek sobre el material de UX ya curado
(objetivo 190, «Diferencia entre diseño UX y diseño UI», perfil `{V:35, A:15, R:20, K:30}`):

- **Válida al primer intento**, 8,4 s, **247 palabras** (dentro del rango 150–300 del cap. 11.1).
- Los siete pasos presentes y en orden.
- La representación adaptativa trajo **un esquema jerárquico y una tabla comparativa** — que es
  lo que corresponde a un perfil con V como canal dominante.
- Las cuatro fuentes citadas (`725, 728, 730, 731`) verificadas contra los fragmentos
  realmente inyectados.
- Renderizada en el visor por HTTP: la activación sale destacada arriba, el concepto central
  rotulado, y después los bloques adaptativos y el ejemplo.

**277 tests en verde** (265 + 12 nuevos), `ruff` limpio salvo el aviso preexistente de
`web/textos.py:35`.

Los 12 tests nuevos cubren: que cada uno de los siete pasos sea obligatorio (parametrizado, uno
por paso), que la activación sea una pregunta y no la explicación completa, que `ejemplo` se
adapte al perfil, que los cuatro pasos del cuerpo sumen para el rango de palabras, y que el
bucle de reparación arregle una cápsula a la que le falte la pregunta de activación.

### Lo que de la lista de la profesora **no** se implementó

Tres puntos quedaron fuera a propósito y conviene tenerlos claros para la próxima reunión:

1. **Embeddings / vectores** (punto 5 de su pipeline). No es un pendiente: contradice
   directamente el cap. 13 del informe que ella ya aceptó, donde se argumenta que la
   recuperación por similitud vectorial introduce un factor probabilístico incompatible con la
   trazabilidad curricular. Se resuelve conversándolo, no programándolo.
2. **OA secundarios por chunk.** `Fragmento.id_objetivo` es una FK singular; admitir varios
   exige una tabla de asociación nueva. Además **hay tensión con otra regla de su propia
   lista**: pide OA secundarios y a la vez «evitar que un chunk pertenezca a varios contenidos».
   Antes de tocar el modelo hay que decidir si «contenido» (tema) y «OA» (objetivo evaluable)
   son la misma jerarquía o dos cosas distintas — hoy el sistema los trata como una sola.
3. **Campo «contenido» asociado al OA** (su ejemplo `OA01 → Contenido: Probabilidad
   condicionada`). Existe `ObjetivoAprendizaje.descripcion`, que es texto libre, pero no es
   exactamente lo mismo.

---

## 6. Pendiente inmediato

Los dos primeros son ahora los que bloquean todo lo demás: el motor está escrito y probado,
pero **no se ha ejecutado nunca contra un modelo real ni sobre material real**.

0. ~~**Conseguir la credencial del LLM y ponerla en `LLM_API_KEY`.**~~ ✅ **Cerrado.** La key de
   DeepSeek está cargada (verificado el 13-ago-2026: `llm.api_key_configured: true` en
   `/health`) y el bake-off ya corrió — ver sección 1. Queda igual el resto de este punto como
   referencia, porque la mitigación que describe sigue siendo la que aplica si al ampliar el
   material real las cuatro cápsulas VARK del mismo objetivo salieran parecidas. El plan §5 ya
   fija la mitigación —
   instrucciones estructurales, no adjetivos de tono— y el prompt ya está construido así, de
   modo que lo que habría que ajustar son las instrucciones de
   `rag/prompts/maestro.py::INSTRUCCION_POR_DIRECTIVA`, no el motor.
1. ~~**Cargar material real de la base de conocimiento.**~~ ✅ **Cerrado el 19-ago-2026 para la
   primera asignatura.** Los cinco objetivos de "Diseño de UX" tienen material curado (13 + 10 +
   10 + 4 + 3 fragmentos validados) y ya se generaron cápsulas reales sobre ellos. Queda como
   deseable —no bloqueante— una **segunda asignatura**, para que la prueba de diferenciación
   entre perfiles VARK del punto 0 no dependa de un solo dominio.
2. ~~**Conectar la UI de Patricio a los endpoints reales.**~~ ✅ **Cerrado el 11-ago-2026**
   (sección 5 nonies). Las cinco vistas del estudiante y el panel del docente llaman a los
   handlers reales; el visor recorre los bloques del contrato por `tipo` y muestra las dos
   formas de actividad. Desde el 19-ago los recorre vía `bloques_legibles()`, que devuelve la
   representación adaptativa seguida del ejemplo.
3. **`tagger.py` (etiquetado asistido por LLM)** sigue sin implementarse. Quedó fuera de la
   Fase 2 porque entonces no había credencial; **ahora sí la hay**, así que el bloqueo
   desapareció y es trabajo pendiente sin más. Hoy el curador asigna el objetivo a mano:
   funciona, pero es lento —se vio al curar los 40 fragmentos de UX—. Cuando se implemente, el
   tagger solo debe **proponer**, nunca decidir.
4. ~~Los **21 avisos de `ruff`** en `web/deps.py`, `web/routers/student.py` y
   `web/routers/teacher.py`.~~ ✅ **Cerrado el 11-ago-2026:** desaparecieron al conectar esos
   routers a la API real, tal como se había previsto. `ruff check .` está limpio en todo el
   repositorio.
5. **Resolver la discrepancia de las tablas 16.2/16.3** con la profesora guía: o se corrige el
   informe con los valores recalculados, o aparece la planilla original que explique la
   diferencia. El código ya entrega los números reales; el informe es lo que habría que ajustar.
6. **Reemplazar los enunciados provisionales de los 16 ítems.** ⚠️ Sigue abierto y ahora es
   más urgente, porque el cuestionario ya se puede responder por la web. `web/textos.py`
   contiene enunciados **equivalentes pero reconstruidos**; los originales están en el
   encabezado de `data/data_cuestionarios_43.csv` (no versionado). Hasta que se copien de ahí,
   quien responda por la aplicación no habrá contestado exactamente la misma pregunta que los
   43 estudiantes ya cargados, y los perfiles no serían estrictamente comparables.
7. **Fijar `SESSION_SECRET` en el `.env` de cada máquina** antes de una demo o de una sesión
   con estudiantes. Sin ella la app funciona, pero cada reinicio de `uvicorn --reload` cierra
   las sesiones abiertas y obliga a responder el cuestionario de nuevo. Se genera con
   `python -c "import secrets; print(secrets.token_hex(32))"`.
8. **Instalar las dependencias opcionales de ingesta** (`pip install -e ".[ingest]"`) en la
   máquina donde se vaya a curar: sin `pymupdf`/`python-pptx` el panel del docente no puede
   procesar archivos. El panel lo detecta y lo dice, pero conviene dejarlo instalado.
9. **Repoblar la base de datos.** Está vacía en esta máquina ahora mismo (0 objetivos, 0
   diagnósticos, 0 fragmentos, 0 cápsulas) — confirmado al auditar el panel de analíticas
   (sección 5 decies). Correr `import_vark_csv.py` y `cargar_objetivos.py` antes de usar
   cualquier vista del docente o del estudiante con datos reales.
10. **Simulador VARK: perfiles reales de la cohorte y comparación V/A/R/K lado a lado.**
    Detalle en sección 5 decies, "Pendiente de esta sección". Es el punto de mayor valor para
    el informe: la comparación lado a lado es la evidencia directa del criterio de término de
    la Fase 3.
11. **Historial de cápsulas: mostrar `estado_validacion` y persistir `intentos`/`segundos`
    de la generación.** Convertiría el panel en evidencia viva del bake-off en vez de depender
    solo de `data/resultados_evaluacion.csv`. Detalle en sección 5 decies.
12. **`scripts/reset_db.py` sin confirmación** antes de `drop_all` + borrar `alembic_version`.
    Es destructivo y de un solo comando; conviene una confirmación explícita antes de que borre
    algo que cueste recuperar en una máquina compartida por el equipo.
13. **Definir con la profesora si "contenido" y "OA" son la misma jerarquía.** De su lista salen
    dos requisitos que hoy se contradicen: pide **OA secundarios** por chunk y a la vez «evitar
    que un chunk pertenezca a varios contenidos». Con el modelo actual —`Fragmento.id_objetivo`
    como FK singular— el segundo se cumple por construcción y el primero es imposible. Implementar
    OA secundarios exige una tabla de asociación nueva, y antes hay que cerrar esa ambigüedad
    conceptual. Detalle en `AUDITORIA_LISTA_PROFESORA_14AGO2026.md`, punto 3.
14. **Zanjar el punto de los embeddings con la profesora.** Su pipeline propuesto los incluye
    (paso 5); el cap. 13 del informe que ella aceptó argumenta explícitamente en contra. No es
    trabajo de programación: es una conversación pendiente sobre si la arquitectura sigue siendo
    la aprobada. Mientras no se cierre, el sistema sigue con recuperación SQL determinista.

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
