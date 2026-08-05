# Studify

Prototipo funcional de generación de micro-aprendizaje educativo mediante IA generativa,
adaptado al perfil VARK del estudiante y anclado en una arquitectura **RAG estructurado**
sobre base de datos relacional (recuperación determinista por SQL, sin embeddings).

Seminario de Título — Ingeniería en Informática, PUCV.
Patricio Hernández Vergara · Vicente Cisternas León · Profesora guía: Sandra Cano Mazuera.

El plan de desarrollo completo está en [`docs/PLAN_DESARROLLO.md`](docs/PLAN_DESARROLLO.md).

---

## Requisitos

| Herramienta | Versión |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 16 |
| Git | cualquiera |

### Instalación en Windows

```powershell
winget install --id Python.Python.3.12 -e
winget install --id PostgreSQL.PostgreSQL.16 -e
```

Cerrar y reabrir la terminal después de instalar para que el PATH se actualice.

Alternativa a Postgres nativo: `docker compose up -d` levanta el mismo Postgres 16 con
idénticas credenciales usando el `docker-compose.yml` incluido. Requiere Docker Desktop.

### Crear el rol y la base

Con Postgres nativo recién instalado (superusuario `postgres`):

```powershell
$env:PGPASSWORD = 'postgres'
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost `
  -c "CREATE ROLE studify LOGIN PASSWORD 'studify'" `
  -c "CREATE DATABASE studify OWNER studify"
```

---

## Puesta en marcha

```powershell
# 1. Entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependencias (modo editable)
pip install -e ".[dev]"

# 3. Configuración
Copy-Item .env.example .env
#    → editar .env y completar LLM_API_KEY

# 4. Base de datos
docker compose up -d          # si eligieron Docker
#    si usan Postgres nativo: crear la BD y ajustar DATABASE_URL en .env

# 5. Migraciones (a partir de la Fase 1)
alembic upgrade head

# 6. Levantar la API
uvicorn studify.main:app --reload --app-dir src
```

Verificación: http://127.0.0.1:8000/health y http://127.0.0.1:8000/docs

```powershell
pytest        # los tests de /health corren sin necesidad de Postgres
ruff check .
```

---

## Arquitectura

Cuatro macro-fases (cap. 18 del informe):

1. **Caracterización** — cuestionario VARK de 16 ítems → vector porcentual `{p_V, p_A, p_R, p_K}`.
   El perfil se persiste como porcentajes, nunca como etiqueta ("visual", "kinestésico"), para
   no perder granularidad.
2. **Recuperación RAG** — consulta SQL determinista por `id_objetivo`, restringida a fragmentos
   con `estado_validacion = 'validado'`. Sin búsqueda vectorial: el contexto educativo exige
   control curricular y trazabilidad explícita.
3. **Generación adaptativa** — prompt maestro en tres bloques (contexto + perfil + formato)
   enviado a un LLM con API compatible con OpenAI.
4. **Validación estructural** — el JSON devuelto se valida con Pydantic; si falla, se reinyecta
   el error y se reintenta. Incluye verificación de que las fuentes citadas correspondan a
   fragmentos realmente inyectados (detección de citas alucinadas).

### Mapa del código

```
src/studify/
├─ config.py       Settings (.env)
├─ main.py         App FastAPI
├─ db/             Modelos y sesión (entidades del cap. 17)
├─ vark/           Scoring, ponderación C_*, reglas de decisión, jerarquía de canales
├─ knowledge/      Ingesta documental, etiquetado asistido, curación humana
├─ rag/            Retriever SQL determinista, plantillas de prompt, orquestador
├─ generation/     Contrato de la microcápsula, generador LLM, validador + reparación
├─ api/routers/    Endpoints REST
└─ web/            UI mínima (Jinja + HTMX)
```

### Nota sobre el modelo de concurrencia

Los endpoints se declaran con `def` (no `async def`) y la capa de datos usa SQLAlchemy
síncrono. FastAPI ejecuta estos handlers en su threadpool, lo que permite hacer I/O
bloqueante (base de datos y llamadas al LLM) sin bloquear el event loop, manteniendo el
código simple.

### Proveedor de LLM

Cualquier endpoint compatible con OpenAI. Se cambia de modelo editando `.env`, sin tocar
código. Candidatos evaluados en el bake-off de la Fase 3: DeepSeek, Qwen y GLM.
