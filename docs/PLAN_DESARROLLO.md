# Studify — Plan de desarrollo del prototipo funcional

Bajada a código de la arquitectura definida en el Informe de Avance
*"Generación de micro-aprendizaje educativo mediante IA generativa, basado en estilos de aprendizaje del estudiante"*.

**Horizonte:** 10 semanas (03-ago-2026 → 09-oct-2026)
**Modalidad:** desarrollo conjunto (ambos integrantes sobre el mismo módulo)
**Prioridad declarada:** que el motor LLM quede funcionando bien primero; UI mínima ahora, UI completa después.

> Nota de calendario: la Carta Gantt del informe (cap. 5) termina el 30-06-26 y hoy es 31-07-26. Este plan re-ancla las fechas al presente y asume una segunda etapa de implementación.

---

## 1. Decisiones de stack

| Componente | Decisión | Por qué |
|---|---|---|
| Lenguaje | Python 3.11+ | Definido en cap. 14 |
| API | FastAPI + Uvicorn | Definido en cap. 14; validación Pydantic nativa |
| BD | **PostgreSQL 16** (no MySQL) | `JSONB` nativo para `contenido_json` / `mini_quiz_json` / `metadatos_json`, y full-text search en español (`to_tsvector('spanish', …)`) sin extensiones. El informe deja abierta la opción. |
| ORM / migraciones | SQLAlchemy 2.0 + Alembic | Las 8 entidades del cap. 17 evolucionarán; migraciones versionadas evitan romper datos de prueba |
| Orquestador | `llama-index-core` + `llama-index-llms-openai-like` | Coherente con cap. 14/15. Se usa **solo** lo necesario: `BaseRetriever` custom, `PromptTemplate`, conector LLM. No se usa `VectorStoreIndex` (sería contradecir el RAG estructurado) |
| LLM | Endpoint OpenAI-compatible (DeepSeek / Qwen / GLM) | Decisión del equipo. Los tres exponen API compatible → un solo cliente, modelo intercambiable por variable de entorno |
| Validación de salida | Pydantic v2 | Es literalmente la "capa de validación estructural" de la Fase 4 (cap. 18) |
| Ingesta | `pymupdf` (PDF), `python-pptx` (PPTX) | Conservan número de página → requisito de trazabilidad |
| UI mínima | Jinja2 + HTMX servido por el mismo FastAPI | Cero build step. Todo pasa por `/api/*`, así que la UI React posterior no obliga a tocar el backend. Streamlit sería más rápido pero es un callejón sin salida |
| Infra local | Docker Compose (solo Postgres) | Reproducible entre ambos computadores |
| Tests | pytest | Las fórmulas VARK y el validador JSON son el corazón; deben tener tests |

**Sobre el LLM chino:** DeepSeek-V3 (`deepseek-chat`) es el más barato y soporta `response_format={"type":"json_object"}`. Qwen-plus suele redactar mejor en español. La decisión final se toma con datos en el bake-off de la Fase 3, no ahora. El código debe permitir cambiar de modelo con una variable de entorno.

---

## 2. Estructura del repositorio

```
Studify/
├─ docker-compose.yml          # Postgres 16
├─ pyproject.toml
├─ .env.example                # LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, DATABASE_URL
├─ alembic/
├─ src/studify/
│  ├─ main.py                  # app FastAPI
│  ├─ config.py                # settings pydantic-settings
│  ├─ db/
│  │  ├─ models.py             # 8 entidades del cap. 17
│  │  └─ session.py
│  ├─ vark/
│  │  ├─ scoring.py            # 16 ítems → puntajes crudos → vector porcentual
│  │  ├─ weighting.py          # fórmulas C_texto / C_visual / C_narrativo / C_practico
│  │  ├─ rules.py              # tabla 11.1 → configuracion_contenido
│  │  └─ hierarchy.py          # canal primario / secundario / multimodalidad (derivado)
│  ├─ knowledge/
│  │  ├─ ingest.py             # PDF/PPTX → fragmentos con página
│  │  ├─ tagger.py             # etiquetado asistido por LLM (propone, no decide)
│  │  └─ curation.py           # flujo de validación humana
│  ├─ rag/
│  │  ├─ retriever.py          # SQL determinista → NodeWithScore
│  │  ├─ prompts/              # plantillas maestras por bloque
│  │  └─ orchestrator.py       # ensamblado del prompt maestro
│  ├─ generation/
│  │  ├─ schemas.py            # contrato Pydantic de la microcápsula
│  │  ├─ generator.py          # llamada al LLM
│  │  └─ validator.py          # validación + bucle de reparación
│  ├─ api/routers/             # students, diagnostics, catalog, capsules, teacher
│  └─ web/                     # templates/ + static/  (UI mínima)
├─ tests/
├─ scripts/
│  ├─ import_vark_csv.py       # cargar los 43 diagnósticos ya recolectados
│  ├─ seed_demo.py
│  └─ eval_runner.py           # batería de evaluación técnica
└─ docs/
```

---

## 3. Contrato de la microcápsula (el artefacto central)

Este esquema es el punto de acuerdo entre el motor LLM y la UI. Definirlo **antes** de escribir el generador.

```json
{
  "titulo": "string (máx. 10 palabras)",
  "objetivo_aprendizaje": "string (1 oración)",
  "contenido": [
    { "tipo": "parrafo | lista_pasos | tabla | esquema | analogia | ejemplo_resuelto | glosario",
      "encabezado": "string | null",
      "cuerpo": "string | array" }
  ],
  "actividad": {
    "tipo": "quiz_mc | intentalo_tu",
    "pregunta": "string",
    "alternativas": ["...", "...", "...", "..."],
    "indice_correcta": 0,
    "retroalimentacion": "string"
  },
  "fuentes": [ { "id_fragmento": 1, "documento": "string", "pagina": 12 } ]
}
```

El validador (`generation/validator.py`) rechaza y reintenta si:
1. El JSON no parsea o no cumple el esquema.
2. `contar_palabras(contenido)` cae fuera de **150–300** (cap. 11.1).
3. `titulo` supera 10 palabras.
4. Falta `actividad` (la actividad de cierre es obligatoria).
5. **Algún `id_fragmento` de `fuentes` no está entre los fragmentos que se inyectaron en el prompt** → esto detecta citas alucinadas, que es el riesgo específico que advierte Hashiyada et al.
6. El idioma detectado no es español (los modelos chinos derivan a inglés/chino en prompts largos).

Máximo 2 reintentos con el error de validación reinyectado; si falla, se registra y se devuelve 502. Esa tasa de fallo es un dato de resultados para el informe final.

---

## 4. Roadmap por fases

### Semana 0 — Setup (03–07 ago)
Repo, `docker-compose.yml` con Postgres, esqueleto FastAPI con `/health`, `.env.example`, Alembic inicializado, `pyproject.toml`, pre-commit con ruff.
**Entregable:** `docker compose up` + `uvicorn` levantan en ambos computadores.

### Fase 1 — Núcleo de datos y VARK (10–21 ago)
- Migración con las 8 entidades del cap. 17 (diccionario de datos ya está escrito, es transcripción).
- `scripts/import_vark_csv.py`: cargar los **43 diagnósticos reales** del Google Forms. Trabajar con datos reales desde el día 1, no con fixtures inventados.
- `scoring.py` → vector porcentual; `weighting.py` → fórmulas C_*; `rules.py` → tabla 11.1; `hierarchy.py` → vista derivada.
- Tests con los casos que ya están en el informe: `{45V, 20A, 15R, 20K}`, `{25V, 20A, 20R, 35K}`, y el perfil por defecto K→A.

**Criterio de término:** `POST /api/diagnosticos` devuelve una `configuracion_contenido` completa, y una consulta sobre los 43 registros **reproduce exactamente las tablas 16.2 y 16.3 del informe** (moda A+K, promedios K=7,96 / A=6,57 / R=5,17 / V=3,65). Si no reproduce, hay un bug en el scoring o un error en el informe — en ambos casos conviene saberlo ahora.

### Fase 2 — Base de conocimiento e ingesta (24 ago – 04 sep)
- Catálogo de `objetivo_aprendizaje` (carga manual: es información curricular, no se infiere).
- `ingest.py`: PDF/PPTX → fragmentos con `pagina_inicio`/`pagina_fin`.
- `tagger.py`: el LLM **propone** objetivo asociado, etiqueta temática y tipo de fragmento; queda en `estado_validacion = 'pendiente'`.
- `curation.py` + endpoints: aprobar/rechazar/editar. **Ningún fragmento sin validar entra al retriever.**
- `retriever.py`: SQL determinista filtrando por `id_objetivo` + `estado_validacion='validado'`, con full-text search en español como filtro secundario y ordenamiento por tipo de fragmento según perfil VARK.

**Criterio de término:** una unidad real de una asignatura cargada, 40–60 fragmentos validados, `GET /api/fragmentos?objetivo=X` devuelve solo material curado.

> ⚠️ Esta fase es la que más se subestima. Techo duro: **una unidad de una asignatura**. No cargar el ramo completo.

### Fase 3 — Motor de generación (07–18 sep) ← *foco principal*
- Cliente LLM vía `OpenAILike` (base_url configurable).
- Prompt maestro en tres bloques: **contexto** (fragmentos con su id) + **perfil** (derivado de `configuracion_contenido`, no de la etiqueta) + **formato** (esquema JSON + límite 150–300 palabras + idioma español obligatorio).
- Validador + bucle de reparación.
- Persistencia en `microcapsula_generada` con FK a `fragmento` → trazabilidad nativa.
- **Bake-off de modelos:** mismo prompt × 3 modelos candidatos × 4 perfiles VARK. Medir: % de JSON válido al primer intento, adherencia al rango de palabras, calidad del español (evaluación ciega entre ustedes dos), latencia y costo por cápsula. → Es una tabla directa para el informe final.
- Caché por `(id_objetivo, hash de configuracion_contenido redondeada)` para no pagar generación repetida en las pruebas.

**Criterio de término:** `POST /api/capsulas {id_estudiante, id_objetivo}` devuelve una cápsula válida ≥95% de las veces, con quiz y fuentes verificables. Comparar visualmente cuatro cápsulas del mismo objetivo generadas para V, A, R y K: si no se distinguen entre sí, la adaptación no está funcionando y hay que trabajar el prompt.

### Fase 4 — UI mínima funcional (21–25 sep)
Jinja + HTMX: cuestionario VARK (16 ítems, selección múltiple y opción de dejar en blanco, según cap. 10) → pantalla de resultado con el vector porcentual → catálogo de temas → cápsula renderizada según perfil → quiz con retroalimentación. Panel de curación mínimo (subir documento, revisar fragmentos, validar).

**Criterio de término:** la demo completa se hace sin abrir Swagger.

### Fase 5 — Evaluación y resultados (28 sep – 09 oct)
- Batería técnica (`eval_runner.py`): 20–30 consultas controladas → fidelidad, exactitud factual, relevancia, trazabilidad; rúbrica 1–5 con doble evaluador.
- **A/B pedagógico (decidido 06-ago-2026, reemplaza el diseño del cap. 8.2 del informe):**
  dos grupos estudian la **misma materia**; el grupo experimental **accede a la app** y la
  recibe como microcápsula personalizada a su perfil VARK, el grupo de control la estudia de
  forma tradicional (apuntes/guías/clase normal) **sin tocar el sistema**. Se comparan
  calificaciones entre ambos grupos.
  - El cap. 8.2 del informe describe otro diseño (control = cápsula genérica vía la app,
    experimental = cápsula adaptada vía la app, ambos usando el sistema) — **queda
    reemplazado**, hay que actualizar el capítulo 8 para el informe final.
  - Implicación para el código: `generation/` **no necesita un modo de generación no
    personalizada** — toda cápsula que el sistema genere está siempre adaptada a un perfil
    real. Simplifica el contrato de `generation/schemas.py` frente a lo que se había previsto.
  - Pendiente de definir: cómo se registran las calificaciones de ambos grupos (es dato
    académico externo, no algo que la BD actual capture) y qué material exacto ve el grupo de
    control para que sea comparable en cobertura y tiempo de estudio al de la app.
- **Validación de la adaptación VARK, con el profesor (aclarado 06-ago-2026).** El informe
  separa en la Tabla 8.1 "adaptabilidad pedagógica" (método: comparar cápsulas de distintos
  perfiles, sin decir quién compara) de "validación docente" (criterios: coherencia académica,
  pertinencia, carga operativa — sin mencionar VARK). En la práctica es una sola actividad: el
  profesor revisa, para un mismo objetivo, las cápsulas generadas para los distintos perfiles y
  valida si la adaptación (estructura, tono, ejemplos, actividad) corresponde a cada perfil.
  Ajustar la rúbrica docente del cap. 8.5 para incluir explícitamente ese criterio.
- Encuesta TAM a estudiantes + rúbrica a docentes (cap. 8.5).
- Estadística descriptiva + redacción del capítulo de resultados.

> **Track paralelo:** los instrumentos, el consentimiento informado y el reclutamiento tienen que estar listos en la **semana 6**, no en la 9. Conseguir participantes es lo que más se atrasa.

---

## 5. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| La curación de documentos consume el presupuesto de tiempo | Techo duro de una unidad / 60 fragmentos. Etiquetado asistido por LLM con revisión humana rápida |
| El modelo chino no respeta `json_object` o el esquema | Parser tolerante (extraer primer bloque JSON) + bucle de reparación + fallback a otro modelo por env var |
| Deriva de idioma (inglés/chino) en prompts largos | Instrucción explícita de idioma + validación automática de idioma en el validador |
| Las cuatro cápsulas VARK salen indistinguibles | Prueba de diferenciación al cierre de la Fase 3; si falla, el prompt debe recibir instrucciones **estructurales** (qué bloques incluir), no adjetivos de tono |
| Costo/latencia durante las pruebas | Caché de cápsulas + modelo barato en desarrollo, modelo bueno solo para la evaluación final |
| Consentimiento y ética con estudiantes | Formulario de consentimiento revisado con la profesora guía antes de la semana 6 |

---

## 6. Decisiones pendientes que bloquean código

Estas se cierran en la Semana 0 / Fase 1. Todas nacen de vacíos del informe:

1. **Mapeo de C_\* a parámetros concretos.** Las fórmulas del cap. 11.2 producen valores continuos, pero `configuracion_contenido` guarda enteros (`recursos_visuales`, `componentes_practicos`, `palabras_texto`). Faltan los cortes. Propuesta: `recursos_visuales = 0 si C_visual<15, 1 si <25, 2 si ≥25`; `palabras_texto = 150 + round(C_texto/100 · 150)`; `componentes_practicos` análogo con C_practico.
2. **`audio_activo`.** El campo existe en la tabla 17.4 pero no hay TTS en el stack del cap. 14. Decidir: (a) fuera de alcance y el canal auditivo se atiende solo con redacción conversacional, o (b) agregar TTS. Recomendación: (a) para el prototipo, y declararlo como trabajo futuro.
3. **Fragmentos no textuales.** ¿Cómo se le entrega una tabla o un diagrama a un LLM de texto? Definición propuesta: al curar, se guarda una **descripción textual** del recurso en `metadatos_json`, y esa descripción es lo que se inyecta; `ruta_recurso` se usa solo para renderizar en la UI.
4. **Selección del tema por el estudiante.** No está en el informe. Se necesita `GET /api/catalogo` (asignatura → unidad → objetivo).
5. **Regeneración.** ¿Puede un estudiante pedir otra cápsula del mismo objetivo? Definir si se versiona o se sobreescribe.

---

## 7. Correcciones pendientes en el informe

Detectadas al leerlo para este plan. No bloquean el código, pero conviene arreglarlas para el informe final:

- **Referencias cruzadas desfasadas** (parecen haber quedado de una numeración anterior): el cap. 16.4 remite a "sección 12.2" cuando las reglas de mapeo están en **11.2**; el cap. 17 remite a "sección 14" cuando la justificación de la BD es el **13**, y a "sección 12.3" que no existe; el cap. 17.1 remite a "sección 10" para los datos sociodemográficos, que están en el **9**, y a "sección 11" para la calificación, que está en el **10**.
- **Resumen vs. Abstract:** el resumen en español es condicional ("se espera que el sistema contribuya a mejorar la retención"), pero el abstract afirma en indicativo ("Preliminary findings […] indicate that […] **effectively improves** knowledge retention"). Como todavía no hay validación empírica, el abstract debería ir en condicional.
- **Cita del cap. 11.1** dice "50 a 70 minutos" mientras el cap. 2 cita la misma fuente como "50 a 75 minutos". Verificar contra Saha et al.
- **Tabla 16.2 (muestra total)** suma 43 estudiantes pero no incluye columna de porcentaje, a diferencia de la tabla de Ing. Informática. Homologar.
- La distribución por año en el cap. 16.1 suma 43 (20+9+7+7) pero los porcentajes (47+21+16+16) suman 100 solo por redondeo. Aclarar con nota al pie.
```
