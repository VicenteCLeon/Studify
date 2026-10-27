<div align="center">

# 📚 Studify

### Micro-aprendizaje adaptativo mediante IA generativa

Generación de contenido educativo personalizado según el perfil de aprendizaje **VARK**
del estudiante, sobre una arquitectura **RAG estructurado** sin embeddings: recuperación
determinista por SQL, trazable hasta el fragmento y la página fuente.

<img src="https://img.shields.io/badge/Arquitectura-RAG%20Estructurado-ff69b4?style=for-the-badge" alt="Arquitectura" />
<img src="https://img.shields.io/badge/Adaptación-Perfil%20VARK-478CBF?style=for-the-badge" alt="Adaptación" />
<img src="https://img.shields.io/badge/Tipo-Educativo-success?style=for-the-badge" alt="Tipo" />

<br/>

<img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
<img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
<img src="https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?style=for-the-badge" alt="SQLAlchemy" />
<img src="https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic" />
<img src="https://img.shields.io/badge/HTMX-1.9-3D72D7?style=for-the-badge&logo=htmx&logoColor=white" alt="HTMX" />
<img src="https://img.shields.io/badge/LLM-DeepSeek%20%2F%20Qwen%20%2F%20GLM-6C5CE7?style=for-the-badge" alt="LLM" />

</div>

<br/>

> **Proyecto de Título** — Ingeniería en Informática, Pontificia Universidad Católica de
> Valparaíso (PUCV).
> **Autores:** Patricio Hernández Vergara · Vicente Cisternas León
> **Profesora guía:** Sandra Cano Mazuera
>
> La UI se presenta al usuario final como **«RepasAi»**; `Studify` es el nombre del
> repositorio y del paquete Python.

---

## 🏗️ Arquitectura

El motor se organiza en cuatro macro-fases (cap. 18 del informe):

| # | Fase | Qué hace |
|---|---|---|
| 1 | **Caracterización** | Cuestionario VARK de 16 ítems → vector porcentual `{V, A, R, K}`. Se persiste como porcentajes, nunca como etiqueta ("visual", "kinestésico"), para no perder granularidad. |
| 2 | **Recuperación RAG** | Consulta SQL determinista por `id_objetivo`, restringida a fragmentos con `estado_validacion = 'validado'`. **Sin búsqueda vectorial**: el contexto educativo exige control curricular y trazabilidad explícita hasta la página fuente. |
| 3 | **Generación adaptativa** | Prompt maestro en tres bloques (contexto + perfil + formato) enviado a un LLM con API compatible con OpenAI. |
| 4 | **Validación estructural** | El JSON devuelto se valida con Pydantic; si falla, se reinyecta el error y se reintenta. Incluye verificación de que las fuentes citadas correspondan a fragmentos realmente inyectados (detección de citas alucinadas). |

## 🗂️ Mapa del código

```
src/studify/
├─ config.py       Settings (.env)
├─ main.py         App FastAPI
├─ db/             Modelos y sesión (entidades del cap. 17)
├─ vark/           Scoring, ponderación C_*, reglas de decisión, jerarquía de canales
├─ knowledge/      Ingesta documental, etiquetado asistido por LLM, curación humana
├─ rag/            Retriever SQL determinista, plantillas de prompt, orquestador
├─ generation/     Contrato de la microcápsula, generador LLM, validador + reparación
├─ media/          Narración del visor (Kokoro, Piper; XTTS como opción administrativa)
├─ api/routers/    Endpoints REST
└─ web/            UI de RepasAi (Jinja2 + HTMX): estudiante, panel del docente y páginas legales
```

---

## ⚙️ Requisitos

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

Cerrar y reabrir la terminal después de instalar para que el `PATH` se actualice.

> **Alternativa a Postgres nativo:** `docker compose up -d` levanta el mismo Postgres 16 con
> idénticas credenciales usando el `docker-compose.yml` incluido. Requiere Docker Desktop.

### Crear el rol y la base

Con Postgres nativo recién instalado (superusuario `postgres`):

```powershell
$env:PGPASSWORD = 'postgres'
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost `
  -c "CREATE ROLE studify LOGIN PASSWORD 'studify'" `
  -c "CREATE DATABASE studify OWNER studify"
```

---

## 🚀 Puesta en marcha

```powershell
# 1. Entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependencias (modo editable)
#    ingest: lectura de PDF y PPTX en el panel del docente
#    audio:  narración del visor (Kokoro y Piper)
pip install -e ".[dev,ingest,audio]"
python scripts/descargar_voces.py   # modelos de voz (~410 MB) a data/voces

# 3. Configuración
Copy-Item .env.example .env
#    → editar .env: LLM_API_KEY, SESSION_SECRET y la clave del docente
#      (TEACHER_PASSWORD; sin ella el panel queda cerrado). Fuera de
#      APP_ENV=dev la app no arranca sin un SESSION_SECRET de 32+ caracteres:
#      python -c "import secrets; print(secrets.token_urlsafe(48))"

# 4. Base de datos
docker compose up -d          # si eligieron Docker
#    si usan Postgres nativo: crear la BD y ajustar DATABASE_URL en .env

# 5. Migraciones
alembic upgrade head

# 6. Levantar la API
uvicorn studify.main:app --reload --app-dir src
```

La app se arranca desde la raíz del repositorio: el `.env` y las carpetas de `data/` se
buscan relativas al directorio de trabajo.

**Verificación:** [`http://127.0.0.1:8000/`](http://127.0.0.1:8000/) (portada) ·
[`/health`](http://127.0.0.1:8000/health) · [`/docs`](http://127.0.0.1:8000/docs)

---

## 🧪 Testing y calidad

```powershell
$env:LLM_API_KEY=""   # para no gastar en el proveedor
.\.venv\Scripts\python -m pytest -q --ignore=tests/test_visual.py --ignore=tests/test_voz.py
ruff check .
```

- Sin Postgres, los tests que necesitan la base se omiten (`@necesita_bd`). Para correrlos todos,
  la base de `DATABASE_URL` tiene que estar levantada.
- `test_visual.py` y `test_voz.py` se ignoran: cargan SDXL y XTTS al importarse.
- Los tests que usan la base escriben en la de desarrollo. Hay fallos conocidos que dependen de
  eso: 4 sin Postgres y 2 con él (`docs/PENDIENTES.md`, R10).

---

## 📝 Notas técnicas

<details>
<summary><strong>Modelo de concurrencia</strong></summary>
<br/>

Los endpoints se declaran con `def` (no `async def`) y la capa de datos usa SQLAlchemy
síncrono. FastAPI ejecuta estos handlers en su threadpool, lo que permite hacer I/O
bloqueante (base de datos y llamadas al LLM) sin bloquear el event loop, manteniendo el
código simple.

</details>

<details>
<summary><strong>Proveedor de LLM</strong></summary>
<br/>

Cualquier endpoint compatible con OpenAI. Se cambia de modelo editando `.env`, sin tocar
código. Candidatos evaluados en el bake-off de la Fase 3: **DeepSeek**, Qwen y GLM —
quedó seleccionado DeepSeek. El bake-off se corrió con `deepseek-chat`, un alias que el
proveedor anunció retirar; producción usa `deepseek-flash` con el razonamiento apagado
(`LLM_THINKING=disabled`).

</details>

---

## 📄 Documentación del proyecto

El índice completo, con qué es cada documento y cuándo leerlo, está en
[`docs/README.md`](docs/README.md). Los principales:

| Documento | Contenido |
|---|---|
| [`docs/AVANCE.md`](docs/AVANCE.md) | Estado actual del proyecto y bitácora: qué se hizo y cómo se verificó. |
| [`docs/PENDIENTES.md`](docs/PENDIENTES.md) | Todo lo que falta, empezando por lo que hay que cerrar antes del piloto. |
| [`docs/PLAN_DESARROLLO.md`](docs/PLAN_DESARROLLO.md) | Roadmap por fases, decisiones de stack, riesgos y contrato de la microcápsula. |
| [`docs/CORRECCIONES_INFORME.md`](docs/CORRECCIONES_INFORME.md) | Qué corregir o agregar en el informe final respecto del de avance. |

---

## ⚖️ Licencia

Copyright © 2026 Patricio Hernández Vergara y Vicente Cisternas León.

El código de RepasAi (Studify) es software libre: puedes usarlo, estudiarlo, modificarlo y
redistribuirlo bajo la **GNU Affero General Public License, versión 3 o posterior**
(`AGPL-3.0-or-later`). El texto completo está en [`LICENSE`](LICENSE). Si ofreces una versión
modificada como servicio en red, la AGPL te obliga a poner su código fuente a disposición de
sus usuarios; por eso la aplicación enlaza este repositorio desde el pie de cada página.

**Qué cubre la licencia y qué no:**

- **Cubre** el código de este repositorio.
- **No cubre:**
  - los **modelos de voz**, que se descargan aparte con `scripts/descargar_voces.py`.
    Kokoro-82M es Apache-2.0. La voz `es_ES-sharvard-medium` de Piper se entrenó con datos
    CC BY 3.0, que exigen atribución, y se ajustó desde una voz con datos de uso solo para
    investigación. XTTS-v2, opción administrativa, está bajo la CPML, solo para uso no
    comercial;
  - el **material de estudio** de los cursos ni las cápsulas generadas a partir de él, que
    pertenecen a sus titulares;
  - los **componentes de terceros**, cada uno con su propia licencia. Entre ellos hay varios
    GPL o AGPL: `phonemizer`, espeak-ng y `piper-tts` son GPL-3.0, `pymupdf` es AGPL-3.0 y
    `psycopg` es LGPL-3.0.

La lista de componentes con su licencia y los créditos de atribución están en los
[Términos y Condiciones](src/studify/web/templates/legal/terminos.html), sección 8 (en la
aplicación, `/terminos#componentes`). El detalle técnico de cada licencia, leído del metadato
de cada paquete, está en [`docs/PRUEBAS_VARK.md`](docs/PRUEBAS_VARK.md).

<div align="center">

<sub>Patricio Hernández Vergara · Vicente Cisternas León · Ingeniería en Informática · PUCV.</sub>

</div>
