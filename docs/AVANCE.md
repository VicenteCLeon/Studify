# Studify — Estado de avance

> Documento vivo. Se actualiza al cierre de cada fase para que cualquier sesión de trabajo
> (o cualquier persona) pueda retomar el proyecto sin releer todo el hilo de conversación.
> Última actualización: **05-ago-2026**, cierre de Semana 0.

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

El documento fuente de todo el diseño es [`seminario_titulo.md`](../seminario_titulo.md)
(el informe de avance ya entregado). El plan de implementación derivado de ese informe está en
[`PLAN_DESARROLLO.md`](PLAN_DESARROLLO.md) — **léase antes de tocar código**, ahí están las
decisiones de arquitectura, el roadmap de 10 semanas y las decisiones pendientes.

Este archivo (`AVANCE.md`) es el complemento: qué se hizo realmente, qué se verificó, qué
quedó pendiente y qué decisiones se tomaron sobre la marcha.

---

## 1. Estado actual en una frase

**Semana 0 (Setup) completa y verificada. Nada commiteado todavía — todo está en el working
tree, pendiente de un primer commit.** La Fase 1 (modelos de datos + scoring VARK) no ha
comenzado.

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
│  ├─ env.py             # lee DATABASE_URL desde studify.config, no desde alembic.ini
│  ├─ script.py.mako
│  └─ versions/          # VACÍO — la primera migración es tarea de la Fase 1
├─ src/studify/
│  ├─ main.py            # app FastAPI + endpoint /health
│  ├─ config.py          # Settings (pydantic-settings, lee .env)
│  ├─ db/
│  │  ├─ base.py         # DeclarativeBase compartida
│  │  ├─ session.py      # engine + SessionLocal + get_db() síncronos
│  │  └─ models.py       # NO EXISTE AÚN — es la tarea principal de la Fase 1
│  ├─ vark/              # paquete vacío (solo __init__.py) — Fase 1
│  ├─ knowledge/         # paquete vacío (solo __init__.py) — Fase 2
│  ├─ rag/               # paquete vacío (solo __init__.py) — Fase 3
│  │  └─ prompts/        # NO EXISTE AÚN
│  ├─ generation/        # paquete vacío (solo __init__.py) — Fase 3
│  ├─ api/routers/       # paquete vacío (solo __init__.py) — endpoints por fase
│  └─ web/               # NO EXISTE AÚN (templates/ + static/) — Fase 4
├─ tests/
│  └─ test_health.py     # smoke test de Semana 0
├─ scripts/               # VACÍO — import_vark_csv.py es la primera tarea real de Fase 1
├─ data/                  # vacío (.gitkeep), ignorado por git salvo el .gitkeep
└─ docs/
   ├─ PLAN_DESARROLLO.md  # plan completo de 10 semanas, decisiones pendientes, riesgos
   └─ AVANCE.md           # este archivo
```

**Nota importante:** los directorios `vark/`, `knowledge/`, `rag/`, `generation/`,
`api/routers/` existen como paquetes Python vacíos (solo `__init__.py`) — es andamiaje de la
Semana 0, no implementación. No asumir que hay lógica ahí.

---

## 5. Pendiente inmediato

1. **Commit de la Semana 0.** El working tree tiene todo listo pero no se ha hecho `git add` /
   `git commit` de nada salvo el `Initial commit` original (que solo trae `.gitattributes`).
2. **Fase 1 — Núcleo de datos y VARK** (siguiente paso de `PLAN_DESARROLLO.md`, sección 4):
   - `src/studify/db/models.py`: las 8 entidades del cap. 17 del informe (`estudiante`,
     `diagnostico_vark`, `respuesta_vark`, `configuracion_contenido`, `objetivo_aprendizaje`,
     `documento_fuente`, `fragmento`, `microcapsula_generada`). El diccionario de datos
     completo (tipos, tamaños, descripciones) ya está escrito en el informe, secciones 17.1–17.4
     — es prácticamente transcripción a SQLAlchemy.
   - Primera migración Alembic (`alembic revision --autogenerate`).
   - `src/studify/vark/scoring.py`, `weighting.py`, `rules.py`, `hierarchy.py` — implementan
     respectivamente: 16 ítems → vector porcentual; fórmulas C_texto/C_visual/C_narrativo/
     C_practico (informe cap. 11.2); tabla de reglas de decisión 11.1; jerarquía de canales
     derivada (no persistida, cap. 17.2).
   - **Se necesita el CSV exportado del Google Forms** con las 43 respuestas reales
     (`scripts/import_vark_csv.py`) — el usuario debe proporcionarlo.
   - Criterio de éxito explícito: los cálculos sobre esos 43 registros deben reproducir
     exactamente las tablas 16.2/16.3 del informe (moda de perfil = A+K; promedios
     K=7,96, A=6,57, R=5,17, V=3,65). Si no coincide, hay un bug en el código o un error en
     el informe — cualquiera de los dos hay que detectarlo ahí, no después.

---

## 6. Decisiones de diseño aún abiertas (no bloquean la Semana 0, sí bloquean partes de la Fase 1/3)

Copiadas y mantenidas en sincronía con `PLAN_DESARROLLO.md` sección 6 — resumen aquí para no
tener que saltar de archivo:

1. **Cortes numéricos de C_\* a enteros.** Las fórmulas del cap. 11.2 dan valores continuos
   (0–100) pero `configuracion_contenido` guarda enteros (`recursos_visuales`,
   `palabras_texto`, `componentes_practicos`). Propuesta ya escrita en el plan, falta
   ratificarla al implementar `vark/rules.py`.
2. **`audio_activo`** (tabla 17.4) no tiene TTS en el stack — se recomienda dejarlo fuera de
   alcance del prototipo y declararlo como trabajo futuro en el informe final.
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

---

## 8. Cómo retomar el trabajo (para una sesión nueva)

```powershell
cd e:\code\Studify\Studify
.\.venv\Scripts\Activate.ps1
uvicorn studify.main:app --reload --app-dir src
# → http://127.0.0.1:8000/health  y  http://127.0.0.1:8000/docs

pytest
ruff check .
```

Si `.venv` no existe (máquina nueva): seguir `README.md` sección "Puesta en marcha" completa,
incluyendo la creación del rol/base de Postgres (comando en README sección "Crear el rol y la
base").

**Orden de lectura recomendado para contexto:** este archivo → `docs/PLAN_DESARROLLO.md` →
`seminario_titulo.md` (el informe fuente) → código en `src/studify/`.
